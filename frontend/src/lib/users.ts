import { apiFetch } from "./api";

export interface User {
  id: string;
  email: string;
  display_name: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

export interface UsersResponse {
  items: User[];
  total: number;
  limit: number;
  offset: number;
}

export async function getUsers(
  options?: {
    limit?: number;
    offset?: number;
  }
): Promise<UsersResponse> {
  const params = new URLSearchParams();

  params.set("limit", String(options?.limit ?? 100));
  params.set("offset", String(options?.offset ?? 0));

  return apiFetch(`/users?${params.toString()}`, {
    method: "GET",
  });
}