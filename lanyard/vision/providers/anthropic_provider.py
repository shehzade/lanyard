import base64
import json
import time

import httpx

from lanyard.vision.models import BadgeFinding
from lanyard.vision.providers.base import DETECTOR_PROMPT, BaseVisionProvider


class AnthropicVisionProvider(BaseVisionProvider):
    def __init__(
        self,
        model_name: str = "claude-3-7-sonnet-20250219",
        api_key: str = "",
        api_base: str = "https://api.anthropic.com",
    ):
        super().__init__(
            model_name=model_name,
            api_key=api_key,
            api_base=api_base or "https://api.anthropic.com",
        )
        self.client = httpx.Client(timeout=60.0)

    def analyze_image(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> BadgeFinding:
        b64_str = base64.b64encode(image_bytes).decode("utf-8")
        schema = BadgeFinding.model_json_schema()

        tool_spec = {
            "name": "record_badge_finding",
            "description": "Records the structured finding of physical security badge analysis.",
            "input_schema": schema,
        }

        payload = {
            "model": self.model_name,
            "max_tokens": 1500,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": mime_type,
                                "data": b64_str,
                            },
                        },
                        {
                            "type": "text",
                            "text": DETECTOR_PROMPT,
                        },
                    ],
                }
            ],
            "tools": [tool_spec],
            "tool_choice": {"type": "tool", "name": "record_badge_finding"},
            "temperature": 0.1,
        }

        url = f"{self.api_base.rstrip('/')}/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        max_retries = 3
        for attempt in range(max_retries):
            try:
                resp = self.client.post(url, headers=headers, json=payload)
                if resp.status_code == 429:
                    time.sleep(2.0 * (attempt + 1))
                    continue
                resp.raise_for_status()
                data = resp.json()

                for block in data.get("content", []):
                    if block.get("type") == "tool_use" and block.get("name") == "record_badge_finding":
                        return BadgeFinding(**block.get("input", {}))

                for block in data.get("content", []):
                    if block.get("type") == "text":
                        txt = block.get("text", "")
                        if "{" in txt and "}" in txt:
                            json_str = txt[txt.find("{") : txt.rfind("}") + 1]
                            return BadgeFinding(**json.loads(json_str))

                return BadgeFinding(has_badge=False, confidence=0.0)
            except Exception:
                if attempt == max_retries - 1:
                    raise
                time.sleep(1.0)

        return BadgeFinding(has_badge=False, confidence=0.0)
