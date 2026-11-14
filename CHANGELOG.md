# Changelog

## 1.7.0 — work-in-progress checkpoint

Partial code published for continued development. Known issues: STATUS.md.

## 1.6.0 — work-in-progress checkpoint

Partial code published for continued development. Known issues: STATUS.md.

## 1.5.0 — work-in-progress checkpoint

### Changes in this round
- Added `/api/executions/abort-all` endpoint to abort all in-flight executions (watchdog escape hatch for callers that cannot correlate a specific execution ID)
- Added tests for the new endpoint: idle abort returns false, viewer role denied
- Updated API endpoint reference in README
- Verified all 38 backend tests pass and 4 frontend tests pass


## 1.4.0 — work-in-progress checkpoint

### Changes in this round
- Marked metrics-accounting and safe-platform-routing as completed in feature-plan.json and PLAN.md
- Verified all 36 backend tests pass and 4 frontend tests pass
- Updated feature status tracking to reflect actual implementation state
- Confirmed metrics invariants enforcement, zero-diverted zero-savings, 17-platform routing with OpenCode v2 and Pi abortable configs


## 1.3.0 — work-in-progress checkpoint

Partial code published for continued development. Known issues: STATUS.md.


## 1.3.0 — work-in-progress checkpoint

### Changes in this round
- Fixed EXECUTION_ID_MAP memory leak in bounded-executor: `cleanup_execution_mapping` now called in `finally` block of `run_bounded_command` to ensure execution_id mappings are cleaned up after success, timeout, or abort
- Added tests verifying cleanup in all three scenarios (success, timeout, abort)
- Verified all 36 backend tests pass: executor (7), sandbox (6), metrics (5), routing (5), auth (6), API workflows (5), LLM (2)
- Confirmed bounded-executor watchdog enforcement: hard wall-clock timeout, abort signals, orphan reaping guard
- Confirmed context-sandboxing-engine: chunked storage, preview summary, substring/regex search
## 1.2.0 — work-in-progress checkpoint
