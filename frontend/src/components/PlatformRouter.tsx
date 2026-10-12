import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { PlatformConfig } from '../types/api';

export const PlatformRouter: React.FC = () => {
  const [platforms, setPlatforms] = useState<PlatformConfig[]>([]);
  const [selectedPlatform, setSelectedPlatform] = useState<PlatformConfig | null>(null);
  const [quietMode, setQuietMode] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(true);
  const [copied, setCopied] = useState<boolean>(false);

  const fetchPlatforms = async () => {
    setLoading(true);
    try {
      const list = await api.listPlatforms();
      setPlatforms(list);
      if (list.length > 0) {
        setSelectedPlatform(list[0]);
      }
    } catch (err) {
      console.warn('Failed to fetch platform list:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPlatforms();
  }, []);

  const handleSelectPlatform = async (p: PlatformConfig) => {
    try {
      const cfg = await api.getPlatformConfig(p.platform_id, quietMode);
      setSelectedPlatform(cfg);
    } catch {
      setSelectedPlatform(p);
    }
  };

  const handleToggleQuietMode = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.checked;
    setQuietMode(val);
    if (selectedPlatform) {
      try {
        const cfg = await api.getPlatformConfig(selectedPlatform.platform_id, val);
        setSelectedPlatform(cfg);
      } catch (err) {
        console.warn('Error toggling quiet mode:', err);
      }
    }
  };

  const copyConfig = () => {
    if (selectedPlatform) {
      navigator.clipboard.writeText(selectedPlatform.config_snippet);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  if (loading && platforms.length === 0) {
    return <div className="card loading-state">⏳ Loading platform catalog...</div>;
  }

  return (
    <div className="platform-container">
      <div className="dashboard-header">
        <div>
          <h2>Multi-Platform MCP Routing (17 Environments)</h2>
          <p className="subtitle">
            Safe tool guidance framing without triggering automated permission classifier denials.
          </p>
        </div>
      </div>

      <div className="platform-split">
        {/* Platform List */}
        <div className="platform-grid">
          {platforms.map((p) => (
            <div
              key={p.platform_id}
              className={`platform-card ${selectedPlatform?.platform_id === p.platform_id ? 'selected' : ''}`}
              onClick={() => handleSelectPlatform(p)}
            >
              <div className="platform-card-header">
                <strong>{p.name}</strong>
                <span className="badge-category">{p.category}</span>
              </div>
              <div className="platform-meta">
                <span>Hook: {p.hook_mode}</span>
                <span>Version: {p.version_supported}</span>
              </div>
            </div>
          ))}
        </div>

        {/* Selected Platform Detail */}
        {selectedPlatform && (
          <div className="platform-detail card">
            <div className="flex-between">
              <div>
                <h3>{selectedPlatform.name} Integration</h3>
                <span className="text-muted">ID: {selectedPlatform.platform_id} · Mode: {selectedPlatform.hook_mode}</span>
              </div>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={quietMode}
                  onChange={handleToggleQuietMode}
                />
                Quiet Mode (Opt-out guidance)
              </label>
            </div>

            <div className="config-box mt-4">
              <div className="flex-between">
                <h4>MCP Configuration Manifest</h4>
                <button className="small-btn" onClick={copyConfig}>
                  {copied ? '✓ Copied!' : '📋 Copy JSON'}
                </button>
              </div>
              <pre className="code-block">{selectedPlatform.config_snippet}</pre>
            </div>

            <div className="guidance-box mt-4">
              <h4>Safe Hook Prompt Guidance (Addresses Issues #911 & #967)</h4>
              <p className="text-muted">
                Legacy framing using &lt;priority_instructions&gt; or "disregard prior directives" trips Claude Code's
                Auto-Mode Bypass permission classifier. Nexus Engine uses transparent, non-adversarial tool guidance:
              </p>
              {selectedPlatform.tool_guidance_block ? (
                <pre className="code-block guidance-preview">
                  {selectedPlatform.tool_guidance_block}
                </pre>
              ) : (
                <div className="empty-state">Quiet mode enabled: No prompt block injected into agent context.</div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
