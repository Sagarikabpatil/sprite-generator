export const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");

function describeConnectionError(error) {
  if (error instanceof TypeError) {
    return new Error(
      "Could not reach the AssetAI backend. Confirm it is running and that this frontend origin is allowed by CORS.",
      { cause: error },
    );
  }
  return error;
}

export async function fetchJson(url, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (!(options.body instanceof FormData) && !headers["Content-Type"] && typeof options.body === "string") {
    headers["Content-Type"] = "application/json";
  }

  let response;
  try {
    response = await fetch(url, { ...options, headers });
  } catch (error) {
    throw describeConnectionError(error);
  }

  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const message = typeof payload === "object" && payload !== null
      ? payload.detail || payload.error || "Request failed."
      : payload || "Request failed.";
    const requestError = new Error(message);
    requestError.status = response.status;
    throw requestError;
  }

  return payload;
}

export function assetRequestUrl(url) {
  return url.startsWith("http") ? url : `${API_BASE}${url}`;
}

export async function fetchAsset(url, token) {
  let response;
  try {
    response = await fetch(assetRequestUrl(url), {
      headers: { Authorization: `Bearer ${token}` },
    });
  } catch (error) {
    throw describeConnectionError(error);
  }
  if (!response.ok) throw new Error("Asset could not be loaded.");
  return response;
}

export async function downloadAsset(url, token, fallbackName) {
  const response = await fetchAsset(url, token);
  const blobUrl = URL.createObjectURL(await response.blob());
  const anchor = document.createElement("a");
  anchor.href = blobUrl;
  anchor.download = response.headers.get("X-Asset-Filename") || fallbackName || "asset";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(blobUrl), 1000);
}
