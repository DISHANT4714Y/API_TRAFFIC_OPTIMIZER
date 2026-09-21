/**
 * Centralized API Service for Intelligent API Traffic Optimizer Dashboard.
 * Communicates with the FastAPI backend using VITE_API_BASE_URL or fallback.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

/**
 * Checks backend health status.
 * @returns {Promise<{ online: boolean, status?: string }>}
 */
export async function checkHealth() {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 3500);

    const response = await fetch(`${API_BASE_URL}/health`, {
      method: 'GET',
      signal: controller.signal,
    });
    clearTimeout(timeoutId);

    if (response.ok) {
      const data = await response.json();
      return { online: true, status: data.status || 'ok' };
    }
    return { online: false, status: `HTTP ${response.status}` };
  } catch (err) {
    return { online: false, error: err.message };
  }
}

/**
 * Fetches current cache and optimization statistics from backend.
 * @returns {Promise<Object>}
 */
export async function getStats() {
  const response = await fetch(`${API_BASE_URL}/cache/stats`, {
    method: 'GET',
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch stats: HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Sends a live resource request through the optimizer proxy.
 * Measures roundtrip latency and reads cache headers.
 * 
 * @param {string} resourceId 
 * @param {Object} [params] 
 * @returns {Promise<Object>}
 */
export async function sendRequest(resourceId, params = {}) {
  const cleanId = resourceId.trim() || 'default';
  const url = new URL(`${API_BASE_URL}/proxy/data/${encodeURIComponent(cleanId)}`);

  Object.entries(params).forEach(([key, val]) => {
    if (val !== undefined && val !== null && val !== '') {
      url.searchParams.append(key, val);
    }
  });

  const startTime = performance.now();

  try {
    const response = await fetch(url.toString(), {
      method: 'GET',
    });

    const endTime = performance.now();
    const latencyMs = Math.round(endTime - startTime);

    // Read cache indication header set by Phase 5 optimizer
    const xCache = (response.headers.get('X-Cache') || 'UNKNOWN').toUpperCase();
    const requestId = response.headers.get('x-request-id') || null;
    const mockDelay = response.headers.get('x-mock-delay-ms') || null;

    let data;
    try {
      data = await response.json();
    } catch {
      data = { raw: await response.text() };
    }

    return {
      ok: response.ok,
      status: response.status,
      resourceId: cleanId,
      xCache,
      source: xCache === 'HIT' ? 'Cache' : (xCache === 'MISS' ? 'Mock API' : 'Direct'),
      latencyMs,
      requestId,
      mockDelay,
      data,
    };
  } catch (err) {
    const endTime = performance.now();
    return {
      ok: false,
      status: 0,
      resourceId: cleanId,
      xCache: 'ERROR',
      source: 'Network Error',
      latencyMs: Math.round(endTime - startTime),
      error: err.message || 'Network request failed',
      data: { error: 'Failed to reach optimizer proxy endpoint.' },
    };
  }
}

/**
 * Resets experiment stats and clears cache on the backend.
 * Uses POST /cache/reset, falling back to /cache/clear.
 * 
 * @returns {Promise<Object>}
 */
export async function resetExperiment() {
  try {
    const response = await fetch(`${API_BASE_URL}/cache/reset`, {
      method: 'POST',
    });
    if (response.ok) {
      return response.json();
    }
  } catch {
    // fallback if reset endpoint is not reachable
  }

  // Fallback to /cache/clear
  const fallbackResp = await fetch(`${API_BASE_URL}/cache/clear`, {
    method: 'POST',
  });
  if (!fallbackResp.ok) {
    throw new Error(`Failed to reset experiment: HTTP ${fallbackResp.status}`);
  }
  return fallbackResp.json();
}
