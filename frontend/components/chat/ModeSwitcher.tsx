'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { useStore } from '@/store';
import { api } from '@/lib/api';
import { ChevronDown, Cpu, Layers, Sparkles, Cloud } from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';
import { errMsg } from '@/lib/utils';

const modes = [
  { id: 'fullram', label: 'Full RAM', icon: Cpu, description: 'Fastest, uses more memory' },
  { id: 'layerstream', label: 'Layer Stream', icon: Layers, description: 'Experimental: low memory for models that do not fit in RAM', experimental: true },
  { id: 'auto', label: 'Auto', icon: Sparkles, description: 'Automatic selection' },
];

const CLOUD_MODE: { id: string; label: string; icon: React.ElementType; description: string } = {
  id: 'cloud',
  label: 'Cloud',
  icon: Cloud,
  description: 'Remote inference via a provider API — no local model loaded',
};

export function ModeSwitcher() {
  const { systemStatus, setSystemStatus, setSettingsOpen } = useStore();
  const [switching, setSwitching] = useState(false);
  const { toast } = useToast();

  const currentMode =
    systemStatus?.current_mode === 'cloud'
      ? CLOUD_MODE
      : modes.find(m => m.id === systemStatus?.current_mode) || modes[2];

  const handleSwitch = async (mode: string) => {
    if (mode === systemStatus?.current_mode) return;

    setSwitching(true);
    try {
      const result = await api.switchMode(mode);
      setSystemStatus({
        ...systemStatus!,
        current_mode: result.mode
      });
      toast({
        title: 'Mode switched',
        description: `Now using ${mode} mode`,
      });
    } catch (error) {
      toast({
        title: 'Failed to switch mode',
        description: errMsg(error),
        variant: 'destructive',
      });
    } finally {
      setSwitching(false);
    }
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" disabled={switching}>
          <currentMode.icon className="h-4 w-4 mr-2" />
          {currentMode.label}
          <ChevronDown className="h-4 w-4 ml-2" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {modes.map((mode) => (
          <DropdownMenuItem
            key={mode.id}
            onClick={() => handleSwitch(mode.id)}
            className="flex items-start gap-2"
            disabled={mode.id === 'cloud'}
          >
            <mode.icon className="h-4 w-4 mt-0.5" />
            <div>
              <p className="font-medium">
                {mode.label}
                {'experimental' in mode && mode.experimental && (
                  <span className="ml-2 text-[10px] font-semibold uppercase tracking-wide text-amber-500">
                    Experimental
                  </span>
                )}
              </p>
              <p className="text-xs text-muted-foreground">{mode.description}</p>
            </div>
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuItem
          onClick={() => setSettingsOpen('cloud')}
          className="flex items-start gap-2"
          disabled={switching}
        >
          <Cloud className="h-4 w-4 mt-0.5" />
          <div>
            <p className="font-medium">Cloud / Online</p>
            <p className="text-xs text-muted-foreground">Add a provider API key to use online models</p>
          </div>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
