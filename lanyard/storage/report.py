import csv
import json
from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent / "templates"


def export_jsonl(findings: list[dict], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(item) + "\n" for item in findings)
    return output_path


def export_csv(findings: list[dict], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "id",
        "confidence",
        "badge_type",
        "employee_name",
        "company_name",
        "department_or_role",
        "id_or_badge_number",
        "security_features",
        "summary",
        "post_author",
        "post_caption",
        "crop_path",
        "original_path",
        "template_path",
        "image_url",
        "post_url",
        "created_at",
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for item in findings:
            row = dict(item)
            if isinstance(row.get("security_features"), list):
                row["security_features"] = ", ".join(row["security_features"])
            writer.writerow(row)
    return output_path


def export_html(findings: list[dict], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cr80_dir = output_path.parent / "cr80"
    cr80_dir.mkdir(exist_ok=True)

    from lanyard.storage.cr80 import convert_badge_to_cr80

    filtered_findings = []
    for f in findings:
        summary_low = (f.get("summary") or "").lower()
        if any(w in summary_low for w in ["novelty/fictional", "graphic illustration", "humanoid robot"]):
            continue

        crop_p = f.get("crop_path")
        orig_p = f.get("original_path")
        corners = f.get("card_corners")
        uid = Path(crop_p).stem.replace("_crop", "").replace("badge_", "") if crop_p else str(f.get("id", "0000"))
        target_png = cr80_dir / f"badge_{uid}_cr80.png"
        target_svg = cr80_dir / f"badge_{uid}_cr80.svg"

        if not target_png.exists():
            source_img = None
            if corners and orig_p and Path(orig_p).exists():
                source_img = Path(orig_p)
            elif crop_p and Path(crop_p).exists():
                source_img = Path(crop_p)
            elif orig_p and Path(orig_p).exists():
                source_img = Path(orig_p)

            if source_img:
                try:
                    convert_badge_to_cr80(
                        source_image=source_img,
                        output_png=target_png,
                        output_svg=target_svg,
                        corners=corners,
                    )
                except Exception:
                    pass

        if target_png.exists():
            f["template_path"] = str(target_png)

        filtered_findings.append(f)

    total_findings = len(filtered_findings)
    high_conf_count = sum(1 for f in filtered_findings if (f.get("confidence") or 0.0) >= 0.90)
    rfid_count = 0
    barcode_count = 0

    for f in filtered_findings:
        feats = f.get("security_features") or []
        for feat in feats:
            feat_lower = str(feat).lower()
            if "smart chip" in feat_lower or "rfid" in feat_lower or "nfc" in feat_lower:
                rfid_count += 1
            if "barcode" in feat_lower or "qr" in feat_lower:
                barcode_count += 1

    findings_json = json.dumps(filtered_findings).replace("</script>", "<\\/script>")

    html_template = (TEMPLATES_DIR / "report.html").read_text(encoding="utf-8")
    styles_css = (TEMPLATES_DIR / "styles.css").read_text(encoding="utf-8")
    app_js = (TEMPLATES_DIR / "app.js").read_text(encoding="utf-8")

    rendered = html_template.replace("/* STYLES */", styles_css)
    rendered = rendered.replace("/* SCRIPT */", app_js)
    rendered = rendered.replace("{total_findings}", str(total_findings))
    rendered = rendered.replace("{high_conf_count}", str(high_conf_count))
    rendered = rendered.replace("{rfid_count}", str(rfid_count))
    rendered = rendered.replace("{barcode_count}", str(barcode_count))
    rendered = rendered.replace("{findings_json}", findings_json)

    output_path.write_text(rendered, encoding="utf-8")
    return output_path
