"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import {
  Settings,
  Bot,
  Palette,
  Database,
  Shield,
  Baby,
  RotateCcw,
  Info,
  Cloud,
} from "lucide-react";
import { GeneralSettings } from "./GeneralSettings";
import { ProjectSettings } from "./ProjectSettings";
import { AgentSettings } from "./AgentSettings";

import { PersonalizationSettings } from "./PersonalizationSettings";
import { DataControlsSettings } from "./DataControlsSettings";
import { SecuritySettings } from "./SecuritySettings";
import { ParentalControlsSettings } from "./ParentalControlsSettings";
import { CloudProvidersSettings } from "./CloudProvidersSettings";
import { useToast } from "@/components/ui/use-toast";
import { api } from "@/lib/api";
import { useSettingsStore } from "@/store/settings";
import type { Agent, SettingsMap } from "@/types";

type Section =
  | "general"
  | "project"
  | "agents"
  | "personalization"
  | "data_controls"
  | "security"
  | "parental_controls"
  | "cloud";


const EMPTY: Record<string, unknown> = {};

interface SectionMeta {
  key: Section;
  label: string;
  icon: React.ElementType;
  description: string;
}

const NAV_GROUPS: { label: string; items: SectionMeta[] }[] = [
  {
    label: "Application",
    items: [
      {
        key: "general",
        label: "General",
        icon: Settings,
        description: "Theme, language, generation defaults, and startup behavior.",
      },
      {
        key: "project",
        label: "Project Info",
        icon: Info,
        description: "Metadata and links shown for this installation.",
      },
    ],
  },
  {
    label: "AI & Models",
    items: [
      {
        key: "agents",
        label: "Agents",
        icon: Bot,
        description: "Create and manage specialized AI personas.",
      },
      {
        key: "personalization",
        label: "Personalization",
        icon: Palette,
        description: "How the AI writes and what it knows about you.",
      },
      {
        key: "cloud",
        label: "Cloud / Online",
        icon: Cloud,
        description: "External API providers used for online mode.",
      },
    ],
  },
  {
    label: "Privacy & Data",
    items: [
      {
        key: "data_controls",
        label: "Data Controls",
        icon: Database,
        description: "Chat history storage, retention, and export.",
      },
    ],
  },
  {
    label: "Access & Safety",
    items: [
      {
        key: "security",
        label: "Security",
        icon: Shield,
        description: "Access control, network binding, and protected data.",
      },
      {
        key: "parental_controls",
        label: "Parental Controls",
        icon: Baby,
        description: "Restrict content, models, and session length.",
      },
    ],
  },
];

const ALL_SECTIONS: SectionMeta[] = NAV_GROUPS.flatMap((g) => g.items);


interface SettingsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function SettingsDialog({ open, onOpenChange }: SettingsDialogProps) {
  const [activeSection, setActiveSection] = useState<Section>("general");
  const [settings, setSettings] = useState<SettingsMap>({});
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const viewportRef = useRef<HTMLDivElement>(null);
  const { toast } = useToast();

  const fetchAllSettings = useCallback(async () => {
    try {
      setLoading(true);
      const data = await api.getAllSettings();
      const { agents: agentList, ...rest } = data;
      setSettings(rest);
      setAgents(agentList || []);
    } catch {
      toast({
        title: "Error",
        description: "Failed to load settings",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    if (open) {
      fetchAllSettings();
    }
  }, [open, fetchAllSettings]);

  // Jump back to the top whenever the user switches sections so they never
  // land mid-page in a freshly selected panel.
  useEffect(() => {
    viewportRef.current?.scrollTo({ top: 0 });
  }, [activeSection]);

  const updateSection = async (section: string, data: Record<string, unknown>) => {
    try {
      const result = await api.updateSettingsSection(section, data);

      setSettings((prev) => ({ ...prev, [section]: data }));
      // Mirror into the global settings store so live consumers (chat storage
      // mode, retention, send_on_enter, sampling defaults) see the change.
      void useSettingsStore.getState().updateSection(section, data);

      toast({
        title: "Saved",
        description: result.message || "Settings updated successfully",
      });
    } catch {
      toast({
        title: "Error",
        description: "Failed to save settings",
        variant: "destructive",
      });
    }
  };

  const resetAll = async () => {
    try {
      await api.resetSettings();
      await fetchAllSettings();
      void useSettingsStore.getState().resetAll();
      toast({ title: "Reset", description: "All settings restored to defaults" });
    } catch {
      toast({
        title: "Error",
        description: "Failed to reset settings",
        variant: "destructive",
      });
    }
  };

  const activeMeta = ALL_SECTIONS.find((s) => s.key === activeSection);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-[90vw] max-w-[900px] h-[80vh] max-h-[680px] p-0 bg-slate-950 border-slate-800 text-white overflow-hidden flex flex-col sm:flex-row">
        <div className="flex h-full w-full">
          {/* Sidebar */}
          <div className="w-[220px] shrink-0 border-r border-slate-800 flex flex-col">
            <DialogHeader className="p-4 pb-2">
              <DialogTitle className="text-lg font-semibold flex items-center gap-2">
                <Settings className="h-5 w-5 text-blue-500" />
                Settings
              </DialogTitle>
            </DialogHeader>
            <Separator className="bg-slate-800" />
            <ScrollArea className="flex-1 py-2">
              <nav className="flex flex-col gap-3 px-2">
                {NAV_GROUPS.map((group) => (
                  <div key={group.label} className="flex flex-col gap-1">
                    <p className="px-3 pt-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                      {group.label}
                    </p>
                    {group.items.map(({ key, label, icon: Icon }) => (
                      <button
                        key={key}
                        onClick={() => setActiveSection(key)}
                        className={cn(
                          "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors text-left w-full",
                          activeSection === key
                            ? "bg-slate-800 text-white"
                            : "text-slate-400 hover:text-white hover:bg-slate-800/50"
                        )}
                      >
                        <Icon className="h-4 w-4 shrink-0" />
                        {label}
                      </button>
                    ))}
                  </div>
                ))}
              </nav>
            </ScrollArea>
            <Separator className="bg-slate-800" />
            <div className="p-3">
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="w-full text-slate-400 hover:text-red-400 hover:bg-red-950/20 justify-start gap-2"
                  >
                    <RotateCcw className="h-4 w-4" />
                    Reset All Defaults
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent className="bg-slate-950 border-slate-800 text-white">
                  <AlertDialogHeader>
                    <AlertDialogTitle>Reset all settings?</AlertDialogTitle>
                    <AlertDialogDescription className="text-slate-400">
                      Every section — including agents, personalization, security
                      and parental controls — will be restored to its default
                      values. This cannot be undone.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel className="bg-slate-900 border-slate-700 text-slate-300 hover:bg-slate-800">
                      Cancel
                    </AlertDialogCancel>
                    <AlertDialogAction
                      className="bg-red-600 hover:bg-red-700"
                      onClick={resetAll}
                    >
                      Reset everything
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </div>
          </div>

          {/* Content */}
          <div className="flex-1 flex flex-col overflow-hidden">
            <div className="px-6 py-4 pr-12 border-b border-slate-800 shrink-0">
              <h2 className="text-lg font-semibold">
                {activeMeta?.label}
              </h2>
              {activeMeta?.description && (
                <p className="text-xs text-slate-500 mt-0.5">
                  {activeMeta.description}
                </p>
              )}
            </div>
            <ScrollArea className="flex-1 px-6 py-4" viewportRef={viewportRef}>
              {loading ? (
                <div className="flex items-center justify-center h-full text-slate-500">
                  Loading settings...
                </div>
              ) : (
                <>
                  {activeSection === "general" && (
                    <GeneralSettings
                      data={settings.general ?? EMPTY}
                      onSave={(data) => updateSection("general", data)}
                    />
                  )}
                  {activeSection === "project" && (
                    <ProjectSettings
                      data={settings.project ?? EMPTY}
                      onSave={(data) => updateSection("project", data)}
                    />
                  )}

                  {activeSection === "agents" && (
                    <AgentSettings
                      agents={agents}
                      onRefresh={fetchAllSettings}
                    />
                  )}
                  {activeSection === "personalization" && (
                    <PersonalizationSettings
                      data={settings.personalization ?? EMPTY}
                      onSave={(data) => updateSection("personalization", data)}
                    />
                  )}
                  {activeSection === "data_controls" && (
                    <DataControlsSettings
                      data={settings.data_controls ?? EMPTY}
                      onSave={(data) => updateSection("data_controls", data)}
                    />
                  )}
                  {activeSection === "security" && (
                    <SecuritySettings
                      data={settings.security ?? EMPTY}
                      onSave={(data) => updateSection("security", data)}
                    />
                  )}
                  {activeSection === "parental_controls" && (
                    <ParentalControlsSettings
                      data={settings.parental_controls ?? EMPTY}
                      onSave={(data) =>
                        updateSection("parental_controls", data)
                      }
                    />
                  )}
                  {activeSection === "cloud" && <CloudProvidersSettings />}
                </>
              )}
            </ScrollArea>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
