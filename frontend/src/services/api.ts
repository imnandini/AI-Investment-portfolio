const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

export type ApiError = Error & { status?: number };
export type HealthResponse = { status: string };

export async function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl}${path}`, {
      method: "GET",
      headers: { Accept: "application/json" },
      signal,
    });
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === "AbortError") throw cause;
    throw new Error(`Could not reach the API at ${apiBaseUrl}. Check that the backend is running.`);
  }

  if (!response.ok) {
    const error = new Error(`The API returned ${response.status} ${response.statusText || "error"}.`) as ApiError;
    error.status = response.status;
    throw error;
  }
  return (await response.json()) as T;
}

export function getHealth(signal?: AbortSignal) {
  return apiGet<HealthResponse>("/health", signal);
}

export { apiBaseUrl };
