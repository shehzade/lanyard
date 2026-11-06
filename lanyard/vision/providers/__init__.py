from lanyard.vision.providers.anthropic_provider import AnthropicVisionProvider
from lanyard.vision.providers.base import DETECTOR_PROMPT, BaseVisionProvider
from lanyard.vision.providers.gemini import GeminiVisionProvider
from lanyard.vision.providers.ollama_provider import OllamaVisionProvider
from lanyard.vision.providers.openai_provider import OpenAIVisionProvider
from lanyard.vision.providers.openrouter import OpenRouterVisionProvider

SUPPORTED_PROVIDERS = {
    "gemini": GeminiVisionProvider,
    "openai": OpenAIVisionProvider,
    "anthropic": AnthropicVisionProvider,
    "ollama": OllamaVisionProvider,
    "openrouter": OpenRouterVisionProvider,
}

DEFAULT_MODELS = {
    "gemini": "gemini-3.8-flash",
    "openai": "gpt-4o",
    "anthropic": "claude-3-7-sonnet-20250219",
    "ollama": "llama3.2-vision",
    "openrouter": "qwen/qwen-2.5-vl-72b-instruct",
}


def get_vision_provider(
    provider: str | None = None,
    model_name: str | None = None,
    api_key: str | None = None,
    api_base: str | None = None,
) -> BaseVisionProvider:
    """
    Factory function returning the appropriate vision provider for physical badge card analysis.
    Auto-detects the provider if not explicitly specified.
    """
    selected_provider = (provider or "").strip().lower()

    if not selected_provider or selected_provider == "auto":
        model_lower = (model_name or "").lower()
        if model_lower.startswith("claude"):
            selected_provider = "anthropic"
        elif model_lower.startswith(("gpt-", "o1")):
            selected_provider = "openai"
        elif any(k in model_lower for k in ["llama3.2-vision", "llava", "minicpm"]):
            selected_provider = "ollama"
        elif "/" in model_lower:
            selected_provider = "openrouter"
        else:
            selected_provider = "gemini"

    provider_cls = SUPPORTED_PROVIDERS.get(selected_provider, GeminiVisionProvider)
    effective_model = model_name or DEFAULT_MODELS.get(selected_provider, "gemini-3.8-flash")

    return provider_cls(
        model_name=effective_model,
        api_key=api_key or "",
        api_base=api_base or "",
    )


__all__ = [
    "DEFAULT_MODELS",
    "DETECTOR_PROMPT",
    "SUPPORTED_PROVIDERS",
    "AnthropicVisionProvider",
    "BaseVisionProvider",
    "GeminiVisionProvider",
    "OllamaVisionProvider",
    "OpenAIVisionProvider",
    "OpenRouterVisionProvider",
    "get_vision_provider",
]
