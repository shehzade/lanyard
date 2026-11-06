from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    ymin: int = Field(description="Top coordinate of the badge bounding box (0 to 1000).")
    xmin: int = Field(description="Left coordinate of the badge bounding box (0 to 1000).")
    ymax: int = Field(description="Bottom coordinate of the badge bounding box (0 to 1000).")
    xmax: int = Field(description="Right coordinate of the badge bounding box (0 to 1000).")


class CardCorner(BaseModel):
    x: int = Field(description="X coordinate from 0 to 1000 across image width (0=left edge, 1000=right edge).")
    y: int = Field(description="Y coordinate from 0 to 1000 down image height (0=top edge, 1000=bottom edge).")


class CardPolygon(BaseModel):
    top_left: CardCorner = Field(
        description="Corner corresponding to top-left of the badge card when viewed upright (where company name/header is at the top)."
    )
    top_right: CardCorner = Field(
        description="Corner corresponding to top-right of the badge card when viewed upright."
    )
    bottom_right: CardCorner = Field(
        description="Corner corresponding to bottom-right of the badge card when viewed upright."
    )
    bottom_left: CardCorner = Field(
        description="Corner corresponding to bottom-left of the badge card when viewed upright."
    )


class BadgeFinding(BaseModel):
    has_badge: bool = Field(
        description="True if an employee ID badge, security pass, or access card is visible in the image."
    )
    confidence: float = Field(default=0.0, description="Confidence score from 0.0 to 1.0.")
    badge_type: str = Field(
        default="none",
        description="Type of credential detected: 'employee', 'contractor', 'visitor', 'access_card', 'parking_pass', or 'none'.",
    )
    bounding_box: BoundingBox | None = Field(
        default=None,
        description="Tight bounding box coordinates around the detected badge (normalized 0-1000). None if has_badge is False.",
    )
    card_corners: CardPolygon | None = Field(
        default=None,
        description="Exact 4 physical corners of the rectangular PVC badge card itself, excluding the lanyard strap, clip, holder frame, or torso. Used for perspective deskewing and CR80 card extraction. None if has_badge is False.",
    )
    employee_name: str | None = Field(
        default=None,
        description="Plaintext name of the employee or badge holder visible on the card (OCR).",
    )
    company_name: str | None = Field(
        default=None,
        description="Company or organization logo or text printed on the badge or lanyard.",
    )
    department_or_role: str | None = Field(
        default=None,
        description="Department, title, or security clearance level visible on the badge.",
    )
    id_or_badge_number: str | None = Field(
        default=None,
        description="Badge number, employee ID, or card serial number visible on the badge.",
    )
    security_features: list[str] = Field(
        default_factory=list,
        description="Visible physical security markers, e.g. ['rfid_chip', 'smart_chip', 'magstripe', 'barcode', 'qr_code', 'holder_clip', 'photo', 'hologram', 'branded_lanyard'].",
    )
    summary: str | None = Field(
        default=None,
        description="Brief technical description of the detected badge and its visible features.",
    )
