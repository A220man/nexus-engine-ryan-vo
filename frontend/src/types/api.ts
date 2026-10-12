export interface ExecutionRecord {
  id: string;
  session_id: string;
  command: string;
  status: string;
  exit_code: number | null;
  duration_ms: number;
  raw_bytes: number;
  sandboxed_bytes: number;
  is_sandboxed: boolean;
  preview_summary: string;
  created_at: string;
  chunks_count: number;
}

export interface ChunkRecord {
  id: string;
  chunk_index: number;
  byte_length: number;
  content: string;
  checksum: string;
  created_at: string;
}

export interface SearchResultItem {
  chunk_index: number;
  line_number: number;
  snippet: string;
  match_score: number;
}

export interface SandboxSearchResponse {
  execution_id: string;
  total_matches: number;
  results: SearchResultItem[];
}

export interface MetricsSummary {
  total_sessions: number;
  total_tool_calls: number;
  total_raw_bytes: number;
  total_diverted_bytes: number;
  overall_savings_ratio: number;
  estimated_tokens_saved: number;
  estimated_cost_saved_usd: number;
  verified_invariants_pass: boolean;
}

export interface SessionMetrics {
  session_id: string;
  platform: string;
  tool_calls_count: number;
  raw_bytes: number;
  diverted_bytes: number;
  savings_ratio: number;
  tokens_saved: number;
  cost_saved_usd: number;
}

export interface PlatformConfig {
  platform_id: string;
  name: string;
  category: string;
  hook_mode: string;
  config_snippet: string;
  tool_guidance_block: string;
  quiet_mode_supported: boolean;
  version_supported: string;
}

export interface EvaluationResult {
  total_samples: number;
  average_raw_bytes: number;
  average_sandboxed_bytes: number;
  compression_ratio: number;
  retrieval_recall: number;
  classifier_safety_score: number;
  run_duration_ms: number;
  provenance: string;
}

export interface AdvisoryResponse {
  execution_id: string;
  provider: string;
  model: string;
  explanation: string;
  advisory_notice: string;
  latency_ms: number;
}

export interface AuthConfig {
  oidc_enabled: boolean;
  oidc_issuer_url: string;
  oidc_client_id: string;
  oidc_audience: string;
  demo_mode: boolean;
  environment: string;
  roles: string[];
}
