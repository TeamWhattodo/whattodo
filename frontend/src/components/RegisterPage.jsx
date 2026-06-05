import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [name, setName] = useState("");
  const [department, setDepartment] = useState("");
  const [position, setPosition] = useState("");
  const [error, setError] = useState("");
  const [usernameChecked, setUsernameChecked] = useState(false);

  const checkUsername = async () => {
    if (!username) { setError("아이디를 입력해주세요."); return; }
    try {
      const res = await fetch(`/api/auth/check-username?username=${username}`);
      if (res.ok) {
        setUsernameChecked(true);
        setError("");
        alert("사용 가능한 아이디입니다.");
      } else {
        setUsernameChecked(false);
        setError("이미 사용 중인 아이디입니다.");
      }
    } catch {
      setError("중복 확인 중 오류가 발생했습니다.");
    }
  };

  const onSubmit = async (e) => {
    e.preventDefault();
    setError("");
    if (password !== passwordConfirm) {
      setError("비밀번호가 일치하지 않습니다.");
      return;
    }
    try {
      await register(username, password, name, department, position);
      navigate("/");
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="login-modal-overlay" style={{ position: "fixed" }}>
      <div className="login-modal" style={{ width: 400 }}>
        <h2 className="login-modal-title">회원가입</h2>
        <div className="login-form">
          <div style={{ display: "flex", gap: 8 }}>
            <div className="login-input-wrap" style={{ flex: 1 }}>
              <span className="login-input-icon">👤</span>
              <input
                className="login-input"
                placeholder="아이디 (3~30자 영숫자)"
                value={username}
                onChange={(e) => { setUsername(e.target.value); setUsernameChecked(false); }}
              />
            </div>
            <button
              type="button"
              onClick={checkUsername}
              style={{
                background: "#3b5bdb", color: "#fff", border: "none",
                borderRadius: 10, padding: "0 14px", fontSize: 13,
                fontWeight: 500, cursor: "pointer", whiteSpace: "nowrap"
              }}
            >
              중복확인
            </button>
          </div>

          <div className="login-input-wrap">
            <span className="login-input-icon">✏️</span>
            <input
              className="login-input"
              placeholder="이름"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>

          <div className="login-input-wrap">
            <span className="login-input-icon">🏢</span>
            <input
              className="login-input"
              placeholder="부서"
              value={department}
              onChange={(e) => setDepartment(e.target.value)}
            />
          </div>

          <div className="login-input-wrap">
            <span className="login-input-icon">💼</span>
            <input
              className="login-input"
              placeholder="직급"
              value={position}
              onChange={(e) => setPosition(e.target.value)}
            />
          </div>

          <div className="login-input-wrap">
            <span className="login-input-icon">🔒</span>
            <input
              className="login-input"
              type="password"
              placeholder="비밀번호 (8자 이상)"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          <div className="login-input-wrap">
            <span className="login-input-icon">🔒</span>
            <input
              className="login-input"
              type="password"
              placeholder="비밀번호 확인"
              value={passwordConfirm}
              onChange={(e) => setPasswordConfirm(e.target.value)}
            />
          </div>

          {error && <div className="login-error">{error}</div>}

          <button className="login-submit-btn" onClick={onSubmit}>가입하기</button>

          <div className="login-modal-footer">
            이미 계정이 있으신가요? <Link to="/login" className="login-register-link">로그인</Link>
          </div>
        </div>
      </div>
    </div>
  );
}
