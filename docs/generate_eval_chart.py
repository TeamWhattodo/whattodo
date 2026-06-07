"""WhatToDo 성능 평가 차트 생성."""
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

_KO_FONT = "/System/Library/Fonts/AppleSDGothicNeo.ttc"
fm.fontManager.addfont(_KO_FONT)
matplotlib.rcParams["font.family"] = fm.FontProperties(fname=_KO_FONT).get_name()
matplotlib.rcParams["axes.unicode_minus"] = False

# ── 데이터 로드 ────────────────────────────────────────────
BASE = "/Users/godori/myspace/04_매력일자리/02_code/01_whattodo/docs"
with open(f"{BASE}/4o.json") as f:
    d4o = json.load(f)
with open(f"{BASE}/4o-mini.json") as f:
    dmini = json.load(f)

# ── 시나리오별 partial_score 정리 ──────────────────────────
SCENARIO_ORDER = ["S1","S2","S3","S4","S5","S6","S7","S8","S9","S10","S11","S12"]
SCENARIO_LABELS = {
    "S1":  "전체 브리핑",
    "S2":  "메일 답장 초안",
    "S3":  "사내 규정 조회",
    "S4":  "Jira 이슈 검색",
    "S5":  "캘린더 일정",
    "S6":  "Gmail 메일 조회",
    "S7":  "KPI 보고서",
    "S8":  "영수증 정산서",
    "S9":  "Notion 문서 검색",
    "S10": "업무 상태 변경",
    "S11": "복합 의도",
    "S12": "Slack 메시지 검색",
}

def get_scenario_map(data):
    return {r["scenario_id"]: r for r in data["results"]}

map4o   = get_scenario_map(d4o)
mapmini = get_scenario_map(dmini)

scores_4o   = [map4o.get(s, {}).get("partial_score", 0)   for s in SCENARIO_ORDER]
scores_mini = [mapmini.get(s, {}).get("partial_score", 0) for s in SCENARIO_ORDER]

# 카테고리 점수
cats = ["briefing", "action", "search", "report", "multi_intent"]
cat_labels = ["브리핑", "액션", "검색", "보고서", "복합 의도"]
cat_4o   = [d4o["summary"]["category_scores"][c]   for c in cats]
cat_mini = [dmini["summary"]["category_scores"][c] for c in cats]

# 전체 지표
MODELS  = ["gpt-4o", "gpt-4o-mini"]
M_COLOR = ["#1565C0", "#2E7D32"]
M_LIGHT = ["#BBDEFB", "#C8E6C9"]

# ─────────────────────────────────────────────────────────
# 레이아웃: 2×2 그리드
#   [상단 좌] 전체 지표 (success rate, partial score)
#   [상단 우] 카테고리 레이더 or 바 차트
#   [하단]    시나리오별 히트맵
# ─────────────────────────────────────────────────────────
fig = plt.figure(figsize=(18, 11), facecolor="#F7F8FA")
gs = fig.add_gridspec(2, 2, height_ratios=[1, 1.1],
                      hspace=0.42, wspace=0.30,
                      left=0.06, right=0.97, top=0.91, bottom=0.07)

ax_top_l = fig.add_subplot(gs[0, 0])   # 전체 지표
ax_top_r = fig.add_subplot(gs[0, 1])   # 카테고리 막대
ax_bot   = fig.add_subplot(gs[1, :])   # 시나리오 히트맵

fig.suptitle(
    "WhatToDo 에이전트 성능 평가  —  TheAgentCompany 방법론 기반",
    fontsize=15, fontweight="bold", color="#1A237E", y=0.97
)

# ══════════════════════════════════════════════════════════
# ① 전체 지표 막대 (상단 좌)
# ══════════════════════════════════════════════════════════
ax_top_l.set_facecolor("#FAFAFA")
ax_top_l.set_title("전체 지표 비교", fontsize=12, fontweight="bold", pad=10, color="#333")

metrics = ["Success Rate (%)", "Avg Partial Score (×100)", "Full Completions (건)"]
vals_4o   = [
    d4o["summary"]["success_rate"],
    d4o["summary"]["avg_partial_score"] * 100,
    d4o["summary"]["full_completions"],
]
vals_mini = [
    dmini["summary"]["success_rate"],
    dmini["summary"]["avg_partial_score"] * 100,
    dmini["summary"]["full_completions"],
]

x = np.arange(len(metrics))
bw = 0.32
bars1 = ax_top_l.bar(x - bw/2, vals_4o,   bw, color=M_COLOR[0], alpha=0.88, label="gpt-4o",      zorder=3)
bars2 = ax_top_l.bar(x + bw/2, vals_mini, bw, color=M_COLOR[1], alpha=0.88, label="gpt-4o-mini", zorder=3)

for bar, v in zip(bars1, vals_4o):
    ax_top_l.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1.2,
                  f"{v:.0f}", ha="center", va="bottom", fontsize=10, fontweight="bold",
                  color=M_COLOR[0])
for bar, v in zip(bars2, vals_mini):
    ax_top_l.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1.2,
                  f"{v:.0f}", ha="center", va="bottom", fontsize=10, fontweight="bold",
                  color=M_COLOR[1])

ax_top_l.set_xticks(x)
ax_top_l.set_xticklabels(metrics, fontsize=9)
ax_top_l.set_ylim(0, 105)
ax_top_l.set_ylabel("점수 / 수치", fontsize=9, color="#555")
ax_top_l.yaxis.grid(True, linestyle="--", alpha=0.4, zorder=0)
ax_top_l.set_axisbelow(True)
ax_top_l.spines[["top","right"]].set_visible(False)
ax_top_l.legend(fontsize=9, loc="upper left")

# 승/패 강조 (mini가 높은 경우)
for i, (v1, v2) in enumerate(zip(vals_4o, vals_mini)):
    if v2 > v1:
        ax_top_l.axvspan(i - 0.5, i + 0.5, alpha=0.04, color=M_COLOR[1])

# ══════════════════════════════════════════════════════════
# ② 카테고리 점수 (상단 우)
# ══════════════════════════════════════════════════════════
ax_top_r.set_facecolor("#FAFAFA")
ax_top_r.set_title("카테고리별 Partial Score", fontsize=12, fontweight="bold", pad=10, color="#333")

x2 = np.arange(len(cat_labels))
b1 = ax_top_r.bar(x2 - bw/2, [v*100 for v in cat_4o],   bw,
                  color=M_COLOR[0], alpha=0.88, label="gpt-4o",      zorder=3)
b2 = ax_top_r.bar(x2 + bw/2, [v*100 for v in cat_mini], bw,
                  color=M_COLOR[1], alpha=0.88, label="gpt-4o-mini", zorder=3)

for bar, v in zip(b1, cat_4o):
    ax_top_r.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1.5,
                  f"{v*100:.0f}", ha="center", va="bottom", fontsize=9.5,
                  fontweight="bold", color=M_COLOR[0])
for bar, v in zip(b2, cat_mini):
    ax_top_r.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1.5,
                  f"{v*100:.0f}", ha="center", va="bottom", fontsize=9.5,
                  fontweight="bold", color=M_COLOR[1])

ax_top_r.set_xticks(x2)
ax_top_r.set_xticklabels(cat_labels, fontsize=9.5)
ax_top_r.set_ylim(0, 118)
ax_top_r.set_ylabel("Partial Score (%)", fontsize=9, color="#555")
ax_top_r.yaxis.grid(True, linestyle="--", alpha=0.4, zorder=0)
ax_top_r.set_axisbelow(True)
ax_top_r.spines[["top","right"]].set_visible(False)
ax_top_r.legend(fontsize=9, loc="upper left")

# ══════════════════════════════════════════════════════════
# ③ 시나리오별 비교 (하단 전체 폭)
# ══════════════════════════════════════════════════════════
ax_bot.set_facecolor("#FAFAFA")
ax_bot.set_title("시나리오별 Partial Score 상세", fontsize=12, fontweight="bold", pad=10, color="#333")

x3 = np.arange(len(SCENARIO_ORDER))
bw3 = 0.35
b3 = ax_bot.bar(x3 - bw3/2, scores_4o,   bw3, color=M_COLOR[0], alpha=0.85, label="gpt-4o",      zorder=3)
b4 = ax_bot.bar(x3 + bw3/2, scores_mini, bw3, color=M_COLOR[1], alpha=0.85, label="gpt-4o-mini", zorder=3)

for bar, v in zip(b3, scores_4o):
    ax_bot.text(bar.get_x() + bar.get_width()/2,
                bar.get_height() + 0.012,
                f"{v:.2f}", ha="center", va="bottom", fontsize=8,
                fontweight="bold", color=M_COLOR[0])
for bar, v in zip(b4, scores_mini):
    ax_bot.text(bar.get_x() + bar.get_width()/2,
                bar.get_height() + 0.012,
                f"{v:.2f}", ha="center", va="bottom", fontsize=8,
                fontweight="bold", color=M_COLOR[1])

# full score 구분선 (1.0)
ax_bot.axhline(1.0, color="#EF5350", lw=1.2, ls="--", alpha=0.6, zorder=2)
ax_bot.text(len(SCENARIO_ORDER) - 0.4, 1.02, "완전 성공", fontsize=8,
            color="#EF5350", va="bottom")

# 시나리오 카테고리 색 배경
cat_of = {
    "S1":"briefing","S2":"action","S3":"search","S4":"search","S5":"search",
    "S6":"search","S7":"report","S8":"report","S9":"search","S10":"action",
    "S11":"multi_intent","S12":"search",
}
cat_bg = {"briefing":"#E3F2FD","action":"#FCE4EC","search":"#E8F5E9",
          "report":"#F3E5F5","multi_intent":"#FFF8E1"}
cat_tc = {"briefing":"#1565C0","action":"#C62828","search":"#2E7D32",
          "report":"#6A1B9A","multi_intent":"#F57F17"}

for i, sid in enumerate(SCENARIO_ORDER):
    cat = cat_of[sid]
    ax_bot.axvspan(i - 0.5, i + 0.5, alpha=0.12, color=cat_bg[cat], zorder=0)

xlabels = [f"{sid}\n{SCENARIO_LABELS[sid]}" for sid in SCENARIO_ORDER]
ax_bot.set_xticks(x3)
ax_bot.set_xticklabels(xlabels, fontsize=8.5)
ax_bot.set_ylim(0, 1.22)
ax_bot.set_ylabel("Partial Score", fontsize=9, color="#555")
ax_bot.yaxis.grid(True, linestyle="--", alpha=0.4, zorder=0)
ax_bot.set_axisbelow(True)
ax_bot.spines[["top","right"]].set_visible(False)
ax_bot.legend(fontsize=10, loc="upper right")

# 카테고리 범례 (하단)
cat_patches = [
    mpatches.Patch(color=cat_bg[c], label=cat_labels[i], alpha=0.7)
    for i, c in enumerate(cats)
]
ax_bot.legend(handles=[
    mpatches.Patch(color=M_COLOR[0], label="gpt-4o"),
    mpatches.Patch(color=M_COLOR[1], label="gpt-4o-mini"),
    *cat_patches,
], fontsize=8.5, loc="upper left", ncol=7,
   handlelength=1.2, columnspacing=1.0)

# ── 저장 ───────────────────────────────────────────────────
out = f"{BASE}/whattodo_eval_chart.png"
plt.savefig(out, dpi=180, bbox_inches="tight",
            facecolor="#F7F8FA", edgecolor="none")
plt.close()
print(f"저장 완료: {out}")

# ── 콘솔 요약 ──────────────────────────────────────────────
print("\n=== 요약 ===")
for model, data in [("gpt-4o", d4o), ("gpt-4o-mini", dmini)]:
    s = data["summary"]
    print(f"{model:12s}  success={s['success_rate']}%  partial={s['avg_partial_score']:.3f}"
          f"  full={s['full_completions']}/{s['total_scenarios']}")
print("\n=== 카테고리 ===")
for c, cl in zip(cats, cat_labels):
    v4 = d4o["summary"]["category_scores"][c]
    vm = dmini["summary"]["category_scores"][c]
    winner = "mini ▲" if vm > v4 else ("4o ▲" if v4 > vm else "동점")
    print(f"  {cl:10s}  4o={v4:.2f}  mini={vm:.2f}  → {winner}")
