"""
LLM Provider 추상화 — SDK를 직접 import하지 말고 이 파일만 호출한다.

    from backend.agents import llm_client
    text = await llm_client.complete("요약해줘", tier="fast")
"""
from typing import Literal

from backend.config import settings

Tier = Literal["fast", "smart"]


def _model(tier: Tier) -> str:
    return settings.fast_model if tier == "fast" else settings.smart_model


async def complete(
    prompt: str,
    tier: Tier = "fast",
    system: str | None = None,
    max_tokens: int = 1024,
) -> str:
    """단일 LLM 호출 진입점. LLM_PROVIDER 환경 변수에 따라 라우팅."""
    if settings.llm_provider == "anthropic":
        return await _anthropic(prompt, tier, system, max_tokens)
    if settings.llm_provider == "openai":
        return await _openai(prompt, tier, system, max_tokens)
    raise ValueError(f"지원하지 않는 LLM_PROVIDER: {settings.llm_provider!r}")


async def _anthropic(prompt: str, tier: Tier, system: str | None, max_tokens: int) -> str:
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    kwargs: dict = {
        "model": _model(tier),
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        kwargs["system"] = system
    response = await client.messages.create(**kwargs)
    return response.content[0].text


async def _openai(prompt: str, tier: Tier, system: str | None, max_tokens: int) -> str:
    import openai

    client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    response = await client.chat.completions.create(
        model=_model(tier), messages=messages, max_tokens=max_tokens,
    )
    return response.choices[0].message.content
