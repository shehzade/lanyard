import json
import time

from google import genai
from google.genai import types

from lanyard.vision.models import BadgeFinding
from lanyard.vision.providers.base import DETECTOR_PROMPT, BaseVisionProvider


class GeminiVisionProvider(BaseVisionProvider):
    def __init__(
        self,
        model_name: str = "gemini-3.8-flash",
        api_key: str = "",
        api_base: str = "",
    ):
        super().__init__(model_name=model_name, api_key=api_key, api_base=api_base)
        self.client = genai.Client(api_key=api_key)

    def analyze_image(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> BadgeFinding:
        image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)

        config = types.GenerateContentConfig(
            temperature=0.1,
            response_mime_type="application/json",
            response_schema=BadgeFinding,
        )

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=[image_part, DETECTOR_PROMPT],
                    config=config,
                )
                if response.text:
                    data = json.loads(response.text)
                    return BadgeFinding(**data)
                return BadgeFinding(has_badge=False, confidence=0.0)
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    time.sleep(2.0 * (attempt + 1))
                    continue
                if attempt == max_retries - 1:
                    raise
                time.sleep(1.0)

        return BadgeFinding(has_badge=False, confidence=0.0)
