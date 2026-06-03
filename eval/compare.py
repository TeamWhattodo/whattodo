"""
모델 비교 평가 스크립트

실행:
    uv run python -m eval.compare                              # 기본 모델 목록으로 비교
    uv run python -m eval.compare gpt-4o gpt-4o-mini          # 모델 직접 지정
    uv run python -m eval.compare gpt-4o gpt-4o-mini --clean  # 이전 결과 삭제 후 실행

동작 순서:
    1. eval/results/, eval/charts/ 정리 (--clean 옵션 또는 기본 동작)
    2. 각 모델별로 run_eval 실행
    3. visualize로 비교 차트 생성
"""
import sys
import shutil
import argparse
import subprocess
from pathlib import Path

RESULTS_DIR = Path("eval/results")
CHARTS_DIR  = Path("eval/charts")
DEFAULT_MODELS = ["gpt-4o", "gpt-4o-mini", "claude-sonnet-4-6"]


def clean():
    for d in (RESULTS_DIR, CHARTS_DIR):
        if d.exists():
            shutil.rmtree(d)
            print(f"🗑  {d}/ 삭제")
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)


def run_eval(model: str):
    print(f"\n{'='*60}")
    print(f"▶ 모델 평가 시작: {model}")
    print(f"{'='*60}")
    result = subprocess.run(
        [sys.executable, "-m", "eval.run_eval", "--model", model],
        check=False,
    )
    if result.returncode != 0:
        print(f"⚠️  {model} 평가 중 오류 발생 (계속 진행)")


def run_visualize():
    print(f"\n{'='*60}")
    print("▶ 비교 차트 생성")
    print(f"{'='*60}")
    subprocess.run([sys.executable, "-m", "eval.visualize"], check=False)


if __name__ == "__main__":
    # 실행 위치 검증
    if not Path("pyproject.toml").exists():
        print("❌ 오류: 프로젝트 루트(whattodo/)에서 실행해야 합니다.")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="모델 비교 평가")
    parser.add_argument("models", nargs="*", help=f"비교할 모델 목록 (기본값: {DEFAULT_MODELS})")
    parser.add_argument("--runs", type=int, default=1, help="모델당 반복 실행 횟수 (기본값: 1, 권장: 5)")
    parser.add_argument("--no-clean", action="store_true", help="이전 결과 삭제 안 함")
    args = parser.parse_args()

    models = args.models or DEFAULT_MODELS

    print(f"\n비교 모델: {models}")
    print(f"모델당 실행 횟수: {args.runs}회")
    print(f"결과 정리: {'건너뜀' if args.no_clean else '실행'}")

    if not args.no_clean:
        clean()

    for model in models:
        for i in range(args.runs):
            if args.runs > 1:
                print(f"\n[{model}] {i+1}/{args.runs}회 실행")
            run_eval(model)

    run_visualize()

    print(f"\n✅ 완료. 차트: {CHARTS_DIR}/")
