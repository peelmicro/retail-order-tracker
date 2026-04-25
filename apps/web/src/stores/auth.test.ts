/** Tests for the Pinia auth store — login, logout, 401 handling, persistence. */
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

const apiFetchMock = vi.fn();
const setApiTokenMock = vi.fn();

vi.mock("@/lib/api", () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
  setApiToken: (token: string | null) => setApiTokenMock(token),
  ApiError: class ApiError extends Error {
    constructor(
      public readonly status: number,
      message: string,
    ) {
      super(message);
    }
  },
  API_URL: "http://localhost:8000",
}));

import { useAuthStore } from "@/stores/auth";

describe("useAuthStore", () => {
  beforeEach(() => {
    apiFetchMock.mockReset();
    setApiTokenMock.mockReset();
    localStorage.clear();
    setActivePinia(createPinia());
  });

  it("starts unauthenticated when localStorage is empty", () => {
    const auth = useAuthStore();
    expect(auth.token).toBeNull();
    expect(auth.user).toBeNull();
    expect(auth.isAuthenticated).toBe(false);
    // Constructor pushes the initial (null) token into the api client.
    expect(setApiTokenMock).toHaveBeenCalledWith(null);
  });

  it("rehydrates the token from localStorage on creation", () => {
    localStorage.setItem("rot:token", "persisted-token");
    setActivePinia(createPinia());
    const auth = useAuthStore();
    expect(auth.token).toBe("persisted-token");
    expect(auth.isAuthenticated).toBe(true);
    expect(setApiTokenMock).toHaveBeenCalledWith("persisted-token");
  });

  it("login stores the token, fetches the user, and persists to localStorage", async () => {
    apiFetchMock
      .mockResolvedValueOnce({ accessToken: "tok-123", tokenType: "bearer" })
      .mockResolvedValueOnce({ username: "admin", email: "a@b.c", role: "admin" });

    const auth = useAuthStore();
    await auth.login("admin", "admin123");

    expect(apiFetchMock).toHaveBeenCalledTimes(2);
    const [loginPath, loginOpts] = apiFetchMock.mock.calls[0] as [string, { method: string }];
    expect(loginPath).toBe("/auth/login");
    expect(loginOpts.method).toBe("POST");
    expect(apiFetchMock.mock.calls[1][0]).toBe("/auth/me");

    expect(auth.token).toBe("tok-123");
    expect(auth.user).toMatchObject({ username: "admin", role: "admin" });
    expect(auth.isAuthenticated).toBe(true);
    expect(localStorage.getItem("rot:token")).toBe("tok-123");
    expect(setApiTokenMock).toHaveBeenCalledWith("tok-123");
  });

  it("login propagates the underlying api error", async () => {
    apiFetchMock.mockRejectedValueOnce(new Error("Bad creds"));

    const auth = useAuthStore();
    await expect(auth.login("admin", "wrong")).rejects.toThrow("Bad creds");
    expect(auth.token).toBeNull();
    expect(localStorage.getItem("rot:token")).toBeNull();
  });

  it("logout clears the token, the user, and localStorage", () => {
    localStorage.setItem("rot:token", "stale");
    setActivePinia(createPinia());
    const auth = useAuthStore();
    expect(auth.token).toBe("stale");

    auth.logout();
    expect(auth.token).toBeNull();
    expect(auth.user).toBeNull();
    expect(auth.isAuthenticated).toBe(false);
    expect(localStorage.getItem("rot:token")).toBeNull();
    expect(setApiTokenMock).toHaveBeenLastCalledWith(null);
  });

  it("api:unauthorized event triggers a logout", () => {
    localStorage.setItem("rot:token", "expired");
    setActivePinia(createPinia());
    const auth = useAuthStore();
    expect(auth.isAuthenticated).toBe(true);

    window.dispatchEvent(new CustomEvent("api:unauthorized"));

    expect(auth.token).toBeNull();
    expect(auth.isAuthenticated).toBe(false);
    expect(localStorage.getItem("rot:token")).toBeNull();
  });

  it("fetchCurrentUser does nothing when there is no token", async () => {
    const auth = useAuthStore();
    const result = await auth.fetchCurrentUser();
    expect(result).toBeNull();
    expect(apiFetchMock).not.toHaveBeenCalled();
  });
});
