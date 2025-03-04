import React, { createContext, useState, useEffect, useContext } from "react";
import { getAnalysisStatus } from "../services/api";

// Create context
const AnalysisContext = createContext();

// Provider component
export const AnalysisProvider = ({ children }) => {
  const [analysisStatus, setAnalysisStatus] = useState({
    isRunning: false,
    currentStep: 0,
    totalSteps: 5,
    currentStepName: "",
    elapsedTime: null,
    logs: [],
  });
  const [statusPolling, setStatusPolling] = useState(null);

  // Start polling when analysis is running
  const startStatusPolling = () => {
    if (statusPolling) return; // Don't start if already polling

    const pollId = setInterval(async () => {
      try {
        const status = await getAnalysisStatus();
        setAnalysisStatus(status);

        // If analysis is no longer running, stop polling
        if (!status.is_running) {
          stopStatusPolling();
        }
      } catch (error) {
        console.error("Failed to poll analysis status:", error);
      }
    }, 2000); // Poll every 2 seconds

    setStatusPolling(pollId);
  };

  // Stop polling
  const stopStatusPolling = () => {
    if (statusPolling) {
      clearInterval(statusPolling);
      setStatusPolling(null);
    }
  };

  // Clean up on unmount
  useEffect(() => {
    return () => stopStatusPolling();
  }, []);

  // Check status on initial load
  useEffect(() => {
    const checkInitialStatus = async () => {
      try {
        const status = await getAnalysisStatus();
        setAnalysisStatus(status);

        if (status.is_running) {
          startStatusPolling();
        }
      } catch (error) {
        console.error("Failed to check initial analysis status:", error);
      }
    };

    checkInitialStatus();
  }, []);

  return (
    <AnalysisContext.Provider
      value={{
        analysisStatus,
        setAnalysisStatus,
        startStatusPolling,
        stopStatusPolling,
      }}
    >
      {children}
    </AnalysisContext.Provider>
  );
};

// Custom hook to use the Analysis context
export const useAnalysis = () => {
  const context = useContext(AnalysisContext);
  if (!context) {
    throw new Error("useAnalysis must be used within an AnalysisProvider");
  }
  return context;
};
