import { useEffect, useState, useRef } from "react";
import { getIntegrations, connectIntegration, disconnectIntegration } from "../api/integrations";
import { useAuth } from "../context/AuthContext";
import { fetchMe, updateMe, deleteMe } from "../api/auth";

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
            <path d="m2 2 20 20" />
            <path d="M6.71 6.71q2.3-.71 5.29-.71 7 0 10 7a15.53 15.53 0 0 1-4.22 5.06" />
            <path d="M17.47 17.47A15.42 15.42 0 0 1 12 19q-7 0-10-7a15.53 15.53 0 0 1 2.22-3.06" />
            <path d="M9.88 9.88a3 3 0 1 0 4.24 4.24" />
          </svg>
        ) : (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z" />
            <circle cx="12" cy="12" r="3" />
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
  width: "480px",
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

export default function SettingsModal({ onClose, onIntegrationsChange }) {
  const { user, logout, refreshUser } = useAuth();
  const [activeTab, setActiveTab] = useState("integration"); // integration, duration, account

  // Tab 1: Integration
  const [integrations, setIntegrations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [openForms, setOpenForms] = useState({});
  const [disconnectTarget, setDisconnectTarget] = useState(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteAccountStatus, setDeleteAccountStatus] = useState("idle");
  const [deleteAccountError, setDeleteAccountError] = useState("");

  const [formData, setFormData] = useState({
    SLACK_BOT_TOKEN: "", SLACK_TEAM_ID: "",
    JIRA_API_TOKEN: "", JIRA_EMAIL: "", JIRA_BASE_URL: "",
    NOTION_API_TOKEN: "",
    access_token: ""
  });
  const [formDays, setFormDays] = useState({
    slack: 14, jira: 14, notion: 14, gmail: 14, calendar: 14
  });
  const [formError, setFormError] = useState("");

  // Tab 2: Duration
  const [syncSettings, setSyncSettings] = useState({});
  const [isSavingDuration, setIsSavingDuration] = useState(false);

  // Tab 3: Profile
  const [profile, setProfile] = useState({ name: "", department: "", position: "" });
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileMsg, setProfileMsg] = useState("");

  // Tab 4: Policy
  const [policies, setPolicies] = useState([]);
  const [policyLoading, setPolicyLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [policyStatus, setPolicyStatus] = useState(null);
  const fileInputRef = useRef(null);

  // General Modal State
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const dragStartPos = useRef({ x: 0, y: 0 });
  const [deletePolicyTarget, setDeletePolicyTarget] = useState(null);

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

  useEffect(() => {
    fetchData();
  }, []);

  const fetchPolicies = async () => {
    setPolicyLoading(true);
    try {
      const { getPolicyList } = await import("../api/policy");
      const data = await getPolicyList();
      setPolicies(data);
    } catch (e) {
      console.error(e);
    } finally {
      setPolicyLoading(false);
    }
  };

  useEffect(() => {
    let timer;
    const pollStatus = async () => {
      try {
        const { getPolicyStatus } = await import("../api/policy");
        const statusData = await getPolicyStatus();
        setPolicyStatus(prev => {
          // 방금 실행 중(running)에서 완료(done) 또는 대기(idle) 상태로 바뀌었다면 파일 목록을 다시 불러옴 (embedded: true 갱신 목적)
          if (prev?.status === "running" && statusData.status !== "running") {
            fetchPolicies();
          }
          return statusData;
        });

        if (statusData.status === "running") {
          timer = setTimeout(pollStatus, 1000);
        } else {
          timer = setTimeout(pollStatus, 3000);
        }
      } catch (e) {
        timer = setTimeout(pollStatus, 3000);
      }
    };

    if (activeTab === "policy") {
      fetchPolicies();
      pollStatus();
    }

    return () => clearTimeout(timer);
  }, [activeTab]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [intData, meData] = await Promise.all([
        getIntegrations(),
        fetchMe()
      ]);
      setIntegrations(intData);
      setSyncSettings(meData?.sync_settings || {});
      setProfile({ name: meData?.name || "", department: meData?.department || "", position: meData?.position || "" });
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
      await fetchData();
      if (onIntegrationsChange) onIntegrationsChange();
    } catch (e) {
      alert("해제 실패: " + e.message);
    }
  };

  const toggleForm = (source) => {
    setOpenForms(prev => ({ ...prev, [source]: !prev[source] }));
  };

  const handleSaveIntegrations = async () => {
    setFormError("");
    setLoading(true);
    let errorMsgs = [];

    const tryConnect = async (source, payload, days) => {
      try {
        await connectIntegration(source, { ...payload, sync_days: days });
      } catch (e) {
        errorMsgs.push(`[${source}] ${e.message}`);
      }
    };

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
        }, formDays.jira);
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
        }, formDays.slack);
      }
    }

    if (formData.NOTION_API_TOKEN) {
      await tryConnect("notion", {
        access_token: formData.NOTION_API_TOKEN
      }, formDays.notion);
    }

    await fetchData();
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
    }
  };

  const handleSaveDuration = async () => {
    setIsSavingDuration(true);
    try {
      await updateMe({ sync_settings: syncSettings });
      alert("기간 설정이 저장되었습니다.");
    } catch (e) {
      alert("저장 실패: " + e.message);
    } finally {
      setIsSavingDuration(false);
    }
  };

  const handleDeleteAccount = () => {
    setDeleteAccountStatus("idle");
    setDeleteAccountError("");
    setShowDeleteConfirm(true);
  };

  const handleSaveProfile = async () => {
    setProfileSaving(true);
    setProfileMsg("");
    try {
      await updateMe(profile);
      await refreshUser();
      setProfileMsg("저장됨");
    } catch (e) {
      setProfileMsg("저장 실패");
    } finally {
      setProfileSaving(false);
    }
  };

  const confirmDeleteAccount = async () => {
    setDeleteAccountStatus("loading");
    try {
      await deleteMe();
      setDeleteAccountStatus("success");
      setTimeout(() => {
        window.location.href = "/";
      }, 1500);
    } catch (e) {
      setDeleteAccountStatus("error");
      setDeleteAccountError(e.message);
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const ext = file.name.split('.').pop().toLowerCase();
    const allowed = ['pdf', 'hwp', 'hwpx', 'docx', 'doc'];
    if (!allowed.includes(ext)) {
      alert("PDF, HWP, DOCX, DOC 파일만 업로드 가능합니다.");
      return;
    }
    setUploading(true);
    try {
      const { uploadPolicy } = await import("../api/policy");
      await uploadPolicy(file);
      fetchPolicies();
    } catch (err) {
      alert("업로드 실패: " + err.message);
    } finally {
      setUploading(false);
      e.target.value = null;
    }
  };

  const handleDeletePolicy = (filename) => {
    setDeletePolicyTarget(filename);
  };

  const confirmDeletePolicy = async () => {
    if (!deletePolicyTarget) return;
    const filename = deletePolicyTarget;
    setDeletePolicyTarget(null);
    try {
      const { deletePolicy } = await import("../api/policy");
      await deletePolicy(filename);
      fetchPolicies();
    } catch (err) {
      alert("삭제 실패: " + err.message);
    }
  };

  const handleStartIngest = async (filename) => {
    try {
      const { triggerPolicyIngest } = await import("../api/policy");
      await triggerPolicyIngest(filename);
    } catch (err) {
      alert("임베딩 시작 실패: " + err.message);
    }
  };

  const handleViewPolicy = async (filename) => {
    try {
      const { downloadPolicy } = await import("../api/policy");
      const blob = await downloadPolicy(filename);
      const url = window.URL.createObjectURL(new Blob([blob], { type: 'application/pdf' }));
      window.open(url, '_blank');
      // 메모리 누수 방지를 위해 약간의 지연 후 URL 해제
      setTimeout(() => window.URL.revokeObjectURL(url), 1000);
    } catch (err) {
      alert("열람 실패: " + err.message);
    }
  };

  const renderIntegrationForm = (source) => (
    <div style={{ marginTop: "12px", display: "flex", flexDirection: "column", gap: "8px" }}>
      {source === "jira" && (
        <>
          <input className="modal-input" placeholder="JIRA_BASE_URL (ex: https://xxx.atlassian.net)"
            value={formData.JIRA_BASE_URL} onChange={e => setFormData({ ...formData, JIRA_BASE_URL: e.target.value })} />
          <input className="modal-input" type="email" placeholder="JIRA_EMAIL"
            value={formData.JIRA_EMAIL} onChange={e => setFormData({ ...formData, JIRA_EMAIL: e.target.value })} />
          <PasswordInput placeholder="JIRA_API_TOKEN"
            value={formData.JIRA_API_TOKEN} onChange={e => setFormData({ ...formData, JIRA_API_TOKEN: e.target.value })} />
        </>
      )}
      {source === "slack" && (
        <>
          <PasswordInput placeholder="SLACK_BOT_TOKEN"
            value={formData.SLACK_BOT_TOKEN} onChange={e => setFormData({ ...formData, SLACK_BOT_TOKEN: e.target.value })} />
          <input className="modal-input" placeholder="SLACK_TEAM_ID"
            value={formData.SLACK_TEAM_ID} onChange={e => setFormData({ ...formData, SLACK_TEAM_ID: e.target.value })} />
        </>
      )}
      {source === "notion" && (
        <PasswordInput placeholder="NOTION_API_TOKEN"
          value={formData.NOTION_API_TOKEN} onChange={e => setFormData({ ...formData, NOTION_API_TOKEN: e.target.value })} />
      )}

      <div style={{ display: "flex", alignItems: "center", gap: "8px", marginTop: "4px" }}>
        <span style={{ fontSize: "14px" }}>초기 크롤링 기간(일):</span>
        <input
          type="number"
          className="modal-input"
          style={{ width: "80px", margin: 0 }}
          value={formDays[source] || 14}
          onChange={e => setFormDays({ ...formDays, [source]: parseInt(e.target.value) || 0 })}
          min={1}
        />
      </div>
    </div>
  );

  const renderDurationInput = (key, label) => (
    <div key={key} style={{ marginBottom: "16px", background: "#F9FAFC", padding: "16px", borderRadius: "8px", border: "1px solid #EBEBEB" }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "12px", alignItems: "center" }}>
        <span style={{ fontWeight: "600", fontSize: "15px", textTransform: key === "gmail" || key === "calendar" ? "none" : "capitalize" }}>{label}</span>
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <input
            type="number"
            className="modal-input"
            style={{ width: "70px", padding: "6px 10px", margin: 0, textAlign: "right", fontSize: "14px" }}
            min="1" max="90"
            value={syncSettings[key] || 14}
            onChange={e => setSyncSettings({ ...syncSettings, [key]: parseInt(e.target.value) || 0 })}
          />
          <span style={{ fontSize: "14px", color: "#555", fontWeight: "500" }}>일</span>
        </div>
      </div>
      <div style={{ display: "flex", gap: "8px" }}>
        {[7, 14, 30, 60, 90].map(days => {
          const isActive = (syncSettings[key] || 14) === days;
          return (
            <button
              key={days}
              type="button"
              className="modal-btn"
              style={{
                flex: 1,
                padding: "6px 0",
                fontSize: "13px",
                background: isActive ? "#EEF4FF" : "#FFFFFF",
                border: `1px solid ${isActive ? "#3b5bdb" : "#DEDEDE"}`,
                color: isActive ? "#3b5bdb" : "#555",
                fontWeight: isActive ? "600" : "400"
              }}
              onClick={() => setSyncSettings({ ...syncSettings, [key]: days })}
            >
              {days}일
            </button>
          );
        })}
      </div>
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
          <h2 style={{ margin: 0, fontSize: "20px" }}>설정</h2>
          <button
            onClick={onClose}
            onMouseDown={e => e.stopPropagation()}
            style={{ background: "none", border: "none", fontSize: "20px", cursor: "pointer", color: "#666" }}
          >✕</button>
        </div>

        <div className="tabs">
          <button className={`tab ${activeTab === "integration" ? "active" : ""}`} onClick={() => setActiveTab("integration")}>연동 관리</button>
          <button className={`tab ${activeTab === "policy" ? "active" : ""}`} onClick={() => setActiveTab("policy")}>문서 업로드</button>
          <button className={`tab ${activeTab === "duration" ? "active" : ""}`} onClick={() => setActiveTab("duration")}>기간 설정</button>
          <button className={`tab ${activeTab === "account" ? "active" : ""}`} onClick={() => setActiveTab("account")}>계정 관리</button>
        </div>

        <div style={{ flex: 1, overflowY: "auto", marginBottom: "16px", marginTop: "16px" }}>
          {/* TAB 1: 연동 관리 */}
          {activeTab === "integration" && (
            <div>
              {loading ? <p>로딩 중...</p> : integrations.map((item) => (
                <div key={item.source} style={{ marginBottom: "12px" }}>
                  <div style={itemStyle}>
                    <strong style={{ textTransform: "capitalize", fontSize: "16px" }}>{item.source}</strong>
                    {item.connected ? (
                      <button className="modal-btn modal-btn-danger" onClick={() => setDisconnectTarget(item.source)}>연동 해제</button>
                    ) : item.source === "google" ? (
                      <button className="modal-btn modal-btn-outline" onClick={() => {
                        const gmailDays = formDays.gmail || 14;
                        const calendarDays = formDays.calendar || 14;
                        window.location.href = `http://localhost:8000/api/integrations/google/login?gmail_sync_days=${gmailDays}&calendar_sync_days=${calendarDays}`;
                      }}>연동하기</button>
                    ) : (
                      <button className="modal-btn modal-btn-outline" onClick={() => toggleForm(item.source)}>
                        {openForms[item.source] ? "닫기" : "연동하기"}
                      </button>
                    )}
                  </div>
                  {/* Google은 OAuth라서 기간 입력을 미리 받아야 함 */}
                  {item.source === "google" && !item.connected && (
                    <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginTop: "4px", padding: "0 12px" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <span style={{ fontSize: "14px", color: "#555", width: "160px" }}>Gmail 크롤링 기간(일):</span>
                        <input
                          type="number"
                          className="modal-input"
                          style={{ width: "80px", margin: 0, padding: "4px 8px" }}
                          value={formDays.gmail || 14}
                          onChange={e => setFormDays({ ...formDays, gmail: parseInt(e.target.value) || 0 })}
                          min={1}
                        />
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <span style={{ fontSize: "14px", color: "#555", width: "160px" }}>캘린더 크롤링 기간(일):</span>
                        <input
                          type="number"
                          className="modal-input"
                          style={{ width: "80px", margin: 0, padding: "4px 8px" }}
                          value={formDays.calendar || 14}
                          onChange={e => setFormDays({ ...formDays, calendar: parseInt(e.target.value) || 0 })}
                          min={1}
                        />
                      </div>
                    </div>
                  )}
                  {openForms[item.source] && renderIntegrationForm(item.source)}
                </div>
              ))}
              {formError && <div style={{ color: "#E53E3E", fontSize: "13px", marginBottom: "12px", whiteSpace: "pre-line" }}>{formError}</div>}
              {Object.values(openForms).some(v => v) && (
                <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "16px" }}>
                  <button type="button" className="modal-btn modal-btn-primary" onClick={handleSaveIntegrations} disabled={loading}>
                    {loading ? "저장 중..." : "폼 정보 저장"}
                  </button>
                </div>
              )}
            </div>
          )}

          {/* TAB 2: 기간 설정 */}
          {activeTab === "duration" && (
            <div>
              <p style={{ fontSize: "14px", color: "#666", marginBottom: "16px" }}>
                각 플랫폼별로 수집할 데이터의 기준 기간(일)을 설정합니다. 값이 작을수록 동기화가 빠릅니다.
              </p>
              {integrations.filter(i => i.connected).length === 0 ? (
                <p style={{ fontSize: "14px", color: "#888" }}>연동된 플랫폼이 없습니다.</p>
              ) : (
                integrations.filter(i => i.connected).map(item => {
                  if (item.source === "google") {
                    return (
                      <div key={item.source}>
                        {renderDurationInput("gmail", "Google (Gmail)")}
                        {renderDurationInput("calendar", "Google (캘린더)")}
                      </div>
                    );
                  }
                  return renderDurationInput(item.source, item.source);
                })
              )}
              {integrations.filter(i => i.connected).length > 0 && (
                <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "24px" }}>
                  <button className="modal-btn modal-btn-primary" onClick={handleSaveDuration} disabled={isSavingDuration}>
                    {isSavingDuration ? "저장 중..." : "기간 저장"}
                  </button>
                </div>
              )}
            </div>
          )}

          {/* TAB 3: 계정 관리 */}
          {activeTab === "account" && (
            <div>
              <div style={{ marginBottom: "20px", padding: "16px", border: "1px solid #EBEBEB", borderRadius: "8px" }}>
                <div style={{ fontWeight: "600", fontSize: "14px", marginBottom: "10px" }}>내 정보 (보고서 자동 입력)</div>
                <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                  <input className="modal-input" placeholder="이름" value={profile.name}
                    onChange={e => setProfile({ ...profile, name: e.target.value })} />
                  <input className="modal-input" placeholder="부서" value={profile.department}
                    onChange={e => setProfile({ ...profile, department: e.target.value })} />
                  <input className="modal-input" placeholder="직급" value={profile.position}
                    onChange={e => setProfile({ ...profile, position: e.target.value })} />
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "8px", marginTop: "8px" }}>
                  <button className="modal-btn modal-btn-primary" onClick={handleSaveProfile} disabled={profileSaving}
                    style={{ fontSize: "13px", padding: "6px 14px" }}>
                    {profileSaving ? "저장 중..." : "저장"}
                  </button>
                  {profileMsg && <span style={{ fontSize: "13px", color: profileMsg === "저장됨" ? "#276749" : "#C53030" }}>{profileMsg}</span>}
                </div>
              </div>
              <div style={{ marginBottom: "24px" }}>
                <p style={{ fontSize: "14px", color: "#666" }}>현재 로그인된 계정: <strong>{user?.username}</strong></p>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                <button className="modal-btn modal-btn-outline" onClick={() => { logout(); onClose(); }} style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: '6px' }}>
                    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                    <polyline points="16 17 21 12 16 7" />
                    <line x1="21" y1="12" x2="9" y2="12" />
                  </svg>
                  로그아웃
                </button>
                <button className="modal-btn modal-btn-danger" onClick={handleDeleteAccount} style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: '6px' }}>
                    <path d="M3 6h18" />
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                    <line x1="10" y1="11" x2="10" y2="17" />
                    <line x1="14" y1="11" x2="14" y2="17" />
                  </svg>
                  회원 탈퇴
                </button>
              </div>
            </div>
          )}

          {/* TAB 4: 사내 규정 관리 */}
          {activeTab === "policy" && (
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px", gap: "16px" }}>
                <p style={{ fontSize: "14px", color: "#666", margin: 0, wordBreak: "keep-all" }}>
                  사내 규정 문서(PDF, 워드, 한글)를 업로드하면 백그라운드에서 자동으로 AI 임베딩이 진행됩니다.
                </p>
                <div style={{ flexShrink: 0 }}>
                  <input type="file" ref={fileInputRef} onChange={handleFileUpload} accept=".pdf,.hwp,.hwpx,.docx,.doc,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/x-hwp,application/haansofthwp" style={{ display: "none" }} />
                  <button className="modal-btn modal-btn-primary" onClick={() => fileInputRef.current.click()} disabled={uploading} style={{ fontSize: "13px", padding: "6px 12px", whiteSpace: "nowrap" }}>
                    {uploading ? "업로드 중..." : "+ 파일 추가"}
                  </button>
                </div>
              </div>

              {policyLoading ? <p>로딩 중...</p> : policies.length === 0 ? (
                <div style={{ padding: "32px", textAlign: "center", background: "#F9FAFC", borderRadius: "8px", border: "1px dashed #DEDEDE" }}>
                  <p style={{ color: "#888", fontSize: "14px", margin: 0 }}>업로드된 사내 규정 문서가 없습니다.</p>
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                  {policies.map(file => {
                    const isRunning = policyStatus?.status === "running" && policyStatus?.current_file === file.name;
                    const progress = isRunning ? policyStatus.progress : 0;

                    return (
                      <div key={file.name} style={{ ...itemStyle, flexDirection: "column", alignItems: "stretch", gap: "8px" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                          <div style={{ display: "flex", flexDirection: "column" }}>
                            <strong
                              style={{ fontSize: "15px", color: "#185FA5", marginBottom: "8px", cursor: "pointer", textDecoration: "underline" }}
                              onClick={() => handleViewPolicy(file.name)}
                              title="클릭하여 새 탭에서 문서 보기"
                            >
                              {file.name}
                            </strong>
                            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                              <span style={{ fontSize: "12px", color: "#888" }}>{(file.size / 1024 / 1024).toFixed(2)} MB</span>
                              {file.embedded ? (
                                <span style={{ fontSize: "12px", color: "#276749", background: "#C6F6D5", padding: "2px 6px", borderRadius: "4px", fontWeight: "600" }}>임베딩 완료</span>
                              ) : isRunning ? (
                                <span style={{ fontSize: "12px", color: "#B7791F", background: "#FEEBC8", padding: "2px 6px", borderRadius: "4px", fontWeight: "600" }}>임베딩 중</span>
                              ) : policyStatus?.status === "error" && policyStatus?.current_file === file.name ? (
                                <span style={{ fontSize: "12px", color: "#C53030", background: "#FED7D7", padding: "2px 6px", borderRadius: "4px", fontWeight: "600" }} title={policyStatus?.error || ""}>임베딩 실패 ⚠</span>
                              ) : (
                                <span style={{ fontSize: "12px", color: "#C53030", background: "#FED7D7", padding: "2px 6px", borderRadius: "4px", fontWeight: "600" }}>임베딩 필요</span>
                              )}
                            </div>
                          </div>
                          <div style={{ display: "flex", gap: "8px" }}>
                            {!file.embedded && !isRunning && (
                              <button className="modal-btn modal-btn-outline" style={{ padding: "6px 10px", color: "#3b5bdb", borderColor: "#3b5bdb", display: "flex", alignItems: "center", gap: "4px" }} onClick={() => handleStartIngest(file.name)}>
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" stroke="none">
                                  <polygon points="5 3 19 12 5 21 5 3" />
                                </svg>
                                {policyStatus?.status === "error" && policyStatus?.current_file === file.name ? "재시도" : "임베딩 시작"}
                              </button>
                            )}
                            <button className="modal-btn modal-btn-outline" style={{ color: "#E53E3E", borderColor: "#E53E3E", padding: "6px 10px" }} onClick={() => handleDeletePolicy(file.name)}>
                              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M3 6h18" /><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /><line x1="10" y1="11" x2="10" y2="17" /><line x1="14" y1="11" x2="14" y2="17" />
                              </svg>
                            </button>
                          </div>
                        </div>
                        {isRunning && (
                          <div style={{ display: "flex", alignItems: "center", gap: "10px", marginTop: "4px" }}>
                            <div style={{ flex: 1, background: "#EBEBEB", height: "8px", borderRadius: "4px", overflow: "hidden" }}>
                              <div style={{ width: `${progress}%`, height: "100%", background: "#3b5bdb", transition: "width 0.3s ease" }}></div>
                            </div>
                            <span style={{ fontSize: "12px", fontWeight: "600", color: "#3b5bdb", width: "32px", textAlign: "right" }}>{progress}%</span>
                          </div>
                        )}
                        {policyStatus?.status === "error" && policyStatus?.current_file === file.name && policyStatus?.error && (
                          <div style={{ marginTop: "4px", padding: "6px 10px", background: "#FFF5F5", border: "1px solid #FEB2B2", borderRadius: "6px", fontSize: "12px", color: "#C53030", whiteSpace: "pre-wrap", wordBreak: "break-all", maxHeight: "80px", overflowY: "auto" }}>
                            {policyStatus.error}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
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
      {deletePolicyTarget && (
        <div style={{ ...overlayStyle, zIndex: 1001, display: "flex", alignItems: "center", justifyContent: "center" }} onClick={() => setDeletePolicyTarget(null)}>
          <div style={{ ...modalStyle, width: "320px", position: "relative", transform: "none", top: "auto", left: "auto", textAlign: "center", zIndex: 1002, overflow: "visible" }} onClick={e => e.stopPropagation()}>
            <h3 style={{ margin: "0 0 16px", fontSize: "18px", color: "#1A1A1A", fontWeight: "600" }}>문서 삭제</h3>
            <p style={{ margin: "0 0 24px", fontSize: "14px", color: "#555", lineHeight: "1.5" }}>
              <strong style={{ color: "#185FA5" }}>{deletePolicyTarget}</strong> 문서를 삭제하시겠습니까?<br />임베딩된 데이터도 모두 삭제됩니다.
            </p>
            <div style={{ display: "flex", gap: "8px", justifyContent: "center" }}>
              <button className="modal-btn modal-btn-outline" onClick={() => setDeletePolicyTarget(null)} style={{ flex: 1 }}>취소</button>
              <button className="modal-btn modal-btn-danger" onClick={confirmDeletePolicy} style={{ flex: 1 }}>삭제하기</button>
            </div>
          </div>
        </div>
      )}
      {showDeleteConfirm && (
        <div style={{ ...overlayStyle, zIndex: 1001, display: "flex", alignItems: "center", justifyContent: "center" }} onClick={() => deleteAccountStatus !== "loading" && deleteAccountStatus !== "success" && setShowDeleteConfirm(false)}>
          <div style={{ ...modalStyle, width: "320px", position: "relative", transform: "none", top: "auto", left: "auto", textAlign: "center", zIndex: 1002, overflow: "visible" }} onClick={e => e.stopPropagation()}>
            <h3 style={{ margin: "0 0 16px", fontSize: "18px", color: "#1A1A1A", fontWeight: "600" }}>회원 탈퇴</h3>

            {deleteAccountStatus === "success" ? (
              <div style={{ marginBottom: "16px", display: "flex", flexDirection: "column", alignItems: "center" }}>
                <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#34A853" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginBottom: "12px" }}>
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                  <polyline points="22 4 12 14.01 9 11.01" />
                </svg>
                <p style={{ margin: "0 0 8px", fontSize: "15px", fontWeight: "500", color: "#333" }}>계정이 성공적으로 삭제되었습니다.</p>
                <p style={{ margin: 0, fontSize: "13px", color: "#666" }}>잠시 후 메인 화면으로 이동합니다...</p>
              </div>
            ) : (
              <>
                <p style={{ margin: "0 0 24px", fontSize: "14px", color: "#555", lineHeight: "1.5" }}>
                  정말로 계정을 삭제하시겠습니까?<br />
                  모든 데이터가 삭제되며 <strong style={{ color: "#E53E3E" }}>복구할 수 없습니다</strong>.
                </p>
                {deleteAccountStatus === "error" && (
                  <p style={{ margin: "0 0 16px", fontSize: "13px", color: "#E53E3E" }}>
                    삭제 실패: {deleteAccountError}
                  </p>
                )}
                <div style={{ display: "flex", gap: "8px", justifyContent: "center" }}>
                  <button className="modal-btn modal-btn-outline" onClick={() => setShowDeleteConfirm(false)} style={{ flex: 1 }} disabled={deleteAccountStatus === "loading"}>취소</button>
                  <button className="modal-btn modal-btn-danger" onClick={confirmDeleteAccount} style={{ flex: 1 }} disabled={deleteAccountStatus === "loading"}>
                    {deleteAccountStatus === "loading" ? "탈퇴 중..." : "탈퇴하기"}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}
