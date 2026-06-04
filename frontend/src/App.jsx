import { useState, useEffect, useRef } from "react";
import axios from "axios";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import "./index.css";
import LoginModal from "./LoginModal";
import IntegrationsModal from "./components/IntegrationsModal";
import { useAuth } from "./context/AuthContext";
import { getIntegrations } from "./api/integrations";

const API = import.meta.env.VITE_API_URL ?? "/api";

const MENUS = [
  { id: "assistant", icon: "🖥️", label: "업무 도우미", query: null },
];

export default function App() {
  const { user: authUser, logout } = useAuth();
  const [sessionId] = useState(() => {
    const key = "wt_session_id";
    let id = sessionStorage.getItem(key);
    if (!id) { id = crypto.randomUUID(); sessionStorage.setItem(key, id); }
    return id;
  });
  const [activeMenu, setActiveMenu]       = useState("assistant");
  const [messages, setMessages]           = useState([]);
  const [chatHistory, setChatHistory]     = useState([]);
  const [input, setInput]                 = useState("");
  const [loading, setLoading]             = useState(false);
  const [toolLogs, setToolLogs]           = useState([]);
  const [integrations, setIntegrations]   = useState({ slack: false, jira: false });
  const [briefingBadge, setBriefingBadge]     = useState(3);
  const [policyStatus, setPolicyStatus]       = useState(null);
  const [policyBannerDismissed, setPolicyBannerDismissed] = useState(false);
  const [showLoginModal, setShowLoginModal]   = useState(false);
  const [showIntegrationsModal, setShowIntegrationsModal] = useState(false);
  const [attachedFile, setAttachedFile]       = useState(null);
  const chatEndRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, toolLogs]);

  useEffect(() => {
    if (!authUser) {
      setMessages([]);
      setChatHistory([]);
    }
  }, [authUser]);

  const fetchIntegrations = async () => {
    if (!authUser) {
      setIntegrations({ slack: false, jira: false, notion: false, gmail: false, calendar: false });
      return;
    }
    try {
      const data = await getIntegrations();
      const map = {};
      data.forEach(item => map[item.source] = item.connected);
      setIntegrations(map);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    fetchIntegrations();
  }, [authUser]);

  useEffect(() => {
    // Handle Google OAuth callback if redirected to frontend with code and state
    const urlParams = new URLSearchParams(window.location.search);
    const code = urlParams.get("code");
    const state = urlParams.get("state");

    if (code && state) {
      setLoading(true);
      // React StrictMode 더블 호출 방지를 위해 파라미터 즉시 제거
      window.history.replaceState({}, document.title, window.location.pathname);

      axios.get(`${API}/integrations/google/callback?state=${encodeURIComponent(state)}&code=${encodeURIComponent(code)}`, {
        withCredentials: true // needed if we depend on cookies for user identification though state is used here
      })
      .then(() => {
        alert("Google 계정 연동이 완료되었습니다!");
        fetchIntegrations();
      })
      .catch((err) => {
        console.error("Google OAuth Error:", err);
        alert("구글 연동 실패: " + (err.response?.data?.detail || err.message));
      })
      .finally(() => {
        setLoading(false);
      });
    }
  }, []);

  useEffect(() => {
    let timer;
    const poll = () => {
      axios.get(`${API}/policy/status`).then(res => {
        setPolicyStatus(res.data);
        if (res.data.status === "running" || res.data.status === "idle") {
          timer = setTimeout(poll, 10000);
        }
      }).catch(() => {});
    };
    poll();
    return () => clearTimeout(timer);
  }, []);

  const handleMenuClick = (menu) => {
    setActiveMenu(menu.id);
    if (menu.query) sendMessage(menu.query);
  };

  const sendMessage = async (query) => {
    if (!query?.trim() || loading) return;
    setLoading(true);
    setToolLogs([]);

    const displayContent = attachedFile ? `📎 ${attachedFile.name}\n${query}` : query;
    setMessages(prev => [...prev, { role: "user", content: displayContent }]);
    setInput("");

    let filePayload = {};
    if (attachedFile) {
      try {
        filePayload = { file_name: attachedFile.name, file_data: await readFileAsBase64(attachedFile) };
      } catch {
        filePayload = {};
      }
      clearAttachment();
    }

    try {
      const res = await fetch(`${API}/chat`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, session_id: sessionId, chat_history: chatHistory, ...filePayload }),
      });

      if (res.status === 401) {
        throw new Error("로그인이 필요합니다. 사이드바에서 로그인해주세요.");
      }
      if (!res.ok) {
        throw new Error(`서버 오류: ${res.status}`);
      }

      const reader  = res.body.getReader();
      const decoder = new TextDecoder();
      let responseText = "처리 중 오류가 발생했습니다.";
      let newHistory   = chatHistory;
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop();

        for (const line of lines) {
          if (!line.trim() || !line.startsWith("data: ")) continue;
          try {
            const event = JSON.parse(line.slice(6));
            if (event.type === "tool_call") {
              setToolLogs(prev => [...prev, `🔧 ${event.tool} 호출 중...`]);
            } else if (event.type === "tool_result") {
              setToolLogs(prev => [...prev, `✅ ${event.tool} 완료`]);
            } else if (event.type === "done") {
              responseText = event.text;
              newHistory   = event.history;
              if (event.files?.length) {
                setMessages(prev => [...prev, { role: "assistant", content: responseText, files: event.files }]);
                setChatHistory(newHistory);
                return;
              }
            }
          } catch (e) {
            console.error("SSE JSON 파싱 오류:", e, "Line:", line);
          }
        }
      }

      setChatHistory(newHistory);
      setMessages(prev => [...prev, { role: "assistant", content: responseText }]);
      if (activeMenu === "briefing") setBriefingBadge(0);
    } catch (error) {
      console.error("채팅 요청 실패:", error);
      setMessages(prev => [...prev, { role: "assistant", content: error.message || "네트워크 오류가 발생했습니다." }]);
    } finally {
      setToolLogs([]);
      setLoading(false);
    }
  };

  const ALLOWED_EXTS = ["txt", "md", "csv", "json", "pdf", "jpg", "jpeg", "png", "gif", "webp"];

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const ext = file.name.rsplit ? file.name.split(".").pop().toLowerCase() : file.name.split(".").pop().toLowerCase();
    if (!ALLOWED_EXTS.includes(ext)) {
      alert(`지원 파일: ${ALLOWED_EXTS.join(", ")}`);
      e.target.value = "";
      return;
    }
    setAttachedFile(file);
  };

  const readFileAsBase64 = (file) => new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result.split(",")[1]);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });

  const clearAttachment = () => {
    setAttachedFile(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  const handleInputChange = (e) => {
    setInput(e.target.value);
    e.target.style.height = "44px";
    e.target.style.height = Math.min(e.target.scrollHeight, 120) + "px";
  };

  const currentMenu = MENUS.find(m => m.id === activeMenu);

  return (
    <>
      <div className="sidebar">
        <div className="sidebar-logo">☑ WhatToDo</div>
        {MENUS.map(menu => (
          <button
            key={menu.id}
            className={`sidebar-menu-item ${activeMenu === menu.id ? "active" : ""}`}
            onClick={() => handleMenuClick(menu)}
          >
            <span>{menu.icon}</span>
            <span>{menu.label}</span>
          </button>
        ))}

        <div className="sidebar-section-label">연동</div>
        <div className="sidebar-integration">
          <span>✉️</span>
          <span>Google</span>
          <span className={`int-status ${integrations.google ? "" : "disconnected"}`}>
            {integrations.google ? "연결됨" : "미연결"}
          </span>
        </div>
        <div className="sidebar-integration">
          <span>#</span>
          <span>Slack</span>
          <span className={`int-status ${integrations.slack ? "" : "disconnected"}`}>
            {integrations.slack ? "연결됨" : "미연결"}
          </span>
        </div>
        <div className="sidebar-integration">
          <span>🔷</span>
          <span>Jira</span>
          <span className={`int-status ${integrations.jira ? "" : "disconnected"}`}>
            {integrations.jira ? "연결됨" : "미연결"}
          </span>
        </div>
        <div className="sidebar-integration">
          <span>📝</span>
          <span>Notion</span>
          <span className={`int-status ${integrations.notion ? "" : "disconnected"}`}>
            {integrations.notion ? "연결됨" : "미연결"}
          </span>
        </div>

        {!authUser && (
          <button className="sidebar-login-btn" onClick={() => setShowLoginModal(true)}>
            <span>🔑</span>
            <span>로그인</span>
          </button>
        )}
      </div>

      <div className="main">
        <div className="main-header">
          <span className="main-header-icon">{currentMenu?.icon}</span>
          <span className="main-header-title">{currentMenu?.label}</span>
          {authUser && (
            <div className="main-header-user">
              <span className="main-header-username">{authUser.username}</span>
              <button className="main-header-logout" onClick={() => setShowIntegrationsModal(true)} style={{ marginRight: '8px' }}>⚙️ 연동 관리</button>
              <button className="main-header-logout" onClick={logout}>로그아웃</button>
            </div>
          )}
        </div>

        {policyStatus?.status === "running" && (
          <div className="policy-banner policy-banner--running">
            ⏳ 사내 규정 문서 임베딩 중...
            {policyStatus.files?.length > 0 && (
              <span> ({policyStatus.done_files?.length ?? 0}/{policyStatus.files.length} 완료)</span>
            )}
          </div>
        )}
        {policyStatus?.status === "done" && policyStatus.done_files?.length > 0 && !policyBannerDismissed && (
          <div className="policy-banner policy-banner--done">
            ✅ 사내 규정 문서 임베딩 완료
            <button className="policy-banner-close" onClick={() => setPolicyBannerDismissed(true)}>×</button>
          </div>
        )}
        {policyStatus?.status === "error" && !policyBannerDismissed && (
          <div className="policy-banner policy-banner--error">
            ❌ 임베딩 실패: {policyStatus.error}
            <button className="policy-banner-close" onClick={() => setPolicyBannerDismissed(true)}>×</button>
          </div>
        )}

        <div className="chat-area">
          {messages.map((msg, i) => {
            const isUser = msg.role === "user";
            return (
              <div key={i} className={`msg-row ${isUser ? "user" : ""}`}>
                <div className="msg-avatar">{isUser ? "나" : "W"}</div>
                <div>
                  <div className="msg-bubble">
                    {isUser ? msg.content : (
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                    )}
                  </div>
                  {msg.files?.length > 0 && (
                    <div className="msg-files">
                      {msg.files.map((f, fi) => (
                        <a key={fi} href={`${API}${f.url.replace("/api","")}`} download={f.name} className="msg-file-btn">
                          ⬇ {f.name}
                        </a>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            );
          })}

          {loading && toolLogs.length > 0 && (
            <div className="msg-row">
              <div className="msg-avatar">W</div>
              <div className="tool-status">
                {toolLogs.map((log, i) => <div key={i}>{log}</div>)}
              </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        <div className="input-area">
          {attachedFile && (
            <div className="attach-chip">
              <span className="attach-chip-name">📎 {attachedFile.name}</span>
              <button className="attach-chip-remove" onClick={clearAttachment} aria-label="첨부 제거">×</button>
            </div>
          )}
          <div className="input-row">
            <input
              type="file"
              ref={fileInputRef}
              style={{ display: "none" }}
              accept=".txt,.md,.csv,.json,.pdf,.jpg,.jpeg,.png,.gif,.webp"
              onChange={handleFileChange}
            />
            <button
              className="btn-attach"
              onClick={() => fileInputRef.current?.click()}
              disabled={loading}
              title="파일 첨부"
              aria-label="파일 첨부"
            >
              📎
            </button>
            <textarea
              value={input}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              placeholder="업무 명령을 입력하세요 (Shift+Enter 줄바꿈)"
              disabled={loading}
            />
            <button className="btn-send" onClick={() => sendMessage(input)} disabled={loading}>
              {loading ? "⏳" : "전송"}
            </button>
          </div>
        </div>
      </div>

      {showLoginModal && (
        <LoginModal onClose={() => setShowLoginModal(false)} />
      )}
      {showIntegrationsModal && (
        <IntegrationsModal 
          onClose={() => setShowIntegrationsModal(false)} 
          onIntegrationsChange={fetchIntegrations} 
        />
      )}
    </>
  );
}