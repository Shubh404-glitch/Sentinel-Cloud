"use client";

import { useEffect, useState } from "react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { getProjects, Project } from "@/lib/projects";

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadProjects() {
      try {
        setLoading(true);
        setError(null);

        const data = await getProjects();

        setProjects(data.items);
      } catch (err) {
        console.error("Failed to load projects:", err);
        setError("Unable to load projects.");
      } finally {
        setLoading(false);
      }
    }

    loadProjects();
  }, []);

  return (
    <DashboardLayout>
      <div className="p-6">
        <div className="mb-6">
          <h1 className="text-2xl font-semibold text-zinc-900">
            Projects
          </h1>

          <p className="mt-2 text-sm text-zinc-600">
            Manage and monitor your SentinelScan projects.
          </p>
        </div>

        {loading && (
          <div className="rounded-lg border border-zinc-200 bg-white p-6">
            <p className="text-sm text-zinc-600">
              Loading projects...
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
                Project List
              </h2>

              <p className="mt-1 text-sm text-zinc-500">
                {projects.length} project
                {projects.length !== 1 ? "s" : ""}
              </p>
            </div>

            {projects.length === 0 ? (
              <div className="px-6 py-12 text-center">
                <p className="text-sm text-zinc-500">
                  No projects found.
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-zinc-200">
                  <thead className="bg-zinc-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wide text-zinc-500">
                        Project
                      </th>

                      <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wide text-zinc-500">
                        Criticality
                      </th>

                      <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wide text-zinc-500">
                        Created
                      </th>
                    </tr>
                  </thead>

                  <tbody className="divide-y divide-zinc-200 bg-white">
                    {projects.map((project) => (
                      <tr
                        key={project.id}
                        className="hover:bg-zinc-50"
                      >
                        <td className="whitespace-nowrap px-6 py-4">
                          <div className="font-medium text-zinc-900">
                            {project.name}
                          </div>

                          <div className="mt-1 text-xs text-zinc-500">
                            {project.id}
                          </div>
                        </td>

                        <td className="whitespace-nowrap px-6 py-4">
                          <span className="rounded-full bg-zinc-100 px-3 py-1 text-xs font-medium capitalize text-zinc-700">
                            {project.criticality}
                          </span>
                        </td>

                        <td className="whitespace-nowrap px-6 py-4 text-sm text-zinc-600">
                          {new Date(
                            project.created_at
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

