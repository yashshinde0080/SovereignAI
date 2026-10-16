// Mirrors AGENT_TOOLS in backend/app/settings/schemas.py — the backend rejects
// any name outside that allowlist, so the two lists must stay in step.
//
// Nothing here executes. The chat path has no tool-calling loop yet, so every
// entry is surfaced as "not available yet" instead of pretending it runs.

export interface AgentTool {
  id: string;
  label: string;
  description: string;
  /** False until a backend executor exists for it. */
  available: boolean;
}

export const AGENT_TOOLS: AgentTool[] = [
  {
    id: 'read_project_files',
    label: 'Read project files',
    description: 'Read files from the permitted project directories.',
    available: false,
  },
  {
    id: 'search_docs',
    label: 'Search documentation',
    description: 'Search the indexed project documentation and RAG store.',
    available: false,
  },
  {
    id: 'analyze_code',
    label: 'Analyze code',
    description: 'Inspect source files and report structure or issues.',
    available: false,
  },
  {
    id: 'run_tests',
    label: 'Run approved tests',
    description: 'Run the project test suite and read the results.',
    available: false,
  },
  {
    id: 'system_info',
    label: 'System information',
    description: 'Read hardware, model, and runtime information.',
    available: false,
  },
];

export function toolLabel(id: string): string {
  return AGENT_TOOLS.find((t) => t.id === id)?.label ?? id;
}
