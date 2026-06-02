import { useState } from "react";
import { Link } from "react-router-dom";

/* Tabler 아이콘(ti-user, ti-lock, ti-eye)을 인라인 SVG로 대체 — 별도 폰트/CDN 의존성 없이 동작 */
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

export default function LoginModal({ onClose, onLogin }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  // UI 전용 — 백엔드 인증 없이 입력한 아이디만 전달한다. (모달 닫기는 onLogin이 처리)
  const onSubmit = (e) => {
    e.preventDefault();
    onLogin?.(username);
  };

  return (
    <div className="login-modal-overlay" onClick={onClose}>
      <div className="login-modal" onClick={(e) => e.stopPropagation()}>
        <button className="login-modal-close" onClick={onClose} aria-label="닫기">×</button>

        <h2 className="login-modal-title">로그인</h2>

        <form onSubmit={onSubmit} className="login-form">
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

          <div className="login-input-wrap">
            <LockIcon />
            <input
              className="login-input"
              type={showPassword ? "text" : "password"}
              placeholder="비밀번호"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <button
              type="button"
              className="login-eye-btn"
              onClick={() => setShowPassword((v) => !v)}
              aria-label={showPassword ? "비밀번호 숨기기" : "비밀번호 표시"}
            >
              <EyeIcon off={showPassword} />
            </button>
          </div>

          <button type="submit" className="login-submit-btn">
            로그인
          </button>
        </form>

        <div className="login-modal-footer">
          계정이 없으신가요?{" "}
          <Link to="/register" className="login-register-link" onClick={onClose}>
            회원가입
          </Link>
        </div>
      </div>
    </div>
  );
}
