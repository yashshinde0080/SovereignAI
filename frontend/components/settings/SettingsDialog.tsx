"use client";

import React, { useState, useEffect, useCallback, useMemo, useRef } from "react";
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
import { Input } from "@/components/ui/input";
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
  Search,
  X,
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
import { searchSettings, type SettingField } from "@/lib/settingsSearch";
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

const HIGHLIGHT_CLASSES = [
  "ring-2",
  "ring-blue-500/70",
  "ring-offset-2",
  "ring-offset-slate-950",
  "rounded-md",
];

/**
 * Scroll the field whose visible label matches `label` into view and flash a
 * ring around its row. Fields are located by label text, so components don't
 * need per-field anchor ids.
 */
function highlightField(label: string) {
  // Radix <Label> renders data-slot="label"; a few catalog entries are group
  // headings (h3) instead, so match those too.
  const nodes = Array.from(
    document.querySelectorAll<HTMLElement>('[data-slot="label"], h3')
  );
  const match = nodes.find((el) => el.textContent?.trim() === label);
  const row = match?.closest("div");
  if (!row) {
    return false;
  }
  row.scrollIntoView({ behavior: "smooth", block: "center" });
  row.classList.add(...HIGHLIGHT_CLASSES);
  window.setTimeout(() => row.classList.remove(...HIGHLIGHT_CLASSES), 1600);
  return true;
}


interface SettingsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Section to reveal on open, e.g. "cloud" from the Cloud Settings shortcuts. */
  initialSection?: string;
}

export function SettingsDialog({ open, onOpenChange, initialSection }: SettingsDialogProps) {
  const [activeSection, setActiveSection] = useState<Section>("general");
  const [settings, setSettings] = useState<SettingsMap>({});
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [jump, setJump] = useState<
    { section: Section; label: string; nonce: number } | null
  >(null);
  const viewportRef = useRef<HTMLDivElement>(null);
  const { toast } = useToast();

  const results = useMemo(() => searchSettings(query), [query]);

  const sectionLabel = useCallback(
    (key: string) => ALL_SECTIONS.find((s) => s.key === key)?.label ?? key,
    []
  );

  const selectSection = useCallback((key: Section) => {
    setJump(null);
    setActiveSection(key);
  }, []);

  const jumpTo = useCallback((field: SettingField) => {
    setQuery("");
    setActiveSection(field.section as Section);
    setJump({
      section: field.section as Section,
      label: field.label,
      nonce: Date.now(),
    });
  }, []);

  const handleSearchKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Escape") {
      setQuery("");
    } else if (e.key === "Enter" && results.length > 0) {
      e.preventDefault();
      jumpTo(results[0]);
    }
  };

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
      // Honor the section the opener asked for (setSettingsOpen('cloud') etc.).
      if (initialSection && ALL_SECTIONS.some((s) => s.key === initialSection)) {
        setActiveSection(initialSection as Section);
        setJump(null);
      }
      fetchAllSettings();
    }
  }, [open, initialSection, fetchAllSettings]);

  // Section switch scrolls back to the top so the user never lands mid-page.
  // A search jump instead scrolls to (and flashes) the matched field, after
  // letting the newly mounted section paint.
  useEffect(() => {
    if (jump && jump.section === activeSection) {
      // Retry briefly: the section may still be painting (or settings may still
      // be loading) when the jump lands, so the target label may not exist yet.
      let attempts = 0;
      let timer = 0;
      const tryScroll = () => {
        attempts += 1;
        if (!highlightField(jump.label) && attempts < 10) {
          timer = window.setTimeout(tryScroll, 100);
        }
      };
      timer = window.setTimeout(tryScroll, 80);
      return () => window.clearTimeout(timer);
    }
    viewportRef.current?.scrollTo({ top: 0, behavior: "smooth" });
  }, [activeSection, jump]);

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
            <div className="px-3 py-2">
              <div className="relative">
                <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" />
                <Input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={handleSearchKeyDown}
                  placeholder="Search settings..."
                  aria-label="Search settings"
                  className="h-8 bg-slate-900 border-slate-700 pl-8 pr-7 text-sm"
                />
                {query && (
                  <button
                    type="button"
                    aria-label="Clear search"
                    onClick={() => setQuery("")}
                    className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded p-0.5 text-slate-500 hover:text-white"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>
            </div>
            <ScrollArea className="flex-1 py-2">
              {query.trim() ? (
                <div className="flex flex-col gap-1 px-2 pb-2">
                  {results.length === 0 ? (
                    <p className="px-3 py-2 text-xs text-slate-500">
                      No matching settings.
                    </p>
                  ) : (
                    results.map((field) => (
                      <button
                        key={`${field.section}.${field.label}`}
                        onClick={() => jumpTo(field)}
                        className="flex flex-col items-start gap-0.5 rounded-lg px-3 py-2 text-left transition-colors hover:bg-slate-800/60"
                      >
                        <span className="text-sm text-slate-200">
                          {field.label}
                        </span>
                        <span className="text-[10px] uppercase tracking-wider text-slate-500">
                          {sectionLabel(field.section)}
                        </span>
                      </button>
                    ))
                  )}
                </div>
              ) : (
              <nav className="flex flex-col gap-3 px-2">
                {NAV_GROUPS.map((group) => (
                  <div key={group.label} className="flex flex-col gap-1">
                    <p className="px-3 pt-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                      {group.label}
                    </p>
                    {group.items.map(({ key, label, icon: Icon }) => (
                      <button
                        key={key}
                        onClick={() => selectSection(key)}
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
              )}
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
