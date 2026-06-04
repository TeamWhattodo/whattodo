const BASE = `${import.meta.env.VITE_API_URL ?? "/api"}/auth`;

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = "요청 실패";
    try { detail = (await res.json()).detail || detail; } catch {}
    throw new Error(detail);
  }
  return res.status === 200 || res.status === 201 ? res.json() : null;
}

export const register = (username, password, name, department, position) =>
  request("/register", { method: "POST", body: JSON.stringify({ username, password, name, department, position }) });

export const login = (username, password) =>
  request("/login", { method: "POST", body: JSON.stringify({ username, password }) });

export const logout = () => request("/logout", { method: "POST" });

export async function fetchMe() {
  const res = await fetch(`${BASE}/me`, { credentials: "include" });
  return res.ok ? res.json() : null;
}
