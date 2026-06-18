"""
Extract scanned Connect PDF pages to markdown using Claude vision API.

Renders each PDF page as an image, sends to Claude, writes one .md per PDF.
Skips PDFs that already have a corresponding .md file unless --force is used.
"""
import argparse
import base64
import os
import sys

from dotenv import load_dotenv
import pymupdf
import anthropic

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
PDF_DIR = os.path.join(PROJECT_ROOT, "02_inputs", "pdf")
OUT_DIR = os.path.join(PROJECT_ROOT, "04_outputs", "md")

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

MODEL = "claude-haiku-4-5-20251001"
DPI_SCALE = 2.0

SYSTEM_PROMPT = """\
You are extracting text from a scanned Microsoft Connect performance review document.
Convert the page content to clean markdown, preserving the document structure:
- Use # for the main title, ## for section headings, ### for sub-headings
- Preserve bullet points and numbered lists
- Preserve bold/italic emphasis where clearly visible
- Preserve tables if present
- Keep paragraph breaks
- Do NOT add commentary, explanations, or meta-notes — output only the document content
- Do NOT wrap output in a code block
- If a page is mostly decorative (dividers, logos, blank) output only what text exists
- Ignore browser chrome, URLs, and page numbers at the edges of the scan"""

USER_PROMPT = "Extract all text from this page as markdown, preserving the document structure."


def page_to_base64(page: pymupdf.Page) -> str:
    """Render a PDF page at high DPI and return as base64 PNG."""
    mat = pymupdf.Matrix(DPI_SCALE, DPI_SCALE)
    pix = page.get_pixmap(matrix=mat)
    return base64.standard_b64encode(pix.tobytes("png")).decode()


def extract_page(client: anthropic.Anthropic, img_b64: str) -> str:
    """Send a single page image to Claude and get markdown back."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": img_b64,
                        },
                    },
                    {"type": "text", "text": USER_PROMPT},
                ],
            }
        ],
    )
    return response.content[0].text.strip()


def extract_pdf_to_markdown(client: anthropic.Anthropic, pdf_path: str) -> str:
    """Extract all pages from a PDF and return combined markdown."""
    doc = pymupdf.open(pdf_path)
    parts: list[str] = []

    for i, page in enumerate(doc):
        print(f"  page {i + 1}/{len(doc)}", end="\r", flush=True)
        img_b64 = page_to_base64(page)
        text = extract_page(client, img_b64)
        parts.append(text)

    print()
    doc.close()
    return "\n\n---\n\n".join(parts)


def main():
    parser = argparse.ArgumentParser(description="Extract Connect PDFs to markdown")
    parser.add_argument("--pdf-dir", default=PDF_DIR)
    parser.add_argument("--out-dir", default=OUT_DIR)
    parser.add_argument("--force", action="store_true", help="Re-extract even if .md exists")
    parser.add_argument("files", nargs="*", help="Specific PDF filenames to process (default: all)")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    client = anthropic.Anthropic()

    if args.files:
        pdfs = args.files
    else:
        pdfs = sorted(f for f in os.listdir(args.pdf_dir) if f.lower().endswith(".pdf"))

    if not pdfs:
        print("No PDFs found in", args.pdf_dir)
        sys.exit(1)

    print(f"Found {len(pdfs)} PDFs -> writing markdown to {args.out_dir}/\n")

    for pdf_name in pdfs:
        pdf_path = os.path.join(args.pdf_dir, pdf_name)
        stem = os.path.splitext(pdf_name)[0]
        out_path = os.path.join(args.out_dir, stem + ".md")

        if os.path.exists(out_path) and not args.force:
            print(f"[skip] {pdf_name} (already extracted)")
            continue

        if not os.path.exists(pdf_path):
            print(f"[error] {pdf_path} not found")
            continue

        doc = pymupdf.open(pdf_path)
        page_count = len(doc)
        doc.close()
        print(f"[{pdf_name}] {page_count} pages...")

        text = extract_pdf_to_markdown(client, pdf_path)

        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)

        print(f"  -> {stem}.md ({len(text):,} chars)")

    print("\nDone.")


if __name__ == "__main__":
    main()
