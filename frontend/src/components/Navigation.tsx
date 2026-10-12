import React from 'react';
import { useAuth } from '../context/AuthContext';

interface NavigationProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  systemHealth: string;
}

export const Navigation: React.FC<NavigationProps> = ({
  activeTab,
  setActiveTab,
  systemHealth,
}) => {
  const { role, setRole, isAuthenticated, logout, loginDemo } = useAuth();

  return (
    <header className="navbar">
      <div className="nav-brand">
        <span className="brand-icon">⚡</span>
        <div>
          <h1 className="brand-title">Nexus Engine</h1>
          <span className="brand-subtitle">Context Window Optimizer · Ryan Vo</span>
        </div>
      </div>

      <nav className="nav-links">
        <button
          className={`nav-btn ${activeTab === 'dashboard' ? 'active' : ''}`}
          onClick={() => setActiveTab('dashboard')}
        >
          📊 Dashboard
        </button>
        <button
          className={`nav-btn ${activeTab === 'sandbox' ? 'active' : ''}`}
          onClick={() => setActiveTab('sandbox')}
        >
          🗜️ Sandbox Console
        </button>
        <button
          className={`nav-btn ${activeTab === 'platforms' ? 'active' : ''}`}
          onClick={() => setActiveTab('platforms')}
        >
          🧭 17 IDE Platforms
        </button>
        <button
          className={`nav-btn ${activeTab === 'evaluation' ? 'active' : ''}`}
          onClick={() => setActiveTab('evaluation')}
        >
          🔬 AI/ML Benchmark
        </button>
      </nav>

      <div className="nav-user">
        <span className={`health-pill ${systemHealth === 'healthy' ? 'online' : 'offline'}`}>
          {systemHealth === 'healthy' ? '● Online' : '○ Degraded'}
        </span>

        {isAuthenticated ? (
          <div className="auth-controls">
            <label className="role-label">Role:</label>
            <select
              className="role-select"
              value={role}
              onChange={(e) => setRole(e.target.value)}
            >
              <option value="viewer">Viewer (Read-only)</option>
              <option value="operator">Operator (Execute)</option>
              <option value="admin">Admin (Full)</option>
            </select>
            <button className="logout-btn" onClick={logout} title="Log out">
              Exit
            </button>
          </div>
        ) : (
          <button className="login-btn" onClick={() => loginDemo('operator')}>
            Demo Login
          </button>
        )}
      </div>
    </header>
  );
};
