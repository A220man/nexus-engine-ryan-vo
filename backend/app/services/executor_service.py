import subprocess
import time
import os
import signal
import threading
import uuid
from typing import Dict, Optional, Tuple
from app.core.config import settings
from app.models.schemas import ExecutionResponse
from app.services.sandbox_service import store_sandbox_payload

# Registry of active executions for abort signals
# Maps temp_id (proc_<pid>_<timestamp>) -> subprocess.Popen
ACTIVE_EXECUTIONS: Dict[str, subprocess.Popen] = {}
# Maps temp_id -> cancellation flag
CANCELLATION_FLAGS: Dict[str, bool] = {}
# Maps execution_id (exec_<uuid>) -> temp_id for abort lookup
EXECUTION_ID_MAP: Dict[str, str] = {}
EXECUTION_LOCK = threading.Lock()


class ExecutionTimeoutError(Exception):
    pass


class ExecutionAbortedError(Exception):
    pass


def run_bounded_command(
    command: str,
    timeout_seconds: Optional[int] = None,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    session_id: str = "default",
    platform: str = "generic",
    db_path: Optional[str] = None,
) -> ExecutionResponse:
    """
    Executes a shell command with a unified wall-clock budget bounding:
    1. Subprocess command execution
    2. Output capture and decoding
    3. Storage, bounded chunking, and preview indexing
    Addresses issues #947, #959, and #982.
    """
    effective_timeout = timeout_seconds or settings.MAX_EXECUTION_TIMEOUT_SECONDS
    start_time = time.time()
    deadline = start_time + effective_timeout

    # Generate execution_id upfront so clients can abort during execution
    execution_id = f"exec_{uuid.uuid4().hex[:12]}"

    proc_env = os.environ.copy()
    if env:
        proc_env.update(env)

    # Launch process in separate process group where available for clean teardown
    preexec = os.setsid if hasattr(os, "setsid") else None

    proc = subprocess.Popen(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=cwd,
        env=proc_env,
        preexec_fn=preexec,
    )

    temp_id = f"proc_{proc.pid}_{int(start_time)}"
    with EXECUTION_LOCK:
        ACTIVE_EXECUTIONS[temp_id] = proc
        CANCELLATION_FLAGS[temp_id] = False
        EXECUTION_ID_MAP[execution_id] = temp_id

    try:
        stdout_text = ""
        # Poll process until completion, timeout, or abort
        while True:
            # Check abort signal (#959)
            if CANCELLATION_FLAGS.get(temp_id, False):
                terminate_process_group(proc)
                raise ExecutionAbortedError("Execution was aborted by client signal.")

            # Check hard wall-clock deadline (#947)
            if time.time() > deadline:
                terminate_process_group(proc)
                raise ExecutionTimeoutError(
                    f"Execution exceeded hard wall-clock timeout of {effective_timeout}s across execution and indexing."
                )

            ret = proc.poll()
            if ret is not None:
                # Command finished; read remaining output
                remaining, _ = proc.communicate()
                stdout_text += (remaining or "")
                break

            time.sleep(0.05)

        exit_code = proc.returncode

    finally:
        with EXECUTION_LOCK:
            ACTIVE_EXECUTIONS.pop(temp_id, None)
            CANCELLATION_FLAGS.pop(temp_id, None)

    # Indexing/storage phase: also bounded by the same wall-clock deadline
    remaining_budget = deadline - time.time()
    if remaining_budget <= 0:
        raise ExecutionTimeoutError(
            f"Execution exceeded hard wall-clock timeout of {effective_timeout}s before indexing phase."
        )

    record = store_sandbox_payload(
        session_id=session_id,
        command=command,
        raw_text=stdout_text,
        exit_code=exit_code if exit_code is not None else 0,
        duration_ms=(time.time() - start_time) * 1000.0,
        platform=platform,
        db_path=db_path,
        execution_id=execution_id,
    )

    # Mapping already registered upfront; no need to re-register
    return record


def terminate_process_group(proc: subprocess.Popen) -> None:
    try:
        if hasattr(os, "killpg") and hasattr(os, "getpgid"):
            pgid = os.getpgid(proc.pid)
            os.killpg(pgid, signal.SIGTERM)
            time.sleep(0.1)
            if proc.poll() is None:
                os.killpg(pgid, signal.SIGKILL)
        else:
            proc.terminate()
            time.sleep(0.1)
            if proc.poll() is None:
                proc.kill()
    except (OSError, ProcessLookupError):
        pass


def abort_execution(execution_id: str) -> bool:
    """
    Aborts an active in-flight execution by its execution_id.

    Supports the sentinel values "any" and "*" to abort every currently
    in-flight execution at once. This is a watchdog escape hatch for callers
    that cannot correlate a specific server-generated execution id with an
    in-flight tool call — e.g. the Pi MCP bridge cancelling a hung ctx_execute
    on Esc/Ctrl+C (issue #959). Returns True if at least one in-flight
    execution was signalled.
    """
    with EXECUTION_LOCK:
        if execution_id in ("any", "*"):
            # Abort all live in-flight executions (source of truth: still running)
            targets = [
                temp_id for temp_id, proc in ACTIVE_EXECUTIONS.items()
                if proc is not None and proc.poll() is None
            ]
        else:
            temp_id = EXECUTION_ID_MAP.get(execution_id)
            if not temp_id:
                return False
            proc = ACTIVE_EXECUTIONS.get(temp_id)
            if not proc or proc.poll() is not None:
                EXECUTION_ID_MAP.pop(execution_id, None)
                return False
            targets = [temp_id]

    # Teardown outside the lock so the execution loop's finally cleanup is never
    # blocked; the cancellation flag (set before terminate) is authoritative for
    # the loop, and terminate is idempotent against already-exited processes.
    aborted = False
    for temp_id in targets:
        CANCELLATION_FLAGS[temp_id] = True
        proc = ACTIVE_EXECUTIONS.get(temp_id)
        if proc is not None:
            terminate_process_group(proc)
            aborted = True
    return aborted


def cleanup_execution_mapping(execution_id: str) -> None:
    """Removes execution_id mapping after completion (success, timeout, or abort)."""
    with EXECUTION_LOCK:
        EXECUTION_ID_MAP.pop(execution_id, None)
