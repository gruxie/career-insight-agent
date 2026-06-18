"""
Parse extracted markdown from Connect reviews into structured JSON.

Takes the raw markdown output from extract_markdown.py and uses a text-only
Claude call to produce structured data conforming to the ConnectReview schema.
"""
import argparse
import json
import os
import sys

from dotenv import load_dotenv
import anthropic

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
MD_DIR = os.path.join(PROJECT_ROOT, "04_outputs", "md")
OUT_DIR = os.path.join(PROJECT_ROOT, "04_outputs", "json")

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
from pydantic import ValidationError

from schema import ConnectReview

MODEL = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = """\
You are a structured data extractor. You will receive the raw markdown text of a \
Microsoft Connect performance review document. Your job is to extract the information \
into a specific JSON structure.

Return ONLY valid JSON matching this schema — no commentary, no markdown fences:

{schema}

Rules:
- Extract all accomplishments listed under "Reflect on the past" / results delivered
- Extract core priorities / competencies with the evidence provided
- Extract goals/priorities from "Look ahead" sections
- Extract manager feedback verbatim where present
- Extract peer/stakeholder quotes into the peer_feedback array with attribution (name and title) when available
- Peer quotes are typically italicized and attributed with a dash and name — separate them from the manager's own comments
- If a field is not present in the document, use null for optional fields or empty arrays
- For impact_rating, look for terms like "Exceptional Impact", "Strong", etc.
- The connect_period should be a short label like "Apr 2026" or "Nov 2024"
- Preserve the full detail of descriptions — do not summarize"""


def build_user_prompt(markdown_text: str) -> str:
    return f"""\
Extract structured data from this Connect review document:

---
{markdown_text}
---

Return the JSON object only."""


def extract_structured(client: anthropic.Anthropic, markdown_text: str) -> ConnectReview:
    """Send markdown to Claude and parse into ConnectReview model."""
    schema_json = json.dumps(ConnectReview.model_json_schema(), indent=2)
    system = SYSTEM_PROMPT.format(schema=schema_json)

    response = client.messages.create(
        model=MODEL,
        max_tokens=8192,
        system=system,
        messages=[
            {"role": "user", "content": build_user_prompt(markdown_text)},
        ],
    )

    raw_text = response.content[0].text.strip()

    # Strip markdown code fences if present despite instructions
    if raw_text.startswith("```"):
        lines = raw_text.split("\n")
        # Remove first and last lines (fences)
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw_text = "\n".join(lines)

    data = json.loads(raw_text)
    return ConnectReview.model_validate(data)


def main():
    parser = argparse.ArgumentParser(description="Parse Connect markdown into structured JSON")
    parser.add_argument("--md-dir", default=MD_DIR)
    parser.add_argument("--out-dir", default=OUT_DIR)
    parser.add_argument("--force", action="store_true", help="Re-parse even if .json exists")
    parser.add_argument("files", nargs="*", help="Specific .md filenames to process (default: all)")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    client = anthropic.Anthropic()

    if args.files:
        mds = args.files
    else:
        mds = sorted(f for f in os.listdir(args.md_dir) if f.lower().endswith(".md"))

    if not mds:
        print("No markdown files found in", args.md_dir)
        sys.exit(1)

    print(f"Found {len(mds)} markdown files -> writing JSON to {args.out_dir}/\n")

    errors: list[str] = []

    for md_name in mds:
        stem = os.path.splitext(md_name)[0]
        md_path = os.path.join(args.md_dir, md_name)
        out_path = os.path.join(args.out_dir, stem + ".json")

        if os.path.exists(out_path) and not args.force:
            print(f"[skip] {md_name} (already parsed)")
            continue

        if not os.path.exists(md_path):
            print(f"[error] {md_path} not found")
            errors.append(md_name)
            continue

        print(f"[{md_name}] parsing...", end=" ", flush=True)

        with open(md_path, "r", encoding="utf-8") as f:
            markdown_text = f.read()

        try:
            review = extract_structured(client, markdown_text)
        except (json.JSONDecodeError, ValidationError) as e:
            print(f"FAILED: {e}")
            errors.append(md_name)
            continue

        with open(out_path, "w", encoding="utf-8") as f:
            f.write(review.model_dump_json(indent=2))

        print(f"-> {stem}.json")

    print(f"\nDone. {len(mds) - len(errors)} succeeded, {len(errors)} failed.")
    if errors:
        print("Failed:", ", ".join(errors))
        sys.exit(1)


if __name__ == "__main__":
    main()
