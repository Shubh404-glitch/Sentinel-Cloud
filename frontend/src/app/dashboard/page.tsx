"use client";

import { useEffect, useState } from "react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { getDashboard, DashboardData } from "@/lib/dashboard";

export default function DashboardPage() {
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);

  useEffect(() => {
    async function loadDashboard() {
      try {
        const data = await getDashboard();
        setDashboard(data);
      } catch (error) {
        console.error("Failed to load dashboard:", error);
      }
    }

    loadDashboard();
  }, []);

  return (
    <DashboardLayout>
      <h1 className="text-4xl font-bold text-zinc-900">
        Dashboard
      </h1>

      <p className="mt-2 text-zinc-600">
        Security overview and system status
      </p>

      <div className="mt-8 grid gap-6 md:grid-cols-3">
        <div className="rounded-xl bg-white p-6 shadow">
          <h2 className="font-semibold text-zinc-900">
            Assets
          </h2>

          <p className="mt-2 text-3xl font-bold text-zinc-900">
            {dashboard ? dashboard.asset_count : "..."}
          </p>
        </div>

        <div className="rounded-xl bg-white p-6 shadow">
          <h2 className="font-semibold text-zinc-900">
            Projects
          </h2>

          <p className="mt-2 text-3xl font-bold text-zinc-900">
            {dashboard ? dashboard.project_count : "..."}
          </p>
        </div>

        <div className="rounded-xl bg-white p-6 shadow">
          <h2 className="font-semibold text-zinc-900">
            Risk Score
          </h2>

          <p className="mt-2 text-3xl font-bold text-zinc-900">
            {dashboard
              ? dashboard.organization_score.score
              : "..."}
          </p>
        </div>

        <div className="rounded-xl bg-white p-6 shadow">
          <h2 className="font-semibold text-zinc-900">
            Open Findings
          </h2>

          <p className="mt-2 text-3xl font-bold text-zinc-900">
            {dashboard
              ? dashboard.open_finding_count
              : "..."}
          </p>
        </div>

        <div className="rounded-xl bg-white p-6 shadow md:col-span-2">
          <h2 className="font-semibold text-zinc-900">
            Risk Distribution
          </h2>

          {dashboard ? (
            <div className="mt-4 space-y-2">
              {Object.entries(dashboard.risk_distribution).map(
                ([severity, count]) => (
                  <div
                    key={severity}
                    className="flex items-center justify-between rounded-lg bg-zinc-50 px-4 py-3"
                  >
                    <span className="capitalize text-zinc-700">
                      {severity}
                    </span>

                    <span className="font-bold text-zinc-900">
                      {count}
                    </span>
                  </div>
                )
              )}
            </div>
          ) : (
            <p className="mt-4 text-zinc-500">
              ...
            </p>
          )}
        </div>
      </div>

      <div className="mt-8 rounded-xl bg-white p-6 shadow">
        <h2 className="text-xl font-semibold text-zinc-900">
          Recent Activity
        </h2>

        {dashboard ? (
          <div className="mt-4 space-y-4">
            {dashboard.recent_timeline_events.map((event) => (
              <div
                key={event.id}
                className="border-b border-zinc-100 pb-4 last:border-b-0 last:pb-0"
              >
                <div className="flex items-center justify-between gap-4">
                  <span className="font-medium capitalize text-zinc-900">
                    {event.event_type.replaceAll("_", " ")}
                  </span>

                  <span className="text-sm text-zinc-500">
                    {new Date(event.created_at).toLocaleString()}
                  </span>
                </div>

                <p className="mt-1 text-zinc-600">
                  {event.summary}
                </p>
              </div>
            ))}
          </div>
        ) : (
          <p className="mt-4 text-zinc-500">
            ...
          </p>
        )}
      </div>
    </DashboardLayout>
  );
}