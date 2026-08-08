"use client";

import DashboardLayout from "@/components/layout/DashboardLayout";

export default function SettingsPage() {
  return (
    <DashboardLayout>
      <div className="p-6">
        <div className="mb-6">
          <h1 className="text-2xl font-semibold text-zinc-900">
            Settings
          </h1>

          <p className="mt-2 text-sm text-zinc-600">
            Manage your SentinelScan Cloud preferences and account settings.
          </p>
        </div>

        <div className="space-y-6">
          {/* General */}
          <section className="rounded-lg border border-zinc-200 bg-white">
            <div className="border-b border-zinc-200 px-6 py-4">
              <h2 className="text-lg font-medium text-zinc-900">
                General
              </h2>

              <p className="mt-1 text-sm text-zinc-500">
                Basic organization and account information.
              </p>
            </div>

            <div className="grid gap-6 px-6 py-6 md:grid-cols-2">
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                  Organization
                </p>
                <p className="mt-1 text-sm font-medium text-zinc-900">
                  SentinelScan Organization
                </p>
                <p className="mt-1 text-xs text-zinc-500">
                  Current organization associated with this account.
                </p>
              </div>

              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                  Account
                </p>
                <p className="mt-1 text-sm font-medium text-zinc-900">
                  Administrator
                </p>
                <p className="mt-1 text-xs text-zinc-500">
                  Current authenticated user.
                </p>
              </div>

              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                  Email
                </p>
                <p className="mt-1 text-sm font-medium text-zinc-900">
                  admin@sentinelscan.local
                </p>
                <p className="mt-1 text-xs text-zinc-500">
                  Account email address.
                </p>
              </div>

              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                  Role
                </p>
                <p className="mt-1 text-sm font-medium text-zinc-900">
                  Administrator
                </p>
                <p className="mt-1 text-xs text-zinc-500">
                  Full administrative access within the organization.
                </p>
              </div>
            </div>
          </section>

          {/* Security */}
          <section className="rounded-lg border border-zinc-200 bg-white">
            <div className="border-b border-zinc-200 px-6 py-4">
              <h2 className="text-lg font-medium text-zinc-900">
                Security
              </h2>

              <p className="mt-1 text-sm text-zinc-500">
                Account security and authentication information.
              </p>
            </div>

            <div className="divide-y divide-zinc-200">
              <div className="flex items-center justify-between px-6 py-5">
                <div>
                  <p className="text-sm font-medium text-zinc-900">
                    Authentication
                  </p>
                  <p className="mt-1 text-sm text-zinc-500">
                    JWT-based authentication is enabled.
                  </p>
                </div>

                <span className="rounded-full bg-green-100 px-3 py-1 text-xs font-medium text-green-700">
                  Active
                </span>
              </div>

              <div className="flex items-center justify-between px-6 py-5">
                <div>
                  <p className="text-sm font-medium text-zinc-900">
                    Access Tokens
                  </p>
                  <p className="mt-1 text-sm text-zinc-500">
                    Access tokens are used to authorize protected API requests.
                  </p>
                </div>

                <span className="rounded-full bg-green-100 px-3 py-1 text-xs font-medium text-green-700">
                  Enabled
                </span>
              </div>

              <div className="flex items-center justify-between px-6 py-5">
                <div>
                  <p className="text-sm font-medium text-zinc-900">
                    Refresh Tokens
                  </p>
                  <p className="mt-1 text-sm text-zinc-500">
                    Refresh tokens support continued authenticated sessions.
                  </p>
                </div>

                <span className="rounded-full bg-green-100 px-3 py-1 text-xs font-medium text-green-700">
                  Enabled
                </span>
              </div>

              <div className="flex items-center justify-between px-6 py-5">
                <div>
                  <p className="text-sm font-medium text-zinc-900">
                    Protected Routes
                  </p>
                  <p className="mt-1 text-sm text-zinc-500">
                    Protected application routes require authentication.
                  </p>
                </div>

                <span className="rounded-full bg-green-100 px-3 py-1 text-xs font-medium text-green-700">
                  Active
                </span>
              </div>

              <div className="flex items-center justify-between px-6 py-5">
                <div>
                  <p className="text-sm font-medium text-zinc-900">
                    Session Management
                  </p>
                  <p className="mt-1 text-sm text-zinc-500">
                    Access and refresh tokens are managed automatically.
                  </p>
                </div>

                <span className="rounded-full bg-green-100 px-3 py-1 text-xs font-medium text-green-700">
                  Active
                </span>
              </div>
            </div>
          </section>

          {/* Application */}
          <section className="rounded-lg border border-zinc-200 bg-white">
            <div className="border-b border-zinc-200 px-6 py-4">
              <h2 className="text-lg font-medium text-zinc-900">
                Application
              </h2>

              <p className="mt-1 text-sm text-zinc-500">
                SentinelScan Cloud application information.
              </p>
            </div>

            <div className="grid gap-6 px-6 py-6 md:grid-cols-2">
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                  Application
                </p>
                <p className="mt-1 text-sm font-medium text-zinc-900">
                  SentinelScan Cloud
                </p>
              </div>

              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                  Version
                </p>
                <p className="mt-1 text-sm font-medium text-zinc-900">
                  V1.0
                </p>
              </div>

              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                  Edition
                </p>
                <p className="mt-1 text-sm font-medium text-zinc-900">
                  Cloud
                </p>
              </div>

              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                  Notifications
                </p>
                <p className="mt-1 text-sm font-medium text-zinc-900">
                  Coming soon
                </p>
                <p className="mt-1 text-xs text-zinc-500">
                  Notification features will be available in a future update.
                </p>
              </div>
            </div>
          </section>
        </div>
      </div>
    </DashboardLayout>
  );
}