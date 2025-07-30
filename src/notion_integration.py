from __future__ import annotations

"""Notion API helper for creating journal entries.

Assumes the target database has the following properties:
- Title (title): top-of-mind keyword (string)
- Date (date): journal date
- Raw (rich_text): original transcript text
- Structured (rich_text): polished transcript text
"""

import os
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any
import json

from dotenv import load_dotenv
from notion_client import Client

# Local utilities
from src.text_utils import chunk_text
from src.date_utils import journal_date as _journal_date

load_dotenv()
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
if NOTION_API_KEY is None or NOTION_DATABASE_ID is None:
    raise RuntimeError("NOTION_API_KEY and NOTION_TEST_DATABASE_ID must be set in .env")

client = Client(auth=NOTION_API_KEY)

# Notion rich-text limit; stay comfortably below 2000 characters.
MAX_CHARS = 1800
# Batch size for appending children blocks to a page (Notion limit is 100 per request)
CHILD_BATCH_SIZE = 50


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


# ----------------------------------
# Shared high-level helper
# ----------------------------------


def _create_page_with_chunks(
    *,
    keyword: str,
    journal_date: date,
    structured_chunks: list[str],
    raw_first_chunk: str | None = None,
) -> tuple[str, str]:
    """Create a page and append *structured_chunks* (paragraph blocks).

    Returns (page_id, page_url).
    """

    page = create_journal_entry(
        keyword=keyword,
        journal_date=journal_date,
        structured=structured_chunks[0],
        raw=raw_first_chunk,
    )

    page_id = page["id"]

    # Append remaining structured chunks (if any)
    children = [_paragraph_block(chunk) for chunk in structured_chunks[1:]]

    for i in range(0, len(children), CHILD_BATCH_SIZE):
        client.blocks.children.append(
            block_id=page_id,
            children=children[i : i + CHILD_BATCH_SIZE],
        )

    return page_id, page["url"]


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

    _, page_url = _create_page_with_chunks(
        keyword=title_text,
        journal_date=logical_date,
        structured_chunks=structured_chunks,
    )

    return page_url


# Public API – create entry from in-memory data and store artifacts


def create_entry_from_memory(
    *,
    raw_transcript: str,
    polished_data: dict[str, str],
    message_dt: datetime,
    entry_id: str | None = None,
) -> tuple[str, str]:
    """Create Notion journal entry *and* save local artifacts from raw/polished data.

    Args:
        raw_transcript: The original transcript text
        polished_data: Dict with 'polished' and 'summary' keys from LLM processing
        message_dt: UTC timestamp of original message
        entry_id: Optional unique ID for this entry (will generate UUID if not provided)

    Returns:
        tuple of (notion_page_url, entry_directory_path)
    """

    if entry_id is None:
        entry_id = str(uuid.uuid4())[:8]  # Short UUID for directory names

    # Extract data from polished result
    title_text = polished_data.get("summary") or "Untitled"
    structured_full = polished_data["polished"]

    # Chunk structured text according to Notion limits
    structured_chunks = chunk_text(structured_full, MAX_CHARS) or [""]

    # Determine journal date
    logical_date = _journal_date(message_dt)

    # ----------------------------------------
    # 1) Create Notion page with structured content
    # ----------------------------------------

    raw_first_chunk = (
        chunk_text(raw_transcript, MAX_CHARS)[0] if raw_transcript else None
    )

    page_id, page_url = _create_page_with_chunks(
        keyword=title_text,
        journal_date=logical_date,
        structured_chunks=structured_chunks,
        raw_first_chunk=raw_first_chunk,
    )

    # ------------------------------------------------
    # 2) Append remaining chunks (raw transcript, etc.)
    # ------------------------------------------------

    children: list[dict[str, Any]] = []

    # Add raw transcript chunks if there are multiple and if raw transcript exists
    if raw_transcript:
        raw_chunks = chunk_text(raw_transcript, MAX_CHARS)
        if len(raw_chunks) > 1:
            children.append(_heading_block("Raw Transcript (continued)"))
            for chunk in raw_chunks[1:]:
                children.append(_paragraph_block(chunk))

    # Push children in batches
    for i in range(0, len(children), CHILD_BATCH_SIZE):
        client.blocks.children.append(
            block_id=page_id,
            children=children[i : i + CHILD_BATCH_SIZE],
        )

    # ----------------------------------------
    # 3) Save artifacts to organized directory
    # ----------------------------------------

    # Create unique directory for this entry
    timestamp_str = message_dt.strftime("%Y%m%d_%H%M%S")
    entry_dir = Path("journal_entries") / f"{timestamp_str}_{entry_id}"
    entry_dir.mkdir(parents=True, exist_ok=True)

    # Save raw transcript
    raw_path = entry_dir / "raw_transcript.txt"
    raw_path.write_text(raw_transcript, encoding="utf-8")

    # Save polished data
    polished_path = entry_dir / "polished.json"
    polished_path.write_text(
        json.dumps(polished_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Save metadata
    metadata = {
        "entry_id": entry_id,
        "message_timestamp_utc": message_dt.isoformat(),
        "journal_date": logical_date.isoformat(),
        "notion_page_url": page_url,
        "notion_page_id": page_id,
        "title": title_text,
    }
    metadata_path = entry_dir / "metadata.json"
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return page_url, str(entry_dir)

