import { create } from 'zustand';

interface SystemStatus {
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

interface Hardware {
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

interface Store {
  // System
  systemStatus: SystemStatus | null;
  setSystemStatus: (status: SystemStatus) => void;
  
  hardware: Hardware | null;
  setHardware: (hw: Hardware) => void;

  // New Universal Task State
  currentModel: string;
  taskType: string;
  executionMode: "fullram" | "layerstream" | "auto";
  inputSchema: Record<string, any>;
  isGenerative: boolean;
  
  setCurrentModel: (model: string) => void;
  setTaskType: (task: string) => void;
  setExecutionMode: (mode: "fullram" | "layerstream" | "auto") => void;
  setIsGenerative: (isGen: boolean) => void;

  // Metrics
  metrics: {
    cpu_percent: number;
    gpu_percent: number;
    gpu_vram_used: number;
    ram_percent: number;
    ram_used_gb: number;
    disk_read_mb: number;
    disk_write_mb: number;
  } | null;
  setMetrics: (metrics: any) => void;
  
  connected: boolean;
  setConnected: (connected: boolean) => void;
  
  history: Array<{time: string, cpu: number, ram: number}>;
  setHistory: (history: any) => void;

  // UI State
  settingsOpen: boolean;
  setSettingsOpen: (open: boolean) => void;
}


export const useStore = create<Store>((set) => ({
  systemStatus: null,
  setSystemStatus: (status) => set({ systemStatus: status }),

  hardware: null,
  setHardware: (hw) => set({ hardware: hw }),
  
  currentModel: "",
  taskType: "",
  executionMode: "auto",
  inputSchema: {},
  isGenerative: false,
  
  setCurrentModel: (model) => set({ currentModel: model }),
  setTaskType: (task) => set({ taskType: task }),
  setExecutionMode: (mode) => set({ executionMode: mode }),
  setIsGenerative: (isGen: boolean) => set({ isGenerative: isGen }),

  metrics: null,
  setMetrics: (metrics) => set({ metrics }),
  
  connected: false,
  setConnected: (connected) => set({ connected }),
  
  history: [],
  setHistory: (history) => set((state) => ({ 
    history: typeof history === 'function' ? history(state.history) : history 
  })),

  settingsOpen: false,
  setSettingsOpen: (open) => set({ settingsOpen: open }),
}));