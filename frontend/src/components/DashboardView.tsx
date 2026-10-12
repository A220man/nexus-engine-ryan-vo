import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { MetricsSummary, SessionMetrics } from '../types/api';

interface DashboardViewProps {
  onSelectSession: (sessionId: string) => void;
}

export const DashboardView: React.FC<DashboardViewProps> = ({ onSelectSession }) => {
  const [summary, setSummary] = useState<MetricsSummary | null>(null);
  const [sessions, setSessions] = useState<SessionMetrics[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchMetrics = async () => {
    setLoading(true);
    setError(null);
    try {
      const [sumData, sessData] = await Promise.all([
        api.getMetricsSummary(),
        api.getSessionMetrics(50),
      ]);
      setSummary(sumData);
      setSessions(sessData);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch metrics');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMetrics();
  }, []);

  const exportMetricsJson = () => {
    const data = {
      summary,
      sessions,
      exported_at: new Date().toISOString(),
    };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `nexus-metrics-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (loading && !summary) {
    return <div className="card loading-state">⏳ Loading verified context metrics...</div>;
  }

  if (error && !summary) {
    return (
      <div className="card error-state">
        <h3>Error Loading Dashboard</h3>
        <p>{error}</p>
        <button className="primary-btn" onClick={fetchMetrics}>
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="dashboard-container">
      <div className="dashboard-header">
        <div>
          <h2>Context Optimization Dashboard</h2>
          <p className="subtitle">
            Real-time verified token reduction and anti-contradiction metrics across all active coding agent sessions.
          </p>
        </div>
        <div className="header-actions">
          <button className="secondary-btn" onClick={exportMetricsJson} title="Export verified metrics">
            📥 Export Report
          </button>
          <button className="primary-btn" onClick={fetchMetrics} title="Refresh metrics">
            🔄 Refresh
          </button>
        </div>
      </div>

      {summary && (
        <div className="metrics-grid">
          <div className="metric-card">
            <span className="metric-label">Context Reduction Ratio</span>
            <span className="metric-value highlight">
              {(summary.overall_savings_ratio * 100).toFixed(1)}%
            </span>
            <span className="metric-meta">Output kept out of context window</span>
          </div>

          <div className="metric-card">
            <span className="metric-label">Estimated Tokens Saved</span>
            <span className="metric-value">
              {summary.estimated_tokens_saved.toLocaleString()}
            </span>
            <span className="metric-meta">~4 chars/token heuristic</span>
          </div>

          <div className="metric-card">
            <span className="metric-label">Cost Saved (USD)</span>
            <span className="metric-value">
              ${summary.estimated_cost_saved_usd.toFixed(4)}
            </span>
            <span className="metric-meta">Claude 3.5 / Opus pricing baseline</span>
          </div>

          <div className="metric-card">
            <span className="metric-label">Total Diverted Bytes</span>
            <span className="metric-value">
              {(summary.total_diverted_bytes / 1024).toFixed(1)} KB
            </span>
            <span className="metric-meta">
              of {(summary.total_raw_bytes / 1024).toFixed(1)} KB raw tool outputs
            </span>
          </div>

          <div className="metric-card">
            <span className="metric-label">Active Sessions</span>
            <span className="metric-value">{summary.total_sessions}</span>
            <span className="metric-meta">{summary.total_tool_calls} total executions</span>
          </div>

          <div className="metric-card">
            <span className="metric-label">Metric Invariants Audit</span>
            <span className={`metric-badge ${summary.verified_invariants_pass ? 'badge-ok' : 'badge-err'}`}>
              {summary.verified_invariants_pass ? '✓ Verified (Part ≤ Whole)' : '⚠ Discrepancy Found'}
            </span>
            <span className="metric-meta">Addresses #950 anti-contradiction rule</span>
          </div>
        </div>
      )}

      <div className="card sessions-table-card">
        <h3>Session Breakdown</h3>
        {sessions.length === 0 ? (
          <div className="empty-state">
            <p>No active sessions recorded yet. Run a command in the Sandbox Console to start optimizing context.</p>
          </div>
        ) : (
          <div className="table-responsive">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Session ID</th>
                  <th>Platform</th>
                  <th>Tool Calls</th>
                  <th>Raw Output</th>
                  <th>Diverted Output</th>
                  <th>Savings</th>
                  <th>Tokens Saved</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((sess) => (
                  <tr key={sess.session_id}>
                    <td className="mono">{sess.session_id}</td>
                    <td>
                      <span className="platform-tag">{sess.platform}</span>
                    </td>
                    <td>{sess.tool_calls_count}</td>
                    <td>{(sess.raw_bytes / 1024).toFixed(1)} KB</td>
                    <td>{(sess.diverted_bytes / 1024).toFixed(1)} KB</td>
                    <td>
                      <span className="savings-pill">
                        {(sess.savings_ratio * 100).toFixed(1)}%
                      </span>
                    </td>
                    <td>{sess.tokens_saved.toLocaleString()}</td>
                    <td>
                      <button
                        className="small-btn"
                        onClick={() => onSelectSession(sess.session_id)}
                      >
                        Inspect
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
