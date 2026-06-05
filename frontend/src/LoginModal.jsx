import { useState } from "react";
import { useAuth } from "./context/AuthContext";

const UserIcon = () => (
  <svg className="login-input-icon" viewBox="0 0 24 24" width="18" height="18"
       fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="7" r="4" />
    <path d="M6 21v-2a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v2" />
  </svg>
);

const LockIcon = () => (
  <svg className="login-input-icon" viewBox="0 0 24 24" width="18" height="18"
       fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="5" y="11" width="14" height="10" rx="2" />
    <path d="M8 11V7a4 4 0 0 1 8 0v4" />
  </svg>
);

const EyeIcon = ({ off }) => (
  <svg viewBox="0 0 24 24" width="18" height="18"
       fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    {off ? (
      <>
        <path d="M3 3l18 18" />
        <path d="M10.6 10.6a2 2 0 0 0 2.8 2.8" />
        <path d="M9.9 4.2A9.1 9.1 0 0 1 12 4c5 0 9 4.5 9 8a12 12 0 0 1-2.2 3.3M6.6 6.6C4.1 8 2.5 10.3 2.5 12c0 3.5 4 8 9 8a9.1 9.1 0 0 0 4.1-1" />
      </>
    ) : (
      <>
        <path d="M2.5 12C4 8.5 8 5 12 5s8 3.5 9.5 7c-1.5 3.5-5.5 7-9.5 7s-8-3.5-9.5-7Z" />
        <circle cx="12" cy="12" r="3" />
      </>
    )}
  </svg>
);

export default function LoginModal({ onClose }) {
  const { login, register } = useAuth();
  const [mode, setMode] = useState("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [name, setName] = useState("");
  const [department, setDepartment] = useState("");
  const [position, setPosition] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);
  const [usernameChecked, setUsernameChecked] = useState(false);

  const resetFields = () => {
    setUsername(""); setPassword(""); setPasswordConfirm("");
    setName(""); setDepartment(""); setPosition("");
    setError(""); setSuccess(""); setUsernameChecked(false);
  };

  const checkUsername = async () => {
    if (!username) { setError("아이디를 입력해주세요."); return; }
    if (username.length < 3) { setError("아이디는 3자 이상 입력해주세요."); return; }
    try {
      const res = await fetch(`http://localhost:8000/api/auth/check-username?username=${username}`, {
        credentials: "include",
        cache: "no-store"
      });
      const data = await res.json();
      if (res.ok) {
        setUsernameChecked(true);
        setError("✅ 사용 가능한 아이디입니다.");
      } else {
        setUsernameChecked(false);
        setError(data.detail || "이미 사용 중인 아이디입니다.");
      }
    } catch {
      setUsernameChecked(false);
      setError("중복 확인 중 오류가 발생했습니다.");
    }
  };

  const onSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    if (mode === "register") {
      if (password !== passwordConfirm) {
        setError("비밀번호가 일치하지 않습니다.");
        return;
      }
    }
    setLoading(true);
    try {
      if (mode === "login") {
        await login(username, password);
        onClose();
      } else {
        await register(username, password, name, department, position);
        setSuccess("회원가입이 완료되었습니다! 로그인해 주세요.");
        setPassword("");
        setTimeout(() => {
          setMode("login");
          setSuccess("");
        }, 2000);
      }
    } catch (err) {
      setError(typeof err.message === "string" ? err.message : "오류가 발생했습니다.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-modal-overlay" onClick={onClose}>
      <div className="login-modal" onClick={(e) => e.stopPropagation()}>
        <button className="login-modal-close" onClick={onClose} aria-label="닫기">×</button>

        <h2 className="login-modal-title">{mode === "login" ? "로그인" : "회원가입"}</h2>

        <form onSubmit={onSubmit} className="login-form">

          {mode === "register" ? (
            <div style={{ display: "flex", gap: 8 }}>
              <div className="login-input-wrap" style={{ flex: 1 }}>
                <UserIcon />
                <input
                  className="login-input"
                  type="text"
                  placeholder="아이디 (3~30자 영숫자)"
                  value={username}
                  onChange={(e) => { setUsername(e.target.value); setUsernameChecked(false); setError(""); }}
                />
              </div>
              <button
                type="button"
                onClick={checkUsername}
                style={{
                  background: "#3b5bdb", color: "#fff", border: "none",
                  borderRadius: 10, padding: "0 14px", fontSize: 13,
                  fontWeight: 500, cursor: "pointer", whiteSpace: "nowrap", height: 46
                }}
              >
                중복확인
              </button>
            </div>
          ) : (
            <div className="login-input-wrap">
              <UserIcon />
              <input
                className="login-input"
                type="text"
                placeholder="아이디"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoFocus
              />
            </div>
          )}

          {mode === "register" && (
            <>
              <div className="login-input-wrap">
                <span className="login-input-icon">✏️</span>
                <input className="login-input" type="text" placeholder="이름" value={name} onChange={(e) => setName(e.target.value)} />
              </div>
              <div className="login-input-wrap">
                <span className="login-input-icon">🏢</span>
                <input className="login-input" type="text" placeholder="부서" value={department} onChange={(e) => setDepartment(e.target.value)} />
              </div>
              <div className="login-input-wrap">
                <span className="login-input-icon">💼</span>
                <input className="login-input" type="text" placeholder="직급" value={position} onChange={(e) => setPosition(e.target.value)} />
              </div>
            </>
          )}

          <div className="login-input-wrap">
            <LockIcon />
            <input
              className="login-input"
              type={showPassword ? "text" : "password"}
              placeholder="비밀번호 (8자 이상)"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <button type="button" className="login-eye-btn" onClick={() => setShowPassword((v) => !v)}>
              <EyeIcon off={showPassword} />
            </button>
          </div>

          {mode === "register" && (
            <div className="login-input-wrap">
              <LockIcon />
              <input
                className="login-input"
                type={showPassword ? "text" : "password"}
                placeholder="비밀번호 확인"
                value={passwordConfirm}
                onChange={(e) => setPasswordConfirm(e.target.value)}
              />
            </div>
          )}

          {error && <div style={{ color: error.startsWith("✅") ? "#1E8449" : "#C53030", fontSize: 13 }}>{error}</div>}
          {success && <div style={{ color: "#276749", fontSize: 13, fontWeight: 600 }}>{success}</div>}

          <button type="submit" className="login-submit-btn" disabled={loading}>
            {loading ? "처리 중..." : mode === "login" ? "로그인" : "회원가입"}
          </button>
        </form>

        <div className="login-modal-footer">
          {mode === "login" ? (
            <>계정이 없으신가요?{" "}
              <button className="login-register-link" onClick={() => { setMode("register"); resetFields(); }}>
                회원가입
              </button>
            </>
          ) : (
            <>이미 계정이 있으신가요?{" "}
              <button className="login-register-link" onClick={() => { setMode("login"); resetFields(); }}>
                로그인
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
