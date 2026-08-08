"use client";

import { useEffect, useState } from "react";

export default function Home() {
  const [healthStatus, setHealthStatus] = useState<string>("Checking...");

  useEffect(() => {
    fetch("http://localhost:8000/health")
      .then((res) => res.json())
      .then((data) => {
        setHealthStatus(data.status === "ok" ? "Backend Connected (OK)" : "Backend Error");
      })
      .catch((err) => {
        setHealthStatus("Backend Disconnected");
      });
  }, []);

  return (
    <div className="flex flex-col flex-1 items-center justify-center min-h-screen bg-zinc-50 font-sans dark:bg-black">
      <main className="flex flex-1 w-full max-w-3xl flex-col items-center justify-center text-center py-32 px-16 sm:items-start sm:text-left">
        <h1 className="text-4xl font-bold tracking-tight text-black dark:text-white mb-8">
          Klarnova Platform
        </h1>
        <div className="flex flex-col items-center gap-4 text-center sm:items-start sm:text-left">
          <p className="text-xl text-zinc-600 dark:text-zinc-400">
            AIOps Backend Status:
          </p>
          <div className={`px-4 py-2 rounded-full font-semibold text-sm ${healthStatus.includes("OK") ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
            {healthStatus}
          </div>
        </div>
      </main>
    </div>
  );
}
