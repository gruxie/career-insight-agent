"""
Aggregate all structured Connect review JSON files into a single career timeline.

Reads individual review JSONs, sends them to Claude as a batch, and produces
a synthesized longitudinal career profile.
"""
import argparse
import json
import os
import sys
from datetime import datetime

from dotenv import load_dotenv
import anthropic
from pydantic import ValidationError

from schema import ConnectReview
from schema_timeline import CareerTimeline

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
JSON_DIR = os.path.join(PROJECT_ROOT, "04_outputs", "json")
TIMELINE_PATH = os.path.join(PROJECT_ROOT, "04_outputs", "career_timeline.json")

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

MODEL = "claude-haiku-4-5-20251001"

# Ordering for chronological sort
MONTH_ORDER = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def parse_period_sort_key(period: str) -> tuple[int, int]:
    """Parse 'Apr 2026' or 'Nov 2021' into (year, month) for sorting."""
    parts = period.strip().split()
    if len(parts) == 2:
        month_str, year_str = parts
        month = MONTH_ORDER.get(month_str.lower()[:3], 0)
        try:
            year = int(year_str)
        except ValueError:
            year = 0
        return (year, month)
    return (0, 0)


def load_reviews(json_dir: str) -> list[dict]:
    """Load and chronologically sort all review JSON files."""
    reviews = []
    for fname in os.listdir(json_dir):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(json_dir, fname)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        reviews.append(data)

    # Sort by connect_period
    reviews.sort(key=lambda r: parse_period_sort_key(r.get("connect_period", "")))
    return reviews


SYSTEM_PROMPT = """\
You are a career analyst synthesizing a longitudinal career profile from multiple \
performance reviews. You will receive a chronologically ordered set of structured \
Connect reviews spanning several years.

Your job is to produce a single aggregated career timeline JSON that captures:
1. Career progression (roles, titles, managers over time)
2. All significant projects organized chronologically with thematic tags
3. Recurring strengths that appear across multiple periods (with evidence)
4. Growth areas and their trajectory (improved, ongoing, resolved)
5. Major theme arcs that span the career
6. All peer endorsements collected with attribution and period
7. Impact ratings over time when available
8. A 2-3 paragraph career narrative summarizing the arc, growth, and trajectory

Return ONLY valid JSON matching this schema — no commentary, no markdown fences:

{schema}

Rules:
- Identify patterns and themes across reviews, not just list items
- For recurring_strengths, only include things evidenced in 2+ periods
- For theme_arcs, trace how themes evolved (e.g., from contributor to leader)
- The career_narrative should tell a compelling story of professional growth
- Tag projects with relevant themes (e.g., "AI", "leadership", "research methods")
- Be specific about evidence — cite which periods support each claim
- Preserve the richness of peer quotes verbatim"""


def build_user_prompt(reviews: list[dict]) -> str:
    reviews_text = ""
    for i, review in enumerate(reviews, 1):
        period = review.get("connect_period", f"Review {i}")
        reviews_text += f"\n{'='*60}\n"
        reviews_text += f"REVIEW {i}: {period}\n"
        reviews_text += f"{'='*60}\n"
        reviews_text += json.dumps(review, indent=2)
        reviews_text += "\n"

    return f"""\
Synthesize the following {len(reviews)} Connect reviews into a single career timeline profile.
The reviews are in chronological order from earliest to most recent.

{reviews_text}

Return the aggregated career timeline JSON."""


def aggregate_timeline(client: anthropic.Anthropic, reviews: list[dict]) -> CareerTimeline:
    """Send all reviews to Claude and get an aggregated timeline back."""
    schema_json = json.dumps(CareerTimeline.model_json_schema(), indent=2)
    system = SYSTEM_PROMPT.format(schema=schema_json)
    user_prompt = build_user_prompt(reviews)

    print(f"  Sending {len(reviews)} reviews ({len(user_prompt):,} chars) to Claude...")

    # Use streaming for large requests that may exceed timeout
    collected_text = []
    with client.messages.stream(
        model=MODEL,
        max_tokens=32768,
        system=system,
        messages=[
            {"role": "user", "content": user_prompt},
        ],
    ) as stream:
        for text in stream.text_stream:
            collected_text.append(text)

    raw_text = "".join(collected_text).strip()

    # Strip markdown code fences if present
    if raw_text.startswith("```"):
        lines = raw_text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw_text = "\n".join(lines)

    data = json.loads(raw_text)
    return CareerTimeline.model_validate(data)


def main():
    parser = argparse.ArgumentParser(description="Aggregate Connect reviews into career timeline")
    parser.add_argument("--json-dir", default=JSON_DIR)
    parser.add_argument(
        "--output",
        default=TIMELINE_PATH,
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing output")
    args = parser.parse_args()

    if os.path.exists(args.output) and not args.force:
        print(f"[skip] {args.output} already exists (use --force to overwrite)")
        sys.exit(0)

    client = anthropic.Anthropic()

    print("Loading reviews...")
    reviews = load_reviews(args.json_dir)
    if not reviews:
        print("No JSON review files found in", args.json_dir)
        sys.exit(1)

    print(f"Found {len(reviews)} reviews spanning:")
    for r in reviews:
        print(f"  - {r.get('connect_period', '?')} ({r.get('job_title', '?')})")

    print("\nAggregating career timeline...")
    try:
        timeline = aggregate_timeline(client, reviews)
    except (json.JSONDecodeError, ValidationError) as e:
        print(f"\n[FAILED] {e}")
        sys.exit(1)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(timeline.model_dump_json(indent=2))

    print(f"\n[OK] Career timeline written to {args.output}")
    print(f"  - {len(timeline.roles)} roles")
    print(f"  - {len(timeline.projects)} projects")
    print(f"  - {len(timeline.recurring_strengths)} recurring strengths")
    print(f"  - {len(timeline.growth_areas)} growth areas")
    print(f"  - {len(timeline.theme_arcs)} theme arcs")
    print(f"  - {len(timeline.peer_endorsements)} peer endorsements")


if __name__ == "__main__":
    main()
