"""
Agentic career assistant — full pipeline orchestrator.

A conversational agent that autonomously decides which tools to run,
manages dependencies, and chains multi-step workflows. Uses Claude
tool-use to route between extraction, analysis, resume generation,
portfolio creation, self-insight, and interview prep.
"""
import argparse
import json
import os
import subprocess
import sys

from dotenv import load_dotenv
import anthropic

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
SKILLS_DIR = os.path.join(PROJECT_ROOT, "03_skills")
INPUTS_DIR = os.path.join(PROJECT_ROOT, "02_inputs")
PDF_DIR = os.path.join(INPUTS_DIR, "pdf")
OUTPUTS_DIR = os.path.join(PROJECT_ROOT, "04_outputs")
MD_DIR = os.path.join(OUTPUTS_DIR, "md")
JSON_DIR = os.path.join(OUTPUTS_DIR, "json")
TIMELINE_PATH = os.path.join(OUTPUTS_DIR, "career_timeline.json")
RESUMES_DIR = os.path.join(OUTPUTS_DIR, "resumes")
PORTFOLIOS_DIR = os.path.join(OUTPUTS_DIR, "portfolios")
PYTHON = os.path.join(PROJECT_ROOT, ".venv", "Scripts", "python.exe")

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))


def safe_print(*args, **kwargs):
    """Print with fallback for Windows encoding issues (emoji, etc.)."""
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        text = " ".join(str(a) for a in args)
        print(text.encode("ascii", errors="replace").decode(), **kwargs)

MODEL = "claude-haiku-4-5-20251001"


# ---------------------------------------------------------------------------
# Tool definitions for Claude
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "check_pipeline_status",
        "description": (
            "Check what pipeline outputs currently exist: which PDFs have been "
            "extracted to markdown, which have structured JSON, whether a career "
            "timeline exists, and what resumes/portfolios have been generated. "
            "Call this first to understand what data is available."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "extract_pdfs_to_markdown",
        "description": (
            "Extract scanned PDF documents to clean markdown using vision OCR. "
            "This is Step 1 of the pipeline. Processes all PDFs in the 02_inputs/pdf/ "
            "directory that haven't been extracted yet."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "force": {
                    "type": "boolean",
                    "description": "Re-extract even if markdown already exists",
                },
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific PDF filenames to process (empty = all)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "extract_structured_json",
        "description": (
            "Parse extracted markdown files into structured JSON with typed fields "
            "(accomplishments, goals, manager feedback, peer quotes). This is Step 2. "
            "Requires markdown files from Step 1."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "force": {
                    "type": "boolean",
                    "description": "Re-parse even if JSON already exists",
                },
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific .md filenames to process (empty = all)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "aggregate_career_timeline",
        "description": (
            "Aggregate all structured review JSONs into a single longitudinal career "
            "timeline with roles, projects, recurring strengths, growth areas, theme "
            "arcs, and a career narrative. Requires structured JSONs from Step 2."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "force": {
                    "type": "boolean",
                    "description": "Overwrite existing timeline",
                },
            },
            "required": [],
        },
    },
    {
        "name": "generate_resume",
        "description": (
            "Generate a tailored resume in markdown format. Requires career timeline. "
            "The resume is customized based on the target role/company."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": (
                        "Target role and company, e.g. 'Senior UX Researcher at "
                        "Google, developer tools'. Required."
                    ),
                },
            },
            "required": ["target"],
        },
    },
    {
        "name": "generate_portfolio",
        "description": (
            "Generate a UX research portfolio with auto-selected case studies. "
            "Requires career timeline. Optionally tailored to a target role."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "Optional target role to tailor case study selection",
                },
            },
            "required": [],
        },
    },
    {
        "name": "career_insight",
        "description": (
            "Answer a career reflection question using the full career data. "
            "Surfaces patterns, strengths, blind spots, and growth trajectories "
            "grounded in evidence from performance reviews."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The reflection question to explore",
                },
            },
            "required": ["question"],
        },
    },
    {
        "name": "interview_questions",
        "description": (
            "Generate behavioral interview questions tailored to a target role, "
            "with suggested projects for STAR answers."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "Target role, e.g. 'Principal UXR at Google'",
                },
            },
            "required": ["target"],
        },
    },
    {
        "name": "star_answer",
        "description": (
            "Build a STAR-format interview answer for a specific behavioral "
            "question using real career evidence."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The interview question to prepare a STAR answer for",
                },
            },
            "required": ["question"],
        },
    },
    {
        "name": "gap_analysis",
        "description": (
            "Analyze gaps between the person's experience and a target role. "
            "Identifies missing skills or experience and suggests reframing strategies."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "Target role to analyze gaps against",
                },
            },
            "required": ["target"],
        },
    },
    {
        "name": "read_file",
        "description": (
            "Read the contents of a generated output file (resume, portfolio, "
            "timeline, etc.) to review or summarize it for the user."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Filename or relative path to read from the project outputs",
                },
            },
            "required": ["filename"],
        },
    },
]


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def check_pipeline_status() -> str:
    """Check what outputs exist."""
    pdfs = sorted(f for f in os.listdir(PDF_DIR) if f.endswith(".pdf")) if os.path.isdir(PDF_DIR) else []
    mds = sorted(f for f in os.listdir(MD_DIR) if f.endswith(".md")) if os.path.isdir(MD_DIR) else []
    jsons = sorted(f for f in os.listdir(JSON_DIR) if f.endswith(".json")) if os.path.isdir(JSON_DIR) else []

    timeline_exists = os.path.exists(TIMELINE_PATH)

    # Find generated resumes and portfolios
    resumes = sorted(f for f in os.listdir(RESUMES_DIR) if f.endswith(".md")) if os.path.isdir(RESUMES_DIR) else []
    portfolios = sorted(f for f in os.listdir(PORTFOLIOS_DIR) if f.endswith(".md")) if os.path.isdir(PORTFOLIOS_DIR) else []

    # Check which PDFs are missing markdown or JSON
    pdf_stems = {os.path.splitext(f)[0] for f in pdfs}
    md_stems = {os.path.splitext(f)[0] for f in mds}
    json_stems = {os.path.splitext(f)[0] for f in jsons}

    missing_md = pdf_stems - md_stems
    missing_json = md_stems - json_stems

    return json.dumps({
        "pdfs": len(pdfs),
        "markdowns": len(mds),
        "structured_jsons": len(jsons),
        "career_timeline": timeline_exists,
        "resumes": resumes,
        "portfolios": portfolios,
        "missing_markdown": sorted(missing_md),
        "missing_json": sorted(missing_json),
        "pipeline_ready": timeline_exists and len(jsons) > 0,
    }, indent=2)


def run_script(script: str, args: list[str]) -> str:
    """Run a pipeline script and return output."""
    cmd = [PYTHON, os.path.join(SKILLS_DIR, script)] + args
    result = subprocess.run(
        cmd, capture_output=True, text=True, cwd=SKILLS_DIR,
        env={**os.environ}, timeout=600,
    )
    output = result.stdout
    if result.returncode != 0:
        output += f"\n[STDERR]\n{result.stderr}"
        output += f"\n[EXIT CODE: {result.returncode}]"
    return output


def extract_pdfs_to_markdown(force: bool = False, files: list[str] | None = None) -> str:
    args = []
    if force:
        args.append("--force")
    if files:
        args.extend(files)
    return run_script("extract_markdown.py", args)


def extract_structured_json(force: bool = False, files: list[str] | None = None) -> str:
    args = []
    if force:
        args.append("--force")
    if files:
        args.extend(files)
    return run_script("extract_structured.py", args)


def aggregate_career_timeline(force: bool = False) -> str:
    args = ["--force"] if force else []
    return run_script("aggregate_timeline.py", args)


def generate_resume(target: str) -> str:
    return run_script("generate_resume.py", ["--target", target])


def generate_portfolio(target: str | None = None) -> str:
    args = ["--force"]
    if target:
        args.extend(["--target", target])
    return run_script("generate_portfolio.py", args)


def load_career_context() -> str:
    """Load career data for insight/interview tools."""
    if not os.path.exists(TIMELINE_PATH):
        return "[ERROR] Career timeline not found. Run the extraction pipeline first."

    with open(TIMELINE_PATH, "r", encoding="utf-8") as f:
        timeline = json.load(f)

    reviews = []
    for fname in sorted(os.listdir(JSON_DIR)):
        if fname.endswith(".json"):
            with open(os.path.join(JSON_DIR, fname), "r", encoding="utf-8") as f:
                reviews.append(json.load(f))

    return json.dumps({"timeline": timeline, "reviews": reviews})


def career_insight_query(client: anthropic.Anthropic, question: str) -> str:
    """Run a career insight query."""
    career_data = load_career_context()
    if career_data.startswith("[ERROR]"):
        return career_data

    system = (
        "You are a thoughtful career coach. You have a person's complete review "
        "history. Ground every insight in specific evidence. Be warm but direct. "
        "~200-400 words."
    )
    response_parts = []
    with client.messages.stream(
        model=MODEL, max_tokens=2048, system=system,
        messages=[
            {"role": "user", "content": f"Career data:\n{career_data}"},
            {"role": "assistant", "content": "I have your career data loaded."},
            {"role": "user", "content": question},
        ],
    ) as stream:
        for text in stream.text_stream:
            response_parts.append(text)
    return "".join(response_parts)


def interview_questions_query(client: anthropic.Anthropic, target: str) -> str:
    """Generate interview questions for a target role."""
    career_data = load_career_context()
    if career_data.startswith("[ERROR]"):
        return career_data

    system = (
        "You are an expert interview coach. Generate 8-10 behavioral interview "
        "questions for the target role, organized by category. For each question, "
        "note which projects from the career data would make strong STAR answers."
    )
    response_parts = []
    with client.messages.stream(
        model=MODEL, max_tokens=4096, system=system,
        messages=[
            {"role": "user", "content": f"Career data:\n{career_data}"},
            {"role": "assistant", "content": "Ready to generate interview questions."},
            {"role": "user", "content": f"Generate behavioral interview questions for: {target}"},
        ],
    ) as stream:
        for text in stream.text_stream:
            response_parts.append(text)
    return "".join(response_parts)


def star_answer_query(client: anthropic.Anthropic, question: str) -> str:
    """Build a STAR answer from career evidence."""
    career_data = load_career_context()
    if career_data.startswith("[ERROR]"):
        return career_data

    system = (
        "You are an expert interview coach. Build a polished STAR (Situation, Task, "
        "Action, Result) answer using specific evidence from the career data. Include "
        "project names, metrics, and peer quotes where available."
    )
    response_parts = []
    with client.messages.stream(
        model=MODEL, max_tokens=2048, system=system,
        messages=[
            {"role": "user", "content": f"Career data:\n{career_data}"},
            {"role": "assistant", "content": "Ready to build STAR answers."},
            {"role": "user", "content": f"Build a STAR answer for: {question}"},
        ],
    ) as stream:
        for text in stream.text_stream:
            response_parts.append(text)
    return "".join(response_parts)


def gap_analysis_query(client: anthropic.Anthropic, target: str) -> str:
    """Analyze experience gaps against a target role."""
    career_data = load_career_context()
    if career_data.startswith("[ERROR]"):
        return career_data

    system = (
        "You are an expert career advisor. Analyze gaps between this person's "
        "experience and the target role. For each gap, suggest how to address it "
        "in an interview (reframe existing experience, acknowledge and show "
        "learning plan, etc.). Be honest but constructive."
    )
    response_parts = []
    with client.messages.stream(
        model=MODEL, max_tokens=4096, system=system,
        messages=[
            {"role": "user", "content": f"Career data:\n{career_data}"},
            {"role": "assistant", "content": "Ready for gap analysis."},
            {"role": "user", "content": f"Analyze gaps for: {target}"},
        ],
    ) as stream:
        for text in stream.text_stream:
            response_parts.append(text)
    return "".join(response_parts)


def read_file(filename: str) -> str:
    """Read a file from the reorganized project structure."""
    normalized = os.path.normpath(filename)
    candidate_paths = [
        os.path.join(PROJECT_ROOT, normalized),
        os.path.join(OUTPUTS_DIR, normalized),
        os.path.join(MD_DIR, normalized),
        os.path.join(JSON_DIR, normalized),
        os.path.join(RESUMES_DIR, normalized),
        os.path.join(PORTFOLIOS_DIR, normalized),
        os.path.join(INPUTS_DIR, normalized),
        os.path.join(PDF_DIR, normalized),
    ]

    path = next((candidate for candidate in candidate_paths if os.path.exists(candidate)), None)
    if path is None:
        return f"[ERROR] File not found: {filename}"
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    # Truncate for context window
    if len(content) > 8000:
        return content[:8000] + f"\n\n[TRUNCATED — {len(content):,} total chars]"
    return content


def execute_tool(
    client: anthropic.Anthropic,
    tool_name: str,
    tool_input: dict,
) -> str:
    """Dispatch a tool call to the appropriate implementation."""
    if tool_name == "check_pipeline_status":
        return check_pipeline_status()
    elif tool_name == "extract_pdfs_to_markdown":
        return extract_pdfs_to_markdown(
            force=tool_input.get("force", False),
            files=tool_input.get("files"),
        )
    elif tool_name == "extract_structured_json":
        return extract_structured_json(
            force=tool_input.get("force", False),
            files=tool_input.get("files"),
        )
    elif tool_name == "aggregate_career_timeline":
        return aggregate_career_timeline(force=tool_input.get("force", False))
    elif tool_name == "generate_resume":
        return generate_resume(target=tool_input["target"])
    elif tool_name == "generate_portfolio":
        return generate_portfolio(target=tool_input.get("target"))
    elif tool_name == "career_insight":
        return career_insight_query(client, question=tool_input["question"])
    elif tool_name == "interview_questions":
        return interview_questions_query(client, target=tool_input["target"])
    elif tool_name == "star_answer":
        return star_answer_query(client, question=tool_input["question"])
    elif tool_name == "gap_analysis":
        return gap_analysis_query(client, target=tool_input["target"])
    elif tool_name == "read_file":
        return read_file(filename=tool_input["filename"])
    else:
        return f"[ERROR] Unknown tool: {tool_name}"


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------

AGENT_SYSTEM = """\
You are a career development assistant with access to a full pipeline of tools \
for analyzing performance reviews and preparing for job searches.

You help people:
- Extract and structure their performance review history from PDFs
- Understand their career patterns, strengths, and growth areas
- Generate tailored resumes and research portfolios
- Prepare for interviews with behavioral questions, STAR answers, and gap analysis

WORKFLOW AWARENESS:
- The pipeline has dependencies: PDFs -> Markdown -> Structured JSON -> Career Timeline
- Before generating resumes, portfolios, or insights, check if the pipeline is complete
- If data is missing, run the necessary extraction steps first
- Always check_pipeline_status before attempting to generate outputs

BEHAVIOR:
- Be proactive: if the user asks for a resume but no timeline exists, run the pipeline
- Chain tools when needed: a request like "prepare me for interviews at Google" should \
trigger multiple tools (gap analysis, questions, resume, portfolio)
- Report progress as you go — the user should know what you're doing
- After generating files, tell the user the filename and a brief summary
- Be concise in status updates, detailed in career insights
- When running long extraction steps, let the user know it will take a moment"""


def agent_loop(client: anthropic.Anthropic):
    """Main agent conversation loop with tool use."""
    messages: list[dict] = []

    print("=" * 60)
    print("  Career Development Agent")
    print("  Your AI-powered career assistant")
    print("=" * 60)
    print()
    print("  I can help you with:")
    print("    - Extract & analyze your performance reviews")
    print("    - Generate tailored resumes and portfolios")
    print("    - Explore career patterns and self-insights")
    print("    - Prepare for interviews (questions, STAR answers, gap analysis)")
    print()
    print("  Just tell me what you need. Type 'q' to quit.")
    print()

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

        messages.append({"role": "user", "content": user_input})

        # Agent loop: keep going until no more tool calls
        while True:
            response = client.messages.create(
                model=MODEL,
                max_tokens=4096,
                system=AGENT_SYSTEM,
                tools=TOOLS,
                messages=messages,
            )

            # Process the response
            assistant_content = response.content
            messages.append({"role": "assistant", "content": assistant_content})

            # Check for tool use
            tool_calls = [b for b in assistant_content if b.type == "tool_use"]

            if not tool_calls:
                # No tools — print text response
                for block in assistant_content:
                    if hasattr(block, "text"):
                        safe_print(f"\nAgent: {block.text}\n")
                break

            # Execute tool calls and collect results
            tool_results = []
            for tool_call in tool_calls:
                # Print text blocks before tool calls
                for block in assistant_content:
                    if hasattr(block, "text") and block.text.strip():
                        safe_print(f"\nAgent: {block.text}")
                        break

                safe_print(f"  [{tool_call.name}] ...", end=" ", flush=True)
                result = execute_tool(client, tool_call.name, tool_call.input)

                # Show brief status
                lines = result.strip().split("\n")
                status_line = lines[-1] if lines else "done"
                if len(status_line) > 100:
                    status_line = status_line[:100] + "..."
                safe_print(status_line)

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_call.id,
                    "content": result,
                })

            messages.append({"role": "user", "content": tool_results})

            # Continue the loop to let the agent process results

        # Trim conversation if too long (keep last 20 messages)
        if len(messages) > 30:
            messages = messages[-30:]


def main():
    parser = argparse.ArgumentParser(description="Career Development Agent")
    args = parser.parse_args()

    client = anthropic.Anthropic()
    agent_loop(client)


if __name__ == "__main__":
    main()
