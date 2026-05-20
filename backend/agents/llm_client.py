from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.language_models.chat_models import BaseChatModel

from backend.config import settings


def get_llm(tier: str = "smart") -> BaseChatModel:
    """설정된 provider에 맞는 LangChain 채팅 모델을 반환한다."""
    model = settings.smart_model if tier == "smart" else settings.fast_model
    if settings.provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=model, api_key=settings.anthropic_api_key)
    elif settings.provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=model, api_key=settings.openai_api_key)
    else:
        raise ValueError(f"지원하지 않는 provider: {settings.provider!r}. 'anthropic' 또는 'openai'를 사용하세요.")


def complete(prompt: str, tier: str = "smart", system: str = "") -> str:
    """단일 LLM 호출. tool_use 없음. classify/write 전용."""
    messages = []
    if system:
        messages.append(SystemMessage(content=system))
    messages.append(HumanMessage(content=prompt))
    return get_llm(tier).invoke(messages).content


if __name__ == "__main__":
    print(complete("안녕하세요", tier="fast"))
