export const API_URL =
  (import.meta.env.VITE_API_URL as string | undefined) ?? "http://localhost:8000";

export type User = { id: string; name: string; email: string };

export type ProjectSummary = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  latest_version: number;
};

export type VersionSummary = {
  number: number;
  prompt: string;
  fix_rounds: number;
  created_at: string;
};

export type ProjectDetail = {
  id: string;
  title: string;
  created_at: string;
  versions: VersionSummary[];
};

export type VersionDetail = {
  number: number;
  prompt: string;
  fix_rounds: number;
  created_at: string;
  files: Record<string, string>;
};

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function readError(response: Response): Promise<string> {
  try {
    const data = await response.json();
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail) && data.detail[0]?.msg) {
      return String(data.detail[0].msg).replace(/^Value error, /, "");
    }
  } catch {
    // The body wasn't JSON; fall through to the generic message.
  }
  return "Something went wrong. Try again.";
}

type RequestOptions = { method?: string; token?: string; body?: unknown };

async function request<T>(
  path: string,
  { method = "GET", token, body }: RequestOptions = {},
): Promise<T> {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;

  const response = await fetch(`${API_URL}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (!response.ok) throw new ApiError(await readError(response), response.status);
  if (response.status === 204) return undefined as T;

  return (await response.json()) as T;
}

export const signUp = (name: string, email: string) =>
  request<{ user: User; token: string }>("/api/users", {
    method: "POST",
    body: { name, email },
  });

export const getMe = (token: string) => request<User>("/api/me", { token });

export const listProjects = (token: string) =>
  request<ProjectSummary[]>("/api/projects", { token });

export const getProject = (token: string, projectId: string) =>
  request<ProjectDetail>(`/api/projects/${projectId}`, { token });

export const getVersion = (token: string, projectId: string, number: number) =>
  request<VersionDetail>(`/api/projects/${projectId}/versions/${number}`, { token });

export const restoreVersion = (token: string, projectId: string, number: number) =>
  request<{ project_id: string; version: number }>(
    `/api/projects/${projectId}/versions/${number}/restore`,
    { method: "POST", token },
  );

export const deleteProject = (token: string, projectId: string) =>
  request<void>(`/api/projects/${projectId}`, { method: "DELETE", token });

export const fileUrl = (projectId: string, version: number, filename: string) =>
  `${API_URL}/api/projects/${projectId}/versions/${version}/files/${filename}`;


export type RunStep = {
  step: string;
  seconds: number;
  prompt_tokens: number;
  completion_tokens: number;
  llm_calls: number;
  waited: number;
};

export type RunSummary = {
  id: number;
  version: number | null;
  kind: "build" | "edit";
  prompt: string;
  status: "passed" | "failed";
  error: string | null;
  duration_seconds: number;
  prompt_tokens: number;
  completion_tokens: number;
  llm_calls: number;
  wait_seconds: number;
  fix_rounds: number;
  steps: RunStep[];
  created_at: string;
};

export const listRuns = (token: string, projectId: string) =>
  request<RunSummary[]>(`/api/projects/${projectId}/runs`, { token });