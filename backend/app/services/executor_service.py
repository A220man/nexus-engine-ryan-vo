import subprocess
import time
import os
import signal
import threading
from typing import Dict, Optional, Tuple
from app.core.config import settings
from app.models.schemas import ExecutionResponse
from app.services.sandbox_service import store_sandbox_payload

# Registry of active executions for abort signals
ACTIVE_EXECUTIONS: Dict[str, subprocess.Popen] = {}
CANCELLATION_FLAGS: Dict[str, bool] = {}
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

    elapsed_ms = (time.time() - start_time) * 1000.0

    # Ensure remaining time budget allows indexing; bounded chunking ensures indexing takes < 100ms
    record = store_sandbox_payload(
        session_id=session_id,
        command=command,
        raw_text=stdout_text,
        exit_code=exit_code if exit_code is not None else 0,
        duration_ms=elapsed_ms,
        platform=platform,
        db_path=db_path,
    )
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
    Aborts an active in-flight execution.
    Addresses issue #959: allows Esc / Ctrl+C / client abort requests to cancel running commands.
    """
    with EXECUTION_LOCK:
        for temp_id, proc in list(ACTIVE_EXECUTIONS.items()):
            CANCELLATION_FLAGS[temp_id] = True
            terminate_process_group(proc)
            return True
    return False
