/**
 * Header – top navigation bar.
 * Pure text, no icons. Includes a live backend-status indicator.
 */

import React, { useEffect, useState } from "react";
import api from "../services/api";

function StatusDot() {
  const [up, setUp] = useState(false);

  useEffect(() => {
    let mounted = true;
    const check = async () => {
      try {
        const r = await api.get("/health", { timeout: 3000 });
        if (mounted) setUp(r?.status === 200);
      } catch {
        if (mounted) setUp(false);
      }
    };
    check();
    const id = setInterval(check, 10_000);
    return () => { mounted = false; clearInterval(id); };
  }, []);

  return (
    <span
      className={`inline-block w-2 h-2 rounded-full mr-1.5 ${
        up ? "bg-green-500" : "bg-red-500"
      }`}
      title={up ? "Backend online" : "Backend offline"}
    />
  );
}

export default function Header() {
  return (
    <header className="bg-white border-b border-gray-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between h-14">
        <span className="text-lg font-bold text-gray-800 tracking-tight">
          Trading Bot
        </span>
        <span className="flex items-center text-xs text-gray-500">
          <StatusDot />
          Backend
        </span>
      </div>
    </header>
  );
}
