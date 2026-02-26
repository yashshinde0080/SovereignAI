'use client';

import { useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { PluginList } from '@/components/plugins/PluginList';
import { usePlugins } from '@/hooks/usePlugins';
import { Puzzle } from 'lucide-react';

export default function PluginsPage() {
  const { plugins, loading, refresh, enablePlugin, disablePlugin } = usePlugins();

  useEffect(() => {
    refresh();
  }, []);

  const builtinPlugins = plugins.filter(p => p.builtin);
  const userPlugins = plugins.filter(p => !p.builtin);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Plugins</h1>
        <p className="text-muted-foreground">
          Extend SovereignAI functionality
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Puzzle className="h-5 w-5" />
            Built-in Plugins
          </CardTitle>
          <CardDescription>
            Core functionality plugins
          </CardDescription>
        </CardHeader>
        <CardContent>
          <PluginList
            plugins={builtinPlugins}
            onEnable={enablePlugin}
            onDisable={disablePlugin}
            loading={loading}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>User Plugins</CardTitle>
          <CardDescription>
            Custom plugins installed in the plugins directory
          </CardDescription>
        </CardHeader>
        <CardContent>
          {userPlugins.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <p>No user plugins installed</p>
              <p className="text-sm mt-2">
                Place plugin files in the <code className="bg-muted px-1 rounded">plugins/</code> directory
              </p>
            </div>
          ) : (
            <PluginList
              plugins={userPlugins}
              onEnable={enablePlugin}
              onDisable={disablePlugin}
              loading={loading}
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
}