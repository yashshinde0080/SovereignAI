import type {
  Agent,
  BenchmarkResult,
  CurrentModel,
  Document,
  DownloadStatus,
  Hardware,
  Message,
  Model,
  Plugin,
  QueryResult,
  Recommendation,
  SettingsMap,
  SystemStatus,
  TaskResult,
  WorkspaceSnapshot,
} from '@/types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;

    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Request failed' }));
      throw new Error(error.detail || 'Request failed');
    }

    return response.json();
  }

  // System
  async getSystemStatus(): Promise<SystemStatus> {
    return this.request('/v1/system/status');
  }

  async getHardware(): Promise<Hardware> {
    return this.request('/v1/system/hardware');
  }

  async getRecommendations(): Promise<{ recommendations: Recommendation[] }> {
    return this.request('/v1/system/recommendation');
  }

  async getResources() {
    return this.request('/v1/system/resources');
  }

  // Models
  async listModels(): Promise<{ models: Model[] }> {
    return this.request('/v1/models/');
  }

  async loadModel(model: string, mode: string = 'auto') {
    return this.request('/v1/models/load', {
      method: 'POST',
      body: JSON.stringify({ model, mode }),
    });
  }

  async unloadModel() {
    return this.request('/v1/models/unload', { method: 'POST' });
  }

  async pullModel(model: string, quant: string) {
    return this.request('/v1/models/pull', {
      method: 'POST',
      body: JSON.stringify({ model, quant }),
    });
  }

  async getPullStatus(model: string): Promise<DownloadStatus> {
    return this.request(`/v1/models/pull/status/${model}`);
  }

  async deleteModel(model: string) {
    return this.request(`/v1/models/${model}`, { method: 'DELETE' });
  }

  async getCurrentModel(): Promise<CurrentModel> {
    return this.request('/v1/models/current');
  }

  // Chat / Execute
  async chat(messages: Message[], stream: boolean = false) {
    return this.request('/v1/chat/completions', {
      method: 'POST',
      body: JSON.stringify({ messages, stream }),
    });
  }

  async executeTask(data: Record<string, unknown>): Promise<TaskResult> {
    return this.request<TaskResult>('/v1/chat/execute', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async switchMode(mode: string): Promise<{ mode: string }> {
    return this.request(`/v1/chat/mode/switch?mode=${mode}`, {
      method: 'POST',
    });
  }

  // Benchmark
  async runBenchmark(iterations: number, maxTokens: number): Promise<BenchmarkResult> {
    return this.request('/v1/benchmark/run', {
      method: 'POST',
      body: JSON.stringify({ iterations, max_tokens: maxTokens }),
    });
  }

  // Documents
  async listDocuments(): Promise<{ documents: Document[] }> {
    return this.request('/v1/rag/documents');
  }

  async uploadDocument(file: File) {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${this.baseUrl}/v1/rag/upload`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw new Error('Upload failed');
    }

    return response.json();
  }

  async queryDocuments(query: string, topK: number = 5): Promise<QueryResult> {
    return this.request('/v1/rag/query', {
      method: 'POST',
      body: JSON.stringify({ query, top_k: topK, generate_response: true }),
    });
  }

  async getDocumentChunks(docId: string): Promise<{
    document_id: string;
    chunks: { chunk_index: number; content: string; metadata: Record<string, unknown> }[];
  }> {
    return this.request(`/v1/rag/documents/${encodeURIComponent(docId)}/chunks`);
  }

  async deleteDocument(docId: string) {
    return this.request(`/v1/rag/documents/${docId}`, { method: 'DELETE' });
  }

  // Plugins
  async listPlugins(): Promise<Plugin[]> {
    return this.request('/v1/plugins/');
  }

  async enablePlugin(pluginId: string) {
    return this.request(`/v1/plugins/${pluginId}/enable`, { method: 'POST' });
  }

  async disablePlugin(pluginId: string) {
    return this.request(`/v1/plugins/${pluginId}/disable`, { method: 'POST' });
  }

  // Workspace Snapshots
  async saveWorkspace() {
    return this.request('/v1/workspace/save', { method: 'POST' });
  }

  async listWorkspaces(): Promise<{ snapshots: WorkspaceSnapshot[] }> {
    return this.request('/v1/workspace/');
  }

  async loadWorkspace(snapId: string): Promise<WorkspaceSnapshot> {
    return this.request(`/v1/workspace/${snapId}`);
  }

  async deleteWorkspace(snapId: string) {
    return this.request(`/v1/workspace/${snapId}`, { method: 'DELETE' });
  }

  // Benchmark Compare
  async compareModes() {
    return this.request('/v1/benchmark/compare');
  }

  // Settings
  async getAllSettings(): Promise<SettingsMap> {
    return this.request('/v1/settings');
  }

  async updateSettingsSection(section: string, data: Record<string, unknown>): Promise<{ message?: string }> {
    return this.request(`/v1/settings/${section.replace(/_/g, '-')}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async resetSettings() {
    return this.request('/v1/settings/reset', { method: 'POST' });
  }

  async setSecurityPassword(password: string) {
    return this.request(`/v1/settings/security/set-password?password=${encodeURIComponent(password)}`, {
      method: 'POST',
    });
  }

  async setParentalPin(pin: string) {
    return this.request(`/v1/settings/parental-controls/set-pin?pin=${encodeURIComponent(pin)}`, {
      method: 'POST',
    });
  }

  // Agents
  async listAgents(): Promise<Agent[]> {
    return this.request('/v1/settings/agents');
  }

  async createAgent(agent: Agent) {
    return this.request('/v1/settings/agents', {
      method: 'POST',
      body: JSON.stringify(agent),
    });
  }

  async updateAgent(agentId: string, agent: Agent) {
    return this.request(`/v1/settings/agents/${agentId}`, {
      method: 'PUT',
      body: JSON.stringify(agent),
    });
  }

  async deleteAgent(agentId: string) {
    return this.request(`/v1/settings/agents/${agentId}`, { method: 'DELETE' });
  }

  async activateAgent(agentId: string) {
    return this.request(`/v1/settings/agents/${agentId}/activate`, {
      method: 'POST',
    });
  }

  async deactivateAllAgents() {
    return this.request('/v1/settings/agents/deactivate', { method: 'POST' });
  }
}

export const api = new ApiClient(API_BASE);
