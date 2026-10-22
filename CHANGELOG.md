# Changelog

## 1.2.0 — work-in-progress checkpoint

Partial code published for continued development. Known issues: STATUS.md.

## 1.1.0 — work-in-progress checkpoint

Partial code published for continued development. Known issues: STATUS.md.

## 1.0.0 — work-in-progress checkpoint

Partial code published for continued development. Known issues: STATUS.md.

All notable changes to this project will be documented in this file.

## [1.0.0] - 2026-10-12

### Added
- Context sandboxing and output compression engine for AI coding agent tool results.
- Bounded wall-clock execution runner with cancellation watchdog across command, indexing, and search phases.
- Anti-contradiction context savings accounting guaranteeing mathematical consistency across sessions.
- Multi-platform routing engine with benign tool guidance framing across 17 IDE environments.
- Chunked SQLite content store with hard chunk size bounds preventing database and WAL bloat.
- Opt-in advisory LLM integration supporting OpenAI, Anthropic, Gemini, and Ollama.
- Keycloak OIDC authentication integration with SAML identity provider broker documentation.
- React + TypeScript web console dashboard for real-time sandbox inspection and savings audit.
- Reproducible AI/ML evaluation suite evaluating context reduction ratio, search recall, and classifier safety.

### Fixed
- Restored abort watchdog semantics: `abort_execution` now honours an "any"/"*" sentinel that cancels in-flight executions even when the caller cannot correlate the server-generated execution id (issue #959). Previously a running command could not be aborted; `test_abort_execution_signal` now passes.
- Corrected documentation honesty: parent-process-death orphan reaping (#982) is recorded as a tracked follow-up rather than implemented, and the evaluation table reports measured values from the bundled 5-sample dataset instead of unmeasured headliner figures.
