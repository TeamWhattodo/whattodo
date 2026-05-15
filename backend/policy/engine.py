"""
Policy Engine — 3-레이어 규정 적용.
L1: Hard Override  → scoring 툴 이전
L2: Context Inject → classify 툴 시스템 프롬프트에 주입
L3: Guardrail      → Action Agent 실행 전 차단
"""
from pathlib import Path

from backend.models import WorkCard
from backend.policy.models import PolicyConfig

_POLICY_PATH = Path(__file__).parent / "policy.json"


class PolicyEngine:
    def __init__(self):
        self._policy = self._load()

    def _load(self) -> PolicyConfig:
        if _POLICY_PATH.exists():
            return PolicyConfig.model_validate_json(_POLICY_PATH.read_text(encoding="utf-8"))
        return PolicyConfig()

    def apply_hard_overrides(self, card: WorkCard) -> WorkCard:
        """L1: scoring 툴 호출 전 강제 설정."""
        ...

    def get_context_prompt(self) -> str:
        """L2: classify 툴 시스템 프롬프트에 append."""
        ...

    def apply_guardrails(self, card: WorkCard, proposed_action: str) -> tuple[bool, str]:
        """L3: (allowed, reason) 반환."""
        ...
