from abc import ABC, abstractmethod

from lanyard.vision.models import BadgeFinding

DETECTOR_PROMPT = """Analyze this image with high scrutiny for physical security, social engineering, and red team OSINT assessment.
Your objective is to identify REAL, PHYSICAL employee identification badges, physical access control cards (HID/RFID/iCLASS/prox cards), security passes, visitor credentials, or corporate access cards worn by individuals or placed on surfaces.

CRITICAL INSTRUCTIONS TO ELIMINATE FALSE POSITIVES:
1. PHYSICAL BADGES ONLY: Do NOT flag generic digital illustrations, clipart, mockups, infographics, stock icons, cartoon drawings (e.g. Acme/Coyote), or abstract badge templates. If it is an illustration/graphic and NOT a photograph of a real physical badge/card, set has_badge = false and confidence = 0.0.
2. DISTANCE AND RESOLUTION: Do NOT flag people where a tiny blur or lanyard string is visible far away in the background or crowd where NO card face details or badge outline can actually be distinguished.
3. CONFERENCES/EVENTS: Only flag real employee/contractor corporate access badges, or company-issued visitor credentials. Do NOT flag generic paper conference attendee name tags (e.g. TED, IEEE, generic trade shows) unless they are official corporate-issued access credentials.

If a REAL physical ID badge or access pass is visible:
1. Set has_badge = true and provide an accurate confidence (0.0 to 1.0).
2. Classify badge_type: 'employee', 'contractor', 'visitor', 'access_card', 'parking_pass'.
3. Provide tight bounding box coordinates (ymin, xmin, ymax, xmax) normalized to a 0-1000 scale enclosing the badge and its immediate clip/holder.
4. Provide card_corners: pinpoint the exact 4 outer corners of the rectangular card face itself (top_left, top_right, bottom_right, bottom_left) in upright card reading orientation (where the company header/logo is at the top), excluding any lanyard clip, lanyard strap, lanyard reel, badge holder tabs, or fingers holding the card.
5. Perform OCR on any legible text on the card: employee name, company name, department/role, badge ID/number.
6. Identify any visible physical security features: rfid_chip, smart_chip, magstripe, barcode, qr_code, photo, hologram, branded_lanyard.
7. Provide a concise technical summary of the findings.

If NO real physical badge is visible in the image, set has_badge = false and confidence = 0.0 with bounding_box = null and card_corners = null."""


class BaseVisionProvider(ABC):
    def __init__(self, model_name: str, api_key: str = "", api_base: str = ""):
        self.model_name = model_name
        self.api_key = api_key
        self.api_base = api_base

    @abstractmethod
    def analyze_image(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> BadgeFinding:
        """Analyze an image and extract structured badge finding."""
