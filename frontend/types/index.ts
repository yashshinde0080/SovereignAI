export interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

export interface Model {
  id: string;
  name: string;
  size_gb: number;
  quant: string;
  family: string;
  parameters: string;
  path: string;
  downloaded: boolean;
  modes_supported: string[];
  created_at?: string;
}

export interface Plugin {
  id: string;
  name: string;
  version: string;
  description: string;
  author: string;
  enabled: boolean;
  builtin: boolean;
  actions: string[];
}

export interface SystemStatus {
  model_loaded: boolean;
  current_model: string | null;
  current_mode: string | null;
  task_type: string | null;
  is_generative: boolean;
  ram_total_gb: number;
  ram_used_gb: number;
  ram_available_gb: number;
  disk_total_gb: number;
  disk_used_gb: number;
  disk_free_gb: number;
  engine_stats: Record<string, any>;
}

export interface Hardware {
  cpu_name: string;
  cpu_cores: number;
  cpu_threads: number;
  has_avx2: boolean;
  has_avx512: boolean;
  ram_total_gb: number;
  gpu_name: string | null;
  gpu_vram_gb: number | null;
  disk_type: string;
  disk_speed_mb_s: number;
}

export interface Metrics {
  cpu_percent: number;
  gpu_percent: number;
  gpu_vram_used: number;
  ram_percent: number;
  ram_used_gb: number;
  disk_read_mb: number;
  disk_write_mb: number;
  model_loaded: string | null;
  mode: string | null;
  task_type: string | null;
  is_generative: boolean;
  engine_stats: Record<string, any>;
}

export interface BenchmarkResult {
  model: string;
  mode: string;
  iterations: number;
  runs: BenchmarkRun[];
  summary: BenchmarkSummary;
}

export interface BenchmarkRun {
  iteration: number;
  tokens: number;
  time_seconds: number;
  tokens_per_second: number;
}

export interface BenchmarkSummary {
  total_tokens: number;
  total_time_seconds: number;
  average_tokens_per_second: number;
  peak_ram_gb: number;
}

export interface Document {
  id: string;
  filename: string;
  chunks: number;
  created_at: string;
}

export interface QueryResult {
  query: string;
  results: SearchResult[];
  generated_response: string | null;
}

export interface SearchResult {
  text: string;
  score: number;
  metadata: Record<string, any>;
  document_id: string;
}