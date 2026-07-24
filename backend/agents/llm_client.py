from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.language_models.chat_models import BaseChatModel
import base64

from backend.config import settings


def get_llm(tier: str = "smart") -> BaseChatModel:
    model = settings.smart_model if tier == "smart" else settings.fast_model
    if settings.llm_provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=model, api_key=settings.anthropic_api_key)
    elif settings.llm_provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=model, api_key=settings.openai_api_key)
    else:
        raise ValueError(f"지원하지 않는 provider: {settings.llm_provider!r}. 'anthropic' 또는 'openai'를 사용하세요.")


def complete(prompt: str, tier: str = "smart", system: str = "") -> str:
    messages = []
    if system:
        messages.append(SystemMessage(content=system))
    messages.append(HumanMessage(content=prompt))
    return get_llm(tier).invoke(messages).content


def complete_with_image(prompt: str, image_path: str, tier: str = "smart", system: str = "") -> str:
    """이미지 포함 LLM 호출 (Vision)."""
    with open(image_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")
    
    ext = image_path.split(".")[-1].lower()
    media_type = "image/jpeg" if ext in ["jpg", "jpeg"] else f"image/{ext}"
    
    messages = []
    if system:
        messages.append(SystemMessage(content=system))
    messages.append(HumanMessage(content=[
        {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{image_data}"}},
        {"type": "text", "text": prompt}
    ]))
    return get_llm(tier).invoke(messages).content


if __name__ == "__main__":
    print(complete("안녕하세요", tier="fast"))