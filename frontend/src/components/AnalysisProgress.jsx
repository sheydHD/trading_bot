import React from "react";

function AnalysisProgress({ currentStep, totalSteps, stepName, timeElapsed }) {
  // Ensure values are defined and of correct type
  const safeCurrentStep = Number(currentStep) || 0;
  const safeTotalSteps = Number(totalSteps) || 1; // Avoid division by zero
  const safeStepName = stepName || "Running analysis";

  const progressPercent = Math.round((safeCurrentStep / safeTotalSteps) * 100);

  return (
    <div className="bg-blue-50 border-l-4 border-blue-400 p-4 mb-6">
      <div className="flex items-start">
        <div className="flex-shrink-0">
          <svg
            className="animate-spin h-5 w-5 text-blue-500 mt-0.5"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            ></circle>
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            ></path>
          </svg>
        </div>
        <div className="ml-3 w-full">
          <h3 className="text-sm font-medium text-blue-800">
            Analysis in progress
          </h3>
          <div className="mt-2 text-sm text-blue-700">
            <p className="mb-1">
              <span className="font-medium">Current Step:</span> {safeStepName}{" "}
              ({safeCurrentStep} of {safeTotalSteps})
            </p>
            <p className="mb-2">
              <span className="font-medium">Time elapsed:</span>{" "}
              {formatElapsedTime(timeElapsed)}
            </p>

            <div className="w-full bg-blue-200 rounded-full h-2.5">
              <div
                className="bg-blue-600 h-2.5 rounded-full"
                style={{ width: `${progressPercent}%` }}
              ></div>
            </div>
            <p className="mt-1 text-right text-xs">{progressPercent}%</p>
          </div>
        </div>
      </div>
    </div>
  );
}

function formatElapsedTime(milliseconds) {
  if (!milliseconds) return "0s";

  const seconds = Math.floor(milliseconds / 1000);
  const minutes = Math.floor(seconds / 60);

  if (minutes > 0) {
    return `${minutes}m ${seconds % 60}s`;
  }
  return `${seconds}s`;
}

export default AnalysisProgress;
