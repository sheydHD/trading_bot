import React, { useState, useEffect } from "react";
import { getAnalysisHistory } from "../services/api";
import LoadingSpinner from "./LoadingSpinner";

function AnalysisHistory() {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchHistory();
  }, []);

  const fetchHistory = async () => {
    setLoading(true);
    try {
      const data = await getAnalysisHistory();
      // Make sure we're dealing with an array
      setHistory(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err.message || "Failed to fetch history");
      setHistory([]);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <LoadingSpinner />;
  }

  if (error) {
    return <div className="text-red-500">{error}</div>;
  }

  if (!history.length) {
    return <div className="text-gray-500">No analysis history available.</div>;
  }

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">Analysis History</h2>
      {history.map((item, index) => (
        <div key={index} className="border rounded p-4">
          <h3 className="font-medium">
            Analysis from {new Date(item.timestamp).toLocaleString()}
          </h3>
          {/* Show summary data */}
          <div className="mt-2 text-sm text-gray-600">
            <p>Stocks analyzed: {(item.top_stocks || []).length}</p>
            <p>Cryptos analyzed: {(item.top_cryptos || []).length}</p>
          </div>
        </div>
      ))}
    </div>
  );
}

export default AnalysisHistory;
