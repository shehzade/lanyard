import math
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageOps

from lanyard.vision.models import CardPolygon


def _find_perspective_coeffs(
    source_points: list[tuple[float, float]], target_points: list[tuple[float, float]]
) -> list[float]:
    """
    Computes 8 homography transformation coefficients mapping target coordinates
    back to source coordinates for PIL Image.Transform.PERSPECTIVE.
    """
    matrix = []
    for (xt, yt), (xs, ys) in zip(target_points, source_points):
        matrix.append([xt, yt, 1, 0, 0, 0, -xs * xt, -xs * yt])
        matrix.append([0, 0, 0, xt, yt, 1, -ys * xt, -ys * yt])
    A = np.matrix(matrix, dtype=float)
    B = np.array(source_points).reshape(8)
    res = np.dot(np.linalg.inv(A.T * A) * A.T, B)
    return np.array(res).reshape(8).tolist()


def convert_badge_to_cr80(
    source_image: Path | str | bytes,
    output_png: Path,
    output_svg: Path | None = None,
    corners: CardPolygon | dict[str, Any] | None = None,
) -> Path:
    """
    Converts an actual badge photo into a standardized CR80 print-ready card.
    If corners are provided, performs AI-guided 4-point homography perspective deskewing
    to flatten the physical badge surface directly onto the card canvas.

    Standard CR80 dimensions: 85.60mm x 53.98mm (3.370" x 2.125") with 3.18mm (1/8") corner radius.
    At 300 DPI:
      - Portrait:  638px x 1012px (53.98mm x 85.60mm)
      - Landscape: 1012px x 638px (85.60mm x 53.98mm)
      - Corner radius: 38px
    """
    output_png.parent.mkdir(parents=True, exist_ok=True)

    if isinstance(source_image, bytes):
        import io

        img = Image.open(io.BytesIO(source_image))
    else:
        img = Image.open(source_image)

    img = img.convert("RGBA")
    src_w, src_h = img.size

    deskewed: Image.Image | None = None
    target_w = 638
    target_h = 1012
    phys_w_mm = "53.98mm"
    phys_h_mm = "85.60mm"

    if corners:
        try:
            if isinstance(corners, CardPolygon):
                tl = (corners.top_left.x, corners.top_left.y)
                tr = (corners.top_right.x, corners.top_right.y)
                br = (corners.bottom_right.x, corners.bottom_right.y)
                bl = (corners.bottom_left.x, corners.bottom_left.y)
            elif isinstance(corners, dict):
                tl = (corners["top_left"]["x"], corners["top_left"]["y"])
                tr = (corners["top_right"]["x"], corners["top_right"]["y"])
                br = (corners["bottom_right"]["x"], corners["bottom_right"]["y"])
                bl = (corners["bottom_left"]["x"], corners["bottom_left"]["y"])
            else:
                tl = tr = br = bl = None

            if tl and tr and br and bl:
                px_tl = (tl[0] * src_w / 1000.0, tl[1] * src_h / 1000.0)
                px_tr = (tr[0] * src_w / 1000.0, tr[1] * src_h / 1000.0)
                px_br = (br[0] * src_w / 1000.0, br[1] * src_h / 1000.0)
                px_bl = (bl[0] * src_w / 1000.0, bl[1] * src_h / 1000.0)

                top_edge = math.hypot(px_tr[0] - px_tl[0], px_tr[1] - px_tl[1])
                bottom_edge = math.hypot(px_br[0] - px_bl[0], px_br[1] - px_bl[1])
                left_edge = math.hypot(px_bl[0] - px_tl[0], px_bl[1] - px_tl[1])
                right_edge = math.hypot(px_br[0] - px_tr[0], px_br[1] - px_tr[1])

                avg_w = (top_edge + bottom_edge) / 2.0
                avg_h = (left_edge + right_edge) / 2.0

                if avg_w > 20 and avg_h > 20:
                    if avg_h >= avg_w:
                        target_w = 638
                        target_h = 1012
                        phys_w_mm = "53.98mm"
                        phys_h_mm = "85.60mm"
                    else:
                        target_w = 1012
                        target_h = 638
                        phys_w_mm = "85.60mm"
                        phys_h_mm = "53.98mm"

                    src_pts = [px_tl, px_tr, px_br, px_bl]
                    dst_pts = [
                        (0.0, 0.0),
                        (float(target_w), 0.0),
                        (float(target_w), float(target_h)),
                        (0.0, float(target_h)),
                    ]

                    coeffs = _find_perspective_coeffs(src_pts, dst_pts)
                    deskewed = img.transform(
                        (target_w, target_h),
                        Image.Transform.PERSPECTIVE,
                        coeffs,
                        Image.Resampling.BICUBIC,
                    )
        except Exception:
            deskewed = None

    if deskewed is None:
        if src_h >= src_w:
            target_w = 638
            target_h = 1012
            phys_w_mm = "53.98mm"
            phys_h_mm = "85.60mm"
        else:
            target_w = 1012
            target_h = 638
            phys_w_mm = "85.60mm"
            phys_h_mm = "53.98mm"

        deskewed = ImageOps.fit(
            img,
            (target_w, target_h),
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )

    rgb_version = deskewed.convert("RGB")
    enhanced = ImageEnhance.Contrast(rgb_version).enhance(1.08)
    enhanced = ImageEnhance.Sharpness(enhanced).enhance(1.22)

    corner_radius = 38
    mask = Image.new("L", (target_w, target_h), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle(
        [(0, 0), (target_w - 1, target_h - 1)],
        radius=corner_radius,
        fill=255,
    )

    cr80_card = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
    cr80_card.paste(enhanced, (0, 0), mask=mask)

    cr80_card.save(output_png, "PNG", dpi=(300, 300))

    if output_svg:
        output_svg.parent.mkdir(parents=True, exist_ok=True)
        rel_png = output_png.name
        svg_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {target_w} {target_h}" width="{phys_w_mm}" height="{phys_h_mm}">
    <defs>
        <clipPath id="cr80-corners">
            <rect width="{target_w}" height="{target_h}" rx="{corner_radius}" ry="{corner_radius}" />
        </clipPath>
    </defs>
    <rect width="{target_w}" height="{target_h}" rx="{corner_radius}" fill="#ffffff" />
    <image href="{rel_png}" width="{target_w}" height="{target_h}" clip-path="url(#cr80-corners)" preserveAspectRatio="xMidYMid slice" />
    <rect width="{target_w}" height="{target_h}" rx="{corner_radius}" fill="none" stroke="#94a3b8" stroke-width="1" opacity="0.4" />
</svg>
"""
        output_svg.write_text(svg_content, encoding="utf-8")

    return output_png
