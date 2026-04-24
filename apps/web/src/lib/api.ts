/** Thin wrapper around fetch() with JWT injection + typed errors. */

import type { ApiErrorShape } from "@/types/api";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

/** Read-only accessor for the current token. Set via auth store. */
let currentToken: string | null = null;

export function setApiToken(token: string | null) {
  currentToken = token;
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

interface FetchOptions extends Omit<RequestInit, "body"> {
  body?: BodyInit | Record<string, unknown> | URLSearchParams;
}

export async function apiFetch<T>(path: string, options: FetchOptions = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (currentToken) {
    headers.set("Authorization", `Bearer ${currentToken}`);
  }

  let body: BodyInit | undefined;
  if (options.body instanceof URLSearchParams || options.body instanceof FormData) {
    body = options.body;
  } else if (options.body !== undefined && typeof options.body === "object") {
    body = JSON.stringify(options.body);
    if (!headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
  } else if (typeof options.body === "string") {
    body = options.body;
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
    body,
  });

  if (response.status === 401) {
    // Fire a custom event; the auth store listens and logs out centrally.
    window.dispatchEvent(new CustomEvent("api:unauthorized"));
    throw new ApiError(401, "Unauthorized");
  }

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const parsed = (await response.json()) as ApiErrorShape;
      if (parsed.detail) detail = parsed.detail;
    } catch {
      /* non-JSON error body — keep statusText */
    }
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export { API_URL };
