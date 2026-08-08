"use client";

import { useRouter } from "next/navigation";
import { logout } from "@/lib/auth";

export default function Navbar() {
  const router = useRouter();

  async function handleLogout() {
    await logout();
    router.push("/login");
  }

  return (
    <header className="flex items-center justify-between border-b border-zinc-200 bg-white px-6 py-4">
      <div className="text-lg font-semibold text-zinc-900">
        SentinelScan Cloud
      </div>

      <div className="flex items-center gap-4">
        <div className="relative group">
          <button
            type="button"
            className="rounded-lg border px-4 py-2 text-sm text-zinc-700 hover:bg-zinc-100"
          >
            Notifications
          </button>

          <div className="pointer-events-none absolute right-0 top-full z-50 mt-2 w-72 rounded-lg border border-zinc-200 bg-white p-3 text-sm text-zinc-600 opacity-0 shadow-lg transition-opacity group-hover:opacity-100">
            <p className="font-medium text-zinc-900">
              Coming soon
            </p>
            <p className="mt-1 text-xs text-zinc-500">
              Notifications will be available in a future update.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-zinc-300 font-semibold text-zinc-900">
            A
          </div>

          <div>
            <p className="text-sm font-medium text-zinc-900">
              Administrator
            </p>
            <p className="text-xs text-zinc-500">
              admin@sentinelscan.local
            </p>
          </div>

          <button
            onClick={handleLogout}
            className="rounded-lg border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100"
          >
            Logout
          </button>
        </div>
      </div>
    </header>
  );
}