import React, { useState } from "react";
import { ChevronDownIcon, ChevronUpIcon } from "@heroicons/react/outline";
import api from "../services/api";

function DebugPanel({
  logs = [],
  isRunning = false,
  analysisTime = null,
  onRefresh,
}) {
  const [isExpanded, setIsExpanded] = useState(false);

  // Ensure logs is always an array
  const safeLogsArray = Array.isArray(logs) ? logs : [];

  const loadExampleData = async () => {
    try {
      const response = await api.get("/api/analysis/example");
      console.log("Loaded example data:", response.data);
      if (onRefresh) {
        onRefresh();
      }
    } catch (error) {
      console.error("Error loading example data:", error);
    }
  };

  const loadLatestAnalysis = async () => {
    try {
      console.log("Manually fetching latest analysis data...");
      await onRefresh();
      console.log("Data refreshed from API");
    } catch (error) {
      console.error("Error reloading latest analysis:", error);
    }
  };

  const inspectFieldNames = async () => {
    try {
      const response = await api.get("/api/analysis/debug");
      console.log("Field names debug info:", response.data);

      // Show an alert with the field names
      if (response.data.sample_data) {
        const fieldInfo = Object.entries(response.data.sample_data)
          .map(([key, info]) => `${key}: ${info.columns.join(", ")}`)
          .join("\n\n");

        alert(`Field names in data:\n\n${fieldInfo}`);
      } else {
        alert("No field data available");
      }
    } catch (error) {
      console.error("Error inspecting field names:", error);
      alert(`Error: ${error.message}`);
    }
  };

  return (
    <div className="bg-gray-100 rounded-md mb-6 overflow-hidden">
      <div
        className="flex justify-between items-center p-3 bg-gray-200 cursor-pointer"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center">
          <span className="font-medium text-gray-700">Debug Information</span>
          {isRunning && (
            <span className="ml-3 inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
              Analysis Running
            </span>
          )}
          {analysisTime && !isRunning && (
            <span className="ml-3 text-sm text-gray-500">
              Last analysis completed in {analysisTime.toFixed(2)} seconds
            </span>
          )}
          {analysisTime && !isRunning && (
            <span className="ml-3 text-sm text-green-500">
              Notifications sent to Telegram and email
            </span>
          )}
        </div>
        {isExpanded ? (
          <ChevronUpIcon className="h-5 w-5 text-gray-500" />
        ) : (
          <ChevronDownIcon className="h-5 w-5 text-gray-500" />
        )}
      </div>

      {isExpanded && (
        <div className="p-3">
          <div className="bg-black text-green-400 font-mono text-sm p-4 rounded h-48 overflow-y-auto">
            {safeLogsArray.length === 0 ? (
              <p>No log entries available.</p>
            ) : (
              safeLogsArray.map((log, index) => (
                <div key={index} className="mb-1">
                  <span className="opacity-60">[{log.timestamp}]</span>{" "}
                  <span
                    className={
                      log.type === "error"
                        ? "text-red-400"
                        : log.type === "warning"
                        ? "text-yellow-400"
                        : ""
                    }
                  >
                    {log.message}
                  </span>
                </div>
              ))
            )}
          </div>
          <div className="mt-4 p-4 bg-gray-100 rounded-md">
            <h3 className="text-lg font-medium mb-2">Debug Tools</h3>
            <div className="flex space-x-2">
              <button
                onClick={loadExampleData}
                className="px-4 py-2 bg-purple-500 text-white rounded hover:bg-purple-700"
              >
                Load Example Data
              </button>
              <button
                onClick={loadLatestAnalysis}
                className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-700 ml-2"
              >
                Reload Latest Data
              </button>
              <button
                onClick={inspectFieldNames}
                className="px-4 py-2 bg-green-500 text-white rounded hover:bg-green-700 ml-2"
              >
                Show Field Names
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default DebugPanel;
