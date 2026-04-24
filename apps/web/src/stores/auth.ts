/** Pinia auth store — JWT + user, persisted to localStorage. */

import { defineStore } from "pinia";
import { computed, ref } from "vue";

import { apiFetch, setApiToken } from "@/lib/api";
import type { LoginResponse, User } from "@/types/api";

const TOKEN_STORAGE_KEY = "rot:token";

export const useAuthStore = defineStore("auth", () => {
  const token = ref<string | null>(localStorage.getItem(TOKEN_STORAGE_KEY));
  const user = ref<User | null>(null);
  const isLoadingUser = ref(false);

  // Push the initial token into the api client so any early requests carry it.
  setApiToken(token.value);

  const isAuthenticated = computed(() => token.value !== null);

  async function login(username: string, password: string): Promise<void> {
    const body = new URLSearchParams({ username, password });
    const response = await apiFetch<LoginResponse>("/auth/login", {
      method: "POST",
      body,
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    });
    _setToken(response.accessToken);
    await fetchCurrentUser();
  }

  async function fetchCurrentUser(): Promise<User | null> {
    if (!token.value) return null;
    isLoadingUser.value = true;
    try {
      user.value = await apiFetch<User>("/auth/me");
      return user.value;
    } finally {
      isLoadingUser.value = false;
    }
  }

  function logout(): void {
    _setToken(null);
    user.value = null;
  }

  function _setToken(newToken: string | null) {
    token.value = newToken;
    setApiToken(newToken);
    if (newToken) {
      localStorage.setItem(TOKEN_STORAGE_KEY, newToken);
    } else {
      localStorage.removeItem(TOKEN_STORAGE_KEY);
    }
  }

  // Central 401 handler: any apiFetch() call that hits 401 dispatches the
  // event and we log out here. The router guard then pushes to /login.
  window.addEventListener("api:unauthorized", () => {
    logout();
  });

  return {
    token,
    user,
    isLoadingUser,
    isAuthenticated,
    login,
    logout,
    fetchCurrentUser,
  };
});
