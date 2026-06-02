"""
WhatToDo 에이전트 성능 평가 스크립트
TheAgentCompany 방법론 기반 (Checkpoint + Partial Completion Score)

실행:
    uv run python -m eval.run_eval                          # 전체 시나리오 (기본 모델)
    uv run python -m eval.run_eval S1 S3                    # 특정 시나리오만
    uv run python -m eval.run_eval --model gpt-4o           # 모델 지정
    uv run python -m eval.run_eval --model gpt-4o S1 S3     # 모델 + 특정 시나리오
"""
import json
import sys
import argparse
import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# 실행 위치 검증 — pyproject.toml이 없으면 잘못된 디렉토리
if not Path("pyproject.toml").exists():
    print("❌ 오류: 프로젝트 루트(whattodo/)에서 실행해야 합니다.")
    print("   cd c:\\intern_study\\test\\whattodo")
    sys.exit(1)

from backend.agents.graph import run_graph
from eval.scenarios import SCENARIOS
from eval.evaluator import (
    check_tool_call,
    check_response_contains,
    llm_judge,
    check_file_exists,
    extract_response,
)

RESULTS_DIR = Path("eval/results")


def evaluate_checkpoint(cp: dict, state: dict, response_text: str, query: str) -> dict:
    cp_type = cp["type"]

    if cp_type == "tool_call":
        passed, reason = check_tool_call(state, cp["tool"])
    elif cp_type == "response_contains":
        passed, reason = check_response_contains(
            response_text, cp["keywords"], cp.get("min_match", 1)
        )
    elif cp_type == "llm_judge":
        passed, reason = llm_judge(response_text, cp["criterion"], query)
    elif cp_type == "file_exists":
        passed, reason = check_file_exists(state, cp["field"])
    else:
        passed, reason = False, f"알 수 없는 타입: {cp_type}"

    return {
        "id": cp["id"],
        "name": cp["name"],
        "points_total": cp["points"],
        "points_earned": cp["points"] if passed else 0,
        "passed": passed,
        "reason": reason,
    }


def evaluate_scenario(scenario: dict) -> dict:
    print(f"\n{'='*60}")
    print(f"[{scenario['id']}] {scenario['name']}  |  카테고리: {scenario['category']}")
    print(f"요청: \"{scenario['query']}\"")
    print("-" * 60)

    thread_id = f"eval_{scenario['id']}_{datetime.datetime.now().strftime('%H%M%S')}"

    try:
        state = run_graph(scenario["query"], thread_id=thread_id)
        response_text = extract_response(state)
        print(f"응답 미리보기: {response_text[:150]}...")
    except Exception as e:
        print(f"❌ 실행 오류: {e}")
        return {
            "scenario_id": scenario["id"],
            "name": scenario["name"],
            "category": scenario["category"],
            "query": scenario["query"],
            "error": str(e),
            "checkpoints": [],
            "earned": 0,
            "total": scenario["total_points"],
            "full_score": 0,
            "partial_score": 0.0,
            "timestamp": datetime.datetime.now().isoformat(),
        }

    print()
    checkpoint_results = []
    for cp in scenario["checkpoints"]:
        result = evaluate_checkpoint(cp, state, response_text, scenario["query"])
        icon = "✅" if result["passed"] else "❌"
        print(f"  {icon} [{result['id']}] {result['name']}")
        print(f"       점수: {result['points_earned']}/{result['points_total']}pt  |  {result['reason']}")
        checkpoint_results.append(result)

    earned = sum(r["points_earned"] for r in checkpoint_results)
    total = scenario["total_points"]
    full = 1 if earned == total else 0
    partial_score = round(0.5 * (earned / total) + 0.5 * full, 3)

    print(f"\n  → 최종: {earned}/{total}pt  |  Partial Score: {partial_score:.3f}  |  {'🎯 완전 완료' if full else '⚠️  부분 완료'}")

    return {
        "scenario_id": scenario["id"],
        "name": scenario["name"],
        "category": scenario["category"],
        "query": scenario["query"],
        "response_preview": response_text[:500],
        "checkpoints": checkpoint_results,
        "earned": earned,
        "total": total,
        "full_score": full,
        "partial_score": partial_score,
        "timestamp": datetime.datetime.now().isoformat(),
    }


def run_all(scenario_ids: list[str] | None = None, model_name: str | None = None) -> dict:
    scenarios = SCENARIOS
    if scenario_ids:
        scenarios = [s for s in SCENARIOS if s["id"] in scenario_ids]
        not_found = set(scenario_ids) - {s["id"] for s in scenarios}
        if not_found:
            print(f"⚠️  존재하지 않는 시나리오 ID: {not_found}")

    print(f"\n{'='*60}")
    print(f"WhatToDo 에이전트 성능 평가")
    print(f"모델: {model_name or '기본값'}")
    print(f"시나리오 수: {len(scenarios)}개")
    print(f"시작 시각: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    results = [evaluate_scenario(s) for s in scenarios]

    # 요약
    valid = [r for r in results if "error" not in r]
    total_full = sum(r["full_score"] for r in valid)
    avg_partial = sum(r["partial_score"] for r in valid) / len(valid) if valid else 0
    success_rate = total_full / len(valid) * 100 if valid else 0

    print(f"\n{'='*60}")
    print("평가 결과 요약")
    print(f"{'='*60}")
    print(f"총 시나리오 : {len(results)}개  (오류: {len(results) - len(valid)}개)")
    print(f"Success Rate: {success_rate:.1f}%  ({total_full}/{len(valid)})")
    print(f"평균 Partial Score: {avg_partial:.3f}")
    print()

    # 카테고리별 집계
    from collections import defaultdict
    by_cat: dict = defaultdict(list)
    for r in valid:
        by_cat[r["category"]].append(r["partial_score"])

    print("카테고리별 평균 Partial Score:")
    for cat, scores in by_cat.items():
        print(f"  {cat:12s}: {sum(scores)/len(scores):.3f}  (n={len(scores)})")
    print()

    print("시나리오별 결과:")
    for r in results:
        if "error" in r:
            print(f"  💥 [{r['scenario_id']}] {r['name']}: 오류 발생")
        else:
            icon = "✅" if r["full_score"] else "⚠️ "
            print(f"  {icon} [{r['scenario_id']}] {r['name']}: {r['earned']}/{r['total']}pt  Partial={r['partial_score']:.3f}")

    # 저장
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    output = {
        "timestamp": ts,
        "model": model_name or "default",
        "summary": {
            "total_scenarios": len(results),
            "valid_scenarios": len(valid),
            "success_rate": round(success_rate, 1),
            "avg_partial_score": round(avg_partial, 3),
            "full_completions": total_full,
            "category_scores": {
                cat: round(sum(s) / len(s), 3) for cat, s in by_cat.items()
            },
        },
        "results": results,
    }

    path = RESULTS_DIR / f"eval_{ts}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n결과 저장: {path}")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WhatToDo 에이전트 성능 평가")
    parser.add_argument("scenarios", nargs="*", help="평가할 시나리오 ID (예: S1 S3). 생략 시 전체 실행")
    parser.add_argument("--model", type=str, default=None, help="사용할 모델 이름 (예: gpt-4o, gpt-4o-mini, claude-sonnet-4-6)")
    args = parser.parse_args()

    # 모델 오버라이드
    if args.model:
        from backend.config import settings
        settings.smart_model = args.model
        settings.fast_model = args.model
        print(f"모델 오버라이드: {args.model}")

    run_all(args.scenarios or None, model_name=args.model)
