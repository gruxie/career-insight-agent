"""
Run the full Connect extraction pipeline:
  1. PDF -> Markdown (vision OCR)
  2. Markdown -> Structured JSON (text extraction)

Usage:
  python run_extraction.py                  # Process all PDFs
  python run_extraction.py --force          # Re-process everything
  python run_extraction.py "Connect Apr 2026.pdf"  # Process specific file
"""
import argparse
import os
import sys
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
PYTHON = os.path.join(PROJECT_ROOT, ".venv", "Scripts", "python.exe")


def run_step(description: str, args: list[str]) -> bool:
    """Run a subprocess step and return True on success."""
    print(f"\n{'=' * 60}")
    print(f"  {description}")
    print(f"{'=' * 60}\n")

    result = subprocess.run(
        [PYTHON] + [os.path.join(SCRIPT_DIR, arg) if arg.endswith(".py") else arg for arg in args],
        cwd=SCRIPT_DIR,
        env={**os.environ},
    )
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="Run full Connect extraction pipeline")
    parser.add_argument("--force", action="store_true", help="Re-extract even if outputs exist")
    parser.add_argument(
        "--step",
        choices=["markdown", "structured", "all"],
        default="all",
        help="Which step to run (default: all)",
    )
    parser.add_argument("files", nargs="*", help="Specific PDF filenames to process")
    args = parser.parse_args()

    force_flag = ["--force"] if args.force else []
    file_args = args.files if args.files else []

    success = True

    # Step 1: PDF -> Markdown
    if args.step in ("markdown", "all"):
        ok = run_step(
            "Step 1: Extracting PDFs to Markdown (Vision OCR)",
            ["extract_markdown.py"] + force_flag + file_args,
        )
        if not ok:
            print("\n[FAILED] Markdown extraction failed.")
            if args.step == "all":
                print("Stopping pipeline.")
                sys.exit(1)
            success = False

    # Step 2: Markdown -> Structured JSON
    if args.step in ("structured", "all"):
        # If specific files given, convert .pdf names to .md names
        md_files = [os.path.splitext(f)[0] + ".md" for f in file_args] if file_args else []
        ok = run_step(
            "Step 2: Parsing Markdown to Structured JSON",
            ["extract_structured.py"] + force_flag + md_files,
        )
        if not ok:
            print("\n[FAILED] Structured extraction failed.")
            success = False

    if success:
        print("\n[OK] Pipeline complete.")
    else:
        print("\n[ERROR] Pipeline completed with errors.")
        sys.exit(1)


if __name__ == "__main__":
    main()
