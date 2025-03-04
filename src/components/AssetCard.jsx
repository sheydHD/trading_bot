import React from "react";

function AssetCard({ asset, type }) {
  // Add debugging
  console.log(`AssetCard rendering for ${type}: ${asset?.Symbol || "unknown"}`);

  // Normalize field names (handle multiple format variations)
  const getField = (field) => {
    // Try all these variations
    const variants = [
      field, // e.g., "Daily_Recommendation"
      field.replace(/[_\s]/g, ""), // e.g., "DailyRecommendation"
      field.replace(/([A-Z])/g, "_$1").toUpperCase(), // e.g., "DAILY_RECOMMENDATION"
      field.replace(/[_\s]/g, " "), // e.g., "Daily Recommendation"
      field.toLowerCase(), // e.g., "daily_recommendation"
      field.toLowerCase().replace(/[_\s]/g, ""), // e.g., "dailyrecommendation"
    ];

    // Try each variant
    for (const variant of variants) {
      if (asset[variant] !== undefined) {
        console.log(`Found field ${field} as ${variant}`);
        return asset[variant];
      }
    }

    return null;
  };

  const getRecommendationColor = (rec) => {
    if (!rec) return "text-gray-500";
    const recUpper = rec.toUpperCase();
    if (recUpper.includes("BUY")) return "text-green-600";
    if (recUpper.includes("SELL")) return "text-red-600";
    return "text-yellow-600";
  };

  // Use getField for all data access
  const recommendation =
    getField("Daily_Recommendation") || getField("DailyRecommendation");
  const currentPrice = getField("Current_Price") || getField("CurrentPrice");
  const takeProfit = getField("Take_Profit") || getField("TakeProfit");
  const score = getField("Score");
  const horizon =
    getField("Recommended_Horizon") || getField("RecommendedHorizon");
  const shortProb =
    getField("Short_Probability") || getField("ShortProbability");
  const midProb = getField("Mid_Probability") || getField("MidProbability");
  const longProb = getField("Long_Probability") || getField("LongProbability");

  // Ensure we always have a valid number or null
  const safeNumber = (value) => {
    if (value === undefined || value === null) return null;
    const num = parseFloat(value);
    return isNaN(num) ? null : num;
  };

  // Safe versions of all values
  const safeCurrentPrice = safeNumber(currentPrice);
  const safeTakeProfit = safeNumber(takeProfit);
  const safeScore = safeNumber(score);

  return (
    <div className="bg-white rounded-lg shadow-md p-4 hover:shadow-lg transition-shadow">
      <div className="flex justify-between items-start">
        <h3 className="text-lg font-bold">{asset.Symbol}</h3>
        <span
          className={`px-2 py-1 rounded text-xs font-medium ${getRecommendationColor(
            recommendation
          )}`}
        >
          {recommendation || "N/A"}
        </span>
      </div>

      <div className="mt-3 space-y-2">
        <div className="flex justify-between">
          <span className="text-gray-500">Current Price:</span>
          <span className="font-medium">
            ${safeCurrentPrice !== null ? safeCurrentPrice.toFixed(2) : "N/A"}
          </span>
        </div>

        <div className="flex justify-between">
          <span className="text-gray-500">Take Profit:</span>
          <span className="font-medium text-green-600">
            ${safeTakeProfit !== null ? safeTakeProfit.toFixed(2) : "N/A"}
          </span>
        </div>

        <div className="flex justify-between">
          <span className="text-gray-500">Score:</span>
          <span className="font-medium">
            {safeScore !== null ? safeScore : "N/A"}/100
          </span>
        </div>
      </div>

      {horizon && (
        <div className="mt-3 pt-3 border-t border-gray-100">
          <div className="text-xs text-gray-500">Recommended Timeframe</div>
          <div className="font-medium">{horizon}-term</div>

          <div className="mt-2 flex items-center justify-between text-xs">
            <div>
              <div className="text-gray-500">Short</div>
              <div>{shortProb || 0}%</div>
            </div>
            <div>
              <div className="text-gray-500">Mid</div>
              <div>{midProb || 0}%</div>
            </div>
            <div>
              <div className="text-gray-500">Long</div>
              <div>{longProb || 0}%</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default AssetCard;
