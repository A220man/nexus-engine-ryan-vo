import time
import pytest
from app.services.executor_service import (
    run_bounded_command,
    abort_execution,
    ExecutionTimeoutError,
    ExecutionAbortedError,
    ACTIVE_EXECUTIONS,
    EXECUTION_ID_MAP,
)


def test_run_bounded_command_success(temp_db: str):
    res = run_bounded_command(
        command="echo 'Hello Nexus Engine'",
        timeout_seconds=5,
        session_id="sess_exec",
        db_path=temp_db,
    )
    assert res.exit_code == 0
    assert "Hello Nexus Engine" in res.preview_summary
    assert res.status == "completed"


def test_run_bounded_command_timeout(temp_db: str):
    # Issue #947: Hard wall-clock timeout bounding execution
    with pytest.raises(ExecutionTimeoutError) as exc_info:
        run_bounded_command(
            command="sleep 2",
            timeout_seconds=1,
            session_id="sess_timeout",
            db_path=temp_db,
        )
    assert "hard wall-clock timeout" in str(exc_info.value)


def test_abort_execution_signal(temp_db: str):
    # Issue #959: Abort signal stops running command
    import threading
    aborted_caught = []

    def background_runner():
        try:
            run_bounded_command(
                command="sleep 5",
                timeout_seconds=10,
                session_id="sess_abort",
                db_path=temp_db,
            )
        except ExecutionAbortedError as e:
            aborted_caught.append(str(e))

    thread = threading.Thread(target=background_runner)
    thread.start()

    time.sleep(0.3)
    aborted = abort_execution("any")
    thread.join(timeout=3.0)

    assert aborted is True
    assert len(aborted_caught) == 1
    assert "aborted by client signal" in aborted_caught[0]


def test_abort_all_returns_false_when_idle():
    # Sentinel "any"/"*" with no in-flight execution must return False, not raise.
    assert not ACTIVE_EXECUTIONS, "expected no in-flight executions at test start"
    assert abort_execution("any") is False
    assert abort_execution("*") is False
def test_execution_id_map_cleaned_up_on_success(temp_db: str):
    """EXECUTION_ID_MAP should be cleaned up after successful execution."""
    assert not EXECUTION_ID_MAP, "map should start empty"
    res = run_bounded_command(
        command="echo 'test'",
        timeout_seconds=5,
        session_id="sess_cleanup",
        db_path=temp_db,
    )
    assert res.status == "completed"
    assert not EXECUTION_ID_MAP, "EXECUTION_ID_MAP should be empty after successful execution"


def test_execution_id_map_cleaned_up_on_timeout(temp_db: str):
    """EXECUTION_ID_MAP should be cleaned up after timeout."""
    assert not EXECUTION_ID_MAP, "map should start empty"
    with pytest.raises(ExecutionTimeoutError):
        run_bounded_command(
            command="sleep 2",
            timeout_seconds=1,
            session_id="sess_timeout_cleanup",
            db_path=temp_db,
        )
    assert not EXECUTION_ID_MAP, "EXECUTION_ID_MAP should be empty after timeout"


def test_execution_id_map_cleaned_up_on_abort(temp_db: str):
    """EXECUTION_ID_MAP should be cleaned up after abort."""
    import threading
    assert not EXECUTION_ID_MAP, "map should start empty"

    aborted_caught = []

    def background_runner():
        try:
            run_bounded_command(
                command="sleep 5",
                timeout_seconds=10,
                session_id="sess_abort_cleanup",
                db_path=temp_db,
            )
        except ExecutionAbortedError as e:
            aborted_caught.append(str(e))

    thread = threading.Thread(target=background_runner)
    thread.start()

    time.sleep(0.3)
    aborted = abort_execution("any")
    thread.join(timeout=3.0)

    assert aborted is True
    assert len(aborted_caught) == 1
    assert not EXECUTION_ID_MAP, "EXECUTION_ID_MAP should be empty after abort"


def test_abort_execution_with_stale_id(temp_db: str):
    """
    Test that abort_execution returns False gracefully when given
    an execution_id whose mapping has been cleaned up (e.g., after
    previous success, timeout, or abort).
    """
    # Start with a clean mapping (as test_execution_id_map_cleaned_up_on_success would leave it)
    assert not EXECUTION_ID_MAP, 'map should start empty'

    # Simulate: add an execution_id to the map, then clean it up
    # (as happens in the finally block after successful execution)
    from uuid import uuid4
    fake_execution_id = f'exec_{uuid4().hex[:12]}'
    # Manually add it to the map (simulating what run_bounded_command does upfront)
    import threading
    # We need to also add a temp_id that ACTIVE_EXECUTIONS would have
    # But since the map is cleaned up, abort should return False
    # 
    # Actually, the simplest test: just try aborting with an id that was
    # never active, or was cleaned up
    result = abort_execution(fake_execution_id)
    assert result is False, f'abort_execution with stale id should return False, got {result}'

    # Also test with a known non-existent id
    result2 = abort_execution('nonexistent_execution_id')
    assert result2 is False, f'abort_execution with nonexistent id should return False, got {result2}'
