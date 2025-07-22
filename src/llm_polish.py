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
import json

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

JSON_PROMPT = (
    "You are a helpful assistant that receives a raw speech transcript. "
    "Return a JSON object with **exactly two keys**:\n"\
    "1. 'polished'  – a *single string* containing the polished transcript in first-person voice. Use blank lines to separate paragraphs. Keep meaning; don't add new content.\n"\
    "2. 'summary'   – a single short phrase (≈3-8 words, no verbs like 'reflecting/thinking') that names the *specific* key event(s) or thought(s). Examples: 'Applied for ILR and built a bot', 'Leaving job; starting open-source work'.\n"\
    "Respond with valid JSON only, no markdown fences or extra keys."
)


def process_transcript(
    text: str,
    *,
    model: str = "gpt-4o-mini",
    temperature: float = 0.3,
    max_tokens: Optional[int] = None,
) -> dict[str, str]:
    """Return a dict with 'polished' text and 'keyword' theme extracted by the LLM."""

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": JSON_PROMPT},
            {"role": "user", "content": text},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content.strip()
    return json.loads(content)


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

    result = process_transcript(
        raw_text,
        model=args.model,
        temperature=args.temperature,
    )
    out_suffix = "_processed.json"
    out_dir = input_path.parent / "polished"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / (input_path.stem + out_suffix)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Processed transcript (JSON) saved → {out_path}")


if __name__ == "__main__":
    main() 