import React from "react";
import { safeMap } from "../utils/helpers";

function AssetTable({ assets = [], type = "stock", compact = false }) {
  if (!assets || assets.length === 0) {
    return <p className="text-gray-500">No {type} data available.</p>;
  }

  const getRecommendationColor = (rec) => {
    if (!rec) return "text-gray-500";
    const recUpper = rec.toUpperCase();
    if (recUpper.includes("BUY")) return "text-green-600";
    if (recUpper.includes("SELL")) return "text-red-600";
    return "text-yellow-600";
  };

  const getField = (asset, field) => {
    const camelCase = field;
    const snake_case = field.replace(/([A-Z])/g, "_$1").toUpperCase();

    // Try both formats
    return asset[camelCase] !== undefined
      ? asset[camelCase]
      : asset[snake_case] !== undefined
      ? asset[snake_case]
      : asset[field.toLowerCase()] !== undefined
      ? asset[field.toLowerCase()]
      : null;
  };

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th
              scope="col"
              className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Symbol
            </th>
            <th
              scope="col"
              className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Recommendation
            </th>
            <th
              scope="col"
              className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Current Price
            </th>
            {!compact && (
              <th
                scope="col"
                className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
              >
                Take Profit
              </th>
            )}
            {!compact && (
              <th
                scope="col"
                className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
              >
                Score
              </th>
            )}
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {safeMap(assets, (asset) => (
            <tr key={asset.Symbol} className="hover:bg-gray-50">
              <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                {asset.Symbol}
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-sm">
                <span
                  className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getRecommendationColor(
                    getField(asset, "Daily_Recommendation")
                  )}`}
                >
                  {getField(asset, "Daily_Recommendation") || "N/A"}
                </span>
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                ${getField(asset, "Current_Price")?.toFixed(2) || "N/A"}
              </td>
              {!compact && (
                <td className="px-6 py-4 whitespace-nowrap text-sm text-green-600">
                  ${getField(asset, "Take_Profit")?.toFixed(2) || "N/A"}
                </td>
              )}
              {!compact && (
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                  {getField(asset, "Score") || "N/A"}/100
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default AssetTable;
