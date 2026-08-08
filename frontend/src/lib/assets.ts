import { apiFetch } from "./api";

export interface Asset {
  id: string;
  identifier: string;
  display_name: string | null;
  tags: string[];
  current_score: number;
  knowledge_depth_label: string;
}

export interface AssetsResponse {
  items: Asset[];
  total: number;
  limit: number;
  offset: number;
}

export async function getProjectAssets(
  projectId: string,
  options?: {
    identifier_contains?: string;
    limit?: number;
    offset?: number;
  }
): Promise<AssetsResponse> {
  const params = new URLSearchParams();

  params.set("limit", String(options?.limit ?? 100));
  params.set("offset", String(options?.offset ?? 0));

  if (options?.identifier_contains) {
    params.set(
      "identifier_contains",
      options.identifier_contains
    );
  }

  return apiFetch(
    `/projects/${projectId}/assets?${params.toString()}`,
    {
      method: "GET",
    }
  );
}