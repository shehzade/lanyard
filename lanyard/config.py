import json
import os
from pathlib import Path

from pydantic import BaseModel, Field

DEFAULT_DATA_DIR = Path.home() / ".lanyard"
DEFAULT_SESSION_DIR = DEFAULT_DATA_DIR / "session"
DEFAULT_COOKIES_FILE = DEFAULT_DATA_DIR / "cookies.json"
DEFAULT_CONFIG_FILE = DEFAULT_DATA_DIR / "config.json"
DEFAULT_OUTPUT_DIR = Path("lanyard_output")


class LanyardConfig(BaseModel):
    vision_provider: str = Field(default="gemini")
    gemini_api_key: str = Field(default="")
    gemini_model: str = Field(default="gemini-3.8-flash")
    openai_api_key: str = Field(default="")
    openai_model: str = Field(default="gpt-4o")
    openai_base_url: str = Field(default="https://api.openai.com/v1")
    anthropic_api_key: str = Field(default="")
    anthropic_model: str = Field(default="claude-3-7-sonnet-20250219")
    openrouter_api_key: str = Field(default="")
    openrouter_model: str = Field(default="qwen/qwen-2.5-vl-72b-instruct")
    ollama_base_url: str = Field(default="http://localhost:11434")
    ollama_model: str = Field(default="qwen2.5vl")
    headless: bool = Field(default=True)
    min_scroll_delay: float = Field(default=2.0)
    max_scroll_delay: float = Field(default=4.5)
    default_keywords: list[str] = Field(
        default=[
            "first day",
            "new badge",
            "work badge",
            "id badge",
            "started a new position",
            "excited to join",
            "day one",
        ]
    )

    @classmethod
    def load(cls) -> "LanyardConfig":
        DEFAULT_DATA_DIR.mkdir(parents=True, exist_ok=True)
        config = cls()

        for env_path in [Path(".env"), Path.cwd() / ".env"]:
            if env_path.exists():
                try:
                    for line in env_path.read_text(encoding="utf-8").splitlines():
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip("'\"")
                            if k not in os.environ:
                                os.environ[k] = v
                except Exception:
                    pass

        if DEFAULT_CONFIG_FILE.exists():
            try:
                data = json.loads(DEFAULT_CONFIG_FILE.read_text(encoding="utf-8"))
                config = cls(**data)
            except Exception:
                pass

        env_provider = os.environ.get("LANYARD_PROVIDER") or os.environ.get("VISION_PROVIDER")
        if env_provider:
            config.vision_provider = env_provider.lower()

        env_gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if env_gemini_key:
            config.gemini_api_key = env_gemini_key

        env_gemini_model = os.environ.get("GEMINI_MODEL")
        if env_gemini_model:
            config.gemini_model = env_gemini_model

        env_openai_key = os.environ.get("OPENAI_API_KEY")
        if env_openai_key:
            config.openai_api_key = env_openai_key

        env_openai_model = os.environ.get("OPENAI_MODEL")
        if env_openai_model:
            config.openai_model = env_openai_model

        env_openai_base = os.environ.get("OPENAI_BASE_URL") or os.environ.get("OPENAI_API_BASE")
        if env_openai_base:
            config.openai_base_url = env_openai_base

        env_anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
        if env_anthropic_key:
            config.anthropic_api_key = env_anthropic_key

        env_anthropic_model = os.environ.get("ANTHROPIC_MODEL")
        if env_anthropic_model:
            config.anthropic_model = env_anthropic_model

        env_openrouter_key = os.environ.get("OPENROUTER_API_KEY")
        if env_openrouter_key:
            config.openrouter_api_key = env_openrouter_key

        env_openrouter_model = os.environ.get("OPENROUTER_MODEL")
        if env_openrouter_model:
            config.openrouter_model = env_openrouter_model

        env_ollama_base = os.environ.get("OLLAMA_BASE_URL") or os.environ.get("OLLAMA_HOST")
        if env_ollama_base:
            config.ollama_base_url = env_ollama_base

        env_ollama_model = os.environ.get("OLLAMA_MODEL")
        if env_ollama_model:
            config.ollama_model = env_ollama_model

        return config

    def save(self) -> None:
        DEFAULT_DATA_DIR.mkdir(parents=True, exist_ok=True)
        DEFAULT_CONFIG_FILE.write_text(self.model_dump_json(indent=2), encoding="utf-8")
