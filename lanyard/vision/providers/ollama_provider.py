import base64
import json
import time

import httpx

from lanyard.vision.models import BadgeFinding
from lanyard.vision.providers.base import DETECTOR_PROMPT, BaseVisionProvider


class OllamaVisionProvider(BaseVisionProvider):
    def __init__(
        self,
        model_name: str = "qwen2.5vl",
        api_key: str = "",
        api_base: str = "http://localhost:11434",
    ):
        super().__init__(
            model_name=model_name,
            api_key=api_key,
            api_base=api_base or "http://localhost:11434",
        )
        self.client = httpx.Client(timeout=120.0)

    def analyze_image(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> BadgeFinding:
        b64_str = base64.b64encode(image_bytes).decode("utf-8")
        schema_json = json.dumps(BadgeFinding.model_json_schema(), indent=2)

        prompt = (
            f"{DETECTOR_PROMPT}\n\n"
            f"You MUST respond ONLY with a valid JSON object strictly matching this JSON schema:\n"
            f"{schema_json}\n"
        )

        payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [b64_str],
                }
            ],
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.1,
            },
        }

        url = f"{self.api_base.rstrip('/')}/api/chat"

        max_retries = 3
        for attempt in range(max_retries):
            try:
                resp = self.client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                content = data.get("message", {}).get("content", "")
                if content:
                    parsed = json.loads(content)
                    return BadgeFinding(**parsed)
                return BadgeFinding(has_badge=False, confidence=0.0)
            except Exception:
                if attempt == max_retries - 1:
                    raise
                time.sleep(1.0)

        return BadgeFinding(has_badge=False, confidence=0.0)
