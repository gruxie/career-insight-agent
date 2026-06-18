"""
Generate a tailored resume from career timeline and structured review data.

Reads the aggregated career timeline and individual review JSONs, asks the user
for a target role/company, and produces a markdown resume tailored to that target.
"""
import argparse
import json
import os
import sys
from datetime import datetime

from dotenv import load_dotenv
import anthropic

from schema_timeline import CareerTimeline

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
TIMELINE_PATH = os.path.join(PROJECT_ROOT, "04_outputs", "career_timeline.json")
JSON_DIR = os.path.join(PROJECT_ROOT, "04_outputs", "json")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "04_outputs", "resumes")
DEFAULT_OUTPUT = os.path.join(OUTPUT_DIR, "resume.md")

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

MODEL = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = """\
You are an expert resume writer. You will receive:
1. A longitudinal career timeline with projects, strengths, themes, and growth areas
2. Individual review data with detailed accomplishments and peer feedback
3. A target context (company, role, or organization the person is applying to)

Your job is to produce a polished, professional resume in markdown format.

Guidelines:
- Structure: Contact placeholder, Summary, Experience (reverse chronological), \
Key Projects & Impact, Skills & Competencies, Education placeholder
- The Summary should be 3-4 sentences tailored to the target context
- Under Experience, group work by role/period with bullet points for key accomplishments
- Select and emphasize projects most relevant to the target context
- Use strong action verbs and quantify impact where data exists (viewer counts, \
study counts, team sizes, etc.)
- Include peer endorsement quotes as brief callouts where they strengthen the narrative
- Keep it to approximately 2 pages worth of content (not too long, not too sparse)
- Write in first person implied (no "I" — use resume conventions like "Led...", "Designed...")
- If the target is a specific company or org, mirror their language and values where authentic
- Do NOT fabricate accomplishments — only use what's in the source data
- Output clean markdown with no code fences or commentary"""


def load_career_data(timeline_path: str, json_dir: str) -> tuple[dict, list[dict]]:
    """Load the career timeline and all individual review JSONs."""
    with open(timeline_path, "r", encoding="utf-8") as f:
        timeline = json.load(f)

    reviews = []
    for fname in sorted(os.listdir(json_dir)):
        if fname.endswith(".json"):
            with open(os.path.join(json_dir, fname), "r", encoding="utf-8") as f:
                reviews.append(json.load(f))

    return timeline, reviews


def build_user_prompt(timeline: dict, reviews: list[dict], target: str) -> str:
    """Build the prompt with career data and target context."""

    # Collect all peer endorsements from individual reviews
    endorsements = []
    for review in reviews:
        period = review.get("connect_period", "")
        mf = review.get("manager_feedback", {})
        for pf in mf.get("peer_feedback", []):
            endorsements.append({
                "quote": pf["quote"],
                "attribution": pf.get("attribution"),
                "period": period,
            })

    return f"""\
Generate a tailored resume for the following target:

TARGET: {target}

CAREER TIMELINE:
{json.dumps(timeline, indent=2)}

PEER ENDORSEMENTS FROM REVIEWS:
{json.dumps(endorsements, indent=2)}

Produce the resume in markdown format, tailored to the target context. \
Select the most relevant projects, strengths, and endorsements for this target."""


def generate_resume(
    client: anthropic.Anthropic,
    timeline: dict,
    reviews: list[dict],
    target: str,
) -> str:
    """Generate a tailored resume via Claude."""
    user_prompt = build_user_prompt(timeline, reviews, target)

    print(f"  Generating resume ({len(user_prompt):,} chars of context)...")

    collected_text = []
    with client.messages.stream(
        model=MODEL,
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": user_prompt},
        ],
    ) as stream:
        for text in stream.text_stream:
            collected_text.append(text)

    return "".join(collected_text).strip()


def main():
    parser = argparse.ArgumentParser(description="Generate a tailored resume")
    parser.add_argument(
        "--timeline",
        default=TIMELINE_PATH,
    )
    parser.add_argument(
        "--json-dir",
        default=JSON_DIR,
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help="Output markdown file path",
    )
    parser.add_argument(
        "--target",
        help="Target role/company (if not provided, will prompt interactively)",
    )
    args = parser.parse_args()

    if not os.path.exists(args.timeline):
        print(f"[error] Career timeline not found: {args.timeline}")
        print("Run aggregate_timeline.py first.")
        sys.exit(1)

    client = anthropic.Anthropic()

    print("Loading career data...")
    timeline, reviews = load_career_data(args.timeline, args.json_dir)
    print(f"  Loaded timeline + {len(reviews)} reviews")

    # Get target context
    target = args.target
    if not target:
        print()
        print("Who are you targeting this resume for?")
        print("Examples:")
        print('  "Senior UX Researcher at Microsoft DevDiv"')
        print('  "UX Research Lead at Google, focused on developer tools"')
        print('  "General purpose - broad UX research role"')
        print()
        target = input("Target: ").strip()
        if not target:
            target = "General purpose UX Research role"

    print(f'\nTarget: "{target}"')
    resume_md = generate_resume(client, timeline, reviews, target)

    # Include target in filename if custom output not specified
    if args.output == DEFAULT_OUTPUT:
        # Create a safe filename from target
        safe_name = "".join(c if c.isalnum() or c in " -_" else "" for c in target)
        safe_name = safe_name.strip().replace(" ", "_")[:60]
        args.output = os.path.join(OUTPUT_DIR, f"resume_{safe_name}.md")

    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(resume_md)

    print(f"\n[OK] Resume written to {args.output}")
    print(f"  ({len(resume_md):,} chars)")


if __name__ == "__main__":
    main()
