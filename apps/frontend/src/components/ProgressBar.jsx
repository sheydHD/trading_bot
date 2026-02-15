/**
 * ProgressBar – shows analysis progress while a run is in-flight.
 *
 * Pure presentational (View layer). No icons.
 */

import React from "react";
import { elapsed } from "../utils/format";

export default function ProgressBar({ step, totalSteps, stepName, elapsedMs }) {
  const pct = totalSteps > 0 ? Math.round((step / totalSteps) * 100) : 0;

  return (
    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
      <p className="text-sm font-medium text-blue-800 mb-1">
        Analysis in progress — {stepName || "working"} ({step}/{totalSteps})
      </p>
      <div className="w-full bg-blue-200 rounded-full h-2 mb-1">
        <div
          className="bg-blue-600 h-2 rounded-full transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="text-xs text-blue-600 text-right">
        {pct}%{elapsedMs ? ` · ${elapsed(elapsedMs)}` : ""}
      </p>
    </div>
  );
}
