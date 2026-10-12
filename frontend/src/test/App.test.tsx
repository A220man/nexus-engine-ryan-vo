import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import App from '../App';

vi.mock('../services/api', () => {
  return {
    api: {
      getHealth: vi.fn().mockResolvedValue({ status: 'healthy', database: 'connected' }),
      getAuthConfig: vi.fn().mockResolvedValue({
        oidc_enabled: false,
        demo_mode: true,
        environment: 'development',
        roles: ['viewer', 'operator', 'admin'],
      }),
      mintDemoToken: vi.fn().mockResolvedValue({
        access_token: 'demo-test-token',
        role: 'operator',
      }),
      setToken: vi.fn(),
      getMetricsSummary: vi.fn().mockResolvedValue({
        total_sessions: 2,
        total_tool_calls: 15,
        total_raw_bytes: 52000,
        total_diverted_bytes: 48500,
        overall_savings_ratio: 0.9327,
        estimated_tokens_saved: 12125,
        estimated_cost_saved_usd: 0.0364,
        verified_invariants_pass: true,
      }),
      getSessionMetrics: vi.fn().mockResolvedValue([
        {
          session_id: 'session-alpha',
          platform: 'claude-code',
          tool_calls_count: 10,
          raw_bytes: 35000,
          diverted_bytes: 33000,
          savings_ratio: 0.9428,
          tokens_saved: 8250,
          cost_saved_usd: 0.0248,
        },
      ]),
      listExecutions: vi.fn().mockResolvedValue([]),
      listPlatforms: vi.fn().mockResolvedValue([
        {
          platform_id: 'claude-code',
          name: 'Claude Code',
          category: 'CLI Agent',
          hook_mode: 'pre-tool-use',
          config_snippet: '{\n  "mcpServers": {}\n}',
          tool_guidance_block: '<tool_guidance>\nNexus Engine optimizer active.\n</tool_guidance>',
          quiet_mode_supported: true,
          version_supported: '2.1+',
        },
        {
          platform_id: 'opencode-v2',
          name: 'OpenCode v2',
          category: 'Terminal IDE',
          hook_mode: 'mcp-schema-v2',
          config_snippet: '{\n  "$schema": "https://opencode.dev/v2/mcp-schema.json"\n}',
          tool_guidance_block: '<tool_guidance>\nNexus Engine optimizer active.\n</tool_guidance>',
          quiet_mode_supported: true,
          version_supported: '2.0+',
        },
      ]),
      getPlatformConfig: vi.fn().mockResolvedValue({
        platform_id: 'claude-code',
        name: 'Claude Code',
        category: 'CLI Agent',
        hook_mode: 'pre-tool-use',
        config_snippet: '{\n  "mcpServers": {}\n}',
        tool_guidance_block: '<tool_guidance>\nNexus Engine optimizer active.\n</tool_guidance>',
        quiet_mode_supported: true,
        version_supported: '2.1+',
      }),
      runEvaluation: vi.fn().mockResolvedValue({
        total_samples: 5,
        average_raw_bytes: 698.6,
        average_sandboxed_bytes: 581.6,
        compression_ratio: 97.8,
        retrieval_recall: 100.0,
        classifier_safety_score: 100.0,
        run_duration_ms: 12.5,
        provenance: 'eval_dataset.json',
      }),
    },
  };
});

describe('Nexus Engine Frontend Application', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders branding, navigation, and dashboard metric cards', async () => {
    render(<App />);

    expect(screen.getByText('Nexus Engine')).toBeInTheDocument();
    expect(screen.getAllByText(/Ryan Vo/).length).toBeGreaterThan(0);

    await waitFor(() => {
      expect(screen.getByText('Context Optimization Dashboard')).toBeInTheDocument();
      expect(screen.getByText('93.3%')).toBeInTheDocument();
      expect(screen.getByText(/Verified \(Part ≤ Whole\)/)).toBeInTheDocument();
      expect(screen.getByText('session-alpha')).toBeInTheDocument();
    });
  });

  it('switches to Sandbox Console tab and displays command runner', async () => {
    render(<App />);

    const sandboxBtn = screen.getByRole('button', { name: /Sandbox Console/i });
    fireEvent.click(sandboxBtn);

    await waitFor(() => {
      expect(screen.getByText('Execute Sandboxed Tool')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Run Command/i })).toBeInTheDocument();
    });
  });

  it('switches to Platforms tab and displays platform catalog and safe guidance', async () => {
    render(<App />);

    const platformsBtn = screen.getByRole('button', { name: /17 IDE Platforms/i });
    fireEvent.click(platformsBtn);

    await waitFor(() => {
      expect(screen.getByText(/Multi-Platform MCP Routing/i)).toBeInTheDocument();
      expect(screen.getByText('Claude Code Integration')).toBeInTheDocument();
      expect(screen.getByText(/Addresses Issues #911 & #967/i)).toBeInTheDocument();
    });
  });

  it('switches to AI/ML Benchmark tab and displays baseline comparison', async () => {
    render(<App />);

    const evalBtn = screen.getByRole('button', { name: /AI\/ML Benchmark/i });
    fireEvent.click(evalBtn);

    await waitFor(() => {
      expect(screen.getByText('AI & Machine Learning Evaluation Suite')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Run Evaluation Benchmark/i })).toBeInTheDocument();
      expect(screen.getByText('Benchmark Baseline vs Nexus Engine')).toBeInTheDocument();
      expect(screen.getByText('97.8% reduction')).toBeInTheDocument();
    });
  });
});
