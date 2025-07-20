from __future__ import annotations

from typing import List

__all__ = ["chunk_text"]


def chunk_text(text: str, max_chars: int = 2000) -> List[str]:
    """Split *text* into chunks no longer than *max_chars* **without** breaking words.

    • Whitespace (space, tab, newline, etc.) is used as the preferred break point.
    • The original spacing and line-breaks inside each chunk are preserved – we slice
      the *original string* rather than re-joining tokens.
    • If a *single word* exceeds *max_chars*, that word becomes its own chunk and
      therefore *can* exceed the limit — this mirrors the behaviour we need for
      rare edge-cases like very long URLs.
    """

    if max_chars <= 0:
        raise ValueError("max_chars must be positive")

    length = len(text)
    if length == 0:
        return []

    chunks: List[str] = []
    start = 0

    while start < length:
        # Naïvely take a slice of max_chars
        end = min(start + max_chars, length)

        # If we've reached the end of the text, append and break
        if end == length:
            chunks.append(text[start:end])
            break

        # If the char right at the boundary is whitespace, perfect split
        if text[end].isspace():
            chunks.append(text[start:end])
            start = end + 1  # skip the whitespace char itself
            continue

        # Otherwise back-track to the last whitespace within the window
        last_space = text.rfind(" ", start, end)
        last_space_tab = text.rfind("\t", start, end)
        last_space_nl = text.rfind("\n", start, end)
        last_break = max(last_space, last_space_tab, last_space_nl)

        if last_break == -1 or last_break <= start:
            # No whitespace within the window – the word itself is > max_chars.
            # Slice at the hard limit even though it breaks the word. This keeps
            # every chunk ≤ max_chars, which is required by Notion.
            chunks.append(text[start:end])
            start = end
        else:
            # Cut at the last whitespace (include it) so we preserve spacing
            chunks.append(text[start:last_break + 1])
            start = last_break + 1  # next chunk starts after the whitespace char

    return chunks 