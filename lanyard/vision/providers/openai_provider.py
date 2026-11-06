import base64
import json
import time

import httpx

from lanyard.vision.models import BadgeFinding
from lanyard.vision.providers.base import DETECTOR_PROMPT, BaseVisionProvider


class OpenAIVisionProvider(BaseVisionProvider):
    def __init__(
        self,
        model_name: str = "gpt-4o",
        api_key: str = "",
        api_base: str = "https://api.openai.com/v1",
    ):
        super().__init__(
            model_name=model_name,
            api_key=api_key,
            api_base=api_base or "https://api.openai.com/v1",
        )
        self.client = httpx.Client(timeout=60.0)

    def analyze_image(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> BadgeFinding:
        b64_str = base64.b64encode(image_bytes).decode("utf-8")
        data_uri = f"data:{mime_type};base64,{b64_str}"

        schema = BadgeFinding.model_json_schema()
        system_instruction = (
            "You are a physical security and red team credential detection specialist. "
            "Analyze the image and return a valid JSON object matching the BadgeFinding schema strictly."
        )

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_instruction},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": DETECTOR_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": data_uri, "detail": "high"},
                        },
                    ],
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "badge_finding",
                    "strict": False,
                    "schema": schema,
                },
            },
            "temperature": 0.1,
        }

        url = f"{self.api_base.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        max_retries = 3
        for attempt in range(max_retries):
            try:
                resp = self.client.post(url, headers=headers, json=payload)
                if resp.status_code == 429:
                    time.sleep(2.0 * (attempt + 1))
                    continue
                resp.raise_for_status()
                result = resp.json()
                content = result["choices"][0]["message"]["content"]
                if content:
                    data = json.loads(content)
                    return BadgeFinding(**data)
                return BadgeFinding(has_badge=False, confidence=0.0)
            except Exception:
                if attempt == max_retries - 1:
                    raise
                time.sleep(1.0)

        return BadgeFinding(has_badge=False, confidence=0.0)
