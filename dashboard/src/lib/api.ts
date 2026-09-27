import { z } from "zod";
import { inputsSchema, snapshotSchema, startSchema } from "./contracts";

export class ApiError extends Error {
  constructor(public code: string, message: string, public status = 0) { super(message); }
}

/** Only a public API origin belongs in this setting. No proxy or secret-bearing URL. */
export function apiBase(): string {
  const url = new URL(process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000");
  if (!["http:", "https:"].includes(url.protocol) || url.username || url.password || url.search || url.hash || url.pathname !== "/") {
    throw new ApiError("CONFIGURATION", "Configure a valid public API origin.");
  }
  return url.origin;
}

async function request<T>(path: string, schema: z.ZodType<T>, options: RequestInit = {}): Promise<T> {
  const controller = new AbortController();
  const abort = () => controller.abort();
  if (options.signal?.aborted) controller.abort();
  options.signal?.addEventListener("abort", abort, { once: true });
  const timer = setTimeout(abort, 12000);
  try {
    const response = await fetch(`${apiBase()}${path}`, { ...options, cache: "no-store", signal: controller.signal });
    let data: unknown;
    try { data = await response.json(); }
    catch { throw new ApiError("INVALID_RESPONSE", "The server returned an unreadable response. Check the backend connection.", response.status); }
    if (!response.ok) {
      const error = z.object({ error: z.object({ code: z.string(), message: z.string() }) }).safeParse(data);
      throw new ApiError(error.success ? error.data.error.code : "SERVER_ERROR", error.success ? error.data.error.message : "The server could not complete this request.", response.status);
    }
    const parsed = schema.safeParse(data);
    if (!parsed.success) throw new ApiError("INVALID_RESPONSE", "The response does not match the dashboard contract. Reconnect or check the backend.", response.status);
    return parsed.data;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError("CONNECTION", "Cannot reach the backend. Check that it is running and allows this dashboard's origin.");
  } finally {
    clearTimeout(timer);
    options.signal?.removeEventListener("abort", abort);
  }
}

export const loadInputs = (signal?: AbortSignal) => request("/api/demo-inputs", inputsSchema, { signal });
export const loadSnapshot = (id: string, signal?: AbortSignal) => request(`/api/runs/${encodeURIComponent(id)}`, snapshotSchema, { signal });
export const startRun = (inputId: string, key: string, signal?: AbortSignal) => request("/api/runs", startSchema, {
  method: "POST", signal, headers: { "Content-Type": "application/json", "Idempotency-Key": key }, body: JSON.stringify({ input_id: inputId }),
});
export const eventUrl = (id: string, after: number) => `${apiBase()}/api/runs/${encodeURIComponent(id)}/events?after_event_id=${after}`;
