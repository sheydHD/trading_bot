/**
 * Dashboard – main view.
 *
 * Pure layout / composition; all state lives in the useDashboard() ViewModel.
 * No icons, no emojis – clean data-driven UI.
 */

import React from "react";
import useDashboard from "../hooks/useDashboard";
import DataTable from "../components/DataTable";
import ProgressBar from "../components/ProgressBar";
import { num } from "../utils/format";

export default function Dashboard() {
  const vm = useDashboard();

  return (
    <div className="space-y-6">
      {/* ---- Top bar: title, meta, actions ---- */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-gray-800">
            Market Analysis
          </h1>
          {vm.lastUpdated && (
            <p className="text-xs text-gray-400 mt-0.5">
              Updated {vm.lastUpdated.toLocaleTimeString()}
              {vm.execTime != null && ` · ran in ${vm.execTime.toFixed(1)}s`}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            className="px-3 py-1.5 text-sm rounded border border-gray-300 text-gray-600 hover:bg-gray-100 disabled:opacity-40"
            onClick={vm.fetchLatest}
            disabled={vm.loading}
          >
            Refresh
          </button>
          <button
            className="px-4 py-1.5 text-sm rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-40"
            onClick={vm.runAnalysis}
            disabled={vm.analyzing}
          >
            {vm.analyzing ? "Running…" : "Run Analysis"}
          </button>
        </div>
      </div>

      {/* ---- Error banner ---- */}
      {vm.error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">
          {vm.error}
        </div>
      )}

      {/* ---- Progress ---- */}
      {vm.analyzing && (
        <ProgressBar
          step={vm.status.step}
          totalSteps={vm.status.totalSteps}
          stepName={vm.status.stepName}
          elapsedMs={vm.status.elapsed}
        />
      )}

      {/* ---- Loading skeleton ---- */}
      {vm.loading && !vm.stocks.length && (
        <div className="text-center py-16 text-gray-400 text-sm">
          Loading analysis data…
        </div>
      )}

      {/* ---- Summary cards ---- */}
      {(vm.stocks.length > 0 || vm.cryptos.length > 0) && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <SummaryCard label="Stocks Analyzed" value={vm.stocks.length} />
          <SummaryCard
            label="UP / DOWN / NEUTRAL"
            value={`${vm.bullishStocks} / ${vm.bearishStocks} / ${vm.neutralStocks}`}
            color={vm.bullishStocks > vm.bearishStocks ? "text-green-600" : vm.bearishStocks > vm.bullishStocks ? "text-red-600" : "text-gray-600"}
          />
          <SummaryCard label="Cryptos Analyzed" value={vm.cryptos.length} />
          <SummaryCard
            label="Model Accuracy"
            value={vm.modelInfo?.avg_accuracy != null ? `${(vm.modelInfo.avg_accuracy * 100).toFixed(1)}%` : "—"}
          />
        </div>
      )}

      {/* ---- Stock table ---- */}
      {vm.stocks.length > 0 && (
        <DataTable rows={vm.stocks} variant="stock" title="Stocks" />
      )}

      {/* ---- Crypto table ---- */}
      {vm.cryptos.length > 0 && (
        <DataTable rows={vm.cryptos} variant="crypto" title="Crypto" />
      )}

      {/* ---- Portfolio ---- */}
      {(vm.portfolio.stocks.length > 0 || vm.portfolio.cryptos.length > 0) && (
        <section>
          <h2 className="text-lg font-semibold text-gray-700 mb-2">
            Portfolio
          </h2>
          {vm.portfolio.stocks.length > 0 && (
            <div className="mb-4">
              <DataTable rows={vm.portfolio.stocks} variant="portfolio" />
            </div>
          )}
          {vm.portfolio.cryptos.length > 0 && (
            <DataTable rows={vm.portfolio.cryptos} variant="portfolio" />
          )}
        </section>
      )}

      {/* ---- Model info ---- */}
      {vm.modelInfo && (
        <div className="text-xs text-gray-400 border-t border-gray-100 pt-4 flex flex-wrap gap-x-6 gap-y-1">
          <span>Method: {vm.modelInfo.method}</span>
          <span>Features: {vm.modelInfo.features_used}</span>
          <span>Horizon: {vm.modelInfo.prediction_horizon}</span>
          {vm.modelInfo.avg_accuracy != null && (
            <span>Avg accuracy: {(vm.modelInfo.avg_accuracy * 100).toFixed(1)}%</span>
          )}
        </div>
      )}
    </div>
  );
}

/* Small summary stat card */
function SummaryCard({ label, value, color = "text-gray-800" }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 px-4 py-3">
      <p className="text-xs text-gray-400 mb-0.5">{label}</p>
      <p className={`text-lg font-semibold ${color}`}>{value}</p>
    </div>
  );
}
