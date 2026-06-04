import { useEffect, useState, useRef } from "react";
import { getIntegrations, connectIntegration, disconnectIntegration } from "../api/integrations";

function PasswordInput({ value, onChange, placeholder }) {
  const [show, setShow] = useState(false);
  return (
    <div className="login-input-wrap" style={{ height: "42px", borderRadius: "8px" }}>
      <input 
        className="login-input" 
        type={show ? "text" : "password"} 
        placeholder={placeholder} 
        value={value} 
        onChange={onChange} 
      />
      <button 
        type="button" 
        className="login-eye-btn" 
        onClick={() => setShow(!show)}
        title={show ? "숨기기" : "보기"}
      >
        {show ? (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="m2 2 20 20"/>
            <path d="M6.71 6.71q2.3-.71 5.29-.71 7 0 10 7a15.53 15.53 0 0 1-4.22 5.06"/>
            <path d="M17.47 17.47A15.42 15.42 0 0 1 12 19q-7 0-10-7a15.53 15.53 0 0 1 2.22-3.06"/>
            <path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/>
          </svg>
        ) : (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/>
            <circle cx="12" cy="12" r="3"/>
          </svg>
        )}
      </button>
    </div>
  );
}

const modalStyle = {
  position: "fixed",
  top: "50%", left: "50%",
  transform: "translate(-50%, -50%)",
  backgroundColor: "#fff",
  padding: "24px",
  borderRadius: "12px",
  boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
  width: "400px",
  maxHeight: "85vh",
  overflowY: "auto",
  zIndex: 1000,
  color: "#333",
  display: "flex",
  flexDirection: "column"
};

const overlayStyle = {
  position: "fixed",
  top: 0, left: 0, right: 0, bottom: 0,
  backgroundColor: "rgba(0,0,0,0.5)",
  zIndex: 999
};

const itemStyle = {
  display: "flex", justifyContent: "space-between", alignItems: "center",
  padding: "12px", border: "1px solid #eee", borderRadius: "8px", marginBottom: "8px"
};

export default function IntegrationsModal({ onClose, onIntegrationsChange }) {
  const [integrations, setIntegrations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [openForms, setOpenForms] = useState({}); // source -> boolean
  const [disconnectTarget, setDisconnectTarget] = useState(null);

  const [pos, setPos] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const dragStartPos = useRef({ x: 0, y: 0 });

  useEffect(() => {
    if (isDragging) {
      const handleMouseMove = (e) => {
        setPos({
          x: e.clientX - dragStartPos.current.x,
          y: e.clientY - dragStartPos.current.y
        });
      };
      const handleMouseUp = () => setIsDragging(false);

      window.addEventListener("mousemove", handleMouseMove);
      window.addEventListener("mouseup", handleMouseUp);
      return () => {
        window.removeEventListener("mousemove", handleMouseMove);
        window.removeEventListener("mouseup", handleMouseUp);
      };
    }
  }, [isDragging]);

  const handleMouseDown = (e) => {
    setIsDragging(true);
    dragStartPos.current = {
      x: e.clientX - pos.x,
      y: e.clientY - pos.y
    };
  };

  // 폼 입력값 상태
  const [formData, setFormData] = useState({ 
    SLACK_BOT_TOKEN: "", SLACK_TEAM_ID: "",
    JIRA_API_TOKEN: "", JIRA_EMAIL: "", JIRA_BASE_URL: "",
    NOTION_API_TOKEN: "",
    access_token: "" // fallback
  });
  const [formError, setFormError] = useState("");

  useEffect(() => {
    fetchIntegrations();
  }, []);

  const fetchIntegrations = async () => {
    setLoading(true);
    try {
      const data = await getIntegrations();
      setIntegrations(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const confirmDisconnect = async () => {
    if (!disconnectTarget) return;
    const source = disconnectTarget;
    setDisconnectTarget(null);
    try {
      await disconnectIntegration(source);
      await fetchIntegrations();
      if (onIntegrationsChange) onIntegrationsChange();
    } catch (e) {
      alert("해제 실패: " + e.message);
    }
  };

  const toggleForm = (source) => {
    setOpenForms(prev => ({ ...prev, [source]: !prev[source] }));
  };

  const handleSaveAll = async () => {
    setFormError("");
    setLoading(true);
    let errorMsgs = [];
    
    const tryConnect = async (source, payload) => {
      try {
        await connectIntegration(source, payload);
      } catch (e) {
        errorMsgs.push(`[${source}] ${e.message}`);
      }
    };

    // 값이 하나라도 입력된 플랫폼에 대해 연동 시도
    if (formData.JIRA_API_TOKEN || formData.JIRA_EMAIL || formData.JIRA_BASE_URL) {
      if (!formData.JIRA_API_TOKEN || !formData.JIRA_EMAIL || !formData.JIRA_BASE_URL) {
        errorMsgs.push("[jira] 모든 필드를 입력해주세요.");
      } else {
        await tryConnect("jira", {
          access_token: JSON.stringify({
            api_token: formData.JIRA_API_TOKEN,
            email: formData.JIRA_EMAIL,
            base_url: formData.JIRA_BASE_URL
          })
        });
      }
    }

    if (formData.SLACK_BOT_TOKEN || formData.SLACK_TEAM_ID) {
      if (!formData.SLACK_BOT_TOKEN || !formData.SLACK_TEAM_ID) {
        errorMsgs.push("[slack] 모든 필드를 입력해주세요.");
      } else {
        await tryConnect("slack", {
          access_token: JSON.stringify({
            bot_token: formData.SLACK_BOT_TOKEN,
            team_id: formData.SLACK_TEAM_ID
          })
        });
      }
    }

    if (formData.NOTION_API_TOKEN) {
      await tryConnect("notion", {
        access_token: formData.NOTION_API_TOKEN
      });
    }

    // 일부 성공/실패 여부와 관계없이 사이드바 반영을 위해 일단 조회
    await fetchIntegrations();
    if (onIntegrationsChange) onIntegrationsChange();

    if (errorMsgs.length > 0) {
      setFormError(errorMsgs.join("\n"));
      setLoading(false);
    } else {
      setFormData({ 
        SLACK_BOT_TOKEN: "", SLACK_TEAM_ID: "",
        JIRA_API_TOKEN: "", JIRA_EMAIL: "", JIRA_BASE_URL: "",
        NOTION_API_TOKEN: "", access_token: ""
      });
      setOpenForms({});
      // 성공적으로 전부 저장되면 모달 닫기
      onClose();
    }
  };

  const renderForm = (source) => (
    <div style={{ marginTop: "12px", display: "flex", flexDirection: "column", gap: "8px" }}>
      {source === "jira" && (
        <>
          <input className="modal-input" placeholder="JIRA_BASE_URL (ex: https://xxx.atlassian.net)" 
            value={formData.JIRA_BASE_URL} onChange={e => setFormData({...formData, JIRA_BASE_URL: e.target.value})} />
          <input className="modal-input" type="email" placeholder="JIRA_EMAIL" 
            value={formData.JIRA_EMAIL} onChange={e => setFormData({...formData, JIRA_EMAIL: e.target.value})} />
          <PasswordInput placeholder="JIRA_API_TOKEN" 
            value={formData.JIRA_API_TOKEN} onChange={e => setFormData({...formData, JIRA_API_TOKEN: e.target.value})} />
        </>
      )}
      {source === "slack" && (
        <>
          <PasswordInput placeholder="SLACK_BOT_TOKEN" 
            value={formData.SLACK_BOT_TOKEN} onChange={e => setFormData({...formData, SLACK_BOT_TOKEN: e.target.value})} />
          <input className="modal-input" placeholder="SLACK_TEAM_ID" 
            value={formData.SLACK_TEAM_ID} onChange={e => setFormData({...formData, SLACK_TEAM_ID: e.target.value})} />
        </>
      )}
      {source === "notion" && (
        <PasswordInput placeholder="NOTION_API_TOKEN" 
          value={formData.NOTION_API_TOKEN} onChange={e => setFormData({...formData, NOTION_API_TOKEN: e.target.value})} />
      )}
      {source !== "jira" && source !== "slack" && source !== "notion" && (
        <PasswordInput placeholder="API Token" 
          value={formData.access_token} onChange={e => setFormData({...formData, access_token: e.target.value})} />
      )}
    </div>
  );

  return (
    <>
      <div style={overlayStyle} onClick={onClose} />
      <div style={{ ...modalStyle, transform: `translate(calc(-50% + ${pos.x}px), calc(-50% + ${pos.y}px))` }}>
        <div 
          style={{ display: "flex", justifyContent: "space-between", marginBottom: "16px", flexShrink: 0, cursor: isDragging ? "grabbing" : "grab" }}
          onMouseDown={handleMouseDown}
        >
          <h2 style={{ margin: 0, fontSize: "20px" }}>플랫폼 연동 관리</h2>
          <button 
            onClick={onClose} 
            onMouseDown={e => e.stopPropagation()}
            style={{ background: "none", border: "none", fontSize: "20px", cursor: "pointer", color: "#666" }}
          >✕</button>
        </div>

        <div style={{ flex: 1, overflowY: "auto", marginBottom: "16px" }}>
          {loading ? <p>로딩 중...</p> : integrations.map((item) => (
            <div key={item.source} style={{ marginBottom: "12px" }}>
              <div style={itemStyle}>
                <strong style={{ textTransform: "capitalize", fontSize: "16px" }}>{item.source}</strong>
                {item.connected ? (
                  <button className="modal-btn modal-btn-danger" onClick={() => setDisconnectTarget(item.source)}>연동 해제</button>
                ) : item.source === "google" ? (
                  <button className="modal-btn modal-btn-outline" onClick={() => window.location.href = "http://localhost:8000/api/integrations/google/login"}>연동하기</button>
                ) : (
                  <button className="modal-btn modal-btn-outline" onClick={() => toggleForm(item.source)}>
                    {openForms[item.source] ? "닫기" : "연동하기"}
                  </button>
                )}
              </div>
              {openForms[item.source] && renderForm(item.source)}
            </div>
          ))}
        </div>

        {formError && <div style={{ color: "#E53E3E", fontSize: "13px", marginBottom: "12px", whiteSpace: "pre-line" }}>{formError}</div>}

        <div style={{ display: "flex", gap: "8px", justifyContent: "flex-end", flexShrink: 0 }}>
          <button type="button" className="modal-btn modal-btn-outline" onClick={onClose} disabled={loading}>취소</button>
          <button type="button" className="modal-btn modal-btn-primary" onClick={handleSaveAll} disabled={loading}>
            {loading ? "저장 중..." : "저장"}
          </button>
        </div>
      </div>

      {disconnectTarget && (
        <div style={{ ...overlayStyle, zIndex: 1001, display: "flex", alignItems: "center", justifyContent: "center" }} onClick={() => setDisconnectTarget(null)}>
          <div style={{ ...modalStyle, width: "320px", position: "relative", transform: "none", top: "auto", left: "auto", textAlign: "center", zIndex: 1002, overflow: "visible" }} onClick={e => e.stopPropagation()}>
            <h3 style={{ margin: "0 0 16px", fontSize: "18px", color: "#1A1A1A", fontWeight: "600" }}>연동 해제</h3>
            <p style={{ margin: "0 0 24px", fontSize: "14px", color: "#555" }}>
              정말로 <strong style={{ textTransform: "capitalize", color: "#185FA5" }}>{disconnectTarget}</strong> 연동을 해제하시겠습니까?
            </p>
            <div style={{ display: "flex", gap: "8px", justifyContent: "center" }}>
              <button className="modal-btn modal-btn-outline" onClick={() => setDisconnectTarget(null)} style={{ flex: 1 }}>취소</button>
              <button className="modal-btn modal-btn-danger" onClick={confirmDisconnect} style={{ flex: 1 }}>해제하기</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
