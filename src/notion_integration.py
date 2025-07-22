from __future__ import annotations

"""Notion API helper for creating journal entries.

Assumes the target database has the following properties:
- Title (title): top-of-mind keyword (string)
- Date (date): journal date
- Raw (rich_text): original transcript text
- Structured (rich_text): polished transcript text
"""

import os
from datetime import date, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from notion_client import Client

# Local utilities
from src.text_utils import chunk_text

load_dotenv()
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

if NOTION_API_KEY is None or NOTION_DATABASE_ID is None:
    raise RuntimeError("NOTION_API_KEY and NOTION_TEST_DATABASE_ID must be set in .env")

client = Client(auth=NOTION_API_KEY)

# Notion rich-text limit; stay comfortably below 2000 characters.
MAX_CHARS = 1800


def _rich_text(text: str) -> list[dict[str, Any]]:
    return [{"type": "text", "text": {"content": text}}]


def _paragraph_block(text: str) -> dict[str, Any]:
    """Return a Notion paragraph block for *text*."""
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": _rich_text(text)},
    }


def _heading_block(text: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "heading_2",
        "heading_2": {"rich_text": _rich_text(text)},
    }


# ----------------------------------
# Low-level helpers (properties only)
# ----------------------------------


def create_journal_entry(
    *,
    keyword: str,
    journal_date: date,
    structured: str,
    raw: str | None = None,
) -> dict[str, Any]:
    """Create a Notion page with mandatory Title/Date and optional text properties."""

    props: dict[str, Any] = {
        "Title": {"title": [{"type": "text", "text": {"content": keyword}}]},
        "Date": {"date": {"start": journal_date.isoformat()}},
        "Structured": {"rich_text": _rich_text(structured)},
    }

    if raw:
        props["Raw"] = {"rich_text": _rich_text(raw)}

    response = client.pages.create(
        parent={"database_id": NOTION_DATABASE_ID},
        properties=props,
    )
    return response


def push_from_files(
    processed_json_path: str | Path,
    raw_transcript_path: str | Path,
    *,
    message_dt: datetime | None = None,
) -> str:
    """Convenience wrapper: read files and create journal entry.

    processed_json_path: output from llm_polish --json containing 'polished' and 'keyword'.
    raw_transcript_path: original .txt transcript.
    message_dt: optional, UTC timestamp of original message. If omitted, date is parsed from
                raw file name assuming *_YYYYMMDD_HHMMSS.txt pattern.
    Returns created page URL.
    """

    import json
    from src.date_utils import journal_date as _journal_date

    processed_data = json.loads(Path(processed_json_path).read_text(encoding="utf-8"))
    # Accept 'summary' as primary, fallback to 'keyword'
    title_text = processed_data.get("summary") or "Untitled"
    structured_full = processed_data["polished"]

    # Chunk structured text according to Notion limits
    structured_chunks = chunk_text(structured_full, MAX_CHARS) or [""]

    # Determine journal date
    if message_dt is None:
        # Try to extract timestamp from file name: *_YYYYMMDD_HHMMSS.txt
        stem = Path(raw_transcript_path).stem
        parts = stem.split("_")
        if len(parts) < 3:
            raise ValueError("Could not parse timestamp from file name")
        timestamp_part = "_".join(parts[-2:])  # e.g. 20250720_203049
        try:
            dt = datetime.strptime(timestamp_part, "%Y%m%d_%H%M%S")
        except ValueError as e:
            raise ValueError("Filename timestamp format incorrect") from e
        message_dt = dt.replace(tzinfo=None)  # naive UTC

    logical_date = _journal_date(message_dt)

    # ----------------------------------------
    # 1) Create page with first chunk in props
    # ----------------------------------------

    page = create_journal_entry(
        keyword=title_text,
        journal_date=logical_date,
        structured=structured_chunks[0],
    )

    page_id = page["id"]

    # ------------------------------------------------
    # 2) Append remaining chunks as paragraph blocks
    # ------------------------------------------------

    children: list[dict[str, Any]] = []

    # Add remaining structured chunks (if any)
    for chunk in structured_chunks[1:]:
        children.append(_paragraph_block(chunk))


    # Notion API allows up to 100 children per request; split accordingly
    BATCH_SIZE = 50
    for i in range(0, len(children), BATCH_SIZE):
        client.blocks.children.append(
            block_id=page_id,
            children=children[i : i + BATCH_SIZE],
        )

    return page["url"] 