from __future__ import annotations

import os
from typing import Optional

from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from a .env file if present (consistent with other modules)
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize the OpenAI client using an explicit api_key to avoid relying on global env state
client = OpenAI(api_key=OPENAI_API_KEY)

# Directory where plain-text transcripts are stored when the script is invoked
# with the --save flag.
TRANSCRIPT_DIR = "transcripts"
os.makedirs(TRANSCRIPT_DIR, exist_ok=True)


def transcribe_audio(
    file_path: str,
    *,
    model: str = "whisper-1",
    language: Optional[str] = None,
) -> str:
    """Transcribe an audio file via OpenAI Whisper.

    Args:
        file_path: Path to the audio file (mp3, ogg, wav, m4a, etc.).
        model: Whisper model identifier. Defaults to ``"whisper-1"``.
        language: Optional BCP-47 language tag to bias transcription (e.g. ``"en"``).

    Returns:
        The transcribed text.

    Raises:
        FileNotFoundError: If the given *file_path* does not exist.
        RuntimeError: If the OpenAI API fails or the response is malformed.
    """

    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Audio file not found: {file_path}")

    with open(file_path, "rb") as audio_file:
        response = client.audio.transcriptions.create(
            model=model,
            file=audio_file,
            language=language,
        )

    # The OpenAI Python SDK returns a pydantic object with a ``text`` attribute
    # that contains the transcription result.
    text: Optional[str] = getattr(response, "text", None)
    if text is None:
        raise RuntimeError("Unexpected OpenAI response: missing 'text' attribute")

    return text


def transcribe_and_save(
    file_path: str,
    *,
    output_path: Optional[str] = None,
    model: str = "whisper-1",
    language: Optional[str] = None,
) -> str:
    """Convenience wrapper: transcribe *file_path* and persist the result.

    If *output_path* is not given, the transcript is saved inside
    ``TRANSCRIPT_DIR`` using the same basename as the audio file plus ``.txt``.
    Returns the final output path.
    """

    transcript = transcribe_audio(file_path, model=model, language=language)

    if output_path is None:
        base = os.path.splitext(os.path.basename(file_path))[0] + ".txt"
        output_path = os.path.join(TRANSCRIPT_DIR, base)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(transcript)

    return output_path


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Transcribe an audio file using OpenAI Whisper")
    parser.add_argument("file", help="Path to the audio file to transcribe")
    parser.add_argument("--model", default="whisper-1", help="Whisper model name")
    parser.add_argument("--language", help="Optional language code (e.g. 'en', 'ru')")
    parser.add_argument("--save", action="store_true", help="Save transcript to a text file in ./transcripts/")
    parser.add_argument("--output", help="Explicit output file path (.txt)")

    args = parser.parse_args()

    try:
        if args.save or args.output:
            out_path = transcribe_and_save(
                args.file,
                output_path=args.output,
                model=args.model,
                language=args.language,
            )
            print(f"Transcript saved → {out_path}")
            result = None
        else:
            result = transcribe_audio(args.file, model=args.model, language=args.language)
    except Exception as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    if result:
        print("--- Transcription result ---\n")
        print(result) 