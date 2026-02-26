import { create } from 'zustand';

interface SystemStatus {
  model_loaded: boolean;
  current_model: string | null;
  current_mode: string | null;
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

  // Metrics
  metrics: {
    cpu_percent: number;
    ram_percent: number;
    ram_used_gb: number;
    disk_read_mb: number;
    disk_write_mb: number;
  } | null;
  setMetrics: (metrics: any) => void;
}

export const useStore = create<Store>((set) => ({
  systemStatus: null,
  setSystemStatus: (status) => set({ systemStatus: status }),

  hardware: null,
  setHardware: (hw) => set({ hardware: hw }),

  metrics: null,
  setMetrics: (metrics) => set({ metrics }),
}));