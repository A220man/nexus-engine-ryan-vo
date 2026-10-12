import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { ExecutionRecord, ChunkRecord, SandboxSearchResponse, AdvisoryResponse } from '../types/api';
import { useAuth } from '../context/AuthContext';

interface SandboxConsoleProps {
  initialSessionId?: string;
}

export const SandboxConsole: React.FC<SandboxConsoleProps> = ({ initialSessionId }) => {
  const { role } = useAuth();
  const [sessionId, setSessionId] = useState<string>(initialSessionId || 'default-session');
  const [command, setCommand] = useState<string>('python3 -c "for i in range(40): print(f\'compilation artifact chunk {i}: exit condition normal\')"');
  const [platform, setPlatform] = useState<string>('claude-code');
  const [timeoutSec, setTimeoutSec] = useState<number>(30);

  const [executions, setExecutions] = useState<ExecutionRecord[]>([]);
  const [selectedExec, setSelectedExec] = useState<ExecutionRecord | null>(null);
  const [chunks, setChunks] = useState<ChunkRecord[]>([]);

  const [searchQuery, setSearchQuery] = useState<string>('');
  const [isRegex, setIsRegex] = useState<boolean>(false);
  const [searchResults, setSearchResults] = useState<SandboxSearchResponse | null>(null);

  const [advisory, setAdvisory] = useState<AdvisoryResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const canExecute = role === 'operator' || role === 'admin';

  const loadExecutions = async () => {
    try {
      const list = await api.listExecutions(sessionId);
      setExecutions(list);
      if (list.length > 0 && !selectedExec) {
        selectExecution(list[0]);
      }
    } catch (err: any) {
      console.warn('Could not load executions:', err.message);
    }
  };

  useEffect(() => {
    loadExecutions();
  }, [sessionId]);

  const selectExecution = async (exec: ExecutionRecord) => {
    setSelectedExec(exec);
    setSearchResults(null);
    setAdvisory(null);
    try {
      const c = await api.getExecutionChunks(exec.id);
      setChunks(c);
    } catch (err) {
      console.warn('Error loading chunks:', err);
    }
  };

  const handleRunCommand = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!command.trim()) return;
    setLoading(true);
    setActionError(null);
    try {
      const record = await api.executeCommand(sessionId, command, platform, timeoutSec);
      setExecutions([record, ...executions]);
      await selectExecution(record);
    } catch (err: any) {
      setActionError(err.message || 'Execution failed');
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedExec || !searchQuery.trim()) return;
    try {
      const res = await api.searchSandbox(selectedExec.id, searchQuery, isRegex);
      setSearchResults(res);
    } catch (err: any) {
      setActionError(err.message || 'Search failed');
    }
  };

  const handleRequestAdvisory = async () => {
    if (!selectedExec) return;
    setLoading(true);
    setActionError(null);
    try {
      const res = await api.requestAdvisory(selectedExec.id, 'Identify key error line');
      setAdvisory(res);
    } catch (err: any) {
      setActionError(err.message || 'Advisory request failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="sandbox-container">
      <div className="console-split">
        {/* Left Column: Command Runner and Execution History */}
        <div className="console-left">
          <div className="card">
            <h3>Execute Sandboxed Tool</h3>
            <p className="subtitle">Runs commands through a bounded watchdog and intercepts oversized output.</p>

            <form onSubmit={handleRunCommand} className="command-form">
              <div className="form-row">
                <div className="form-group flex-1">
                  <label>Session ID:</label>
                  <input
                    type="text"
                    value={sessionId}
                    onChange={(e) => setSessionId(e.target.value)}
                    required
                  />
                </div>
                <div className="form-group">
                  <label>Platform:</label>
                  <select value={platform} onChange={(e) => setPlatform(e.target.value)}>
                    <option value="claude-code">Claude Code</option>
                    <option value="opencode-v2">OpenCode v2</option>
                    <option value="pi">Pi Agent</option>
                    <option value="vscode-copilot">VS Code Copilot</option>
                    <option value="generic">Generic Stdio</option>
                  </select>
                </div>
                <div className="form-group w-80">
                  <label>Timeout (s):</label>
                  <input
                    type="number"
                    min="1"
                    max="300"
                    value={timeoutSec}
                    onChange={(e) => setTimeoutSec(Number(e.target.value))}
                  />
                </div>
              </div>

              <div className="form-group">
                <label>Command to execute:</label>
                <textarea
                  rows={3}
                  value={command}
                  onChange={(e) => setCommand(e.target.value)}
                  placeholder="e.g. pytest tests/ -v or git diff"
                  required
                />
              </div>

              {actionError && <div className="error-banner">{actionError}</div>}

              <button
                type="submit"
                className="primary-btn w-full"
                disabled={loading || !canExecute}
                title={canExecute ? 'Execute' : 'Requires operator or admin role'}
              >
                {loading ? '⏳ Executing with Watchdog...' : '▶ Run Command'}
              </button>
            </form>
          </div>

          <div className="card mt-4">
            <div className="flex-between">
              <h3>Session Executions</h3>
              <button className="small-btn" onClick={loadExecutions}>
                Refresh
              </button>
            </div>
            {executions.length === 0 ? (
              <div className="empty-state">No executions yet for session "{sessionId}".</div>
            ) : (
              <div className="exec-list">
                {executions.map((item) => (
                  <div
                    key={item.id}
                    className={`exec-item ${selectedExec?.id === item.id ? 'selected' : ''}`}
                    onClick={() => selectExecution(item)}
                  >
                    <div className="exec-item-header">
                      <span className={`status-tag ${item.exit_code === 0 ? 'tag-success' : 'tag-fail'}`}>
                        Exit {item.exit_code ?? 'None'}
                      </span>
                      <span className="mono text-muted">{item.id}</span>
                    </div>
                    <div className="exec-cmd mono">{item.command}</div>
                    <div className="exec-stats">
                      <span>{(item.raw_bytes / 1024).toFixed(1)} KB raw</span>
                      <span>{(item.duration_ms).toFixed(0)} ms</span>
                      {item.is_sandboxed && <span className="sandboxed-tag">Sandboxed</span>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Preview, Chunks, and Search */}
        <div className="console-right">
          {selectedExec ? (
            <div className="card">
              <div className="exec-detail-header">
                <div>
                  <h3>Execution Detail: {selectedExec.id}</h3>
                  <span className="text-muted">
                    {selectedExec.created_at} · Status: {selectedExec.status}
                  </span>
                </div>
                <div className="header-actions">
                  <button
                    className="secondary-btn"
                    onClick={handleRequestAdvisory}
                    disabled={loading || !canExecute}
                  >
                    🧠 Advisory Explain
                  </button>
                </div>
              </div>

              {advisory && (
                <div className="advisory-box">
                  <h4>Advisory Analysis ({advisory.provider})</h4>
                  <p>{advisory.explanation}</p>
                  <span className="advisory-disclaimer">{advisory.advisory_notice}</span>
                </div>
              )}

              <div className="detail-metrics">
                <div>
                  <strong>Raw Size:</strong> {selectedExec.raw_bytes} bytes
                </div>
                <div>
                  <strong>Preview Size:</strong> {selectedExec.sandboxed_bytes} bytes
                </div>
                <div>
                  <strong>Reduction:</strong>{' '}
                  {selectedExec.raw_bytes > 0
                    ? `${(((selectedExec.raw_bytes - selectedExec.sandboxed_bytes) / selectedExec.raw_bytes) * 100).toFixed(1)}%`
                    : '0%'}
                </div>
                <div>
                  <strong>Indexed Chunks:</strong> {chunks.length}
                </div>
              </div>

              <div className="preview-section mt-4">
                <h4>Context-Optimized Preview Returned to Agent:</h4>
                <pre className="code-block">{selectedExec.preview_summary}</pre>
              </div>

              {/* Sub-search section */}
              <div className="search-section mt-4">
                <h4>Targeted Search within Sandboxed Chunks (`ctx_search`):</h4>
                <form onSubmit={handleSearch} className="search-form">
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search query or keyword (e.g. error, test failure, token)..."
                    required
                  />
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={isRegex}
                      onChange={(e) => setIsRegex(e.target.checked)}
                    />
                    Regex
                  </label>
                  <button type="submit" className="primary-btn">
                    🔍 Search
                  </button>
                </form>

                {searchResults && (
                  <div className="search-results mt-2">
                    <div className="results-header">
                      Found {searchResults.total_matches} match(es) in artifact {searchResults.execution_id}:
                    </div>
                    {searchResults.results.length === 0 ? (
                      <div className="empty-state">No matching lines found.</div>
                    ) : (
                      <div className="results-list">
                        {searchResults.results.map((res, i) => (
                          <div key={i} className="result-item">
                            <span className="result-loc">
                              Chunk {res.chunk_index} : Line {res.line_number}
                            </span>
                            <pre className="result-snippet">{res.snippet}</pre>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="card empty-state">
              <h3>No Execution Selected</h3>
              <p>Select an execution from the left list or run a new command to inspect sandboxed chunks.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
