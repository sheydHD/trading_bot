import axios from "axios";

const API_URL = process.env.REACT_APP_API_URL;
const API_KEY = process.env.REACT_APP_API_KEY;

// Create axios instance with default config
const api = axios.create({
  baseURL: API_URL || "/api",
  headers: {
    "Content-Type": "application/json",
    "X-API-Key": API_KEY,
  },
});

// Get latest analysis with fallback to cache
export const getLatestAnalysis = async () => {
  try {
    // First check if we've got data in localStorage that we can use
    // while waiting for API response
    const cachedData = localStorage.getItem("latestAnalysis");
    let parsedCache = null;

    if (cachedData) {
      try {
        parsedCache = JSON.parse(cachedData);
        console.log("Found cached analysis in localStorage:", parsedCache);
      } catch (e) {
        console.warn("Failed to parse cached analysis:", e);
      }
    }

    // Continue with API request
    const response = await api.get("/analysis/latest");
    console.log("Latest analysis API Response:", response.data);

    // If we got a good response, cache it in localStorage
    if (
      response.data &&
      (response.data.best_stocks?.length > 0 ||
        response.data.best_cryptos?.length > 0)
    ) {
      localStorage.setItem("latestAnalysis", JSON.stringify(response.data));
    }

    // Check if we got valid data
    if (
      response.data &&
      (response.data.best_stocks?.length > 0 ||
        response.data.best_cryptos?.length > 0 ||
        response.data.top_stocks?.length > 0 ||
        response.data.top_cryptos?.length > 0)
    ) {
      return response.data;
    } else {
      console.log("API returned empty data, checking history...");
      // If no data in latest, try to get from history
      const history = await getAnalysisHistory();
      if (history && history.length > 0) {
        console.log("Using most recent history entry");
        return history[history.length - 1];
      }
      return response.data; // Return empty data if no history
    }
  } catch (error) {
    console.error("Error fetching latest analysis:", error);
    throw error;
  }
};

// Get analysis history
export const getAnalysisHistory = async () => {
  try {
    const response = await api.get("/analysis/history");
    console.log("History API Response:", response.data);

    // Make sure we return an array
    return Array.isArray(response.data) ? response.data : [];
  } catch (error) {
    console.error("Error fetching analysis history:", error);
    return []; // Always return an array, even on error
  }
};

// Run new analysis
export const runAnalysis = async () => {
  try {
    console.log("Starting analysis run...");
    const response = await api.post("/analysis/run");
    console.log("Analysis run response:", response.data);

    // More detailed logging of the data
    if (response.data && response.data.data) {
      const data = response.data.data;
      console.log("Analysis data details:", {
        best_stocks: {
          length: data.best_stocks?.length,
          sample: data.best_stocks?.length > 0 ? data.best_stocks[0] : null,
        },
        top_stocks: {
          length: data.top_stocks?.length,
          sample: data.top_stocks?.length > 0 ? data.top_stocks[0] : null,
        },
        best_cryptos: {
          length: data.best_cryptos?.length,
          sample: data.best_cryptos?.length > 0 ? data.best_cryptos[0] : null,
        },
        top_cryptos: {
          length: data.top_cryptos?.length,
          sample: data.top_cryptos?.length > 0 ? data.top_cryptos[0] : null,
        },
        wallet_stocks: {
          length: data.wallet_stocks?.length,
          sample: data.wallet_stocks?.length > 0 ? data.wallet_stocks[0] : null,
        },
        wallet_cryptos: {
          length: data.wallet_cryptos?.length,
          sample:
            data.wallet_cryptos?.length > 0 ? data.wallet_cryptos[0] : null,
        },
      });
    }

    return response.data;
  } catch (error) {
    console.error("Error running analysis:", error);
    throw error;
  }
};

// Get analysis status
export const getAnalysisStatus = async () => {
  try {
    const response = await api.get("/analysis/status");
    return response.data;
  } catch (error) {
    console.error("Error fetching analysis status:", error);
    throw error;
  }
};

export default api;
