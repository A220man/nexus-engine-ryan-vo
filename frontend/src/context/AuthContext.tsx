import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { api } from '../services/api';
import { AuthConfig } from '../types/api';

interface AuthContextType {
  token: string | null;
  role: string;
  email: string;
  isAuthenticated: boolean;
  authConfig: AuthConfig | null;
  loginDemo: (role?: string) => Promise<void>;
  logout: () => void;
  setRole: (role: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  // Store access token in memory only; never persist to localStorage
  const [token, setTokenState] = useState<string | null>(null);
  const [role, setRoleState] = useState<string>('operator');
  const [email, setEmailState] = useState<string>('operator@example.com');
  const [authConfig, setAuthConfig] = useState<AuthConfig | null>(null);

  useEffect(() => {
    // Auto-initialize demo credentials in local environment
    const initAuth = async () => {
      try {
        const config = await api.getAuthConfig();
        setAuthConfig(config);
        if (config.demo_mode) {
          const res = await api.mintDemoToken('operator', 'operator@example.com');
          api.setToken(res.access_token);
          setTokenState(res.access_token);
          setRoleState(res.role);
        }
      } catch (err) {
        console.warn('Auth configuration initialization error:', err);
      }
    };
    initAuth();
  }, []);

  const loginDemo = async (targetRole: string = 'operator') => {
    try {
      const res = await api.mintDemoToken(targetRole, `${targetRole}@example.com`);
      api.setToken(res.access_token);
      setTokenState(res.access_token);
      setRoleState(res.role);
      setEmailState(`${targetRole}@example.com`);
    } catch (err) {
      console.error('Failed to mint demo token:', err);
      throw err;
    }
  };

  const logout = () => {
    api.setToken(null);
    setTokenState(null);
    setRoleState('viewer');
    setEmailState('');
  };

  const setRole = async (newRole: string) => {
    await loginDemo(newRole);
  };

  return (
    <AuthContext.Provider
      value={{
        token,
        role,
        email,
        isAuthenticated: !!token,
        authConfig,
        loginDemo,
        logout,
        setRole,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
