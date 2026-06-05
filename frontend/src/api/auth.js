const BASE = `${import.meta.env.VITE_API_URL ?? "/api"}/auth`;

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = "요청 실패";
    try {
      const body = await res.json();
      const raw = body.detail;
      if (Array.isArray(raw)) {
        // Pydantic validation 에러 배열 → "Value error, " 접두어 제거 후 한국어 메시지만 추출
        detail = raw.map(e => {
          const msg = e.msg || JSON.stringify(e);
          return msg.replace(/^Value error,\s*/i, "");
        }).join(", ");
      } else if (typeof raw === "string") {
        detail = raw.replace(/^Value error,\s*/i, "");
      }
    } catch {}
    throw new Error(detail);
  }
  // 성공 응답 — JSON 파싱 실패해도 null 반환 (회원가입 성공 처리)
  if (res.status === 200 || res.status === 201) {
    try { return await res.json(); } catch { return null; }
  }
  return null;
}

export const register = (username, password, name, department, position) =>
  request("/register", { method: "POST", body: JSON.stringify({ username, password, name, department, position }) });

export const login = (username, password) =>
  request("/login", { method: "POST", body: JSON.stringify({ username, password }) });

export const logout = () => request("/logout", { method: "POST" });

export const refresh = () => request("/refresh", { method: "POST" });

export async function fetchMe() {
  const res = await fetch(`${BASE}/me`, { credentials: "include" });
  return res.ok ? res.json() : null;
}

export const updateMe = (data) =>
  request("/me", { method: "PUT", body: JSON.stringify(data) });

export const deleteMe = () =>
  request("/me", { method: "DELETE" });
