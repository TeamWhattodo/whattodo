import { useState, useEffect, useRef } from "react";
import axios from "axios";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import "./index.css";
import LoginModal from "./LoginModal";
import SettingsModal from "./components/SettingsModal";
import { useAuth } from "./context/AuthContext";
import { getIntegrations } from "./api/integrations";

const API = import.meta.env.VITE_API_URL ?? "/api";

const MENUS = [
  { id: "assistant", icon: "🖥️", label: "업무 도우미", query: "긴급도 순으로 오늘 처리해야 할 업무 정리해줘" },
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
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [attachedFile, setAttachedFile]       = useState(null);
  const chatEndRef = useRef(null);
  const fileInputRef = useRef(null);
  const textareaRef = useRef(null);

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
    if (textareaRef.current) textareaRef.current.style.height = "44px";

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
    const ext = file.name.split(".").pop().toLowerCase();
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
    if (e.target.scrollHeight > 44) {
      e.target.style.height = Math.min(e.target.scrollHeight, 300) + "px";
    }
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
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
            <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
            <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
            <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
          </svg>
          <span>Google</span>
          <span className={`int-status ${integrations.google ? "" : "disconnected"}`}>
            {integrations.google ? "연결됨" : "미연결"}
          </span>
        </div>
        <div className="sidebar-integration">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52z" fill="#E01E5A"/>
            <path d="M6.313 15.165a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313z" fill="#E01E5A"/>
            <path d="M8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834z" fill="#36C5F0"/>
            <path d="M8.834 6.313a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312z" fill="#36C5F0"/>
            <path d="M18.956 8.834a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522v-2.521z" fill="#2EB67D"/>
            <path d="M17.688 8.834a2.528 2.528 0 0 1-2.523 2.521 2.527 2.527 0 0 1-2.52-2.521V2.522A2.527 2.527 0 0 1 15.165 0a2.528 2.528 0 0 1 2.523 2.522v6.312z" fill="#2EB67D"/>
            <path d="M15.165 18.956a2.528 2.528 0 0 1 2.52 2.522A2.528 2.528 0 0 1 15.165 24a2.527 2.527 0 0 1-2.523-2.522v-2.522h2.523z" fill="#ECB22E"/>
            <path d="M15.165 17.688a2.527 2.527 0 0 1-2.52-2.523 2.526 2.526 0 0 1 2.52-2.52h6.313A2.527 2.527 0 0 1 24 15.165a2.528 2.528 0 0 1-2.522 2.523h-6.313z" fill="#ECB22E"/>
          </svg>
          <span>Slack</span>
          <span className={`int-status ${integrations.slack ? "" : "disconnected"}`}>
            {integrations.slack ? "연결됨" : "미연결"}
          </span>
        </div>
        <div className="sidebar-integration">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M11.664 12.003L4.975 18.692a2.368 2.368 0 0 1-3.348 0 2.368 2.368 0 0 1 0-3.348l6.69-6.689a2.368 2.368 0 0 1 3.347 3.348z" fill="#2684FF"/>
            <path d="M22.373 12.003l-6.689 6.689a2.368 2.368 0 0 1-3.348 0 2.368 2.368 0 0 1 0-3.348l6.689-6.689a2.368 2.368 0 0 1 3.348 3.348z" fill="#2684FF"/>
            <path d="M11.664 1.294L4.975 7.983a2.368 2.368 0 0 1-3.348 0 2.368 2.368 0 0 1 0-3.348l6.69-6.689a2.368 2.368 0 0 1 3.347 3.348z" fill="#0052CC"/>
          </svg>
          <span>Jira</span>
          <span className={`int-status ${integrations.jira ? "" : "disconnected"}`}>
            {integrations.jira ? "연결됨" : "미연결"}
          </span>
        </div>
        <div className="sidebar-integration">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M4.12 3C3.5 3 3 3.5 3 4.12v15.76C3 20.5 3.5 21 4.12 21h15.76c.62 0 1.12-.5 1.12-1.12V4.12C21 3.5 20.5 3 19.88 3H4.12zM7.5 7.5h2v6.62l6-7.85h3v9h-2V8.62L10.5 16.5h-3v-9z" fill="#111111"/>
          </svg>
          <span>Notion</span>
          <span className={`int-status ${integrations.notion ? "" : "disconnected"}`}>
            {integrations.notion ? "연결됨" : "미연결"}
          </span>
        </div>

        {!authUser ? (
          <button className="sidebar-login-btn" onClick={() => setShowLoginModal(true)}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/>
              <polyline points="10 17 15 12 10 7"/>
              <line x1="15" y1="12" x2="3" y2="12"/>
            </svg>
            <span>로그인</span>
          </button>
        ) : (
          <button className="sidebar-login-btn" style={{ background: "#FEE2E2", color: "#DC2626", border: "1px solid #FECACA" }} onClick={logout}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
              <polyline points="16 17 21 12 16 7"/>
              <line x1="21" y1="12" x2="9" y2="12"/>
            </svg>
            <span>로그아웃</span>
          </button>
        )}
      </div>

      <div className="main">
        <div className="main-header">
          <span className="main-header-icon">{currentMenu?.icon}</span>
          <span className="main-header-title">{currentMenu?.label}</span>
          {authUser && (
            <div className="main-header-user">
              <span className="main-header-username">{[authUser.department, authUser.name, authUser.position].filter(Boolean).join(" ") || authUser.username}</span>
              <button className="main-header-logout" onClick={() => setShowSettingsModal(true)} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/>
                  <circle cx="12" cy="12" r="3"/>
                </svg>
                설정
              </button>
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
              ref={textareaRef}
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
      {showSettingsModal && (
        <SettingsModal 
          onClose={() => setShowSettingsModal(false)} 
          onIntegrationsChange={fetchIntegrations} 
        />
      )}
    </>
  );
}
