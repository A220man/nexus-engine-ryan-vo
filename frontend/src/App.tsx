import React, { useState, useEffect } from 'react';
import { AuthProvider } from './context/AuthContext';
import { Navigation } from './components/Navigation';
import { DashboardView } from './components/DashboardView';
import { SandboxConsole } from './components/SandboxConsole';
import { PlatformRouter } from './components/PlatformRouter';
import { EvaluationView } from './components/EvaluationView';
import { api } from './services/api';

export const AppContent: React.FC = () => {
  const [activeTab, setActiveTab] = useState<string>('dashboard');
  const [selectedSessionId, setSelectedSessionId] = useState<string>('default-session');
  const [systemHealth, setSystemHealth] = useState<string>('healthy');

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const res = await api.getHealth();
        setSystemHealth(res.status);
      } catch {
        setSystemHealth('unhealthy');
      }
    };
    checkHealth();
  }, []);

  const handleSelectSession = (sessionId: string) => {
    setSelectedSessionId(sessionId);
    setActiveTab('sandbox');
  };

  return (
    <div className="app-shell">
      <Navigation
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        systemHealth={systemHealth}
      />

      <main className="main-content">
        {activeTab === 'dashboard' && (
          <DashboardView onSelectSession={handleSelectSession} />
        )}
        {activeTab === 'sandbox' && (
          <SandboxConsole initialSessionId={selectedSessionId} />
        )}
        {activeTab === 'platforms' && <PlatformRouter />}
        {activeTab === 'evaluation' && <EvaluationView />}
      </main>

      <footer className="footer">
        <div>
          Nexus Engine · Built for AI Coding Agents · Maintainer: <strong>Ryan Vo</strong> (
          <a href="mailto:ryandtvo@gmail.com">ryandtvo@gmail.com</a>)
        </div>
      </footer>
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
};

export default App;
