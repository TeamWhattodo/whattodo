"""
평가 결과 시각화 스크립트

실행:
    uv run python -m eval.visualize                          # eval/results/ 전체 비교
    uv run python -m eval.visualize eval/results/파일1.json eval/results/파일2.json
"""
import json
import sys
import argparse
from pathlib import Path

RESULTS_DIR = Path("eval/results")
CHARTS_DIR = Path("eval/charts")


def load_result(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def collect_results(paths: list[Path]) -> list[dict]:
    results = []
    for p in paths:
        data = load_result(p)
        results.append(data)
    return results


def average_by_model(results: list[dict]) -> list[dict]:
    """같은 모델의 결과가 여러 개면 평균 내서 하나로 합친다."""
    from collections import defaultdict
    groups: dict = defaultdict(list)
    for r in results:
        groups[r.get("model", "unknown")].append(r)

    averaged = []
    for model, runs in groups.items():
        if len(runs) == 1:
            averaged.append(runs[0])
            continue

        # summary 평균
        sr = sum(r["summary"]["success_rate"] for r in runs) / len(runs)
        ps = sum(r["summary"]["avg_partial_score"] for r in runs) / len(runs)
        fc = sum(r["summary"]["full_completions"] for r in runs) / len(runs)

        # 카테고리별 평균
        cats: dict = defaultdict(list)
        for r in runs:
            for cat, sc in r["summary"].get("category_scores", {}).items():
                cats[cat].append(sc)
        cat_avg = {cat: round(sum(v) / len(v), 3) for cat, v in cats.items()}

        # 시나리오별 평균
        sid_scores: dict = defaultdict(list)
        sid_meta: dict = {}
        for r in runs:
            for res in r.get("results", []):
                if "error" not in res:
                    sid_scores[res["scenario_id"]].append(res["partial_score"])
                    sid_meta[res["scenario_id"]] = {k: v for k, v in res.items() if k != "partial_score"}

        avg_results = []
        for sid, scores in sid_scores.items():
            entry = {**sid_meta.get(sid, {}), "scenario_id": sid,
                     "partial_score": round(sum(scores) / len(scores), 3)}
            avg_results.append(entry)

        averaged.append({
            "model": model,
            "runs": len(runs),
            "summary": {
                "success_rate": round(sr, 1),
                "avg_partial_score": round(ps, 3),
                "full_completions": round(fc, 2),
                "category_scores": cat_avg,
            },
            "results": avg_results,
        })
        print(f"  {model}: {len(runs)}회 실행 평균 처리")

    return averaged


def plot_comparison(results: list[dict]) -> None:
    import matplotlib.pyplot as plt
    import matplotlib
    matplotlib.rcParams["font.family"] = "Malgun Gothic"  # Windows 한글 폰트
    matplotlib.rcParams["axes.unicode_minus"] = False

    CHARTS_DIR.mkdir(parents=True, exist_ok=True)

    labels = [r.get("model", "unknown") for r in results]
    categories = sorted({
        cat
        for r in results
        for cat in r.get("summary", {}).get("category_scores", {}).keys()
    })

    # ── 1. Success Rate 바 차트 ──────────────────────────────────
    fig, ax = plt.subplots(figsize=(8, 4))
    rates = [r["summary"]["success_rate"] for r in results]
    bars = ax.bar(labels, rates, color=["#4C72B0", "#DD8452", "#55A868", "#C44E52"][:len(labels)])
    ax.set_ylim(0, 100)
    ax.set_ylabel("Success Rate (%)")
    ax.set_title("모델별 Success Rate 비교")
    for bar, val in zip(bars, rates):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1, f"{val:.1f}%", ha="center", fontsize=10)
    plt.tight_layout()
    out = CHARTS_DIR / "success_rate.png"
    plt.savefig(out, dpi=150)
    plt.close()
    print(f"저장: {out}")

    # ── 2. Partial Score 바 차트 ────────────────────────────────
    fig, ax = plt.subplots(figsize=(8, 4))
    scores = [r["summary"]["avg_partial_score"] for r in results]
    bars = ax.bar(labels, scores, color=["#4C72B0", "#DD8452", "#55A868", "#C44E52"][:len(labels)])
    ax.set_ylim(0, 1.0)
    ax.set_ylabel("Avg Partial Score")
    ax.set_title("모델별 평균 Partial Score 비교")
    for bar, val in zip(bars, scores):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01, f"{val:.3f}", ha="center", fontsize=10)
    plt.tight_layout()
    out = CHARTS_DIR / "partial_score.png"
    plt.savefig(out, dpi=150)
    plt.close()
    print(f"저장: {out}")

    # ── 3. 카테고리별 Partial Score 그룹 바 차트 ────────────────
    if categories:
        import numpy as np
        x = np.arange(len(categories))
        width = 0.8 / max(len(results), 1)
        fig, ax = plt.subplots(figsize=(10, 5))
        colors = ["#4C72B0", "#DD8452", "#55A868", "#C44E52"]
        for i, (r, label) in enumerate(zip(results, labels)):
            cat_scores = r["summary"].get("category_scores", {})
            vals = [cat_scores.get(cat, 0) for cat in categories]
            offset = (i - len(results) / 2 + 0.5) * width
            bars = ax.bar(x + offset, vals, width, label=label, color=colors[i % len(colors)])
        ax.set_xticks(x)
        ax.set_xticklabels(categories, rotation=15)
        ax.set_ylim(0, 1.0)
        ax.set_ylabel("Partial Score")
        ax.set_title("카테고리별 Partial Score 모델 비교")
        ax.legend()
        plt.tight_layout()
        out = CHARTS_DIR / "category_comparison.png"
        plt.savefig(out, dpi=150)
        plt.close()
        print(f"저장: {out}")

    # ── 4. 시나리오별 Partial Score 히트맵 ─────────────────────
    scenario_ids = sorted({
        r["scenario_id"]
        for data in results
        for r in data.get("results", [])
        if "error" not in r
    })
    if scenario_ids and len(results) > 1:
        import numpy as np
        matrix = []
        for data in results:
            row_map = {r["scenario_id"]: r["partial_score"] for r in data.get("results", []) if "error" not in r}
            matrix.append([row_map.get(sid, 0) for sid in scenario_ids])

        fig, ax = plt.subplots(figsize=(max(8, len(scenario_ids)), max(3, len(results))))
        im = ax.imshow(matrix, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
        ax.set_xticks(range(len(scenario_ids)))
        ax.set_xticklabels(scenario_ids, rotation=45, ha="right")
        ax.set_yticks(range(len(labels)))
        ax.set_yticklabels(labels)
        ax.set_title("시나리오 × 모델 Partial Score 히트맵")
        plt.colorbar(im, ax=ax)
        for i in range(len(results)):
            for j in range(len(scenario_ids)):
                ax.text(j, i, f"{matrix[i][j]:.2f}", ha="center", va="center", fontsize=8,
                        color="black" if 0.3 < matrix[i][j] < 0.7 else "white")
        plt.tight_layout()
        out = CHARTS_DIR / "heatmap.png"
        plt.savefig(out, dpi=150)
        plt.close()
        print(f"저장: {out}")

    print(f"\n모든 차트 저장 완료: {CHARTS_DIR}/")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="평가 결과 시각화")
    parser.add_argument("files", nargs="*", help="비교할 result JSON 파일 경로 (생략 시 eval/results/ 전체)")
    args = parser.parse_args()

    if args.files:
        paths = [Path(f) for f in args.files]
    else:
        paths = sorted(RESULTS_DIR.glob("eval_*.json"))
        if not paths:
            print(f"결과 파일이 없습니다. 먼저 평가를 실행하세요: uv run python -m eval.run_eval")
            sys.exit(1)
        print(f"발견된 결과 파일 {len(paths)}개: {[p.name for p in paths]}")

    results = collect_results(paths)
    if not results:
        print("로드된 결과가 없습니다.")
        sys.exit(1)

    print(f"\n로드된 결과: {len(results)}개")
    results = average_by_model(results)
    print(f"비교 모델: {[r.get('model', 'unknown') for r in results]}")
    plot_comparison(results)
