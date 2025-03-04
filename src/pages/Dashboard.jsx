import React, { useState, useEffect } from "react";
import api, {
  getLatestAnalysis,
  runAnalysis,
  getAnalysisStatus,
} from "../services/api";
import AssetCard from "../components/AssetCard";
import AssetTable from "../components/AssetTable";
import LoadingSpinner from "../components/LoadingSpinner";
import ErrorAlert from "../components/ErrorAlert";
import RefreshButton from "../components/RefreshButton";
import RunAnalysisButton from "../components/RunAnalysisButton";
import DebugPanel from "../components/DebugPanel";
import AnalysisProgress from "../components/AnalysisProgress";
import { useAnalysis } from "../context/AnalysisContext";
import { debugInspect } from "../utils/helpers";
import RawDataDisplay from "../components/RawDataDisplay";

function Dashboard() {
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState(null);
  const [analysis, setAnalysis] = useState({
    best_stocks: [],
    top_stocks: [],
    best_cryptos: [],
    top_cryptos: [],
    wallet_stocks: [],
    wallet_cryptos: [],
  });
  const [lastUpdated, setLastUpdated] = useState(null);
  const { analysisStatus, setAnalysisStatus, startStatusPolling } =
    useAnalysis();
  const [analysisTime, setAnalysisTime] = useState(null);

  const fetchAnalysis = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getLatestAnalysis();
      console.log("Fetched analysis data:", data);

      // Ensure we have valid data objects even if some parts are missing
      const processedData = {
        best_stocks: data?.best_stocks || [],
        top_stocks: data?.top_stocks || [],
        best_cryptos: data?.best_cryptos || [],
        top_cryptos: data?.top_cryptos || [],
        wallet_stocks: data?.wallet_stocks || [],
        wallet_cryptos: data?.wallet_cryptos || [],
      };

      // Check if we got anything meaningful
      if (
        processedData.best_stocks.length === 0 &&
        processedData.best_cryptos.length === 0 &&
        processedData.top_stocks.length === 0 &&
        processedData.top_cryptos.length === 0
      ) {
        console.warn("No meaningful data found in API response");
        // Try the example endpoint as a fallback
        try {
          console.log("Trying example data endpoint...");
          const exampleResponse = await api.get("/api/analysis/example");
          if (exampleResponse.data) {
            console.log("Using example data instead");
            setAnalysis(exampleResponse.data);
            setLastUpdated(new Date());
            return;
          }
        } catch (exErr) {
          console.error("Failed to get example data:", exErr);
        }
      }

      setAnalysis(processedData);
      setLastUpdated(new Date());
    } catch (err) {
      console.error("Error fetching analysis:", err);
      setError(err.message || "Failed to fetch analysis data");
    } finally {
      setLoading(false);
    }
  };

  const handleRunAnalysis = async () => {
    setAnalyzing(true);
    setError(null);

    try {
      // Start the analysis
      const response = await runAnalysis();

      if (response.success) {
        // Extract data from response
        const apiData = response.data || {};

        // Immediately set the data from the response
        const safeData = {
          best_stocks: [],
          top_stocks: [],
          best_cryptos: [],
          top_cryptos: [],
          wallet_stocks: [],
          wallet_cryptos: [],
          ...apiData,
        };

        setAnalysis(safeData);
        setLastUpdated(new Date());
        setAnalysisTime(response.execution_time);

        // Log the result size for debugging
        console.log("Analysis data size:", {
          best_stocks: safeData.best_stocks?.length || 0,
          top_stocks: safeData.top_stocks?.length || 0,
          best_cryptos: safeData.best_cryptos?.length || 0,
          top_cryptos: safeData.top_cryptos?.length || 0,
          wallet_stocks: safeData.wallet_stocks?.length || 0,
          wallet_cryptos: safeData.wallet_cryptos?.length || 0,
        });
      } else {
        console.warn("Analysis failed, fetching latest cached results");
        // Even if run fails, try to fetch latest cached results
        try {
          const latestData = await getLatestAnalysis();
          if (
            latestData &&
            (latestData.best_stocks?.length > 0 ||
              latestData.best_cryptos?.length > 0)
          ) {
            console.log("Found cached data:", latestData);
            setAnalysis(latestData);
            setLastUpdated(new Date());
          }
        } catch (cacheErr) {
          console.error("Failed to fetch cached data:", cacheErr);
        }
        throw new Error(response.error || "Analysis failed");
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setAnalyzing(false);
    }
  };

  const checkAnalysisStatus = async () => {
    if (!analyzing) return;

    try {
      const status = await getAnalysisStatus();
      setAnalysisStatus({
        isRunning: status.is_running,
        currentStep: status.current_step,
        totalSteps: status.total_steps,
        currentStepName: status.current_step_name,
        elapsedTime: status.elapsed_time,
        logs: status.logs || analysisStatus.logs,
      });

      // If analysis is still running, schedule another check
      if (status.is_running) {
        setTimeout(checkAnalysisStatus, 1000);
      } else if (analyzing) {
        // If our UI thinks it's analyzing but server says it's done,
        // we should refresh the data
        setAnalyzing(false);
        fetchAnalysis();
      }
    } catch (err) {
      console.error("Failed to check analysis status:", err);
      // Still schedule another check in case of temporary error
      setTimeout(checkAnalysisStatus, 2000);
    }
  };

  useEffect(() => {
    fetchAnalysis();
    // Set up periodic refresh (every 5 minutes)
    const interval = setInterval(fetchAnalysis, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    // Start checking status when analysis begins
    if (analyzing) {
      checkAnalysisStatus();
    }
  }, [analyzing]);

  useEffect(() => {
    // If we were analyzing and now we're not, fetch the latest results
    if (!analyzing && analysisStatus && !analysisStatus.isRunning) {
      const fetchLatestResults = async () => {
        try {
          console.log("Fetching latest analysis results...");
          const data = await getLatestAnalysis();

          if (data) {
            console.log("Received latest analysis data:", data);
            setAnalysis({
              best_stocks: data.best_stocks || [],
              top_stocks: data.top_stocks || [],
              best_cryptos: data.best_cryptos || [],
              top_cryptos: data.top_cryptos || [],
              wallet_stocks: data.wallet_stocks || [],
              wallet_cryptos: data.wallet_cryptos || [],
            });
            setLastUpdated(new Date());
          }
        } catch (err) {
          console.error("Error fetching latest results:", err);
        }
      };

      fetchLatestResults();
    }
  }, [analyzing, analysisStatus]);

  if (loading && !analysis) {
    return <LoadingSpinner />;
  }

  if (error && !analysis) {
    return <ErrorAlert message={error} onRetry={fetchAnalysis} />;
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-gray-800">
          Market Analysis Dashboard
        </h1>
        <div className="flex items-center space-x-4">
          {lastUpdated && (
            <p className="text-sm text-gray-500">
              Last updated: {lastUpdated.toLocaleTimeString()}
            </p>
          )}
          <RefreshButton onClick={fetchAnalysis} loading={loading} />
          <RunAnalysisButton onClick={handleRunAnalysis} loading={analyzing} />
        </div>
      </div>

      {error && <ErrorAlert message={error} className="mb-4" />}

      <DebugPanel
        logs={analysisStatus.logs}
        isRunning={analysisStatus.isRunning}
        analysisTime={analysisTime}
      />

      {analyzing && (
        <AnalysisProgress
          currentStep={analysisStatus.currentStep}
          totalSteps={analysisStatus.totalSteps}
          stepName={analysisStatus.currentStepName}
          timeElapsed={analysisStatus.elapsedTime}
        />
      )}

      {analysis && (
        <div className="space-y-8">
          {/* Top Picks Section */}
          <section>
            <h2 className="text-xl font-semibold text-gray-700 mb-4">
              🔥 Best Stock Picks (Top 6)
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {analysis.best_stocks && analysis.best_stocks.length > 0 ? (
                analysis.best_stocks.map((stock) => (
                  <AssetCard key={stock.Symbol} asset={stock} type="stock" />
                ))
              ) : (
                <p className="text-gray-500 col-span-full">
                  No bullish stocks found. 😔
                </p>
              )}
            </div>
          </section>

          {/* Other Stocks Section */}
          <section>
            <h2 className="text-xl font-semibold text-gray-700 mb-4">
              🏢 Other Top Stocks
            </h2>
            {analysis.top_stocks && analysis.top_stocks.length > 0 ? (
              <AssetTable
                assets={analysis.top_stocks.filter(
                  (stock) =>
                    !analysis.best_stocks?.some(
                      (bs) => bs.Symbol === stock.Symbol
                    )
                )}
                type="stock"
              />
            ) : (
              <p className="text-gray-500">No stocks data available.</p>
            )}
          </section>

          {/* Best Cryptos Section */}
          <section>
            <h2 className="text-xl font-semibold text-gray-700 mb-4">
              🔥 Best Crypto Picks (Top 6)
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {analysis.best_cryptos && analysis.best_cryptos.length > 0 ? (
                analysis.best_cryptos.map((crypto) => (
                  <AssetCard key={crypto.Symbol} asset={crypto} type="crypto" />
                ))
              ) : (
                <p className="text-gray-500 col-span-full">
                  No bullish cryptos found. 😔
                </p>
              )}
            </div>
          </section>

          {/* Wallet Section */}
          <section>
            <h2 className="text-xl font-semibold text-gray-700 mb-4">
              👜 My Portfolio
            </h2>

            <div className="mb-6">
              <h3 className="text-lg font-medium text-gray-600 mb-2">Stocks</h3>
              <AssetTable
                assets={analysis.wallet_stocks}
                type="stock"
                compact
              />
            </div>

            <div>
              <h3 className="text-lg font-medium text-gray-600 mb-2">
                Cryptos
              </h3>
              <AssetTable
                assets={analysis.wallet_cryptos}
                type="crypto"
                compact
              />
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

export default Dashboard;
