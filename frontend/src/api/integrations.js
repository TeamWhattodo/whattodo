const BASE = `${import.meta.env.VITE_API_URL ?? "/api"}/integrations`;

async function request(path = "", options = {}) {
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

export const getIntegrations = () => request("/", { method: "GET" });

export const connectIntegration = (source, payload) =>
  request(`/${source}`, { method: "POST", body: JSON.stringify(payload) });

export const disconnectIntegration = (source) =>
  request(`/${source}`, { method: "DELETE" });
