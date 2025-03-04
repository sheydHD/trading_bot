import React from "react";
import { RefreshIcon } from "@heroicons/react/outline";

function RefreshButton({ onClick, loading = false }) {
  return (
    <button
      type="button"
      className="inline-flex items-center px-3 py-2 border border-transparent text-sm leading-4 font-medium rounded-md text-primary-700 bg-primary-100 hover:bg-primary-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
      onClick={onClick}
      disabled={loading}
    >
      <RefreshIcon
        className={`-ml-0.5 mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`}
        aria-hidden="true"
      />
      Refresh
    </button>
  );
}

export default RefreshButton;
