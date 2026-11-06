import json
import sqlite3
from pathlib import Path

from lanyard.vision.models import BadgeFinding


class Database:
    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_tables()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self) -> None:
        with self._get_conn() as conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                image_url TEXT UNIQUE,
                post_url TEXT,
                post_author TEXT,
                post_caption TEXT,
                analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS findings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                image_id INTEGER,
                has_badge INTEGER,
                confidence REAL,
                badge_type TEXT,
                employee_name TEXT,
                company_name TEXT,
                department_or_role TEXT,
                id_or_badge_number TEXT,
                security_features TEXT,
                summary TEXT,
                crop_path TEXT,
                original_path TEXT,
                template_path TEXT,
                card_corners TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (image_id) REFERENCES images(id)
            )
            """)
            try:
                conn.execute("ALTER TABLE images ADD COLUMN post_author TEXT")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE images ADD COLUMN post_caption TEXT")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE findings ADD COLUMN template_path TEXT")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE findings ADD COLUMN card_corners TEXT")
            except Exception:
                pass
            conn.commit()

    def is_image_analyzed(self, image_url: str) -> bool:
        with self._get_conn() as conn:
            cur = conn.execute("SELECT id FROM images WHERE image_url = ?", (image_url,))
            return cur.fetchone() is not None

    def record_image(
        self,
        image_url: str,
        post_url: str | None = None,
        post_author: str | None = None,
        post_caption: str | None = None,
    ) -> int:
        with self._get_conn() as conn:
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO images (image_url, post_url, post_author, post_caption)
                VALUES (?, ?, ?, ?)
                """,
                (image_url, post_url or "", post_author or "", post_caption or ""),
            )
            conn.commit()
            if cur.lastrowid and cur.lastrowid > 0:
                return cur.lastrowid
            cur = conn.execute("SELECT id FROM images WHERE image_url = ?", (image_url,))
            row = cur.fetchone()
            return row["id"] if row else -1

    def record_finding(
        self,
        image_id: int,
        finding: BadgeFinding,
        crop_path: str | None = None,
        original_path: str | None = None,
        template_path: str | None = None,
    ) -> int:
        corners_json = json.dumps(finding.card_corners.model_dump()) if finding.card_corners else None
        with self._get_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO findings (
                    image_id, has_badge, confidence, badge_type,
                    employee_name, company_name, department_or_role,
                    id_or_badge_number, security_features, summary,
                    crop_path, original_path, template_path, card_corners
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    image_id,
                    1 if finding.has_badge else 0,
                    finding.confidence,
                    finding.badge_type,
                    finding.employee_name,
                    finding.company_name,
                    finding.department_or_role,
                    finding.id_or_badge_number,
                    json.dumps(finding.security_features),
                    finding.summary,
                    crop_path or "",
                    original_path or "",
                    template_path or "",
                    corners_json,
                ),
            )
            conn.commit()
            return cur.lastrowid or -1

    def update_finding_cr80(
        self,
        finding_id: int,
        template_path: str,
        card_corners: dict | None = None,
    ) -> None:
        with self._get_conn() as conn:
            if card_corners is not None:
                conn.execute(
                    "UPDATE findings SET template_path = ?, card_corners = ? WHERE id = ?",
                    (template_path, json.dumps(card_corners), finding_id),
                )
            else:
                conn.execute(
                    "UPDATE findings SET template_path = ? WHERE id = ?",
                    (template_path, finding_id),
                )
            conn.commit()

    def get_all_badge_findings(self) -> list[dict]:
        with self._get_conn() as conn:
            cur = conn.execute("""
            SELECT f.*, i.image_url, i.post_url, i.post_author, i.post_caption
            FROM findings f
            JOIN images i ON f.image_id = i.id
            WHERE f.has_badge = 1
            ORDER BY f.confidence DESC, f.id DESC
            """)
            rows = cur.fetchall()
            results = []
            for r in rows:
                item = dict(r)
                try:
                    item["security_features"] = json.loads(item.get("security_features") or "[]")
                except Exception:
                    item["security_features"] = []
                if item.get("card_corners"):
                    try:
                        item["card_corners"] = json.loads(item["card_corners"])
                    except Exception:
                        item["card_corners"] = None
                else:
                    item["card_corners"] = None
                results.append(item)
            return results
