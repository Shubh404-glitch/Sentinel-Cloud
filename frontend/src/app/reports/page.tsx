"use client";

import { useEffect, useState } from "react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { getProjects, Project } from "@/lib/projects";
import { getProjectReports, Report } from "@/lib/reports";

export default function ReportsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [reports, setReports] = useState<Report[]>([]);

  const [loadingProjects, setLoadingProjects] = useState(true);
  const [loadingReports, setLoadingReports] = useState(false);

  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadProjects() {
      try {
        setLoadingProjects(true);
        setError(null);

        const data = await getProjects();

        setProjects(data.items);

        if (data.items.length > 0) {
          setSelectedProjectId(data.items[0].id);
        }
      } catch (err) {
        console.error("Failed to load projects:", err);
        setError("Unable to load projects.");
      } finally {
        setLoadingProjects(false);
      }
    }

    loadProjects();
  }, []);

  useEffect(() => {
    if (!selectedProjectId) {
      setReports([]);
      return;
    }

    async function loadReports() {
      try {
        setLoadingReports(true);
        setError(null);

        const data = await getProjectReports(selectedProjectId);

        setReports(data.items);
      } catch (err) {
        console.error("Failed to load reports:", err);
        setError("Unable to load reports.");
      } finally {
        setLoadingReports(false);
      }
    }

    loadReports();
  }, [selectedProjectId]);

  return (
    <DashboardLayout>
      <div className="p-6">
        <div className="mb-6">
          <h1 className="text-2xl font-semibold text-zinc-900">
            Reports
          </h1>

          <p className="mt-2 text-sm text-zinc-600">
            Review scan reports and their processing status.
          </p>
        </div>

        {loadingProjects && (
          <div className="rounded-lg border border-zinc-200 bg-white p-6">
            <p className="text-sm text-zinc-600">
              Loading projects...
            </p>
          </div>
        )}

        {!loadingProjects && projects.length === 0 && (
          <div className="rounded-lg border border-zinc-200 bg-white p-6">
            <p className="text-sm text-zinc-600">
              No projects found.
            </p>
          </div>
        )}

        {!loadingProjects && projects.length > 0 && (
          <>
            <div className="mb-6 rounded-lg border border-zinc-200 bg-white p-6">
              <label
                htmlFor="project"
                className="block text-sm font-medium text-zinc-700"
              >
                Project
              </label>

              <select
                id="project"
                value={selectedProjectId}
                onChange={(event) =>
                  setSelectedProjectId(event.target.value)
                }
                className="mt-2 block w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 outline-none focus:border-zinc-500 focus:ring-1 focus:ring-zinc-500"
              >
                {projects.map((project) => (
                  <option key={project.id} value={project.id}>
                    {project.name}
                  </option>
                ))}
              </select>
            </div>

            {error && (
              <div className="mb-6 rounded-lg border border-red-200 bg-red-50 p-6">
                <p className="text-sm text-red-700">
                  {error}
                </p>
              </div>
            )}

            {!error && (
              <div className="overflow-hidden rounded-lg border border-zinc-200 bg-white">
                <div className="border-b border-zinc-200 px-6 py-4">
                  <h2 className="text-lg font-medium text-zinc-900">
                    Report List
                  </h2>

                  <p className="mt-1 text-sm text-zinc-500">
                    {loadingReports
                      ? "Loading reports..."
                      : `${reports.length} report${
                          reports.length !== 1 ? "s" : ""
                        }`}
                  </p>
                </div>

                {!loadingReports && reports.length === 0 ? (
                  <div className="px-6 py-12 text-center">
                    <p className="text-sm text-zinc-500">
                      No reports found for this project.
                    </p>
                  </div>
                ) : (
                  !loadingReports && (
                    <div className="overflow-x-auto">
                      <table className="min-w-full divide-y divide-zinc-200">
                        <thead className="bg-zinc-50">
                          <tr>
                            <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wide text-zinc-500">
                              Source
                            </th>

                            <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wide text-zinc-500">
                              Status
                            </th>

                            <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wide text-zinc-500">
                              Schema
                            </th>

                            <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wide text-zinc-500">
                              Raw Data
                            </th>

                            <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wide text-zinc-500">
                              Created
                            </th>
                          </tr>
                        </thead>

                        <tbody className="divide-y divide-zinc-200 bg-white">
                          {reports.map((report) => (
                            <tr
                              key={report.id}
                              className="hover:bg-zinc-50"
                            >
                              <td className="px-6 py-4">
                                <div className="font-medium text-zinc-900">
                                  {report.source_edition}
                                </div>

                                <div className="mt-1 text-xs text-zinc-500">
                                  {report.id}
                                </div>
                              </td>

                              <td className="whitespace-nowrap px-6 py-4">
                                <span className="rounded-full bg-zinc-100 px-3 py-1 text-xs font-medium capitalize text-zinc-700">
                                  {report.processing_status}
                                </span>
                              </td>

                              <td className="whitespace-nowrap px-6 py-4 text-sm text-zinc-600">
                                {report.schema_version}
                              </td>

                              <td className="whitespace-nowrap px-6 py-4">
                                {report.has_raw_blob ? (
                                  <span className="rounded-full bg-green-100 px-3 py-1 text-xs font-medium text-green-700">
                                    Available
                                  </span>
                                ) : (
                                  <span className="rounded-full bg-zinc-100 px-3 py-1 text-xs font-medium text-zinc-600">
                                    Not available
                                  </span>
                                )}
                              </td>

                              <td className="whitespace-nowrap px-6 py-4 text-sm text-zinc-600">
                                {new Date(
                                  report.created_at
                                ).toLocaleDateString()}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )
                )}
              </div>
            )}
          </>
        )}
      </div>
    </DashboardLayout>
  );
}
