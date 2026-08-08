"use client";

import { useEffect, useState } from "react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { getUsers, User } from "@/lib/users";

export default function UsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadUsers() {
      try {
        setLoading(true);
        setError(null);

        const data = await getUsers();

        setUsers(data.items);
      } catch (err) {
        console.error("Failed to load users:", err);
        setError("Unable to load users.");
      } finally {
        setLoading(false);
      }
    }

    loadUsers();
  }, []);

  return (
    <DashboardLayout>
      <div className="p-6">
        <div className="mb-6">
          <h1 className="text-2xl font-semibold text-zinc-900">
            Users
          </h1>

          <p className="mt-2 text-sm text-zinc-600">
            Manage users and access within your organization.
          </p>
        </div>

        {loading && (
          <div className="rounded-lg border border-zinc-200 bg-white p-6">
            <p className="text-sm text-zinc-600">
              Loading users...
            </p>
          </div>
        )}

        {error && !loading && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-6">
            <p className="text-sm text-red-700">
              {error}
            </p>
          </div>
        )}

        {!loading && !error && (
          <div className="overflow-hidden rounded-lg border border-zinc-200 bg-white">
            <div className="border-b border-zinc-200 px-6 py-4">
              <h2 className="text-lg font-medium text-zinc-900">
                User List
              </h2>

              <p className="mt-1 text-sm text-zinc-500">
                {users.length} user
                {users.length !== 1 ? "s" : ""}
              </p>
            </div>

            {users.length === 0 ? (
              <div className="px-6 py-12 text-center">
                <p className="text-sm text-zinc-500">
                  No users found.
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-zinc-200">
                  <thead className="bg-zinc-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wide text-zinc-500">
                        User
                      </th>

                      <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wide text-zinc-500">
                        Role
                      </th>

                      <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wide text-zinc-500">
                        Status
                      </th>

                      <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wide text-zinc-500">
                        Created
                      </th>
                    </tr>
                  </thead>

                  <tbody className="divide-y divide-zinc-200 bg-white">
                    {users.map((user) => (
                      <tr
                        key={user.id}
                        className="hover:bg-zinc-50"
                      >
                        <td className="px-6 py-4">
                          <div className="font-medium text-zinc-900">
                            {user.display_name}
                          </div>

                          <div className="mt-1 text-sm text-zinc-500">
                            {user.email}
                          </div>

                          <div className="mt-1 text-xs text-zinc-400">
                            {user.id}
                          </div>
                        </td>

                        <td className="whitespace-nowrap px-6 py-4">
                          <span className="rounded-full bg-zinc-100 px-3 py-1 text-xs font-medium capitalize text-zinc-700">
                            {user.role}
                          </span>
                        </td>

                        <td className="whitespace-nowrap px-6 py-4">
                          {user.is_active ? (
                            <span className="rounded-full bg-green-100 px-3 py-1 text-xs font-medium text-green-700">
                              Active
                            </span>
                          ) : (
                            <span className="rounded-full bg-red-100 px-3 py-1 text-xs font-medium text-red-700">
                              Inactive
                            </span>
                          )}
                        </td>

                        <td className="whitespace-nowrap px-6 py-4 text-sm text-zinc-600">
                          {new Date(
                            user.created_at
                          ).toLocaleDateString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}

