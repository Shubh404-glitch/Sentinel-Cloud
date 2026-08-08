import { apiFetch } from "./api";

export interface DashboardTimelineEvent {
  id: string;
  event_type: string;
  summary: string;
  asset_id: string;
  project_id: string;
  created_at: string;
}

export interface DashboardData {
  organization_score: {
    scope: string;
    score: number;
    contributing_factors: {
      method: string;
      final_score: number;
      child_scores: number[];
    };
    created_at: string;
  };
  project_count: number;
  asset_count: number;
  open_finding_count: number;
  risk_distribution: Record<string, number>;
  recent_timeline_events: DashboardTimelineEvent[];
}

export async function getDashboard(): Promise<DashboardData> {
  return apiFetch("/dashboard", {
    method: "GET",
  });
}