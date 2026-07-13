import { create } from 'zustand';
import type { SystemStatus, Hardware } from '@/types';

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