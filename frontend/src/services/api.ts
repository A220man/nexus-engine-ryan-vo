import {
  ExecutionRecord,
  ChunkRecord,
  SandboxSearchResponse,
  MetricsSummary,
  SessionMetrics,
  PlatformConfig,
  EvaluationResult,
  AdvisoryResponse,
  AuthConfig,
} from '../types/api';

const API_BASE = (import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000') + '/api';

class ApiClient {
  private token: string | null = null;

  setToken(token: string | null) {
    this.token = token;
  }

  getToken(): string | null {
    return this.token;
  }

  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const headers = new Headers(options.headers || {});
    headers.set('Content-Type', 'application/json');

    if (this.token) {
      headers.set('Authorization', `Bearer ${this.token}`);
    }

    const response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      let errorMsg = `HTTP Error ${response.status}`;
      try {
        const errorData = await response.json();
        if (errorData.detail) {
          errorMsg = typeof errorData.detail === 'string' ? errorData.detail : JSON.stringify(errorData.detail);
        }
      } catch {
        // use default error message
      }
      throw new Error(errorMsg);
    }

    return response.json();
  }

  async getHealth(): Promise<{ status: string; database: string }> {
    return this.request('/health');
  }

  async getAuthConfig(): Promise<AuthConfig> {
    return this.request('/auth/config');
  }

  async mintDemoToken(role: string = 'operator', email: string = 'operator@example.com'): Promise<{ access_token: string; role: string }> {
    return this.request('/auth/demo-token', {
      method: 'POST',
      body: JSON.stringify({ role, email }),
    });
  }

  async executeCommand(sessionId: string, command: string, platform: string = 'generic', timeoutSeconds?: number): Promise<ExecutionRecord> {
    return this.request('/executions', {
      method: 'POST',
      body: JSON.stringify({
        session_id: sessionId,
        command,
        platform,
        timeout_seconds: timeoutSeconds,
      }),
    });
  }

  async listExecutions(sessionId?: string, limit: number = 50): Promise<ExecutionRecord[]> {
    const query = new URLSearchParams();
    if (sessionId) query.set('session_id', sessionId);
    query.set('limit', limit.toString());
    return this.request(`/executions?${query.toString()}`);
  }

  async getExecutionDetail(id: string): Promise<ExecutionRecord> {
    return this.request(`/executions/${id}`);
  }

  async getExecutionChunks(id: string): Promise<ChunkRecord[]> {
    return this.request(`/executions/${id}/chunks`);
  }

  async abortExecution(id: string): Promise<{ execution_id: string; aborted: boolean }> {
    return this.request(`/executions/${id}/abort`, {
      method: 'POST',
    });
  }

  async createSandbox(sessionId: string, text: string, title?: string, platform: string = 'generic'): Promise<ExecutionRecord> {
    return this.request('/sandboxes', {
      method: 'POST',
      body: JSON.stringify({
        session_id: sessionId,
        text,
        title,
        platform,
      }),
    });
  }

  async searchSandbox(executionId: string, query: string, regex: boolean = false): Promise<SandboxSearchResponse> {
    const params = new URLSearchParams({
      query,
      regex: regex.toString(),
    });
    return this.request(`/sandboxes/${executionId}/search?${params.toString()}`);
  }

  async getMetricsSummary(): Promise<MetricsSummary> {
    return this.request('/metrics/summary');
  }

  async getSessionMetrics(limit: number = 50): Promise<SessionMetrics[]> {
    return this.request(`/metrics/sessions?limit=${limit}`);
  }

  async listPlatforms(): Promise<PlatformConfig[]> {
    return this.request('/platforms');
  }

  async getPlatformConfig(platformId: string, quietMode: boolean = false): Promise<PlatformConfig> {
    return this.request(`/platforms/${platformId}/config?quiet_mode=${quietMode}`);
  }

  async runEvaluation(maxSamples: number = 10): Promise<EvaluationResult> {
    return this.request('/evaluation/run', {
      method: 'POST',
      body: JSON.stringify({ max_samples: maxSamples }),
    });
  }

  async requestAdvisory(executionId: string, promptHint?: string): Promise<AdvisoryResponse> {
    return this.request('/advisory/explain', {
      method: 'POST',
      body: JSON.stringify({
        execution_id: executionId,
        prompt_hint: promptHint,
      }),
    });
  }
}

export const api = new ApiClient();
