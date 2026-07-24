const TOKEN_KEY = "mailctl_token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || "";
}
export function setToken(t) {
  if (t) localStorage.setItem(TOKEN_KEY, t);
  else localStorage.removeItem(TOKEN_KEY);
}

async function request(path, { method = "GET", body, form } = {}) {
  const headers = {};
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let payload;
  if (form) {
    payload = new URLSearchParams(form).toString();
    headers["Content-Type"] = "application/x-www-form-urlencoded";
  } else if (body !== undefined) {
    payload = JSON.stringify(body);
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`/api${path}`, { method, headers, body: payload });
  if (res.status === 401) {
    setToken("");
    if (!location.pathname.includes("/login")) location.href = "/login";
    throw new Error("Sesión expirada");
  }
  if (!res.ok) {
    let detail = `Error ${res.status}`;
    try {
      const j = await res.json();
      detail = j.detail || detail;
    } catch {}
    throw new Error(detail);
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  login: (email, password) =>
    request("/auth/login", { method: "POST", form: { username: email, password } }),
  me: () => request("/auth/me"),
  changePassword: (current_password, new_password) =>
    request("/change-password", { method: "POST", body: { current_password, new_password } }),
  stats: () => request("/stats"),

  accounts: () => request("/accounts"),
  createAccount: (data) => request("/accounts", { method: "POST", body: data }),
  updateAccount: (id, data) => request(`/accounts/${id}`, { method: "PATCH", body: data }),
  deleteAccount: (id) => request(`/accounts/${id}`, { method: "DELETE" }),
  testAccount: (id) => request(`/accounts/${id}/test`, { method: "POST" }),
  syncAccount: (id) => request(`/accounts/${id}/sync`, { method: "POST" }),
  authorizeMicrosoft: (id) =>
    request(`/accounts/${id}/microsoft/authorize`, { method: "POST" }),

  messages: (params) => request(`/messages?${new URLSearchParams(params)}`),
  message: (id) => request(`/messages/${id}`),

  alerts: (params) => request(`/alerts?${new URLSearchParams(params)}`),
  resolveAlert: (id) => request(`/alerts/${id}/resolve`, { method: "POST" }),
};
