"""4단계 아키텍처 — 레이어 구분 다이어그램."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import matplotlib.patheffects as pe

_KO_FONT = "/System/Library/Fonts/AppleSDGothicNeo.ttc"
fm.fontManager.addfont(_KO_FONT)
matplotlib.rcParams["font.family"] = fm.FontProperties(fname=_KO_FONT).get_name()
matplotlib.rcParams["axes.unicode_minus"] = False

# ── 색상 ─────────────────────────────────────────────────
C_BG    = "#F7F8FA"
C_WHITE = "#FFFFFF"
LAYER_COLORS = {
    "ext":    ("#1565C0", "#BBDEFB"),   # 외부서비스
    "worker": ("#263238", "#ECEFF1"),   # 워커
    "db":     ("#004D40", "#B2DFDB"),   # DB
    "agent":  ("#1B2631", "#EAF0F6"),   # Agent 서비스
    "ui":     ("#4E342E", "#EFEBE9"),   # UI
}
A_FA = "#2E7D32"; A_BA = "#388E3C"
A_SA = "#0D47A1"; A_RA = "#4A148C"; A_AA = "#B71C1C"

fig, ax = plt.subplots(figsize=(16, 13))
fig.patch.set_facecolor(C_BG)
ax.set_facecolor(C_BG)
ax.set_xlim(0, 1); ax.set_ylim(0, 1)
ax.axis("off")

# ── 헬퍼 ─────────────────────────────────────────────────
def box(ax, x, y, w, h, fill, text="", tc="#FFFFFF",
        fs=8.5, bold=False, radius=0.012, lw=0, edge="none", z=3):
    bp = FancyBboxPatch((x, y), w, h,
                        boxstyle=f"round,pad=0,rounding_size={radius}",
                        linewidth=lw, edgecolor=edge,
                        facecolor=fill, zorder=z)
    ax.add_patch(bp)
    if text:
        ax.text(x + w/2, y + h/2, text, ha="center", va="center",
                fontsize=fs, color=tc,
                fontweight="bold" if bold else "normal",
                zorder=z+1, linespacing=1.5)

def layer_bg(ax, y, h, theme_key, label, label_fs=9):
    fill_c, bg_c = LAYER_COLORS[theme_key]
    bp = FancyBboxPatch((0.02, y), 0.96, h,
                        boxstyle="round,pad=0,rounding_size=0.012",
                        linewidth=1.5, edgecolor=fill_c,
                        facecolor=bg_c, alpha=0.30, zorder=1)
    ax.add_patch(bp)
    # 왼쪽 강조 바
    bar = FancyBboxPatch((0.02, y + h - 0.030), 0.96, 0.030,
                         boxstyle="round,pad=0,rounding_size=0.008",
                         linewidth=0, facecolor=fill_c, alpha=0.85, zorder=2)
    ax.add_patch(bar)
    ax.text(0.033, y + h - 0.015, label,
            ha="left", va="center", fontsize=label_fs,
            color=C_WHITE, fontweight="bold", zorder=3)

def arr(ax, x1, y1, x2, y2, color="#555", lw=1.8, label="",
        style="-|>", rad=0.0, ls="solid"):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(
                    arrowstyle=style, color=color, lw=lw,
                    mutation_scale=12,
                    connectionstyle=f"arc3,rad={rad}",
                    linestyle=ls,
                ),
                zorder=6)
    if label:
        mx, my = (x1+x2)/2, (y1+y2)/2
        ax.text(mx + 0.012, my, label, fontsize=7.5,
                color=color, va="center", fontweight="bold", zorder=7)

# ══════════════════════════════════════════════════════════
# 레이어 정의 (위 → 아래)
# y 좌표: 1.0 상단 기준
# ══════════════════════════════════════════════════════════

# ① 외부 서비스  y: 0.850 ~ 0.960
layer_bg(ax, 0.852, 0.105, "ext", "① 외부 서비스")
svcs = ["Gmail", "Slack", "Jira", "Notion", "Calendar"]
sw, sg, sx0 = 0.110, 0.062, 0.058
for i, s in enumerate(svcs):
    box(ax, sx0 + i*(sw+sg), 0.872, sw, 0.056,
        LAYER_COLORS["ext"][0], s, fs=9.5, bold=True, radius=0.010)

# ② 백그라운드 워커  y: 0.710 ~ 0.837
layer_bg(ax, 0.712, 0.124, "worker",
         "② 백그라운드 워커  (APScheduler — FastAPI lifespan, 2~15분 주기)")
steps = [
    ("SDK 직접 호출",      "각 서비스 API 호출"),
    ("LLM 요약",          "raw → summary 변환"),
    ("deadline 추출",      '"내일까지" → ISO 변환'),
    ("PostgreSQL 저장",    "work_items 테이블"),
]
bw, bg_, bx0 = 0.196, 0.017, 0.038
for i, (t, s) in enumerate(steps):
    bx = bx0 + i*(bw+bg_)
    box(ax, bx, 0.732, bw, 0.072,
        LAYER_COLORS["worker"][0], radius=0.009)
    ax.text(bx+bw/2, 0.768+0.010, t,
            ha="center", va="center", fontsize=8.5,
            fontweight="bold", color=C_WHITE, zorder=5)
    ax.text(bx+bw/2, 0.768-0.013, s,
            ha="center", va="center", fontsize=7.5,
            color="#B0BEC5", zorder=5)
    if i < len(steps)-1:
        arr(ax, bx+bw+0.002, 0.768, bx+bw+bg_-0.002, 0.768,
            color="#78909C", lw=1.2)

# ③ 데이터 레이어  y: 0.570 ~ 0.697
layer_bg(ax, 0.572, 0.123, "db",
         "③ 데이터 레이어  —  PostgreSQL + pgvector")
db_items = [
    ("work_items",   "summary · deadline · status · source_id"),
    ("sessions",     "대화 이력  (AsyncPostgresSaver)"),
    ("policy_docs",  "규정집 벡터  (pgvector)"),
    ("users",        "JWT · OAuth 토큰  AES-256"),
]
dw, dg, dx0 = 0.207, 0.018, 0.038
for i, (t, s) in enumerate(db_items):
    dx = dx0 + i*(dw+dg)
    box(ax, dx, 0.592, dw, 0.072,
        LAYER_COLORS["db"][0], radius=0.009)
    ax.text(dx+dw/2, 0.628+0.010, t,
            ha="center", va="center", fontsize=8.5,
            fontweight="bold", color=C_WHITE, zorder=5)
    ax.text(dx+dw/2, 0.628-0.013, s,
            ha="center", va="center", fontsize=7.5,
            color="#80CBC4", zorder=5)

ax.text(0.50, 0.578,
        "★  urgency_level 저장 없음 — 조회 시점에 deadline 기준 남은 시간으로 실시간 계산",
        ha="center", va="bottom", fontsize=7.5,
        color=LAYER_COLORS["db"][0], fontweight="bold", zorder=5)

# ④ Agent 서비스  y: 0.310 ~ 0.557
layer_bg(ax, 0.312, 0.243, "agent",
         "④ Agent 서비스  —  Supervisor + ReAct 패턴")

# Supervisor 바
box(ax, 0.038, 0.490, 0.924, 0.045,
    "#212121",
    "Supervisor  (create_react_agent · Smart LLM · temperature=0)"
    "     →     Thought  →  Tool Call  →  Observe  →  ...",
    fs=8.5, bold=True, radius=0.010)

# SubAgents
agents = [
    ("fetch_agent",    A_FA, "DB SELECT\n긴급도 실시간 계산\n(deadline 기준 남은 시간)"),
    ("briefing_agent", A_BA, "LLM 단일 호출\n(tool 없음)\n마크다운 브리핑"),
    ("search_agent",   A_SA, "pgvector RAG\nParent-Child 청킹\nko-sroberta 임베딩"),
    ("report_agent",   A_RA, "Excel / PDF 생성\n(부분 완성)"),
    ("action_agent",   A_AA, "외부 SDK 직접 쓰기\n25 tools\nHitL interrupt()"),
]
aw, ag_, ax0 = 0.165, 0.013, 0.030
for i, (name, color, desc) in enumerate(agents):
    axp = ax0 + i*(aw+ag_)
    box(ax, axp, 0.326, aw, 0.148, color, radius=0.010)
    ax.text(axp+aw/2, 0.430, name,
            ha="center", va="center", fontsize=8.5,
            fontweight="bold", color=C_WHITE, zorder=5)
    ax.text(axp+aw/2, 0.388, desc,
            ha="center", va="center", fontsize=7.5,
            color="#ECEFF1", zorder=5, linespacing=1.5)
    # Supervisor → SubAgent
    arr(ax, axp+aw/2, 0.490, axp+aw/2, 0.474,
        color="#90A4AE", lw=1.2)

# fetch_agent에 DB 읽기 강조 배지
fa_cx = ax0 + 0*(aw+ag_) + aw/2
box(ax, fa_cx-0.048, 0.455, 0.096, 0.022,
    "#1B5E20", "← DB 읽기",
    fs=7, bold=True, radius=0.007, z=6)

# ⑤ 사용자 인터페이스  y: 0.160 ~ 0.295
layer_bg(ax, 0.162, 0.132, "ui",
         "⑤ 사용자 인터페이스  —  React 19 + Vite  (nginx)")
ui_items = [
    ("현재 액션 상태 표시", "에이전트 동작 현황 실시간 표시"),
    ("invoke 형식 출력",    "완료 후 전체 결과 한번에 반환\n(스트리밍 없음)"),
    ("긴급도 카드 UI",      "🔴 긴급 / 🟡 중요 / 🟢 일반\n우선순위 순 카드 목록"),
]
uw, ug, ux0 = 0.270, 0.028, 0.075
for i, (t, s) in enumerate(ui_items):
    ux = ux0 + i*(uw+ug)
    box(ax, ux, 0.182, uw, 0.090,
        LAYER_COLORS["ui"][0], radius=0.009)
    ax.text(ux+uw/2, 0.227+0.013, t,
            ha="center", va="center", fontsize=8.5,
            fontweight="bold", color=C_WHITE, zorder=5)
    ax.text(ux+uw/2, 0.227-0.018, s,
            ha="center", va="center", fontsize=7.5,
            color="#BCAAA4", zorder=5, linespacing=1.5)

# ══════════════════════════════════════════════════════════
# 레이어 간 화살표
# ══════════════════════════════════════════════════════════

# ① 외부 서비스 → ② 워커  (수집 읽기)
arr(ax, 0.50, 0.852, 0.50, 0.836, color=LAYER_COLORS["ext"][0], lw=2.0,
    label="수집 (읽기)")

# ② 워커 → ③ DB
arr(ax, 0.50, 0.712, 0.50, 0.695, color=LAYER_COLORS["worker"][0], lw=2.0)

# ③ DB → fetch_agent (읽기, 강조)
arr(ax, fa_cx, 0.572, fa_cx, 0.474,
    color=LAYER_COLORS["db"][0], lw=2.2, label="읽기")

# ③ DB → search_agent (pgvector RAG)
sa_cx = ax0 + 2*(aw+ag_) + aw/2
arr(ax, sa_cx, 0.572, sa_cx, 0.474,
    color=LAYER_COLORS["db"][0], lw=1.5)

# ④ Agent → ⑤ UI
arr(ax, 0.50, 0.312, 0.50, 0.295,
    color=LAYER_COLORS["agent"][0], lw=2.0)

# action_agent → ① 외부서비스 (쓰기, 역방향 강조)
aa_cx = ax0 + 4*(aw+ag_) + aw/2
ax.annotate("",
    xy=(0.930, 0.900), xytext=(0.930, 0.400),
    arrowprops=dict(
        arrowstyle="-|>", color=A_AA, lw=2.0,
        mutation_scale=13,
        connectionstyle="arc3,rad=0",
    ), zorder=7)
ax.text(0.955, 0.650, "쓰기\n(발송·생성·삭제)",
        ha="center", va="center", fontsize=7.5,
        color=A_AA, fontweight="bold", zorder=8)

# ══════════════════════════════════════════════════════════
# 제목
# ══════════════════════════════════════════════════════════
ax.text(0.50, 0.983,
        "4단계  —  Supervisor + ReAct 패턴 (현재)",
        ha="center", va="top", fontsize=14,
        fontweight="bold", color="#1A237E")
ax.text(0.50, 0.963,
        "외부 서비스  →  백그라운드 수집  →  PostgreSQL  →  Supervisor  →  UI",
        ha="center", va="top", fontsize=9, color="#555")

# ══════════════════════════════════════════════════════════
# 저장
# ══════════════════════════════════════════════════════════
out = "/Users/godori/myspace/04_매력일자리/02_code/01_whattodo/docs/diagrams/arch_phase4.png"
plt.savefig(out, dpi=180, bbox_inches="tight",
            facecolor=C_BG, edgecolor="none")
plt.close()
print(f"저장 완료: {out}")
