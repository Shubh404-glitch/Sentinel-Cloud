import { apiFetch } from "./api";

export interface Report {
  id: string;
  source_edition: string;
  schema_version: string;
  processing_status: string;
  processing_failure_reason: string | null;
  created_at: string;
  has_raw_blob: boolean;
}

export interface ReportsResponse {
  items: Report[];
  total: number;
  limit: number;
  offset: number;
}

export async function getProjectReports(
  projectId: string,
  options?: {
    limit?: number;
    offset?: number;
  }
): Promise<ReportsResponse> {
  const params = new URLSearchParams();

  params.set("limit", String(options?.limit ?? 100));
  params.set("offset", String(options?.offset ?? 0));

  return apiFetch(
    `/projects/${projectId}/reports?${params.toString()}`,
    {
      method: "GET",
    }
  );
}