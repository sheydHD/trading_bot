export const safeMap = (array, callback) => {
  if (!array || !Array.isArray(array)) {
    console.warn("Attempted to map over non-array:", array);
    return [];
  }
  return array.map(callback);
};

/**
 * Deep inspect and log an object structure for debugging
 * @param {Object} obj - The object to inspect
 * @param {string} name - The name for the log
 */
export const debugInspect = (obj, name = "Data") => {
  if (!obj) {
    console.log(`${name}: null or undefined`);
    return;
  }

  if (typeof obj !== "object") {
    console.log(`${name}: ${typeof obj} - ${obj}`);
    return;
  }

  const result = {};

  Object.keys(obj).forEach((key) => {
    const value = obj[key];

    if (Array.isArray(value)) {
      result[key] = {
        type: "array",
        length: value.length,
        sample: value.length > 0 ? value[0] : null,
      };
    } else if (value && typeof value === "object") {
      result[key] = {
        type: "object",
        keys: Object.keys(value),
        sample:
          Object.keys(value).length > 0 ? value[Object.keys(value)[0]] : null,
      };
    } else {
      result[key] = {
        type: typeof value,
        value: value,
      };
    }
  });

  console.log(`${name} structure:`, result);
};
