"""WhatToDo 최종 아키텍처 다이어그램 생성 스크립트."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

# 한국어 폰트 등록
_KO_FONT = "/System/Library/Fonts/AppleSDGothicNeo.ttc"
fm.fontManager.addfont(_KO_FONT)
_FONT_NAME = fm.FontProperties(fname=_KO_FONT).get_name()
matplotlib.rcParams["font.family"] = _FONT_NAME
matplotlib.rcParams["axes.unicode_minus"] = False

# ── 색상 팔레트 ─────────────────────────────────────────────
C_BG      = "#F7F8FA"
C_WHITE   = "#FFFFFF"
C_ARROW   = "#666666"

# 섹션별 테마 색
T_EXT   = dict(header="#1565C0", light="#BBDEFB", mid="#1976D2", dark="#0D47A1")
T_WRK   = dict(header="#263238", light="#ECEFF1", mid="#37474F", dark="#1C313A")
T_DB    = dict(header="#004D40", light="#B2DFDB", mid="#00695C", dark="#002B27")
T_SUP   = dict(header="#212121", light="#F5F5F5", mid="#424242", dark="#000000")
T_FA    = dict(header="#2E7D32", light="#C8E6C9", mid="#388E3C", dark="#1B5E20")
T_SA    = dict(header="#0D47A1", light="#BBDEFB", mid="#1565C0", dark="#0A2472")
T_RA    = dict(header="#4A148C", light="#E1BEE7", mid="#6A1B9A", dark="#2D0060")
T_AA    = dict(header="#B71C1C", light="#FFCDD2", mid="#C62828", dark="#7F0000")
T_VAL   = dict(header="#37474F", light="#ECEFF1", mid="#455A64", dark="#1C313A")
T_SSE   = dict(header="#4E342E", light="#EFEBE9", mid="#5D4037", dark="#321911")
T_USER  = dict(header="#1A237E", light="#C5CAE9", mid="#283593", dark="#0D1466")


def box(ax, x, y, w, h, fill, text="", text_color=C_WHITE,
        fs=8.5, bold=False, radius=0.012, lw=0, edge="none",
        va="center", ha="center", zorder=3, linespacing=1.4):
    bp = FancyBboxPatch((x, y), w, h,
                        boxstyle=f"round,pad=0,rounding_size={radius}",
                        linewidth=lw, edgecolor=edge,
                        facecolor=fill, zorder=zorder)
    ax.add_patch(bp)
    if text:
        ax.text(x + w / 2 if ha == "center" else x + 0.010,
                y + h / 2, text,
                ha=ha, va=va, fontsize=fs,
                color=text_color, fontweight="bold" if bold else "normal",
                zorder=zorder + 1, linespacing=linespacing)


def section(ax, x, y, w, h, theme, label, label_fs=8):
    """섹션 배경 + 상단 헤더 바."""
    # 배경
    bp = FancyBboxPatch((x, y), w, h,
                        boxstyle="round,pad=0,rounding_size=0.012",
                        linewidth=1, edgecolor=theme["header"],
                        facecolor=theme["light"], alpha=0.25, zorder=1)
    ax.add_patch(bp)
    # 왼쪽 강조 바
    bar = FancyBboxPatch((x, y + h - 0.022), w, 0.022,
                         boxstyle="round,pad=0,rounding_size=0.006",
                         linewidth=0, facecolor=theme["header"],
                         alpha=0.90, zorder=2)
    ax.add_patch(bar)
    ax.text(x + 0.012, y + h - 0.011, label,
            ha="left", va="center", fontsize=label_fs,
            color=C_WHITE, fontweight="bold", zorder=3)


def arr(ax, x1, y1, x2, y2, color=C_ARROW, lw=1.5, label="", ls="-"):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="-|>", color=color,
                                lw=lw, mutation_scale=11,
                                linestyle=ls),
                zorder=6)
    if label:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        ax.text(mx + 0.006, my, label, fontsize=6.5,
                color=color, va="center", zorder=7)


# ── 캔버스 ─────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(18, 11.5))
fig.patch.set_facecolor(C_BG)
ax.set_facecolor(C_BG)
ax.set_xlim(0, 1)
ax.set_ylim(0, 1)
ax.axis("off")

# ── 제목 ───────────────────────────────────────────────────
ax.text(0.50, 0.983, "WhatToDo — 최종 아키텍처",
        ha="center", va="top", fontsize=16, fontweight="bold", color="#1A237E")
ax.text(0.50, 0.962, "Supervisor + ReAct 패턴  ·  백그라운드 수집 → PostgreSQL → invoke 출력 → React UI",
        ha="center", va="top", fontsize=9.5, color="#555")

# ══════════════════════════════════════════════════════════
# ① 외부 서비스 (y: 0.895 ~ 0.940)
# ══════════════════════════════════════════════════════════
section(ax, 0.02, 0.887, 0.960, 0.060, T_EXT, "외부 서비스")
svcs = ["Gmail", "Slack", "Jira", "Notion", "Calendar"]
sw, sg = 0.110, 0.064
sx0 = 0.055
for i, s in enumerate(svcs):
    box(ax, sx0 + i * (sw + sg), 0.896, sw, 0.038,
        T_EXT["mid"], s, fs=9, bold=True, radius=0.010)

# ══════════════════════════════════════════════════════════
# ② 백그라운드 워커 (y: 0.795 ~ 0.878)
# ══════════════════════════════════════════════════════════
section(ax, 0.02, 0.793, 0.960, 0.082, T_WRK,
        "백그라운드 워커  (APScheduler — FastAPI lifespan)")

steps = [
    ("SDK 직접 호출", "2~15분 주기 수집"),
    ("LLM 요약", "raw → summary"),
    ("Deadline 추출", '"내일까지" → ISO 변환'),
    ("PostgreSQL 저장", "work_items 테이블"),
]
bw, bg_, bx0 = 0.196, 0.016, 0.035
for i, (t, s) in enumerate(steps):
    bx = bx0 + i * (bw + bg_)
    box(ax, bx, 0.808, bw, 0.054, T_WRK["mid"],
        t + "\n" + s, fs=8.5, bold=False, radius=0.009)
    ax.text(bx + bw / 2, 0.835 + 0.009, t,
            ha="center", va="center", fontsize=8.5,
            fontweight="bold", color=C_WHITE, zorder=5)
    ax.text(bx + bw / 2, 0.835 - 0.011, s,
            ha="center", va="center", fontsize=7.5,
            color="#CFD8DC", zorder=5)
    if i < len(steps) - 1:
        arr(ax, bx + bw + 0.001, 0.835, bx + bw + bg_ - 0.001, 0.835,
            color="#90A4AE", lw=1.2)

# 외부서비스 → 워커
for sx in [sx0 + i * (sw + sg) + sw / 2 for i in range(len(svcs))]:
    arr(ax, sx, 0.887, sx, 0.875, color=T_EXT["mid"], lw=1.1)

# 워커 → DB
arr(ax, 0.50, 0.793, 0.50, 0.768, color=T_WRK["header"], lw=1.8)

# ══════════════════════════════════════════════════════════
# ③ PostgreSQL + pgvector (y: 0.685 ~ 0.762)
# ══════════════════════════════════════════════════════════
section(ax, 0.02, 0.683, 0.960, 0.082, T_DB,
        "데이터 레이어  —  PostgreSQL + pgvector")

db_cols = [
    ("work_items", "summary · deadline · status · source_id"),
    ("sessions", "대화 이력  (AsyncPostgresSaver)"),
    ("policy_docs", "규정집 벡터  (pgvector)"),
    ("users", "JWT · OAuth 토큰  AES-256"),
]
dw, dg, dx0 = 0.210, 0.018, 0.035
for i, (title, sub) in enumerate(db_cols):
    dx = dx0 + i * (dw + dg)
    box(ax, dx, 0.698, dw, 0.056, T_DB["mid"],
        radius=0.009, zorder=3)
    ax.text(dx + dw / 2, 0.726 + 0.008, title,
            ha="center", va="center", fontsize=8.5,
            fontweight="bold", color=C_WHITE, zorder=5)
    ax.text(dx + dw / 2, 0.726 - 0.011, sub,
            ha="center", va="center", fontsize=7.5,
            color="#B2DFDB", zorder=5)

# urgency 주석
ax.text(0.025, 0.687,
        "★  urgency_level 저장 없음 — 조회 시점에 저장된 deadline 기준 남은 시간으로 실시간 계산",
        fontsize=7.5, color=T_DB["header"], va="bottom", fontweight="bold")

# DB → Supervisor
arr(ax, 0.50, 0.683, 0.50, 0.655, color=T_DB["header"], lw=1.8)

# ══════════════════════════════════════════════════════════
# ④ Supervisor (y: 0.615 ~ 0.650)
# ══════════════════════════════════════════════════════════
box(ax, 0.02, 0.613, 0.960, 0.040, T_SUP["header"],
    "Supervisor  (create_react_agent · Smart LLM · temperature=0)"
    "     →     Thought  →  Tool Call  →  Observe  →  ...",
    fs=9, bold=True, radius=0.012)

# Supervisor → SubAgents
agent_xs = [0.083, 0.243, 0.403, 0.563, 0.800]
for cx in agent_xs:
    arr(ax, cx, 0.613, cx, 0.586, color=T_SUP["mid"], lw=1.3)

# ══════════════════════════════════════════════════════════
# ⑤ SubAgents (y: 0.482 ~ 0.606)
# ══════════════════════════════════════════════════════════
section(ax, 0.02, 0.480, 0.960, 0.127, dict(
    header="#37474F", light="#ECEFF1", mid="#546E7A", dark="#263238"),
    "Sub-Agents")

agents = [
    ("fetch_agent",    T_FA, "DB SELECT\n긴급도 실시간 계산\n(deadline 기준 남은 시간)", "안정", "#A5D6A7", "#1B5E20"),
    ("briefing_agent", T_FA, "LLM 단일 호출\n(tool 없음)\n마크다운 브리핑",     "안정", "#A5D6A7", "#1B5E20"),
    ("search_agent",   T_SA, "pgvector RAG\nParent-Child 청킹\nko-sroberta 임베딩", "안정", "#90CAF9", "#0D47A1"),
    ("report_agent",   T_RA, "Excel / PDF\n파일 생성\n(부분 완성)",             "부분", "#CE93D8", "#4A148C"),
    ("action_agent",   T_AA, "외부 SDK 쓰기\n25 tools\nHitL interrupt()",        "불안정", "#EF9A9A", "#B71C1C"),
]

aw, ag_, ax0 = 0.168, 0.013, 0.027
for i, (name, theme, desc, status, badge_bg, badge_tc) in enumerate(agents):
    ax_ = ax0 + i * (aw + ag_)
    box(ax, ax_, 0.494, aw, 0.108, theme["mid"], radius=0.010, zorder=3)
    # 에이전트 이름
    ax.text(ax_ + aw / 2, 0.570, name,
            ha="center", va="center", fontsize=8.5,
            fontweight="bold", color=C_WHITE, zorder=5)
    # 설명
    ax.text(ax_ + aw / 2, 0.530, desc,
            ha="center", va="center", fontsize=7.5,
            color="#ECEFF1", zorder=5, linespacing=1.5)
    # 상태 배지
    bdw = 0.070
    box(ax, ax_ + (aw - bdw) / 2, 0.576, bdw, 0.020,
        badge_bg, status, text_color=badge_tc,
        fs=7, bold=True, radius=0.006, zorder=6)

# action_agent → 외부서비스 (역방향 쓰기)
ax.annotate("", xy=(0.920, 0.900),
            xytext=(0.920, 0.540),
            arrowprops=dict(arrowstyle="-|>", color=T_AA["header"],
                            lw=1.5, mutation_scale=10,
                            connectionstyle="arc3,rad=0"),
            zorder=6)
ax.text(0.945, 0.720, "쓰기\n(발송·생성·삭제)",
        ha="center", va="center", fontsize=7,
        color=T_AA["header"], fontweight="bold", zorder=7)

# ══════════════════════════════════════════════════════════
# ⑥ Validation Layer (y: 0.355 ~ 0.472)
# ══════════════════════════════════════════════════════════
section(ax, 0.02, 0.355, 0.960, 0.118, T_VAL, "Validation Layer")

vals = [
    ("Layer 1 — Python 강제 차단",
     "파괴적 액션: 코드 레벨 interrupt()\n사용자 확인 요청 후 재개\n프롬프트 의존 금지"),
    ("Layer 2 — LLM 품질 검증",
     "has_write_output=True 일 때만 실행\nis_sufficient 판단 → 재생성 최대 2회\n단순 조회는 생략 (토큰 절약)"),
    ("HitL (Human-in-the-Loop)",
     "발송 · 삭제 · 수정 전 사용자 승인\nLangGraph interrupt() 메커니즘\n승인 후 해당 시점부터 재개"),
]
vw, vg, vx0 = 0.291, 0.018, 0.035
for i, (title, desc) in enumerate(vals):
    vx = vx0 + i * (vw + vg)
    box(ax, vx, 0.370, vw, 0.092, T_VAL["mid"], radius=0.009, zorder=3)
    ax.text(vx + vw / 2, 0.434, title,
            ha="center", va="center", fontsize=8.5,
            fontweight="bold", color=C_WHITE, zorder=5)
    ax.text(vx + vw / 2, 0.400, desc,
            ha="center", va="center", fontsize=7.5,
            color="#CFD8DC", zorder=5, linespacing=1.5)

# SubAgents → Validation
arr(ax, 0.50, 0.480, 0.50, 0.465, color=T_VAL["header"], lw=1.8)

# Validation → SSE
arr(ax, 0.50, 0.355, 0.50, 0.330, color=T_SSE["header"], lw=1.8)

# ══════════════════════════════════════════════════════════
# ⑦ UI 출력 (y: 0.220 ~ 0.322)
# ══════════════════════════════════════════════════════════
section(ax, 0.02, 0.218, 0.960, 0.108, T_SSE,
        "UI 출력  —  React 19 + Vite  (nginx)")

ui_items = [
    ("현재 액션 상태 표시",  T_SSE["mid"],  "에이전트가 어떤 도구를\n호출 중인지 UI에 표시"),
    ("invoke 형식 출력",     "#5D4037",     "스트리밍 없음\n완료 후 전체 결과 한번에 반환"),
    ("긴급도 카드 UI",       "#4E342E",     "🔴 긴급  /  🟡 중요  /  🟢 일반\n우선순위 순 카드 목록"),
    ("React 19 + Vite",      "#1565C0",     "nginx 정적 서빙\n다중 사용자 세션 분리"),
]
ew, eg, ex0 = 0.210, 0.018, 0.035
for i, (name, color, desc) in enumerate(ui_items):
    ex = ex0 + i * (ew + eg)
    box(ax, ex, 0.233, ew, 0.076, color, radius=0.010, zorder=3)
    ax.text(ex + ew / 2, 0.285, name,
            ha="center", va="center", fontsize=8.5,
            fontweight="bold", color=C_WHITE, zorder=5)
    ax.text(ex + ew / 2, 0.254, desc,
            ha="center", va="center", fontsize=8,
            color="#EFEBE9", zorder=5, linespacing=1.5)

# UI → 사용자
arr(ax, 0.50, 0.218, 0.50, 0.195, color=T_USER["header"], lw=1.8)

# ══════════════════════════════════════════════════════════
# ⑧ 사용자 (y: 0.110 ~ 0.188)
# ══════════════════════════════════════════════════════════
box(ax, 0.330, 0.108, 0.340, 0.080, T_USER["header"],
    "사용자\n자연어 채팅 입력  /  invoke 응답 수신",
    fs=10, bold=True, radius=0.015)

# ══════════════════════════════════════════════════════════
# ⑨ 범례 (최하단 수평 배치)
# ══════════════════════════════════════════════════════════
legend = [
    (T_FA["mid"],     "읽기 에이전트\n(fetch/briefing)"),
    (T_SA["mid"],     "검색 에이전트\n(search)"),
    (T_RA["mid"],     "파일 생성\n(report)"),
    (T_AA["mid"],     "쓰기 에이전트\n(action, HitL)"),
    (T_EXT["mid"],    "외부 서비스"),
    (T_DB["mid"],     "PostgreSQL\n+pgvector"),
    (T_SUP["header"], "Supervisor\n(ReAct 루프)"),
]

# 범례 배경 바
box(ax, 0.02, 0.010, 0.960, 0.088, "#EBEBEB",
    radius=0.008, lw=1, edge="#CCCCCC", zorder=2)
ax.text(0.50, 0.090, "범례",
        ha="center", va="top", fontsize=8, fontweight="bold",
        color="#555", zorder=5)

lw_item = 0.110; lg_item = 0.016; lx_start = 0.035
for i, (color, label) in enumerate(legend):
    lx = lx_start + i * (lw_item + lg_item)
    box(ax, lx, 0.018, lw_item, 0.068, color, radius=0.007, zorder=3)
    ax.text(lx + lw_item / 2, 0.052, label,
            ha="center", va="center", fontsize=7.5,
            color=C_WHITE, fontweight="bold", zorder=5, linespacing=1.4)

# ══════════════════════════════════════════════════════════
# 저장
# ══════════════════════════════════════════════════════════
out = "/Users/godori/myspace/04_매력일자리/02_code/01_whattodo/docs/whattodo_architecture.png"
plt.savefig(out, dpi=180, bbox_inches="tight",
            facecolor=C_BG, edgecolor="none")
plt.close()
print(f"저장 완료: {out}")
