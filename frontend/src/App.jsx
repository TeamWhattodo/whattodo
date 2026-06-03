import { useState, useEffect, useRef } from "react";
import axios from "axios";
import "./index.css";

const API = import.meta.env.VITE_API_URL ?? "/api";

const MENUS = [
  { id: "assistant", icon: "🖥️", label: "업무 도우미", query: null },
  { id: "briefing",  icon: "📋", label: "브리핑",      query: "긴급한 업무 정리해줘" },
  { id: "schedule",  icon: "📅", label: "일정",         query: "오늘 일정 정리해줘" },
  { id: "summary",   icon: "📄", label: "문서 요약",    query: "최근 문서 요약해줘" },
  { id: "expense",   icon: "🧾", label: "정산 리포트",  query: "정산 현황 알려줘" },
];



export default function App() {
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
  const [briefingBadge, setBriefingBadge] = useState(3);
  const [policyStatus, setPolicyStatus]   = useState(null);
  const chatEndRef = useRef(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, toolLogs]);

  useEffect(() => {
    axios.get(`${API}/integrations`).then(res => {
      setIntegrations(res.data);
    }).catch(() => {});
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

    setMessages(prev => [...prev, { role: "user", content: query }]);
    setInput("");

    try {
      const res = await fetch(`${API}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, session_id: sessionId, chat_history: chatHistory }),
      });

      if (!res.ok) {
        throw new Error(`API 오류: ${res.status}`);
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
        buffer = lines.pop(); // 마지막 불완전한 줄은 버퍼에 남겨둠

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
      setMessages(prev => [...prev, { role: "assistant", content: "네트워크 오류 또는 서버 오류가 발생했습니다." }]);
    } finally {
      setToolLogs([]);
      setLoading(false);
    }
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
            {menu.id === "briefing" && briefingBadge > 0 && (
              <span className="badge">{briefingBadge}</span>
            )}
          </button>
        ))}

        <div className="sidebar-section-label">연동</div>
        <div className="sidebar-integration">
          <span>✉️</span>
          <span>Gmail</span>
          <span className={`int-status ${integrations.gmail ? "" : "disconnected"}`}>
            {integrations.gmail ? "연결됨" : "미연결"}
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
      </div>

      <div className="main">
        <div className="main-header">
          <span className="main-header-icon">{currentMenu?.icon}</span>
          <span className="main-header-title">{currentMenu?.label}</span>
          <span className="main-header-pill">✅ 준비 완료</span>
        </div>

        {policyStatus?.status === "running" && (
          <div className="policy-banner policy-banner--running">
            ⏳ 사내 규정 문서 임베딩 중...
            {policyStatus.files?.length > 0 && (
              <span> ({policyStatus.done_files?.length ?? 0}/{policyStatus.files.length} 완료)</span>
            )}
          </div>
        )}
        {policyStatus?.status === "done" && policyStatus.done_files?.length > 0 && (
          <div className="policy-banner policy-banner--done">
            ✅ 사내 규정 문서 임베딩 완료
          </div>
        )}
        {policyStatus?.status === "error" && (
          <div className="policy-banner policy-banner--error">
            ❌ 임베딩 실패: {policyStatus.error}
          </div>
        )}

        <div className="chat-area">
          {messages.map((msg, i) => {
            const isUser = msg.role === "user";
            return (
              <div key={i} className={`msg-row ${isUser ? "user" : ""}`}>
                <div className="msg-avatar">{isUser ? "나" : "W"}</div>
                <div>
                  <div className="msg-bubble">{msg.content}</div>
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
          <div className="input-row">
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
    </>
  );
}