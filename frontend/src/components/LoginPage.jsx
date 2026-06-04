import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const onSubmit = async (e) => {
    e.preventDefault();
    setError("");
    try {
      await login(username, password);
      navigate("/");
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <form onSubmit={onSubmit} style={{ maxWidth: 320, margin: "80px auto", display: "flex", flexDirection: "column", gap: 12 }}>
      <h2>로그인</h2>
      <input placeholder="아이디" value={username} onChange={(e) => setUsername(e.target.value)} />
      <input type="password" placeholder="비밀번호" value={password} onChange={(e) => setPassword(e.target.value)} />
      {error && <div style={{ color: "red" }}>{error}</div>}
      <button type="submit">로그인</button>
      <Link to="/register">계정 만들기</Link>
    </form>
  );
}
