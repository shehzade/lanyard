from lanyard.vision.models import BadgeFinding
from lanyard.vision.providers import (
    DEFAULT_MODELS,
    DETECTOR_PROMPT,
    SUPPORTED_PROVIDERS,
    BaseVisionProvider,
    get_vision_provider,
)


class BadgeDetector:
    """
    Multimodal vision detector for physical employee ID badges, access passes, and credentials.
    Supports pluggable vision backends:
      - Google Gemini (gemini-3.8-flash, gemini-2.5-pro)
      - OpenAI (gpt-4o, gpt-4o-mini, gpt-4-turbo)
      - Anthropic (claude-3-7-sonnet-20250219, claude-3-5-sonnet-20241022, claude-3-5-haiku)
      - Ollama (llama3.2-vision, qwen2.5-vl, llava)
      - OpenRouter (pixtral, qwen-vl, custom endpoints)
    """

    def __init__(
        self,
        api_key: str = "",
        model_name: str = "gemini-3.8-flash",
        provider: str | None = None,
        api_base: str | None = None,
    ):
        self.provider_instance: BaseVisionProvider = get_vision_provider(
            provider=provider,
            model_name=model_name,
            api_key=api_key,
            api_base=api_base,
        )
        self.model_name = self.provider_instance.model_name

    def analyze_image(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> BadgeFinding:
        return self.provider_instance.analyze_image(image_bytes=image_bytes, mime_type=mime_type)


__all__ = ["DEFAULT_MODELS", "DETECTOR_PROMPT", "SUPPORTED_PROVIDERS", "BadgeDetector"]
