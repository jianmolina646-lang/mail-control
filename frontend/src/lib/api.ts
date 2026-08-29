import type { TokenPair, User } from "./types";

const API_URL = import.meta.env.VITE_API_URL ?? "";
const ACCESS_KEY = "mce.access";
const USER_KEY = "mce.user";
const SESSION_EVENT = "mce.session-change";
const SESSION_STARTED_KEY = "mce.session-started";
const LAST_ACTIVITY_KEY = "mce.last-activity";
const IDLE_TIMEOUT_MS = 30 * 60 * 1000;
const ABSOLUTE_TIMEOUT_MS = 12 * 60 * 60 * 1000;

function notifySessionChange() {
  window.dispatchEvent(new Event(SESSION_EVENT));
}

export function saveSession(tokens: TokenPair) {
  const now = Date.now();
  sessionStorage.setItem(ACCESS_KEY, tokens.access_token);
  if (!localStorage.getItem(SESSION_STARTED_KEY)) {
    localStorage.setItem(SESSION_STARTED_KEY, String(now));
  }
  localStorage.setItem(LAST_ACTIVITY_KEY, String(now));
  localStorage.setItem(USER_KEY, JSON.stringify(tokens.user));
  notifySessionChange();
}

export function clearSession() {
  void fetch(`${API_URL}/v1/auth/logout`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: "{}",
  });
  sessionStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(USER_KEY);
  localStorage.removeItem(SESSION_STARTED_KEY);
  localStorage.removeItem(LAST_ACTIVITY_KEY);
  notifySessionChange();
}

export function currentUser(): User | null {
  try {
    const value = localStorage.getItem(USER_KEY);
    return value ? (JSON.parse(value) as User) : null;
  } catch {
    return null;
  }
}

export function sessionExpired(now = Date.now()) {
  const startedAt = Number(localStorage.getItem(SESSION_STARTED_KEY));
  const lastActivity = Number(localStorage.getItem(LAST_ACTIVITY_KEY));
  if (!startedAt || !lastActivity) return hasSession();
  return now - lastActivity >= IDLE_TIMEOUT_MS || now - startedAt >= ABSOLUTE_TIMEOUT_MS;
}

export function recordSessionActivity(now = Date.now()) {
  if (!hasSession() || sessionExpired(now)) return;
  const previous = Number(localStorage.getItem(LAST_ACTIVITY_KEY));
  if (!previous || now - previous >= 15_000) {
    localStorage.setItem(LAST_ACTIVITY_KEY, String(now));
  }
}

async function refreshSession(): Promise<boolean> {
  const response = await fetch(`${API_URL}/v1/auth/refresh`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: "{}",
  });
  if (!response.ok) {
    clearSession();
    return false;
  }
  saveSession((await response.json()) as TokenPair);
  return true;
}

export async function api<T>(
  path: string,
  init: RequestInit = {},
  canRefresh = true,
): Promise<T> {
  const token = sessionStorage.getItem(ACCESS_KEY);
  if (token) recordSessionActivity();
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body) headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers,
    credentials: "include",
  });
  if (response.status === 401 && canRefresh && (await refreshSession())) {
    return api<T>(path, init, false);
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? "No fue posible completar la solicitud.");
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function apiBlob(path: string, canRefresh = true): Promise<Blob> {
  const token = sessionStorage.getItem(ACCESS_KEY);
  if (token) recordSessionActivity();
  const headers = new Headers({ Accept: "image/*" });
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${API_URL}${path}`, { headers, credentials: "include" });
  if (response.status === 401 && canRefresh && (await refreshSession())) {
    return apiBlob(path, false);
  }
  if (!response.ok) throw new Error("No fue posible cargar la imagen.");
  return response.blob();
}

export function hasSession() {
  return Boolean(sessionStorage.getItem(ACCESS_KEY) || localStorage.getItem(USER_KEY));
}

export function subscribeSession(onChange: () => void) {
  window.addEventListener(SESSION_EVENT, onChange);
  window.addEventListener("storage", onChange);
  return () => {
    window.removeEventListener(SESSION_EVENT, onChange);
    window.removeEventListener("storage", onChange);
  };
}
