#!/usr/bin/env python3.11
"""Generate the EN student install guide as .docx FROM the markdown.

Single source of truth: docs/STUDENT-INSTALL-EN.md. This is a thin wrapper around
docs/build_eleve_guide_fr.py: it reuses the very same markdown->docx parser and
renderer, only swapping the source file, the output file, the footer label and the
diagram caption to English.

    python3.11 docs/build_eleve_guide_en.py    # -> GUIDE-INSTALL-STUDENT-EN.docx
"""
from pathlib import Path
import tempfile

import build_eleve_guide_fr as b
from docx import Document

DOCS_DIR = Path(__file__).resolve().parent
SOURCE_MD = DOCS_DIR / "STUDENT-INSTALL-EN.md"
OUT = DOCS_DIR / "GUIDE-INSTALL-STUDENT-EN.docx"

# English caption for the architecture diagram (overrides the FR default).
b._MERMAID_CAPTIONS = {
    0: ("Student-side topology: your browser goes through the coach (sidecar), "
        "which forwards to the OWASP app, queries Ollama (judge + hints) and, in "
        "cohort mode, reports your events to the teacher dashboard."),
}
b._MERMAID_DEFAULT_CAPTION = "Student-side architecture diagram."


def main() -> None:
    if not SOURCE_MD.exists():
        raise SystemExit(f"Source not found: {SOURCE_MD}")
    print(f"Generating {OUT.name} from {SOURCE_MD.name} ...")
    md = SOURCE_MD.read_text(encoding="utf-8")
    blocks = b.parse_markdown(md)

    doc = Document()
    b.setup_styles(doc)
    b.add_footer_pagenum(doc, "JuiceLab Coach for PwnzzAI - Student guide")

    with tempfile.TemporaryDirectory(dir=str(DOCS_DIR)) as td:
        b.render_blocks(doc, blocks, Path(td))
        doc.save(str(OUT))
    print(f"  [ok] {OUT.name} generated ({OUT.stat().st_size // 1024} Ko)")
    print("Done.")


if __name__ == "__main__":
    main()
