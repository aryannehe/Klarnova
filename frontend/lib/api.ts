export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

const TOKEN_KEY = "klarnova_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) window.localStorage.setItem(TOKEN_KEY, token);
  else window.localStorage.removeItem(TOKEN_KEY);
}

export interface User {
  username: string;
  role: string;
}

export interface Incident {
  id: number;
  alert_name: string;
  severity: string;
  priority: string;
  status: string;
  namespace: string;
  resource_kind: string;
  resource_name: string;
  description: string | null;
  labels: Record<string, string>;
  created_at: string;
  detected_at: string | null;
  remediated_at: string | null;
  root_cause: string | null;
  confidence_score: number | null;
}

export interface AgentRun {
  agent: string;
  status: string;
  inputs: unknown;
  outputs: unknown;
}

export interface Remediation {
  action: string;
  category: string;
  outcome: string;
  time_to_resolve: number | null;
}

export interface Trace {
  incident: Incident;
  requires_approval: boolean;
  selected_action: {
    action_type: string | null;
    target_resource: string | null;
    namespace: string | null;
    source: string;
  } | null;
  agent_runs: AgentRun[];
  remediations: Remediation[];
}

export interface PendingApproval {
  incident_id: number;
  alert_name: string;
  severity: string;
  priority: string;
  status: string;
  namespace: string;
  resource_kind: string;
  resource_name: string;
  root_cause: string | null;
  confidence_score: number | null;
  detected_at: string | null;
  selected_action: {
    action_type: string | null;
    target_resource: string | null;
    namespace: string | null;
    source: string;
  };
}

export interface Stats {
  total: number;
  resolved: number;
  escalated: number;
  open: number;
  resolved_rate: number;
  by_status: Record<string, number>;
  by_severity: Record<string, number>;
  avg_mttd_seconds: number | null;
  avg_mttr_seconds: number | null;
  last_7_days: { date: string; count: number }[];
}

export interface ApprovalBody {
  incident_id: string;
  action_type: string;
  approved: boolean;
  target_resource?: string | null;
  namespace?: string | null;
}

export interface PolicyRules {
  whitelist: string[];
  severity_order: Record<string, number>;
  confidence_threshold: number;
  actions: Record<string, Record<string, string>>;
}

export interface PolicyUpdateBody {
  action: string;
  severity: string;
  execution_mode: "auto" | "require_approval";
}

export interface KnowledgeSourceEntry {
  id: string | null;
  title: string;
  source: string;
}

export interface KnowledgeSources {
  path: string;
  collections: Record<string, KnowledgeSourceEntry[]>;
}

export interface KnowledgeDoc {
  id: number;
  source_url: string;
  doc_type: string;
  content_hash: string;
  last_ingested: string | null;
}

export interface KnowledgeDocs {
  docs: KnowledgeDoc[];
  count: number;
  collections: Record<string, number>;
}

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const hasBody = init.body != null;
  if (hasBody && !(init.body instanceof URLSearchParams) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, `Cannot reach backend at ${API_BASE}`);
  }

  if (res.status === 401) {
    setToken(null);
    if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
      window.dispatchEvent(new Event("klarnova:unauthorized"));
    }
  }

  if (!res.ok) {
    let detail: unknown = res.statusText;
    try {
      const body = await res.json();
      detail = (body as { detail?: unknown }).detail ?? detail;
    } catch {
      // keep statusText fallback
    }
    throw new ApiError(
      res.status,
      typeof detail === "string" ? detail : JSON.stringify(detail)
    );
  }
  return (await res.json()) as T;
}

export function login(username: string, password: string): Promise<{ access_token: string }> {
  return request("/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ username, password }),
  });
}

export const api = {
  me: () => request<User>("/v1/auth/me"),
  incidents: (status?: string, limit = 200) => {
    const params = new URLSearchParams({ limit: String(limit) });
    if (status) params.set("status", status);
    return request<Incident[]>(`/v1/incidents?${params.toString()}`);
  },
  incident: (id: string | number) => request<Incident>(`/v1/incidents/${id}`),
  trace: (id: string | number) => request<Trace>(`/v1/incidents/${id}/trace`),
  stats: () => request<Stats>("/v1/incidents/stats"),
  pending: () => request<{ pending: PendingApproval[] }>("/v1/actions/pending"),
  approve: (body: ApprovalBody) =>
    request<{ status: string }>("/v1/actions/approve", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  pods: (namespace = "sock-shop") =>
    request<{ pods: string[] }>(
      `/v1/kubernetes/pods?namespace=${encodeURIComponent(namespace)}`
    ),
  policy: () => request<PolicyRules>("/v1/config/policy"),
  updatePolicyRule: (body: PolicyUpdateBody) =>
    request<PolicyRules>("/v1/config/policy/rules", {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  knowledgeSources: () => request<KnowledgeSources>("/v1/config/knowledge/sources"),
  refreshKnowledge: () =>
    request<{ added: number }>("/v1/config/knowledge/refresh", { method: "POST" }),
  knowledgeDocs: () => request<KnowledgeDocs>("/v1/config/knowledge/docs"),
};
