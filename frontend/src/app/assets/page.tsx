"use client";

import { useEffect, useState } from "react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { getProjectAssets, Asset } from "@/lib/assets";

const PROJECT_ID = "8228ec6e-fc01-48bb-b364-6a740b15083e";

export default function AssetsPage() {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadAssets() {
      try {
        setLoading(true);
        setError(null);

        const data = await getProjectAssets(PROJECT_ID);

        setAssets(data.items);
        setTotal(data.total);
      } catch (err) {
        console.error("Failed to load assets:", err);
        setError("Failed to load assets.");
      } finally {
        setLoading(false);
      }
    }

    loadAssets();
  }, []);

  return (
    <DashboardLayout>
      <div>
        <h1 className="text-3xl font-bold text-zinc-900">
          Assets
        </h1>

        <p className="mt-2 text-zinc-600">
          Assets discovered and monitored by SentinelScan.
        </p>

        <div className="mt-8 rounded-xl bg-white p-6 shadow">
          <h2 className="text-lg font-semibold text-zinc-900">
            Project Assets
          </h2>

          <p className="mt-1 text-sm text-zinc-500">
            {total} asset{total === 1 ? "" : "s"} found
          </p>

          {loading && (
            <p className="mt-6 text-zinc-500">
              Loading assets...
            </p>
          )}

          {error && (
            <p className="mt-6 text-red-600">
              {error}
            </p>
          )}

          {!loading && !error && assets.length === 0 && (
            <p className="mt-6 text-zinc-500">
              No assets found.
            </p>
          )}

          {!loading && !error && assets.length > 0 && (
            <div className="mt-6 overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-zinc-200 text-sm text-zinc-500">
                    <th className="px-4 py-3 font-medium">
                      Asset
                    </th>

                    <th className="px-4 py-3 font-medium">
                      Score
                    </th>

                    <th className="px-4 py-3 font-medium">
                      Knowledge
                    </th>

                    <th className="px-4 py-3 font-medium">
                      Tags
                    </th>
                  </tr>
                </thead>

                <tbody>
                  {assets.map((asset) => (
                    <tr
                      key={asset.id}
                      className="border-b border-zinc-100 last:border-0"
                    >
                      <td className="px-4 py-4">
                        <p className="font-medium text-zinc-900">
                          {asset.display_name || asset.identifier}
                        </p>

                        {asset.display_name && (
                          <p className="mt-1 text-sm text-zinc-500">
                            {asset.identifier}
                          </p>
                        )}
                      </td>

                      <td className="px-4 py-4 font-semibold text-zinc-900">
                        {asset.current_score}
                      </td>

                      <td className="px-4 py-4 text-sm text-zinc-600">
                        {asset.knowledge_depth_label}
                      </td>

                      <td className="px-4 py-4">
                        {asset.tags.length > 0 ? (
                          <div className="flex flex-wrap gap-2">
                            {asset.tags.map((tag) => (
                              <span
                                key={tag}
                                className="rounded-full bg-zinc-100 px-2 py-1 text-xs text-zinc-700"
                              >
                                {tag}
                              </span>
                            ))}
                          </div>
                        ) : (
                          <span className="text-sm text-zinc-400">
                            No tags
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}