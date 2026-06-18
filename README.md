# Career Development Agent

An AI-powered career development toolkit that extracts, structures, and leverages performance review data to help professionals understand themselves and prepare for job searches.

## What It Does

This multi-agent system takes scanned performance review PDFs and transforms them into actionable career intelligence:

1. **Extract** — OCR scanned PDFs into clean markdown using Claude vision
2. **Structure** — Parse markdown into typed JSON with accomplishments, goals, feedback, and peer quotes
3. **Aggregate** — Synthesize all reviews into a longitudinal career timeline with themes, strengths, and growth arcs
4. **Generate** — Produce tailored resumes, case study portfolios, and cover letters
5. **Reflect** — Interactive self-insight agent for exploring career patterns
6. **Prepare** — Interview preparation with behavioral questions, STAR answers, and gap analysis

## Project Structure

```
├── 01_orchestrator/           # Main entry point
│   └── career_agent.py        #   Full agentic assistant (tool-use loop)
├── 02_inputs/                 # Source materials
│   └── pdf/                   #   Place your scanned review PDFs here
├── 03_skills/                 # Supporting scripts (can be run independently)
│   ├── extract_markdown.py    #   PDF → Markdown (vision OCR)
│   ├── extract_structured.py  #   Markdown → Structured JSON
│   ├── aggregate_timeline.py  #   JSONs → Career Timeline
│   ├── generate_resume.py     #   Tailored resume generator
│   ├── generate_portfolio.py  #   Case study portfolio generator
│   ├── self_insight.py        #   Interactive career reflection
│   ├── interview_prep.py      #   Interview prep (5 modes)
│   ├── run_extraction.py      #   Pipeline orchestrator (steps 1+2)
│   ├── schema.py              #   Pydantic models for review data
│   └── schema_timeline.py     #   Pydantic models for career timeline
├── 04_outputs/                # Generated artifacts (gitignored)
│   ├── md/                    #   Extracted markdown
│   ├── json/                  #   Structured review JSONs
│   ├── resumes/               #   Generated resumes
│   ├── portfolios/            #   Generated portfolios
│   └── career_timeline.json   #   Aggregated career profile
├── .env.example               # API key template
├── requirements.txt           # Python dependencies
└── README.md
```

## Quick Start

### Prerequisites

- Python 3.11+
- An [Anthropic API key](https://console.anthropic.com/settings/keys)

### Setup

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/career-development-agent.git
cd career-development-agent

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate    # Windows
# source .venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Configure API key
cp .env.example .env
# Edit .env and add your Anthropic API key
```

### Usage

#### Option 1: Full Agent (Recommended)

The career agent autonomously manages the full pipeline — just tell it what you need:

```bash
python 01_orchestrator/career_agent.py
```

Example prompts:
- "Extract and analyze my performance reviews"
- "Generate a resume for a UX Research Lead at Google"
- "Prepare me for interviews at Meta"
- "What are my recurring strengths?"

#### Option 2: Run Individual Skills

Each skill can be run independently:

```bash
# Step 1: Extract PDFs to markdown
python 03_skills/extract_markdown.py

# Step 2: Parse markdown to structured JSON
python 03_skills/extract_structured.py

# Step 3: Aggregate into career timeline
python 03_skills/aggregate_timeline.py

# Generate outputs
python 03_skills/generate_resume.py --target "Senior UXR at Google"
python 03_skills/generate_portfolio.py --target "Research Lead at Meta"

# Interactive tools
python 03_skills/self_insight.py
python 03_skills/interview_prep.py
```

#### Option 3: Pipeline Orchestrator

Run the extraction pipeline (steps 1+2) in one command:

```bash
python 03_skills/run_extraction.py           # All PDFs
python 03_skills/run_extraction.py --force   # Re-extract everything
```

## Input Format

Place scanned PDF performance reviews in `02_inputs/pdf/`. The system is designed for Microsoft Connect reviews but can be adapted for other formats by modifying the schema and extraction prompts.

### Supported Document Structure

The structured extraction expects documents with:
- Employee metadata (name, title, manager, period)
- Self-assessment / accomplishments
- Goals and priorities
- Manager feedback
- Peer endorsements / stakeholder quotes

## Customization

### Adapting the Schema

Edit `03_skills/schema.py` to match your review format. The `ConnectReview` model defines what fields get extracted. After changing the schema:

```bash
python 03_skills/extract_structured.py --force  # Re-parse all markdowns
python 03_skills/aggregate_timeline.py --force   # Re-aggregate timeline
```

### Changing the LLM Model

Each script defines a `MODEL` constant at the top. Change it to use a different Claude model (e.g., `claude-sonnet-4-5-20241022` for higher quality extraction).

## How It Works

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Scanned    │     │   Clean     │     │ Structured  │     │   Career    │
│    PDFs     │────▶│  Markdown   │────▶│    JSON     │────▶│  Timeline   │
│             │     │             │     │             │     │             │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
   (vision OCR)       (text LLM)         (aggregation)          │
                                                                 │
                                              ┌──────────────────┼──────────────┐
                                              ▼                  ▼              ▼
                                        ┌──────────┐    ┌────────────┐  ┌───────────┐
                                        │ Resumes  │    │ Portfolios │  │ Interview │
                                        │          │    │            │  │   Prep    │
                                        └──────────┘    └────────────┘  └───────────┘
```

## Privacy & Security

- **No data leaves your machine** except via API calls to Anthropic for processing
- The `.env` file (with your API key) is gitignored
- The `04_outputs/` directory is gitignored — your career data stays local
- The `02_inputs/pdf/` directory is gitignored — your source documents stay local

## License

MIT
