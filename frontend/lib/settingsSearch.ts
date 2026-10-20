/**
 * Static index of Settings dialog fields.
 *
 * Kept in sync by hand with the section components. `label` must match the
 * visible <Label> text exactly — the dialog locates the rendered control by
 * matching that text, so no per-field anchor ids are needed.
 */

export interface SettingField {
  section: string;
  label: string;
  /** Extra words that should also match this field (aliases). */
  keywords?: string;
}

export const SETTINGS_FIELDS: SettingField[] = [
  // General
  { section: "general", label: "Temperature", keywords: "sampling creativity random" },
  { section: "general", label: "Top P", keywords: "sampling nucleus probability" },
  { section: "general", label: "Max Tokens", keywords: "length reply cap" },
  { section: "general", label: "Theme", keywords: "dark light appearance color" },
  { section: "general", label: "Language", keywords: "locale translation" },
  { section: "general", label: "Font Size", keywords: "text scale zoom accessibility" },
  { section: "general", label: "Default Mode", keywords: "engine fullram layerstream cloud auto" },
  { section: "general", label: "Max Context Length", keywords: "context window tokens" },
  { section: "general", label: "Startup Model", keywords: "model autoload boot" },
  { section: "general", label: "Auto-start backend", keywords: "server boot" },
  { section: "general", label: "Minimize to tray", keywords: "tray background" },
  { section: "general", label: "Show status bar", keywords: "metrics statusbar" },
  { section: "general", label: "Enable notifications", keywords: "alerts desktop" },
  { section: "general", label: "Stream responses", keywords: "streaming tokens" },
  { section: "general", label: "Show token speed", keywords: "tokens per second tok/s" },
  { section: "general", label: "Send on Enter", keywords: "keyboard submit" },
  { section: "general", label: "Enable sounds", keywords: "audio chime notification" },
  { section: "general", label: "Auto-save sessions", keywords: "history save" },

  // Project
  { section: "project", label: "Project Name" },
  { section: "project", label: "Version" },
  { section: "project", label: "Environment", keywords: "development production" },
  { section: "project", label: "Description" },
  { section: "project", label: "Author / Organization" },
  { section: "project", label: "API Endpoint", keywords: "url backend" },
  { section: "project", label: "GitHub Repository", keywords: "repo link" },
  { section: "project", label: "Documentation URL", keywords: "docs link" },

  // Personalization
  { section: "personalization", label: "Style", keywords: "tone base style" },
  { section: "personalization", label: "Characteristics", keywords: "personality persona" },
  { section: "personalization", label: "Headers & Lists", keywords: "format markdown" },
  { section: "personalization", label: "Response Length" },
  { section: "personalization", label: "Preferred Name", keywords: "name address you" },
  { section: "personalization", label: "Profession", keywords: "job occupation" },
  { section: "personalization", label: "Interests", keywords: "hobbies" },
  { section: "personalization", label: "Context About You", keywords: "user context background" },
  { section: "personalization", label: "Custom Instructions", keywords: "system prompt" },

  // Data Controls
  { section: "data_controls", label: "Save chat history", keywords: "storage" },
  { section: "data_controls", label: "Encrypt local data", keywords: "aes encryption privacy" },
  { section: "data_controls", label: "Auto-delete old sessions", keywords: "sweep cleanup" },
  { section: "data_controls", label: "Clear data on exit", keywords: "wipe delete" },
  { section: "data_controls", label: "Data Retention", keywords: "retention period days" },
  { section: "data_controls", label: "Allow model training", keywords: "privacy telemetry" },
  { section: "data_controls", label: "Log API requests", keywords: "logging debug" },
  { section: "data_controls", label: "Export Format", keywords: "json csv markdown" },

  // Security
  { section: "security", label: "Require password", keywords: "lock access" },
  { section: "security", label: "Session timeout (minutes)", keywords: "idle lock" },
  { section: "security", label: "Bind to localhost only", keywords: "network lan bind" },
  { section: "security", label: "API Token", keywords: "bearer auth key" },
  { section: "security", label: "API Port", keywords: "port bind" },
  { section: "security", label: "Enable CORS", keywords: "cross origin" },
  { section: "security", label: "Allowed Origins", keywords: "cors origin" },
  { section: "security", label: "Encrypt models at rest", keywords: "encryption aes" },
  { section: "security", label: "Audit logging", keywords: "audit trail" },
  { section: "security", label: "Disable external plugins", keywords: "plugins sandbox" },
  { section: "security", label: "Max concurrent requests", keywords: "concurrency queue" },

  // Parental Controls
  { section: "parental_controls", label: "Enable Parental Controls", keywords: "kids safety" },
  { section: "parental_controls", label: "Require PIN for settings", keywords: "pin lock" },
  { section: "parental_controls", label: "Content filter level", keywords: "filter strictness" },
  { section: "parental_controls", label: "Block explicit content", keywords: "nsfw adult" },
  { section: "parental_controls", label: "Restricted Topics", keywords: "block topics" },
  { section: "parental_controls", label: "Max session duration", keywords: "time limit" },
  { section: "parental_controls", label: "Disable custom instructions", keywords: "prompt lock" },
  { section: "parental_controls", label: "Activity log", keywords: "monitor review" },
  { section: "parental_controls", label: "Allowed Models (empty = all)", keywords: "whitelist models" },
];

/**
 * Ranked, case-insensitive substring search over label + keywords.
 * Prefix matches on the label rank before mid-string matches.
 */
export function searchSettings(query: string): SettingField[] {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  const scored: { field: SettingField; score: number }[] = [];
  for (const field of SETTINGS_FIELDS) {
    const label = field.label.toLowerCase();
    const hay = `${label} ${field.keywords ?? ""}`;
    if (!hay.includes(q)) continue;
    const score = label.startsWith(q) ? 0 : label.includes(q) ? 1 : 2;
    scored.push({ field, score });
  }
  scored.sort(
    (a, b) =>
      a.score - b.score ||
      SETTINGS_FIELDS.indexOf(a.field) - SETTINGS_FIELDS.indexOf(b.field)
  );
  return scored.map((s) => s.field);
}
