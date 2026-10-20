'use client';

import { useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { HardwareCard } from '@/components/system/HardwareCard';
import { MetricCard } from '@/components/system/MetricCard';
import { ResourceChart } from '@/components/system/ResourceChart';
import { useMetrics } from '@/hooks/useMetrics';
import { useStore } from '@/store';
import { Cpu, MemoryStick, HardDrive, Gpu, Activity } from 'lucide-react';
import { api } from '@/lib/api';


/** Render a detected value, or a non-numeric label when there is none.
   Unknown counts come back as null (or 0 from a provider that knows nothing);
   showing "0 GB" / "0 cores" for those stated a fact the app did not have. */
function known(value: number | null | undefined, unit: string, digits = 1): string {
  return typeof value === 'number' && Number.isFinite(value) && value > 0
    ? `${value.toFixed(digits)} ${unit}`
    : 'Unavailable';
}

/** Disk type is a string that may legitimately come back as "Unknown". */
function diskLabel(diskType: string | null | undefined): string {
  return !diskType || diskType.toLowerCase() === 'unknown' ? 'Not detected' : diskType;
}

export default function SystemPage() {
  const { hardware, setHardware, systemStatus, setSystemStatus } = useStore();
  const { metrics, history, connected } = useMetrics();

  useEffect(() => {
    const fetchSystemData = async () => {
      // allSettled, not all: one failing endpoint must not blank the page. A
      // single rejected request used to leave every hardware card on its
      // fallback while the WebSocket metrics kept ticking, so the dashboard
      // read "Unknown / 0 GB / None" next to live CPU and RAM figures.
      const [hw, status] = await Promise.allSettled([
        api.getHardware(),
        api.getSystemStatus()
      ]);
      if (hw.status === 'fulfilled') setHardware(hw.value);
      else console.error('Failed to fetch hardware profile:', hw.reason);
      if (status.status === 'fulfilled') setSystemStatus(status.value);
      else console.error('Failed to fetch system status:', status.reason);
    };
    fetchSystemData();
  }, [setHardware, setSystemStatus]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">System</h1>
        <p className="text-muted-foreground">
          Hardware profile and resource monitoring
        </p>
      </div>

      {/* Hardware Profile */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <HardwareCard
          title="CPU"
          icon={Cpu}
          value={hardware?.cpu_name || 'Not detected'}
          details={[
            hardware ? `${hardware.cpu_cores} cores / ${hardware.cpu_threads} threads` : 'Unavailable',
            hardware
              ? `AVX2: ${hardware.has_avx2 ? '✓' : '✗'} | AVX512: ${hardware.has_avx512 ? '✓' : '✗'}`
              : 'Instruction sets unavailable'
          ]}
        />
        <HardwareCard
          title="Memory"
          icon={MemoryStick}
          value={known(hardware?.ram_total_gb, 'GB')}
          details={[
            `Available: ${known(systemStatus?.ram_available_gb, 'GB')}`,
            `Used: ${known(systemStatus?.ram_used_gb, 'GB')}`
          ]}
        />
        <HardwareCard
          title="Storage"
          icon={HardDrive}
          value={diskLabel(hardware?.disk_type)}
          details={[
            `Speed: ${known(hardware?.disk_speed_mb_s, 'MB/s', 0)}`,
            // Free space comes from the live status call, not the profile: the
            // profile is captured once at startup.
            `Free: ${known(systemStatus?.disk_free_gb, 'GB', 0)}`
          ]}
        />
        <HardwareCard
          title="GPU"
          icon={Gpu}
          value={hardware?.gpu_name || 'Not detected'}
          details={[
            !hardware?.gpu_name
              ? 'No GPU detected'
              : hardware?.gpu_vram_gb
                ? `VRAM: ${hardware.gpu_vram_gb} GB`
                : 'VRAM: Unavailable'
          ]}
        />
      </div>

      {/* Live Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4">
        <MetricCard
          title="CPU Usage"
          value={metrics?.cpu_percent || 0}
          unit="%"
          status={(metrics?.cpu_percent ?? 0) > 80 ? 'critical' : (metrics?.cpu_percent ?? 0) > 50 ? 'warning' : 'normal'}
        />
        <MetricCard
          title="GPU Usage"
          value={metrics?.gpu_percent || 0}
          unit="%"
          status={(metrics?.gpu_percent ?? 0) > 80 ? 'critical' : (metrics?.gpu_percent ?? 0) > 50 ? 'warning' : 'normal'}
        />
        <MetricCard
          title="RAM Usage"
          value={metrics?.ram_percent || 0}
          unit="%"
          status={(metrics?.ram_percent ?? 0) > 80 ? 'critical' : (metrics?.ram_percent ?? 0) > 60 ? 'warning' : 'normal'}
        />
        <MetricCard
          title="Disk Read"
          value={metrics?.disk_read_mb || 0}
          unit="MB/s"
        />
        <MetricCard
          title="Disk Write"
          value={metrics?.disk_write_mb || 0}
          unit="MB/s"
        />
      </div>

      {/* Resource Charts */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            Resource History
          </CardTitle>
          <CardDescription>
            {connected ? 'Live updates' : 'Disconnected - Reconnecting...'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ResourceChart data={history} />
        </CardContent>
      </Card>

      {/* Engine Stats */}
      {systemStatus?.engine_stats && Object.keys(systemStatus.engine_stats).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Engine Statistics</CardTitle>
            <CardDescription>
              Current model: {systemStatus.current_model} ({systemStatus.current_mode})
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {Object.entries(systemStatus.engine_stats).map(([key, value]) => (
                <div key={key} className="p-3 bg-muted rounded-lg">
                  <p className="text-sm text-muted-foreground">{key.replace(/_/g, ' ')}</p>
                  <p className="text-lg font-semibold">
                    {typeof value === 'number' ? value.toFixed(2) : String(value)}
                  </p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}