"""
Interactive self-insight agent for career reflection and discovery.

Loads career timeline and structured review data, then engages in a
multi-turn conversation helping the user explore patterns, strengths,
blind spots, and growth opportunities grounded in their actual history.
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

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

MODEL = "claude-haiku-4-5-20251001"

STARTER_PROMPTS = [
    "What are my strongest recurring themes across my career?",
    "Where have I grown the most over the past 5 years?",
    "What blind spots or growth areas keep showing up?",
    "How has my relationship with AI evolved over time?",
    "What do my peers consistently say about me?",
    "What kind of work energizes me most based on the evidence?",
    "How has my scope and influence expanded over time?",
    "What skills should I develop next based on my trajectory?",
]

SYSTEM_PROMPT = """\
You are a thoughtful career coach and self-insight facilitator. You have access to \
a person's complete performance review history spanning multiple years at Microsoft, \
including their self-assessments, manager feedback, peer endorsements, goals, and \
an aggregated career timeline.

Your role is to help them reflect deeply on their career by:
- Surfacing patterns they may not see themselves
- Connecting themes across different review periods
- Highlighting tensions or contradictions in the data
- Identifying growth trajectories and inflection points
- Offering reframes that help them articulate their value
- Being honest about blind spots or areas that stalled

Ground every insight in specific evidence from their data. Quote or cite specific \
review periods, projects, peer feedback, or manager comments. Do not fabricate or \
extrapolate beyond what the data supports.

Be warm but direct. Favor depth over breadth — it's better to explore one insight \
thoroughly than to list many superficially. Ask follow-up questions to deepen \
reflection when appropriate.

When the user asks a question, structure your response as:
1. A direct answer grounded in evidence
2. A pattern or connection they might not have noticed
3. A reflective question to go deeper (when appropriate)

Keep responses focused and conversational — roughly 200-400 words unless the \
question warrants more detail."""


def load_career_data(timeline_path: str, json_dir: str) -> str:
    """Load and format all career data as context."""
    with open(timeline_path, "r", encoding="utf-8") as f:
        timeline = json.load(f)

    reviews = []
    for fname in sorted(os.listdir(json_dir)):
        if fname.endswith(".json"):
            with open(os.path.join(json_dir, fname), "r", encoding="utf-8") as f:
                reviews.append(json.load(f))

    # Build a compact but complete context block
    context = "=== CAREER TIMELINE ===\n"
    context += json.dumps(timeline, indent=2)
    context += "\n\n=== INDIVIDUAL REVIEWS ===\n"
    for review in reviews:
        period = review.get("connect_period", "Unknown")
        context += f"\n--- {period} ---\n"
        context += json.dumps(review, indent=2)
        context += "\n"

    return context


def show_menu():
    """Display starter prompts."""
    print("\n  Suggested questions (or type your own):\n")
    for i, prompt in enumerate(STARTER_PROMPTS, 1):
        print(f"    {i}. {prompt}")
    print(f"\n    Type 'q' to quit, or enter a number or your own question.\n")


def main():
    parser = argparse.ArgumentParser(description="Interactive career self-insight agent")
    parser.add_argument(
        "--timeline",
        default=TIMELINE_PATH,
    )
    parser.add_argument(
        "--json-dir",
        default=JSON_DIR,
    )
    args = parser.parse_args()

    if not os.path.exists(args.timeline):
        print(f"[error] Career timeline not found: {args.timeline}")
        print("Run aggregate_timeline.py first.")
        sys.exit(1)

    print("Loading career data...")
    career_context = load_career_data(args.timeline, args.json_dir)
    print(f"  Loaded {len(career_context):,} chars of career context\n")

    client = anthropic.Anthropic()

    # Conversation history
    messages: list[dict] = []

    # Inject career data as first user message + acknowledgment
    messages.append({
        "role": "user",
        "content": (
            "Here is my complete career data for reference. Use this to answer "
            "my questions. Do not repeat it back to me — just acknowledge you "
            "have it and are ready.\n\n" + career_context
        ),
    })

    # Get initial acknowledgment
    print("Initializing insight agent...", end=" ", flush=True)
    collected = []
    with client.messages.stream(
        model=MODEL,
        max_tokens=256,
        system=SYSTEM_PROMPT,
        messages=messages,
    ) as stream:
        for text in stream.text_stream:
            collected.append(text)

    ack = "".join(collected).strip()
    messages.append({"role": "assistant", "content": ack})
    print("Ready.\n")

    # Show welcome
    print("=" * 60)
    print("  Career Self-Insight Agent")
    print("  Explore your career patterns, strengths, and growth")
    print("=" * 60)

    show_menu()

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in ("q", "quit", "exit"):
            print("\nGoodbye!")
            break

        if user_input.lower() == "menu":
            show_menu()
            continue

        # Check if user typed a number for a starter prompt
        if user_input.isdigit():
            idx = int(user_input) - 1
            if 0 <= idx < len(STARTER_PROMPTS):
                user_input = STARTER_PROMPTS[idx]
                print(f"  -> {user_input}")
            else:
                print(f"  Pick 1-{len(STARTER_PROMPTS)}, or type your own question.")
                continue

        messages.append({"role": "user", "content": user_input})

        # Stream the response
        print("\nInsight Agent: ", end="", flush=True)
        collected = []
        try:
            with client.messages.stream(
                model=MODEL,
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                messages=messages,
            ) as stream:
                for text in stream.text_stream:
                    print(text, end="", flush=True)
                    collected.append(text)
        except Exception as e:
            print(f"\n[error] {e}")
            messages.pop()  # Remove the failed user message
            continue

        response_text = "".join(collected).strip()
        messages.append({"role": "assistant", "content": response_text})

        print("\n")

        # Trim conversation history if it gets too long (keep career context + last 10 turns)
        if len(messages) > 22:  # 2 (init) + 20 (10 user/assistant pairs)
            messages = messages[:2] + messages[-20:]


if __name__ == "__main__":
    main()
