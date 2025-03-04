import React, { useState } from "react";
import { ChevronDownIcon, ChevronUpIcon } from "@heroicons/react/outline";

function DebugPanel({
  logs = [],
  isRunning = false,
  analysisTime = null,
  onRefresh,
}) {
  const [isExpanded, setIsExpanded] = useState(false);

  // Ensure logs is always an array
  const safeLogsArray = Array.isArray(logs) ? logs : [];

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
        </div>
      )}
    </div>
  );
}

export default DebugPanel;
