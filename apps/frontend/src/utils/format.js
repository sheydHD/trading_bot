/** Formatting utilities for the dashboard views. */

/**
 * Format a number to fixed decimal places, returning "—" for null/NaN.
 * @param {number|null} val
 * @param {number} digits
 * @returns {string}
 */
export function num(val, digits = 2) {
  if (val == null || Number.isNaN(val)) return "—";
  return Number(val).toFixed(digits);
}

/**
 * Format as dollar price.
 * @param {number|null} val
 * @returns {string}
 */
export function price(val) {
  if (val == null || Number.isNaN(val)) return "—";
  return `$${Number(val).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

/**
 * Format a percentage change with +/- sign.
 * @param {number|null} val  – already in percent (e.g. 2.3 = 2.3%)
 * @returns {string}
 */
export function pct(val) {
  if (val == null || Number.isNaN(val)) return "—";
  const sign = val > 0 ? "+" : "";
  return `${sign}${Number(val).toFixed(2)}%`;
}

/**
 * Return a Tailwind text-color class for a percentage change.
 */
export function changeColor(val) {
  if (val == null) return "text-gray-400";
  if (val > 0) return "text-green-600";
  if (val < 0) return "text-red-600";
  return "text-gray-500";
}

/**
 * Return a Tailwind text-color class for a prediction direction.
 */
export function directionColor(dir) {
  if (dir === "UP") return "text-green-600";
  if (dir === "DOWN") return "text-red-600";
  return "text-gray-500";
}

/**
 * Return a Tailwind bg class for a score value.
 */
export function scoreBg(score) {
  if (score == null) return "bg-gray-100 text-gray-700";
  if (score >= 70) return "bg-green-100 text-green-800";
  if (score >= 50) return "bg-yellow-100 text-yellow-800";
  return "bg-red-100 text-red-800";
}

/**
 * Format elapsed milliseconds to human string.
 */
export function elapsed(ms) {
  if (!ms) return "0s";
  const s = Math.floor(ms / 1000);
  const m = Math.floor(s / 60);
  return m > 0 ? `${m}m ${s % 60}s` : `${s}s`;
}
