import React, { useState, useEffect } from "react";
import { getAnalysisHistory } from "../services/api";
import LoadingSpinner from "../components/LoadingSpinner";
import ErrorAlert from "../components/ErrorAlert";

function History() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [history, setHistory] = useState([]);

  useEffect(() => {
    const fetchHistory = async () => {
      try {
        setLoading(true);
        const data = await getAnalysisHistory();
        setHistory(data);
      } catch (err) {
        setError(err.message || "Failed to fetch history data");
      } finally {
        setLoading(false);
      }
    };

    fetchHistory();
  }, []);

  if (loading) {
    return <LoadingSpinner />;
  }

  if (error) {
    return <ErrorAlert message={error} />;
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-800 mb-6">
        Analysis History
      </h1>

      {history.length === 0 ? (
        <p className="text-gray-500">No historical data available yet.</p>
      ) : (
        <div className="space-y-6">
          {history.map((item, index) => (
            <div key={index} className="bg-white p-4 rounded-lg shadow">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-lg font-semibold">
                  Analysis from {new Date(item.timestamp).toLocaleString()}
                </h2>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <h3 className="font-medium mb-2">Best Stocks</h3>
                  <p>{item.best_stocks.length} stocks found</p>
                </div>
                <div>
                  <h3 className="font-medium mb-2">Best Cryptos</h3>
                  <p>{item.best_cryptos.length} cryptos found</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default History;
