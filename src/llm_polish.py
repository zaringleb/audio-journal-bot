from __future__ import annotations

"""Utility that sends raw transcript text to an LLM (OpenAI Chat API)
for light editing / polishing: fixes punctuation, removes filler words,
and produces clean prose while retaining meaning and voice.
"""

import argparse
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = (
    "You are a helpful assistant that rewrites a raw speech transcript "
    "into clear, well-punctuated, readable text while preserving the speaker's "
    "original voice and meaning. Fix obvious grammar issues, add punctuation, "
    "and split into paragraphs where it makes sense, but do NOT add new content "
    "or summarise. Return only the polished text."
)


def polish_text(
    text: str,
    *,
    model: str = "gpt-3.5-turbo-0125",
    temperature: float = 0.2,
    max_tokens: Optional[int] = None,
) -> str:
    """Send *text* to the LLM and return the polished version."""

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Polish a transcript using an OpenAI chat model.")
    parser.add_argument("input", help="Path to the transcript text file")
    parser.add_argument("--output", help="Optional output file path (.txt)")
    parser.add_argument("--model", default="gpt-3.5-turbo-0125", help="OpenAI chat model")
    parser.add_argument("--temperature", type=float, default=0.2, help="Sampling temperature")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.is_file():
        raise FileNotFoundError(input_path)

    raw_text = input_path.read_text(encoding="utf-8")

    polished = polish_text(
        raw_text,
        model=args.model,
        temperature=args.temperature,
    )

    if args.output:
        out_path = Path(args.output)
    else:
        out_dir = input_path.parent / "polished"
        out_dir.mkdir(exist_ok=True)
        out_path = out_dir / (input_path.stem + "_polished.txt")

    out_path.write_text(polished, encoding="utf-8")
    print(f"Polished transcript saved → {out_path}")


if __name__ == "__main__":
    main() 