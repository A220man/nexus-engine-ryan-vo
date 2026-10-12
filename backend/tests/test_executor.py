import time
import pytest
from app.services.executor_service import (
    run_bounded_command,
    abort_execution,
    ExecutionTimeoutError,
    ExecutionAbortedError,
    ACTIVE_EXECUTIONS,
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
