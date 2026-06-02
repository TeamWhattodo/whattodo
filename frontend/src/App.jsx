import { useState, useEffect, useRef } from "react";
import axios from "axios";
import "./index.css";
import LoginModal from "./LoginModal";

const API = "http://localhost:8000/api";

const MENUS = [
  { id: "assistant", icon: "🖥️", label: "업무 도우미", query: null },
];

function urgencyDot(level) {
  if (level >= 4) return "urgent";
  if (level >= 3) return "high";
  return "normal";
}

function parseTaskCards(text) {
  const lines = text.split("\n").filter(l => l.trim());
  const tasks = [];
  for (const line of lines) {
    const slackMatch = line.match(/Slack/i);
    const jiraMatch  = line.match(/Jira|PROJ/i);
    const source = slackMatch ? "Slack" : jiraMatch ? "Jira" : "기타";
    const urgentWord = /긴급|초과|마감|즉시|urgent/i.test(line);
    const highWord   = /승인|검토|대기|pending/i.test(line);
    const level = urgentWord ? 5 : highWord ? 3 : 2;
    if (/^[-•*\d]/.test(line.trim()) && line.trim().length > 4) {
      tasks.push({ title: line.replace(/^[-•*\d.\s]+/, "").trim(), source, level });
    }
  }
  return tasks.slice(0, 6);
}

export default function App() {
  // UI 전용 로그인 상태 — 실제 인증 없이 모달에서 입력한 아이디를 보관한다.
  const [authUser, setAuthUser] = useState(null);
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
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [attachedFile, setAttachedFile]   = useState(null);
  const chatEndRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, toolLogs]);

  useEffect(() => {
    axios.get(`${API}/integrations`).then(res => {
      setIntegrations(res.data);
    }).catch(() => {});
  }, []);

  const handleMenuClick = (menu) => {
    setActiveMenu(menu.id);
    if (menu.query) sendMessage(menu.query);
  };

  const sendMessage = async (query) => {
    if (!query?.trim() || loading) return;
    setLoading(true);
    setToolLogs([]);

    setMessages(prev => [...prev, { role: "user", content: query }]);
    setInput("");

    const res = await fetch(`${API}/chat`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, session_id: sessionId, chat_history: chatHistory }),
    });

    const reader  = res.body.getReader();
    const decoder = new TextDecoder();
    let responseText = "";
    let newHistory   = chatHistory;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value);
      for (const line of chunk.split("\n")) {
        if (!line.startsWith("data: ")) continue;
        try {
          const event = JSON.parse(line.slice(6));
          if (event.type === "tool_call") {
            setToolLogs(prev => [...prev, `🔧 ${event.tool} 호출 중...`]);
          } else if (event.type === "tool_result") {
            setToolLogs(prev => [...prev, `✅ ${event.tool} 완료`]);
          } else if (event.type === "done") {
            responseText = event.text;
            newHistory   = event.history;
          }
        } catch {}
      }
    }

    setChatHistory(newHistory);
    setMessages(prev => [...prev, { role: "assistant", content: responseText }]);
    setToolLogs([]);
    setLoading(false);
  };

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (file) setAttachedFile(file);
  };

  const clearAttachment = () => {
    setAttachedFile(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
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
          <span>✉️</span>
          <span>Gmail</span>
          <span className="int-status disconnected">미연결</span>
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
              <span className="main-header-username">{authUser}</span>
              <button className="main-header-logout" onClick={() => setAuthUser(null)}>로그아웃</button>
            </div>
          )}
        </div>

        <div className="chat-area">
          {messages.map((msg, i) => {
            const isUser = msg.role === "user";
            const tasks  = !isUser ? parseTaskCards(msg.content) : [];
            return (
              <div key={i} className={`msg-row ${isUser ? "user" : ""}`}>
                <div className="msg-avatar">{isUser ? "나" : "W"}</div>
                <div>
                  <div className="msg-bubble">{msg.content}</div>
                  {tasks.length > 0 && (
                    <div className="task-card">
                      {tasks.map((t, j) => (
                        <div key={j} className="task-card-item">
                          <span className={`task-dot ${urgencyDot(t.level)}`} />
                          <span className="task-title">{t.title}</span>
                          <span className="task-source">{t.source}</span>
                        </div>
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
              onChange={e => setInput(e.target.value)}
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
        <LoginModal
          onClose={() => setShowLoginModal(false)}
          onLogin={(username) => {
            setAuthUser(username?.trim() || "사용자");
            setShowLoginModal(false);
          }}
        />
      )}
    </>
  );
}