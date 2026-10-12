# Product development plan

Each round completes one feature or repair. Future items are planned, not implemented claims.

## Current round

context-sandboxing-engine

## Roadmap

### context-sandboxing-engine — Context Sandboxing and Chunked Retrieval Engine

Status: done

Acceptance:
- Captures and sandboxes tool output exceeding size threshold into SQLite storage
- Generates deterministic structural summary preview with line and byte counts
- Indexes chunks with hard chunk-size limits to prevent database bloat
- Provides targeted search and retrieval within sandboxed outputs without polluting active model context

Implementation: `backend/app/services/sandbox_service.py`, `backend/app/api/endpoints.py`, `backend/app/core/database.py`

Tests: `backend/tests/test_sandbox.py`

### metrics-accounting — Anti-Contradiction Context Savings Accounting

Status: planned

Acceptance:
- Enforces mathematical invariants so session savings never exceed global totals
- Calculates true savings percentage strictly from diverted output
- Reports zero savings when no tool execution was diverted

### safe-platform-routing — Safe Cross-Platform MCP Routing and Framing

Status: planned

Acceptance:
- Provides benign tool guidance framing across 17 IDE platforms
- Eliminates prompt-injection false positives in auto-mode classifiers
- Supports OpenCode v2 configuration and platform-specific exports

### bounded-executor — Watchdog-Enforced Bounded Execution Runner

Status: planned

Acceptance:
- Enforces wall-clock timeout bounding across command execution, indexing, and search
- Supports abort signals to interrupt in-flight execution on user request
- Reaps orphan child processes on parent termination

