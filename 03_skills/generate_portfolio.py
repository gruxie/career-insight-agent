"""
Generate a UX research portfolio with case studies from career data.

Reads career timeline and individual review JSONs, auto-selects the strongest
projects, and produces a polished markdown portfolio with case study write-ups.
Optionally tailored to a target role/company.
"""
import argparse
import json
import os
import sys

from dotenv import load_dotenv
import anthropic

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
TIMELINE_PATH = os.path.join(PROJECT_ROOT, "04_outputs", "career_timeline.json")
JSON_DIR = os.path.join(PROJECT_ROOT, "04_outputs", "json")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "04_outputs", "portfolios")
DEFAULT_OUTPUT = os.path.join(OUTPUT_DIR, "portfolio.md")

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

MODEL = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = """\
You are an expert UX research portfolio writer. You will receive a person's complete \
career data including projects, accomplishments, peer feedback, and career timeline. \
Your job is to produce a polished research portfolio in markdown format.

First, auto-select the 5-7 strongest projects for the portfolio based on:
- Depth of evidence (detailed description, clear methods, measurable outcomes)
- Diversity of methods (mix of generative, evaluative, quant, qual)
- Impact demonstrated (product changes, stakeholder influence, metrics)
- Relevance to the target context (if provided)
- Recency (favor recent work but include standout older projects)

For each selected project, write a case study with this structure:

## [Project Title]
**Role** | **Timeline** | **Methods Used**

### Challenge
What problem or question drove this research? (2-3 sentences)

### Approach
What methods did you use and why? How was the study designed? (3-5 sentences)

### Key Findings
The most important discoveries, with specifics. Use bullet points. (3-5 bullets)

### Impact
What changed as a result? Product decisions, strategy shifts, metrics. (2-4 sentences)

### Reflection
What was learned about craft, process, or collaboration. (1-2 sentences, optional)

Also include:
- A portfolio introduction (3-4 sentences positioning the researcher)
- A "Research Philosophy" section (2-3 sentences on their approach to research)
- A skills/methods summary at the end

Guidelines:
- Use strong, active language — this is a showcase document
- Include specific metrics, viewer counts, stakeholder names where available
- Weave in peer endorsement quotes where they strengthen a case study
- If a target role is specified, emphasize projects most relevant to it
- Do NOT fabricate details — only use what's in the source data
- Output clean markdown with no code fences or commentary
- Aim for a comprehensive but scannable document (roughly 3000-5000 words)"""


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


def build_prompt(timeline: dict, reviews: list[dict], target: str) -> str:
    """Build the portfolio generation prompt."""
    # Collect peer endorsements
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

    target_line = f"\nTARGET CONTEXT: {target}" if target else ""

    return f"""\
Generate a UX research portfolio with auto-selected case studies.
{target_line}

CAREER TIMELINE:
{json.dumps(timeline, indent=2)}

PEER ENDORSEMENTS:
{json.dumps(endorsements, indent=2)}

Select the 5-7 strongest projects and write the portfolio in markdown."""


def generate_portfolio(
    client: anthropic.Anthropic,
    timeline: dict,
    reviews: list[dict],
    target: str | None,
) -> str:
    """Generate the portfolio via Claude."""
    user_prompt = build_prompt(timeline, reviews, target or "")

    print(f"  Generating portfolio ({len(user_prompt):,} chars of context)...")

    collected = []
    with client.messages.stream(
        model=MODEL,
        max_tokens=16384,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": user_prompt},
        ],
    ) as stream:
        for text in stream.text_stream:
            collected.append(text)

    return "".join(collected).strip()


def main():
    parser = argparse.ArgumentParser(description="Generate a UX research portfolio")
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
    )
    parser.add_argument("--target", help="Optional target role/company to tailor for")
    parser.add_argument("--force", action="store_true", help="Overwrite existing output")
    args = parser.parse_args()

    if not os.path.exists(args.timeline):
        print(f"[error] Career timeline not found: {args.timeline}")
        print("Run aggregate_timeline.py first.")
        sys.exit(1)

    client = anthropic.Anthropic()

    print("Loading career data...")
    timeline, reviews = load_career_data(args.timeline, args.json_dir)
    print(f"  Loaded timeline + {len(reviews)} reviews")

    # Interactive target prompt if not provided via CLI
    target = args.target
    if not target:
        print("\n  Optionally tailor the portfolio to a target role.")
        print("  Press Enter for a general-purpose portfolio.")
        target = input("  Target (or Enter to skip): ").strip() or None

    if target:
        print(f'\n  Tailoring for: "{target}"')
        safe = "".join(c if c.isalnum() or c in " -_" else "" for c in target)
        safe = safe.strip().replace(" ", "_")[:60]
        if args.output == DEFAULT_OUTPUT:
            args.output = os.path.join(OUTPUT_DIR, f"portfolio_{safe}.md")
    else:
        print("\n  Generating general-purpose portfolio")

    if os.path.exists(args.output) and not args.force:
        print(f"[skip] {args.output} already exists (use --force to overwrite)")
        sys.exit(0)

    portfolio = generate_portfolio(client, timeline, reviews, target)

    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(portfolio)

    print(f"\n[OK] Portfolio written to {args.output}")
    print(f"  ({len(portfolio):,} chars)")


if __name__ == "__main__":
    main()
