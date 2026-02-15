/**
 * useDashboard – ViewModel for the Dashboard view.
 *
 * Encapsulates ALL business logic:
 *  - Fetching latest analysis data
 *  - Triggering a new analysis run
 *  - Polling analysis status while a run is in progress
 *  - Exposing derived / formatted values for the view layer
 */

import { useState, useEffect, useCallback, useRef } from "react";
import api from "../services/api";

const POLL_INTERVAL = 3000; // ms
const AUTO_REFRESH  = 5 * 60 * 1000; // 5 min

/** @returns {import("./useDashboard").DashboardVM} */
export default function useDashboard() {
  // ---- state ----------------------------------------------------------
  const [data, setData]             = useState(null);   // full API payload
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState(null);
  const [analyzing, setAnalyzing]   = useState(false);
  const [status, setStatus]         = useState({
    isRunning: false, step: 0, totalSteps: 4, stepName: "", elapsed: null,
  });
  const [lastUpdated, setLastUpdated] = useState(null);
  const [execTime, setExecTime]       = useState(null);

  const pollRef = useRef(null);

  // ---- fetch latest ---------------------------------------------------
  const fetchLatest = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get("/analysis/latest", { timeout: 120_000 });
      if (res.data && !res.data.error) {
        setData(res.data);
        setLastUpdated(new Date());
      } else {
        setError(res.data?.error || "Empty response");
      }
    } catch (err) {
      setError(err.response?.data?.error || err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  // ---- run analysis ---------------------------------------------------
  const runAnalysis = useCallback(async () => {
    if (analyzing) return;
    setAnalyzing(true);
    setError(null);
    setExecTime(null);
    _startPolling();

    try {
      // Kick off analysis (returns immediately – runs in background)
      const res = await api.post("/analysis/run", null, { timeout: 30_000 });
      const body = res.data;
      if (!body.success) {
        setError(body.error || "Analysis failed to start");
        setAnalyzing(false);
        _stopPolling();
        return;
      }

      // Poll until analysis completes, then fetch results
      await new Promise((resolve, reject) => {
        const check = setInterval(async () => {
          try {
            const s = await api.get("/analysis/status", { timeout: 5000 });
            if (!s.data.is_running) {
              clearInterval(check);
              resolve();
            }
          } catch { /* ignore transient polling errors */ }
        }, POLL_INTERVAL);
        // Safety timeout: 15 minutes
        setTimeout(() => { clearInterval(check); reject(new Error("Analysis timed out")); }, 900_000);
      });

      // Fetch the fresh result
      const latest = await api.get("/analysis/latest", { timeout: 30_000 });
      if (latest.data && !latest.data.error) {
        setData(latest.data);
        setLastUpdated(new Date());
      }
    } catch (err) {
      setError(err.response?.data?.error || err.message);
    } finally {
      setAnalyzing(false);
      _stopPolling();
    }
  }, [analyzing]);

  // ---- status polling -------------------------------------------------
  function _startPolling() {
    _stopPolling();
    pollRef.current = setInterval(async () => {
      try {
        const res = await api.get("/analysis/status", { timeout: 5000 });
        const s = res.data;
        setStatus({
          isRunning:  Boolean(s.is_running),
          step:       s.current_step ?? 0,
          totalSteps: s.total_steps ?? 4,
          stepName:   s.current_step_name ?? "",
          elapsed:    s.elapsed_time ?? null,
        });
      } catch { /* ignore transient errors */ }
    }, POLL_INTERVAL);
  }

  function _stopPolling() {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }

  // ---- lifecycle ------------------------------------------------------
  useEffect(() => {
    fetchLatest();
    const id = setInterval(fetchLatest, AUTO_REFRESH);
    return () => { clearInterval(id); _stopPolling(); };
  }, [fetchLatest]);

  // ---- derived values -------------------------------------------------
  const stocks       = data?.stocks       ?? [];
  const cryptos      = data?.cryptos      ?? [];
  const portfolio    = data?.portfolio    ?? { stocks: [], cryptos: [] };
  const modelInfo    = data?.model_info   ?? null;

  const bullishStocks  = stocks.filter((s) => s.prediction === "UP").length;
  const bearishStocks  = stocks.filter((s) => s.prediction === "DOWN").length;
  const neutralStocks  = stocks.filter((s) => s.prediction === "NEUTRAL").length;
  const bullishCryptos = cryptos.filter((c) => c.prediction === "UP").length;
  const bearishCryptos = cryptos.filter((c) => c.prediction === "DOWN").length;
  const neutralCryptos = cryptos.filter((c) => c.prediction === "NEUTRAL").length;

  return {
    // raw
    stocks, cryptos, portfolio, modelInfo,
    // meta
    loading, error, analyzing, status, lastUpdated, execTime,
    // derived
    bullishStocks, bearishStocks, neutralStocks,
    bullishCryptos, bearishCryptos, neutralCryptos,
    // actions
    fetchLatest, runAnalysis,
  };
}
