/**
 * API client (Model layer in MVVM).
 *
 * Single axios instance configured with base URL and API key.
 * Individual endpoint helpers are NOT exported – the ViewModel
 * (useDashboard) calls api.get / api.post directly so the data
 * contract stays in one place.
 */

import axios from "axios";

const API_URL =
  (typeof import.meta !== "undefined" && import.meta.env?.VITE_API_URL) || "";

const API_KEY =
  (typeof import.meta !== "undefined" && import.meta.env?.VITE_API_KEY) || "";

const api = axios.create({
  baseURL: API_URL || "/api",
  headers: {
    "Content-Type": "application/json",
    ...(API_KEY ? { "X-API-Key": API_KEY } : {}),
  },
  timeout: 30_000,
});

export default api;
