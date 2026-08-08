export default function Home() {
  return (
    <main className="min-h-screen bg-zinc-950 text-white p-8">
      <h1 className="text-4xl font-bold">
        Sentinel Cloud
      </h1>

      <p className="mt-2 text-zinc-400">
        Security Operations Dashboard
      </p>

      <div className="mt-8 grid gap-6 md:grid-cols-3">
        <div className="rounded-xl bg-zinc-900 p-6">
          <h2 className="text-xl font-semibold">
            Assets
          </h2>
          <p className="mt-2 text-3xl font-bold">
            0
          </p>
        </div>

        <div className="rounded-xl bg-zinc-900 p-6">
          <h2 className="text-xl font-semibold">
            Reports
          </h2>
          <p className="mt-2 text-3xl font-bold">
            0
          </p>
        </div>

        <div className="rounded-xl bg-zinc-900 p-6">
          <h2 className="text-xl font-semibold">
            Risk Score
          </h2>
          <p className="mt-2 text-3xl font-bold">
            --
          </p>
        </div>
      </div>
    </main>
  );
}