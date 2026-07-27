async function request(path, { method = "GET", body, form } = {}) {
  const headers = {};
  const unsafe = !["GET", "HEAD", "OPTIONS"].includes(method);

  let payload;
  if (form) {
    payload = new URLSearchParams(form).toString();
    headers["Content-Type"] = "application/x-www-form-urlencoded";
  } else if (body !== undefined) {
    payload = JSON.stringify(body);
    headers["Content-Type"] = "application/json";
  }
  if (unsafe) {
    const csrf = document.cookie
      .split("; ")
      .find((item) => item.startsWith("mailctl_csrf="))
      ?.split("=")
      .slice(1)
      .join("=");
    if (csrf) headers["X-CSRF-Token"] = decodeURIComponent(csrf);
  }

  const res = await fetch(`/api${path}`, {
    method,
    headers,
    body: payload,
    credentials: "same-origin",
  });
  if (res.status === 401 && !location.pathname.includes("/login")) {
    location.href = "/login";
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

function query(params = {}) {
  return new URLSearchParams(
    Object.entries(params).filter(([, value]) =>
      value !== undefined && value !== null && value !== ""
    ),
  ).toString();
}

export const api = {
  login: (email, password, otp = "") =>
    request("/auth/login", { method: "POST", form: { username: email, password, otp } }),
  logout: () => request("/auth/logout", { method: "POST" }),
  me: () => request("/auth/me"),
  changePassword: (current_password, new_password) =>
    request("/change-password", { method: "POST", body: { current_password, new_password } }),
  twoFactorStatus: () => request("/auth/2fa"),
  setupTwoFactor: (current_password) =>
    request("/auth/2fa/setup", { method: "POST", body: { current_password } }),
  confirmTwoFactor: (code) =>
    request("/auth/2fa/confirm", { method: "POST", body: { code } }),
  disableTwoFactor: (current_password, code) =>
    request("/auth/2fa", { method: "DELETE", body: { current_password, code } }),
  syncHistory: (limit = 100) => request(`/sync-history?limit=${limit}`),
  stats: () => request("/stats"),

  accounts: () => request("/accounts"),
  createAccount: (data) => request("/accounts", { method: "POST", body: data }),
  updateAccount: (id, data) => request(`/accounts/${id}`, { method: "PATCH", body: data }),
  deleteAccount: (id) => request(`/accounts/${id}`, { method: "DELETE" }),
  testAccount: (id) => request(`/accounts/${id}/test`, { method: "POST" }),
  syncAccount: (id) => request(`/accounts/${id}/sync`, { method: "POST" }),
  authorizeMicrosoft: (id) =>
    request(`/accounts/${id}/microsoft/authorize`, { method: "POST" }),

  messages: (params) => request(`/messages?${query(params)}`),
  message: (id) => request(`/messages/${id}`),

  alerts: (params) => request(`/alerts?${query(params)}`),
  resolveAlert: (id) => request(`/alerts/${id}/resolve`, { method: "POST" }),

  subscriptions: (params = {}) =>
    request(`/subscriptions?${query(params)}`),
  subscription: (id) => request(`/subscriptions/${id}`),
  subscriptionStats: () => request("/subscriptions/stats"),
  rebuildSubscriptions: () =>
    request("/subscriptions/rebuild", { method: "POST" }),
};
