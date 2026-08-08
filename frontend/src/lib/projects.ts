import { apiFetch } from "./api";

export interface Project {
  id: string;
  name: string;
  criticality: string;
  created_at: string;
}

export interface ProjectsResponse {
  items: Project[];
  total: number;
  limit: number;
  offset: number;
}

export async function getProjects(
  options?: {
    limit?: number;
    offset?: number;
  }
): Promise<ProjectsResponse> {
  const params = new URLSearchParams();

  params.set("limit", String(options?.limit ?? 100));
  params.set("offset", String(options?.offset ?? 0));

  return apiFetch(`/projects?${params.toString()}`, {
    method: "GET",
  });
}