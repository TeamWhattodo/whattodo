import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const onSubmit = async (e) => {
    e.preventDefault();
    setError("");
    try {
      await register(username, password);
      navigate("/");
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <form onSubmit={onSubmit} style={{ maxWidth: 320, margin: "80px auto", display: "flex", flexDirection: "column", gap: 12 }}>
      <h2>회원가입</h2>
      <input placeholder="아이디 (3~30자 영숫자)" value={username} onChange={(e) => setUsername(e.target.value)} />
      <input type="password" placeholder="비밀번호 (8자 이상)" value={password} onChange={(e) => setPassword(e.target.value)} />
      {error && <div style={{ color: "red" }}>{error}</div>}
      <button type="submit">가입하기</button>
      <Link to="/login">로그인으로</Link>
    </form>
  );
}
