export interface Session {
  id: number
  title: string
  workspace: string | null
  created_at: number
  updated_at: number
}

export interface FileNode {
  name: string
  path: string
  type: "dir" | "file"
  children?: FileNode[]
}

export interface ToolMeta {
  name?: string
  args?: Record<string, unknown>
  ok?: boolean
  kind?: string
}

export interface Message {
  id: number
  session_id?: number
  role: "user" | "assistant" | "tool"
  content: string
  meta?: ToolMeta | null
  created_at: number
}

export interface Attachment {
  id: string
  name: string
  size: number
}

export interface Settings {
  provider: string
  model: string
  base_url: string
  api_key: string
  temperature: number
  max_steps: number
  disable_thinking: boolean
  auto_approve_commands: boolean
  allow_cloud_fallback: boolean
  allow_webchat_fallback: boolean
  learn_workflows: boolean
  browser_headless: boolean
  browser_cdp_port?: number
  webchat_site: string
  hard_base_url: string
  hard_model: string
  hard_api_key: string
  hard_fallback_site: string
  firecrawl_api_key: string
  github_token: string
  gateway_base_url: string
  gateway_api_key: string
  gateway: string
  keys?: Record<string, string>
  local_model_path: string
  policies?: Record<string, string>
  workspace: string
  auto_gateways?: string[]
  gateway_models?: Record<string, string>
  rubric_enabled?: boolean
  rubric_text?: string
  rubric_max_iterations?: number
  agents?: AgentProfile[]
  active_agent?: string
}

export interface AgentProfile {
  id: string
  name: string
  provider: string
  gateway?: string
  model: string
  base_url?: string
  api_key?: string
  disable_thinking?: boolean
}

export interface LocalModel {
  name: string
  path: string
  size_bytes: number
  modified: number
  active: boolean
  builtin: boolean
}

export interface CatalogModel {
  id: string
  name: string
  filename: string
  url: string
  size_bytes: number
  context: number
  description: string
  downloaded: boolean
}

export interface ModelsPayload {
  local: LocalModel[]
  catalog: CatalogModel[]
  download: { active?: boolean; filename?: string; downloaded?: number; total?: number; error?: string | null; done?: boolean }
  models_dir: string
  backend: {
    selected: "auto" | "vulkan" | "cpu" | string
    active: "vulkan" | "cpu" | string
    available: boolean
    executable: string
    gpu_layers: number
    context_size: number
  }
}

export interface Automation {
  id: string
  name: string
  prompt: string
  interval_minutes: number
  status: "active" | "cancelled" | string
  next_run?: number
  overdue?: boolean
  last_run_at?: number | null
  last_status?: string
  created_at?: number
}

export interface Mission {
  id: string
  name: string
  prompt: string
  session_id?: number | null
  status: "pinned"
  created_at?: number
}

export type ChatMode = "saved" | "auto" | "chatgpt" | "gemini"

export interface BrowserState {
  url: string
  title: string
  can_back: boolean
  can_forward: boolean
  headless?: boolean
  engine?: "chrome" | "chromium" | string
}

export interface BrowserPayload {
  state: BrowserState
  frame: string | null
}

export interface ToolRun {
  id: string
  name: string
  args: Record<string, unknown>
  argsText?: string
  status: "running" | "done"
  ok?: boolean
  result?: string
}

export interface ApprovalRequest {
  id: string
  command: string
}

export interface WorkspacePayload {
  path: string | null
  exists: boolean
  tree: FileNode[]
}

export type RightTab = "browser" | "screen" | "terminal" | "file" | "mission" | "earn" | "security"

export interface EarningOpportunity {
  id: string
  title: string
  category: string
  summary: string
  platforms: string[]
  startup_cost: number
  time_to_cash_days: number
  automation: number
  demand: number
  competition: number
  risk: number
  skills: string[]
  offer: string
  pricing: string
  first_steps: string[]
  tags: string[]
  score: number
  why: string
  launched?: boolean
  source?: string
  url?: string
}

export interface EarningTask {
  id: number
  venture_id: number
  phase: string
  role: string
  title: string
  detail: string
  acceptance: string
  priority: number
  estimate_min: number
  metric?: string | null
  status: "pending" | "done" | string
  draft?: string | null
  result?: string | null
  created_at: number
  completed_at?: number | null
}

export interface EarningVenture {
  id: number
  opportunity_id: string
  name: string
  mission: string
  currency: string
  status: string
  created_at: number
  updated_at: number
  opportunity: EarningOpportunity | null
  tasks: EarningTask[]
  income: Record<string, number>
  progress: { total: number; done: number; pending: number }
  existing?: boolean
}

export interface EarningAction {
  venture_id: number
  venture: string
  task_id: number
  title: string
  role: string
  phase: string
  priority: number
  estimate_min: number
  acceptance: string
  draft: string
}

export interface EarningLearning {
  id: number
  venture_id?: number | null
  lesson: string
  tags: string
  uses: number
  created_at: number
}

export interface EarningBrief {
  generated_at: number
  currency: string
  income: Record<string, number>
  actions: EarningAction[]
  lessons: EarningLearning[]
  ventures: Array<{ id: number; name: string; progress: { total: number; done: number; pending: number }; income: Record<string, number> }>
  guardrail: string
}

export interface EarningOverview {
  settings: {
    currency: string
    skills: string[]
    weekly_hours: number
    starting_capital: number
    autopilot: boolean
    country: string
  }
  currency: string
  income: Record<string, number>
  income_events: Array<{ id: number; amount: number; currency: string; source: string; notes: string; created_at: number }>
  active_ventures: EarningVenture[]
  ventures_count: number
  tasks_pending: number
  tasks_done: number
  best_opportunities: EarningOpportunity[]
  next_actions: Array<{ venture_id: number; venture: string; task_id: number; title: string; role: string; priority: number; estimate_min: number }>
  learning: EarningLearning[]
  categories: string[]
  autopilot: boolean
  guardrail: string
}

export interface ApprovalEvent {
  id: number
  session_id?: number | null
  tool: string
  action: string
  level: "safe" | "caution" | "dangerous" | string
  approved: number | boolean
  auto: number | boolean
  created_at: number
}

export interface EarningRadar {
  query: string
  opportunities: EarningOpportunity[]
  signals: Array<{ title: string; url: string; description: string }>
  signals_text: string
  live_search: boolean
  note: string
}

export interface SkillInfo {
  name: string
  description: string
  slug: string
  source: string
  size: number
}

export interface MCPToolInfo {
  name: string
  original: string
  description: string
}

export interface MCPServer {
  id: string
  name: string
  command: string
  args: string[]
  env?: Record<string, string>
  enabled: boolean
  status?: string
  error?: string | null
  tools?: MCPToolInfo[]
}

export interface MCPPreset {
  id: string
  name: string
  command: string
  args: string[]
  description: string
}

export interface OpenRouterModel {
  id: string
  name: string
  context_length: number
  tools: boolean
  vision: boolean
  recommended: boolean
}
