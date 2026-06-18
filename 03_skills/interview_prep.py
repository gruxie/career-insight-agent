"""
Interactive interview preparation agent.

Loads career timeline and structured review data, then helps the user
prepare for interviews by generating behavioral questions, STAR-format
answers, talking points, and mock interview practice — all grounded in
their actual career history.
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

MODES = {
    "1": ("Generate behavioral questions for a target role", "questions"),
    "2": ("Practice STAR answers from your real experience", "star"),
    "3": ("Build talking points for a specific topic", "talking_points"),
    "4": ("Mock interview (interviewer asks, you answer, get feedback)", "mock"),
    "5": ("Identify gaps between your experience and a target role", "gap_analysis"),
}

SYSTEM_PROMPT = """\
You are an expert interview coach with deep knowledge of behavioral interviewing, \
STAR method responses, and tech industry hiring practices. You have access to a \
person's complete performance review history spanning 5+ years at Microsoft, including \
self-assessments, manager feedback, peer endorsements, accomplishments, and an \
aggregated career timeline.

Your role is to help them prepare for job interviews by:
- Generating realistic behavioral questions tailored to their target role
- Helping them craft STAR (Situation, Task, Action, Result) answers from real experiences
- Building concise talking points that highlight their strongest evidence
- Running mock interviews with realistic follow-up questions
- Identifying experience gaps and suggesting how to address them

Rules:
- ONLY use accomplishments, projects, and feedback from their actual career data
- Never fabricate experiences — if they lack evidence for something, say so honestly
- Tailor question difficulty and framing to the target role level
- For STAR answers, pull specific details (project names, metrics, peer quotes)
- Be encouraging but honest about weak spots
- When in mock interview mode, stay in character as the interviewer"""

QUESTION_PROMPT = """\
Generate 8-10 behavioral interview questions that would likely come up for this \
target role. Organize them by category (leadership, technical, collaboration, etc.). \
For each question, note in parentheses which projects from the career data would \
make strong answers.

Target role: {target}"""

STAR_PROMPT = """\
The user wants to practice a STAR answer. Help them build one from their real \
experience. Ask which question or topic they want to prepare for, then construct \
a polished STAR response using specific evidence from their career data. Include \
the project name, what they did, metrics if available, and relevant peer quotes.

If the user provides a question, build the STAR answer directly."""

TALKING_POINTS_PROMPT = """\
Generate concise talking points the user can memorize for this topic. Each point \
should be 1-2 sentences, backed by a specific example from their career data. \
Include a "power quote" from peer feedback if one fits.

Topic: {topic}"""

MOCK_INTRO = """\
You are now the interviewer. You are interviewing this candidate for: {target}

Conduct a realistic behavioral interview:
1. Start with a warm intro and an opening question
2. Ask follow-up questions based on their answers (probe for specifics)
3. After each answer, briefly note (in italics) what was strong and what could improve
4. Move to new questions naturally
5. After 4-5 questions, wrap up and give overall feedback

Stay in character. Be professional but warm. Ask one question at a time."""

GAP_PROMPT = """\
Analyze the gap between this person's career experience and the target role. \
For each gap, suggest how they could address it in an interview (reframe existing \
experience, acknowledge and show learning plan, etc.).

Target role: {target}"""


def load_career_data(timeline_path: str, json_dir: str) -> str:
    """Load and format all career data as context."""
    with open(timeline_path, "r", encoding="utf-8") as f:
        timeline = json.load(f)

    reviews = []
    for fname in sorted(os.listdir(json_dir)):
        if fname.endswith(".json"):
            with open(os.path.join(json_dir, fname), "r", encoding="utf-8") as f:
                reviews.append(json.load(f))

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
    """Display mode options."""
    print("\n  Interview Prep Modes:\n")
    for key, (desc, _) in MODES.items():
        print(f"    {key}. {desc}")
    print(f"\n    Type 'q' to quit, 'menu' to see options again.\n")


def get_target(existing_target: str | None) -> str:
    """Prompt for target role if not already set."""
    if existing_target:
        print(f"  Current target: {existing_target}")
        change = input("  Keep this target? (Y/n): ").strip().lower()
        if change != "n":
            return existing_target

    print("\n  What role are you preparing for?")
    print("  Examples:")
    print('    "Senior UX Researcher at Google, developer tools"')
    print('    "UX Research Manager at Meta, AI products"')
    print('    "Principal Researcher at Microsoft DevDiv"')
    target = input("\n  Target role: ").strip()
    return target or "Senior UX Researcher role"


def stream_response(
    client: anthropic.Anthropic,
    messages: list[dict],
    max_tokens: int = 4096,
) -> str:
    """Stream a response from Claude and return the full text."""
    collected = []
    with client.messages.stream(
        model=MODEL,
        max_tokens=max_tokens,
        system=SYSTEM_PROMPT,
        messages=messages,
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
            collected.append(text)
    print("\n")
    return "".join(collected).strip()


def run_questions_mode(client: anthropic.Anthropic, messages: list[dict], target: str):
    """Generate behavioral questions for the target role."""
    prompt = QUESTION_PROMPT.format(target=target)
    messages.append({"role": "user", "content": prompt})
    print("\nGenerating questions...\n")
    response = stream_response(client, messages)
    messages.append({"role": "assistant", "content": response})


def run_star_mode(client: anthropic.Anthropic, messages: list[dict]):
    """Interactive STAR answer builder."""
    print("\n  What interview question do you want to prepare a STAR answer for?")
    print('  Example: "Tell me about a time you influenced a product decision with research"')
    question = input("\n  Question: ").strip()
    if not question:
        return

    prompt = f"{STAR_PROMPT}\n\nQuestion to prepare for: {question}"
    messages.append({"role": "user", "content": prompt})
    print("\nBuilding STAR answer...\n")
    response = stream_response(client, messages)
    messages.append({"role": "assistant", "content": response})


def run_talking_points_mode(client: anthropic.Anthropic, messages: list[dict]):
    """Generate talking points for a topic."""
    print("\n  What topic do you want talking points for?")
    print("  Examples: 'AI leadership', 'cross-team collaboration', 'research methodology'")
    topic = input("\n  Topic: ").strip()
    if not topic:
        return

    prompt = TALKING_POINTS_PROMPT.format(topic=topic)
    messages.append({"role": "user", "content": prompt})
    print("\nGenerating talking points...\n")
    response = stream_response(client, messages)
    messages.append({"role": "assistant", "content": response})


def run_mock_mode(client: anthropic.Anthropic, messages: list[dict], target: str):
    """Run a mock interview session."""
    prompt = MOCK_INTRO.format(target=target)
    messages.append({"role": "user", "content": prompt})
    print("\nStarting mock interview...\n")
    response = stream_response(client, messages)
    messages.append({"role": "assistant", "content": response})

    # Continue the mock interview loop
    while True:
        try:
            answer = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not answer or answer.lower() in ("q", "quit", "exit", "stop", "end"):
            print("\n  Mock interview ended.\n")
            break
        messages.append({"role": "user", "content": answer})
        print("\nInterviewer: ", end="", flush=True)
        response = stream_response(client, messages)
        messages.append({"role": "assistant", "content": response})


def run_gap_mode(client: anthropic.Anthropic, messages: list[dict], target: str):
    """Analyze gaps between experience and target role."""
    prompt = GAP_PROMPT.format(target=target)
    messages.append({"role": "user", "content": prompt})
    print("\nAnalyzing gaps...\n")
    response = stream_response(client, messages)
    messages.append({"role": "assistant", "content": response})


def main():
    parser = argparse.ArgumentParser(description="Interview preparation agent")
    parser.add_argument(
        "--timeline",
        default=TIMELINE_PATH,
    )
    parser.add_argument(
        "--json-dir",
        default=JSON_DIR,
    )
    parser.add_argument("--target", help="Target role (skip interactive prompt)")
    args = parser.parse_args()

    if not os.path.exists(args.timeline):
        print(f"[error] Career timeline not found: {args.timeline}")
        print("Run aggregate_timeline.py first.")
        sys.exit(1)

    print("Loading career data...")
    career_context = load_career_data(args.timeline, args.json_dir)
    print(f"  Loaded {len(career_context):,} chars of career context\n")

    client = anthropic.Anthropic()

    # Initialize conversation with career data
    messages: list[dict] = [
        {
            "role": "user",
            "content": (
                "Here is my complete career data. Use this to help me prepare "
                "for interviews. Do not repeat it — just acknowledge you're ready.\n\n"
                + career_context
            ),
        },
    ]

    print("Initializing interview prep agent...", end=" ", flush=True)
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

    print("=" * 60)
    print("  Interview Preparation Agent")
    print("  Practice questions, build STAR answers, run mock interviews")
    print("=" * 60)

    target = args.target
    if not target:
        target = get_target(None)

    show_menu()

    while True:
        try:
            choice = input("Mode (1-5, or 'q'): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if choice.lower() in ("q", "quit", "exit"):
            print("\nGoodbye!")
            break

        if choice.lower() == "menu":
            show_menu()
            continue

        if choice.lower() == "target":
            target = get_target(target)
            continue

        if choice not in MODES:
            print("  Pick 1-5, 'menu', 'target', or 'q'")
            continue

        _, mode = MODES[choice]

        if mode == "questions":
            target = get_target(target)
            run_questions_mode(client, messages, target)
        elif mode == "star":
            run_star_mode(client, messages)
        elif mode == "talking_points":
            run_talking_points_mode(client, messages)
        elif mode == "mock":
            target = get_target(target)
            run_mock_mode(client, messages, target)
        elif mode == "gap_analysis":
            target = get_target(target)
            run_gap_mode(client, messages, target)

        # Trim history if too long
        if len(messages) > 22:
            messages = messages[:2] + messages[-20:]


if __name__ == "__main__":
    main()
