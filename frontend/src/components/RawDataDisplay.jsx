import React from "react";

const RawDataDisplay = ({ data, title }) => {
  return (
    <div className="mt-4 p-4 bg-gray-100 rounded-md">
      <h3 className="text-lg font-medium mb-2">{title || "Raw Data"}</h3>
      <pre className="text-xs overflow-auto max-h-60 bg-white p-2 rounded">
        {JSON.stringify(data, null, 2)}
      </pre>
    </div>
  );
};

export default RawDataDisplay;
