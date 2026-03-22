#!/usr/bin/env python3
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    db_path = Path("/opt/ai-practice/backend/data/app.db")
    if not db_path.exists():
        print("ERROR: DB_NOT_FOUND", db_path)
        return 1

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()

    cur.execute(
        "SELECT user_id FROM users WHERE role = ? AND is_active = 1 ORDER BY created_at ASC LIMIT 1",
        ("admin",),
    )
    row = cur.fetchone()
    if row is None:
        print("ERROR: ADMIN_USER_NOT_FOUND")
        conn.close()
        return 2
    admin_user_id = row[0]

    cur.execute(
        "SELECT scenario_id FROM scenarios WHERE scenario_type = ? LIMIT 1",
        ("presentation",),
    )
    row = cur.fetchone()
    if row is None:
        scenario_id = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO scenarios (scenario_id, scenario_type, name, description, persona_prompt, is_active, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                scenario_id,
                "presentation",
                "presentation_default",
                "Auto fixture for voice flow verification",
                None,
                1,
                now,
            ),
        )
    else:
        scenario_id = row[0]

    cur.execute(
        "SELECT presentation_id FROM presentations WHERE title = ? LIMIT 1",
        ("Voice Flow Test PPT",),
    )
    row = cur.fetchone()
    if row is None:
        presentation_id = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO presentations (presentation_id, title, file_url, file_size_bytes, upload_date, version_number, status, uploaded_by_admin_id, total_pages, ocr_progress) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                presentation_id,
                "Voice Flow Test PPT",
                "/tmp/voice-flow-test.pptx",
                1024,
                now,
                1,
                "ready",
                admin_user_id,
                1,
                1.0,
            ),
        )
    else:
        presentation_id = row[0]
        cur.execute(
            "UPDATE presentations SET status = ?, total_pages = ? WHERE presentation_id = ?",
            ("ready", 1, presentation_id),
        )

    cur.execute(
        "SELECT page_id FROM pages WHERE presentation_id = ? AND page_number = ?",
        (presentation_id, 1),
    )
    row = cur.fetchone()
    if row is None:
        cur.execute(
            "INSERT INTO pages (page_id, presentation_id, page_number, ocr_extracted_text, image_url, extraction_confidence, needs_manual_review) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid.uuid4()),
                presentation_id,
                1,
                "Voice flow test page",
                None,
                0.99,
                0,
            ),
        )

    conn.commit()
    conn.close()
    print("OK: PRESENTATION_SCENARIO_ID", scenario_id)
    print("OK: PRESENTATION_ID", presentation_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
