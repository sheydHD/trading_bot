/**
 * DataTable – reusable sortable table for stock / crypto / portfolio data.
 *
 * Pure presentational component (View in MVVM).
 * All data & formatting come from props.
 */

import React, { useState, useMemo } from "react";
import { price, pct, num, changeColor, directionColor, scoreBg } from "../utils/format";

const COLUMNS = {
  stock: [
    { key: "symbol",           label: "Symbol",      cls: "font-semibold" },
    { key: "name",             label: "Name",        cls: "hidden lg:table-cell text-gray-500 text-xs", truncate: true },
    { key: "sector",           label: "Sector",      cls: "hidden xl:table-cell text-gray-500 text-xs" },
    { key: "price",            label: "Price",       fmt: price, align: "right" },
    { key: "change_1d",        label: "1 D",         fmt: pct, color: changeColor, align: "right" },
    { key: "change_5d",        label: "5 D",         fmt: pct, color: changeColor, align: "right" },
    { key: "prediction",       label: "Signal",      color: directionColor, bold: true },
    { key: "confidence",       label: "Conf.",       fmt: (v) => (v != null ? `${(v * 100).toFixed(0)}%` : "—"), align: "right" },
    { key: "score",            label: "Score",       badge: scoreBg, align: "center" },
    { key: "technical_score",  label: "Tech",        align: "right", cls: "hidden md:table-cell" },
    { key: "fundamental_score",label: "Fund",        align: "right", cls: "hidden md:table-cell" },
    { key: "rsi",              label: "RSI",         align: "right", cls: "hidden lg:table-cell" },
    { key: "pe_ratio",         label: "P/E",         fmt: (v) => num(v, 1), align: "right", cls: "hidden lg:table-cell" },
    { key: "macd_trend",       label: "MACD",        cls: "hidden xl:table-cell text-xs" },
    { key: "model_accuracy",   label: "Acc.",        fmt: (v) => (v != null ? `${(v * 100).toFixed(1)}%` : "—"), align: "right", cls: "hidden xl:table-cell" },
  ],
  crypto: [
    { key: "symbol",     label: "Symbol",  cls: "font-semibold" },
    { key: "price",      label: "Price",   fmt: price, align: "right" },
    { key: "change_1d",  label: "1 D",     fmt: pct, color: changeColor, align: "right" },
    { key: "change_5d",  label: "5 D",     fmt: pct, color: changeColor, align: "right" },
    { key: "prediction", label: "Signal",  color: directionColor, bold: true },
    { key: "confidence", label: "Conf.",   fmt: (v) => (v != null ? `${(v * 100).toFixed(0)}%` : "—"), align: "right" },
    { key: "score",      label: "Score",   badge: scoreBg, align: "center" },
    { key: "rsi",        label: "RSI",     align: "right", cls: "hidden md:table-cell" },
    { key: "macd_trend", label: "MACD",    cls: "hidden lg:table-cell text-xs" },
    { key: "model_accuracy", label: "Acc.", fmt: (v) => (v != null ? `${(v * 100).toFixed(1)}%` : "—"), align: "right", cls: "hidden lg:table-cell" },
  ],
  portfolio: [
    { key: "symbol",     label: "Symbol",  cls: "font-semibold" },
    { key: "price",      label: "Price",   fmt: price, align: "right" },
    { key: "change_1d",  label: "1 D",     fmt: pct, color: changeColor, align: "right" },
    { key: "change_5d",  label: "5 D",     fmt: pct, color: changeColor, align: "right" },
    { key: "prediction", label: "Signal",  color: directionColor, bold: true },
    { key: "score",      label: "Score",   badge: scoreBg, align: "center" },
    { key: "rsi",        label: "RSI",     align: "right" },
    { key: "support",    label: "Support", fmt: price, align: "right", cls: "hidden md:table-cell" },
    { key: "resistance", label: "Resist.", fmt: price, align: "right", cls: "hidden md:table-cell" },
  ],
};

export default function DataTable({ rows = [], variant = "stock", title }) {
  const columns = COLUMNS[variant] || COLUMNS.stock;
  const [sortKey, setSortKey] = useState("score");
  const [sortAsc, setSortAsc] = useState(false);

  const sorted = useMemo(() => {
    if (!rows.length) return rows;
    return [...rows].sort((a, b) => {
      const av = a[sortKey] ?? -Infinity;
      const bv = b[sortKey] ?? -Infinity;
      if (av < bv) return sortAsc ? -1 : 1;
      if (av > bv) return sortAsc ? 1 : -1;
      return 0;
    });
  }, [rows, sortKey, sortAsc]);

  function handleSort(key) {
    if (sortKey === key) setSortAsc(!sortAsc);
    else { setSortKey(key); setSortAsc(false); }
  }

  if (!rows.length) {
    return (
      <div className="text-sm text-gray-400 py-6 text-center">
        No {variant} data available.
      </div>
    );
  }

  const alignCls = (a) =>
    a === "right" ? "text-right" : a === "center" ? "text-center" : "text-left";

  return (
    <div>
      {title && (
        <h2 className="text-lg font-semibold text-gray-700 mb-2">{title}</h2>
      )}
      <div className="overflow-x-auto rounded-lg border border-gray-200">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50 text-gray-500 uppercase text-xs">
            <tr>
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={`px-3 py-2 cursor-pointer select-none whitespace-nowrap ${alignCls(col.align)} ${col.cls || ""}`}
                  onClick={() => handleSort(col.key)}
                >
                  {col.label}
                  {sortKey === col.key ? (sortAsc ? " ▲" : " ▼") : ""}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {sorted.map((row) => (
              <tr key={row.symbol} className="hover:bg-gray-50">
                {columns.map((col) => {
                  const raw = row[col.key];
                  const display = col.fmt ? col.fmt(raw) : (raw ?? "—");
                  const colorCls = col.color ? col.color(raw) : "";
                  const badgeCls = col.badge ? col.badge(raw) : "";

                  return (
                    <td
                      key={col.key}
                      className={`px-3 py-2 whitespace-nowrap ${alignCls(col.align)} ${col.cls || ""} ${colorCls} ${col.bold ? "font-semibold" : ""}`}
                    >
                      {badgeCls ? (
                        <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${badgeCls}`}>
                          {display}
                        </span>
                      ) : col.truncate ? (
                        <span className="block max-w-[160px] truncate">{display}</span>
                      ) : (
                        display
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
