#!/usr/bin/env python3
"""Genere le guide d'installation ELEVE FR au format .docx DEPUIS le markdown.

Source de verite UNIQUE : docs/STUDENT-INSTALL-FR.md (~400 lignes). Ce script
PARSE ce markdown et le rend fidelement en docs/GUIDE-INSTALL-ELEVE.docx, en
reutilisant les helpers python-docx (palette, styles, tables, code, notes,
captures) et la chaine de rendu Mermaid deja presents dans le depot
(build_install_guides.py / build_coach_guide.py).

Constructions markdown gerees (toutes celles presentes dans le fichier) :
    - # H1            -> page de titre (title_block)
    - ## / ###        -> Heading 1 / Heading 2
    - paragraphes     -> runs, avec **gras** et `code` inline
    - tables GFM      -> add_table (en-tete grise)
    - ``` fences      -> code_block (bash/powershell/text/ini/dockerfile/...)
    - ```mermaid      -> rendu PNG via render_mermaid + add_diagram (centre)
    - > blockquotes   -> note (encadre jaune) ; table interne rendue apres
    - listes - / *    -> bullet ; listes 1. -> numbered (sous-listes indentees)
    - ![alt](img/..)  -> add_screenshot (chemin relatif a docs/)
    - --- (regle)     -> ignore (fin de section)
    - lien de langue reciproque + ancres pures -> nettoyes

Dependances :
    - python-docx               (pip install python-docx)
    - @mermaid-js/mermaid-cli    -> binaire `mmdc` (npm i -g @mermaid-js/mermaid-cli)
      + un Chromium (mmdc en a besoin ; /snap/bin/chromium convient).

Interpreteur :
    Utiliser python3.11 : le `python3` par defaut de la machine est 3.13 et n'a
    PAS python-docx. python3.11 a bien python-docx.

Usage :
    python3.11 docs/build_eleve_guide_fr.py
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Inches, Mm, Pt, RGBColor
except ImportError:
    sys.exit(
        "python-docx introuvable. Installer : pip install python-docx "
        "(utiliser python3.11 : python3.11 -c 'import docx')."
    )

DOCS_DIR = Path(__file__).resolve().parent
IMG_DIR = DOCS_DIR / "img"
SOURCE_MD = DOCS_DIR / "STUDENT-INSTALL-FR.md"
ELEVE_OUT = DOCS_DIR / "GUIDE-INSTALL-ELEVE.docx"

# Palette (identique au modele JuiceLab, teinte violette du coach pour le titre)
BLUE = RGBColor(0x2E, 0x75, 0xB6)
PURPLE = RGBColor(0x6D, 0x28, 0xD9)
DARK = RGBColor(0x22, 0x22, 0x22)
GREY_FILL = "F2F2F2"
NOTE_FILL = "FFF4D6"
HEAD_FILL = "EDE7FB"

# ---------------------------------------------------------------------------
# Rendu Mermaid -> PNG (repris de build_install_guides.py)
# ---------------------------------------------------------------------------


def _find_mmdc() -> str:
    """Prefere le mmdc local (docs/node_modules) au mmdc global."""
    local = DOCS_DIR / "node_modules" / ".bin" / "mmdc"
    if local.is_file():
        return str(local)
    return shutil.which("mmdc") or ""


def _find_chromium() -> str:
    """Chromium utilisable pour mmdc. PUPPETEER_EXECUTABLE_PATH gagne, sinon
    on tente les binaires systeme courants (le Chromium snap fonctionne)."""
    exe = os.environ.get("PUPPETEER_EXECUTABLE_PATH", "")
    if exe and Path(exe).exists():
        return exe
    for cand in ("/snap/bin/chromium", "/usr/bin/chromium-browser",
                 "/usr/bin/chromium", "/usr/bin/google-chrome"):
        if Path(cand).exists():
            return cand
    return ""


def render_mermaid(source: str, out_png: Path, tmp: Path) -> bool:
    """Rend un diagramme Mermaid en PNG via mmdc. Retourne True si succes."""
    mmdc = _find_mmdc()
    if not mmdc:
        print("  [warn] mmdc introuvable — diagramme saute. Installer : "
              "cd docs && npm install @mermaid-js/mermaid-cli", file=sys.stderr)
        return False

    mmd = tmp / (out_png.stem + ".mmd")
    mmd.write_text(source.strip() + "\n", encoding="utf-8")

    pcfg = tmp / "puppeteer.json"
    chromium = _find_chromium()
    if chromium:
        pcfg.write_text(
            '{"executablePath":"%s","args":["--no-sandbox","--disable-gpu"]}'
            % chromium, encoding="utf-8",
        )
    else:
        pcfg.write_text('{"args":["--no-sandbox","--disable-gpu"]}',
                        encoding="utf-8")

    cmd = [mmdc, "-i", str(mmd), "-o", str(out_png),
           "-b", "white", "-s", "2", "-p", str(pcfg)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not out_png.exists():
        print(f"  [warn] echec rendu {out_png.name} :\n{proc.stderr.strip()}",
              file=sys.stderr)
        return False
    return True


# ---------------------------------------------------------------------------
# Helpers python-docx (repris de build_install_guides.py)
# ---------------------------------------------------------------------------


def setup_styles(doc: Document) -> None:
    section = doc.sections[0]
    section.page_width = Mm(210)
    section.page_height = Mm(297)
    section.top_margin = Mm(20)
    section.bottom_margin = Mm(20)
    section.left_margin = Mm(20)
    section.right_margin = Mm(20)

    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)

    for level, size in ((1, 18), (2, 14), (3, 12)):
        st = doc.styles[f"Heading {level}"]
        st.font.name = "Calibri"
        st.font.size = Pt(size)
        st.font.bold = True
        st.font.color.rgb = PURPLE if level == 1 else DARK

    zoom = doc.settings.element.find(qn("w:zoom"))
    if zoom is not None:
        zoom.set(qn("w:percent"), "100")
        if zoom.get(qn("w:val")) is not None:
            del zoom.attrib[qn("w:val")]


_PPR_AFTER_SHD = (
    "w:tabs", "w:suppressAutoHyphens", "w:kinsoku", "w:wordWrap",
    "w:overflowPunct", "w:topLinePunct", "w:autoSpaceDE", "w:autoSpaceDN",
    "w:bidi", "w:adjustRightInd", "w:snapToGrid", "w:spacing", "w:ind",
    "w:contextualSpacing", "w:mirrorIndents", "w:suppressOverlap", "w:jc",
    "w:textDirection", "w:textAlignment", "w:textboxTightWrap", "w:outlineLvl",
    "w:divId", "w:cnfStyle", "w:rPr", "w:sectPr", "w:pPrChange",
)


def _shade(paragraph, fill: str) -> None:
    pPr = paragraph._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), fill)
    pPr.insert_element_before(shd, *_PPR_AFTER_SHD)


def title_block(doc: Document, title: str, subtitle: str) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = p.add_run(title)
    run.font.size = Pt(26)
    run.font.bold = True
    run.font.color.rgb = PURPLE
    sub = doc.add_paragraph()
    r = sub.add_run(subtitle)
    r.font.size = Pt(12)
    r.font.color.rgb = DARK
    r.italic = True
    bar = doc.add_paragraph()
    pPr = bar._p.get_or_add_pPr()
    pbdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "12")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "6D28D9")
    pbdr.append(bottom)
    pPr.append(pbdr)


def add_footer_pagenum(doc: Document, label: str) -> None:
    """Pied de page : libelle a gauche + numero de page a droite."""
    footer = doc.sections[0].footer
    p = footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(label + "  -  page ")
    run.font.size = Pt(9)
    run.font.color.rgb = DARK
    fld_begin = OxmlElement("w:fldSimple")
    fld_begin.set(qn("w:instr"), "PAGE")
    run2 = p.add_run()
    run2._r.addnext(fld_begin)
    r = OxmlElement("w:r")
    t = OxmlElement("w:t")
    t.text = "1"
    r.append(t)
    fld_begin.append(r)


def para(doc: Document, text: str) -> None:
    doc.add_paragraph(text)


def bullet(doc: Document, text: str, level: int = 0) -> None:
    style = "List Bullet" if level == 0 else f"List Bullet {min(level + 1, 3)}"
    try:
        doc.add_paragraph(text, style=style)
    except KeyError:
        doc.add_paragraph(text, style="List Bullet")


def numbered(doc: Document, text: str) -> None:
    doc.add_paragraph(text, style="List Number")


def code_block(doc: Document, lines: list[str]) -> None:
    for ln in lines:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.space_before = Pt(0)
        _shade(p, GREY_FILL)
        run = p.add_run(ln if ln else " ")
        run.font.name = "Consolas"
        run.font.size = Pt(9.5)
    doc.add_paragraph().paragraph_format.space_after = Pt(4)


def note(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    _shade(p, NOTE_FILL)
    _add_inline_runs(p, text, base_size=Pt(10.5))


def add_table(doc: Document, headers: list[str], rows: list[list[str]],
              widths_mm: list[int] | None = None) -> None:
    ncols = len(headers)
    table = doc.add_table(rows=1, cols=ncols)
    table.style = "Table Grid"
    hdr = table.rows[0].cells
    for i, h in enumerate(headers):
        hdr[i].text = ""
        _add_inline_runs(hdr[i].paragraphs[0], h, base_size=Pt(10), bold=True)
        _shade(hdr[i].paragraphs[0], HEAD_FILL)
    for row in rows:
        cells = table.add_row().cells
        for i in range(ncols):
            val = row[i] if i < len(row) else ""
            cells[i].text = ""
            _add_inline_runs(cells[i].paragraphs[0], val, base_size=Pt(10))
    if widths_mm:
        for col_idx, w in enumerate(widths_mm):
            for cell in table.columns[col_idx].cells:
                cell.width = Mm(w)


def add_diagram(doc: Document, png: Path, caption: str) -> None:
    if png and png.exists():
        doc.add_picture(str(png), width=Inches(6.2))
        doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap = doc.add_paragraph()
        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = cap.add_run(caption)
        r.italic = True
        r.font.size = Pt(9)
        r.font.color.rgb = DARK


def add_screenshot(doc: Document, png: Path, caption: str) -> None:
    """Insere une capture d'ecran versionnee (docs/img/) + legende centree."""
    if png and png.exists():
        add_diagram(doc, png, caption)
    else:
        print("  [warn] capture introuvable, saut : %s" % png, file=sys.stderr)


# ---------------------------------------------------------------------------
# Rendu des runs inline : **gras** et `code`
# ---------------------------------------------------------------------------

_INLINE_RE = re.compile(r"(\*\*.+?\*\*|`[^`]+`)")
# liens markdown [texte](url) -> texte ; <url autonome> -> url
_MDLINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_ANGLE_URL_RE = re.compile(r"<((?:https?://|mailto:)[^>]+)>")


def _strip_links(text: str) -> str:
    text = _MDLINK_RE.sub(r"\1", text)
    text = _ANGLE_URL_RE.sub(r"\1", text)
    return text


def _add_inline_runs(paragraph, text: str, base_size=None, bold=False) -> None:
    """Ajoute des runs en interpretant **gras** et `code` inline."""
    text = _strip_links(text)
    parts = _INLINE_RE.split(text)
    for part in parts:
        if not part:
            continue
        if part.startswith("**") and part.endswith("**") and len(part) >= 4:
            run = paragraph.add_run(part[2:-2])
            run.bold = True
        elif part.startswith("`") and part.endswith("`") and len(part) >= 2:
            run = paragraph.add_run(part[1:-1])
            run.font.name = "Consolas"
        else:
            run = paragraph.add_run(part)
        if bold:
            run.bold = True
        if base_size is not None:
            run.font.size = base_size


def rich_para(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    _add_inline_runs(p, text)


def rich_bullet(doc: Document, text: str, level: int = 0) -> None:
    style = "List Bullet" if level == 0 else f"List Bullet {min(level + 1, 3)}"
    try:
        p = doc.add_paragraph(style=style)
    except KeyError:
        p = doc.add_paragraph(style="List Bullet")
    _add_inline_runs(p, text)


def rich_numbered(doc: Document, text: str) -> None:
    p = doc.add_paragraph(style="List Number")
    _add_inline_runs(p, text)


# ---------------------------------------------------------------------------
# Parsing markdown -> liste de blocs
# ---------------------------------------------------------------------------

_TABLE_SEP_RE = re.compile(r"^\s*\|?[\s:\-]+\|[\s:|\-]*$")


def _is_table_row(line: str) -> bool:
    s = line.strip()
    return s.startswith("|") and s.count("|") >= 2


def _split_table_row(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def _is_table_sep(line: str) -> bool:
    s = line.strip()
    if not (s.startswith("|") or "|" in s):
        return False
    return bool(_TABLE_SEP_RE.match(s)) and "-" in s


def parse_markdown(md: str) -> list[dict]:
    """Tokenise le markdown en une liste de blocs typés."""
    lines = md.split("\n")
    blocks: list[dict] = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        stripped = line.strip()

        # ligne vide
        if not stripped:
            i += 1
            continue

        # regle horizontale
        if stripped == "---" or re.fullmatch(r"-{3,}", stripped):
            blocks.append({"type": "hr"})
            i += 1
            continue

        # fence de code (``` ou ```lang)
        if stripped.startswith("```"):
            lang = stripped[3:].strip().lower()
            i += 1
            body: list[str] = []
            while i < n and not lines[i].strip().startswith("```"):
                body.append(lines[i])
                i += 1
            i += 1  # consomme la fence fermante
            if lang == "mermaid":
                blocks.append({"type": "mermaid", "src": "\n".join(body)})
            else:
                blocks.append({"type": "code", "lines": body})
            continue

        # titres
        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            level = len(m.group(1))
            blocks.append({"type": "heading", "level": level,
                           "text": m.group(2).strip()})
            i += 1
            continue

        # blockquote (potentiellement multi-ligne, peut contenir une table)
        if stripped.startswith(">"):
            quote_lines: list[str] = []
            while i < n and lines[i].strip().startswith(">"):
                content = lines[i].strip()[1:]
                if content.startswith(" "):
                    content = content[1:]
                quote_lines.append(content)
                i += 1
            blocks.append({"type": "quote", "lines": quote_lines})
            continue

        # image seule
        m = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)\s*$", stripped)
        if m:
            blocks.append({"type": "image", "alt": m.group(1),
                           "path": m.group(2)})
            i += 1
            continue

        # table GFM (entete + separateur)
        if _is_table_row(line) and i + 1 < n and _is_table_sep(lines[i + 1]):
            headers = _split_table_row(line)
            i += 2  # entete + separateur
            rows: list[list[str]] = []
            while i < n and _is_table_row(lines[i]):
                rows.append(_split_table_row(lines[i]))
                i += 1
            blocks.append({"type": "table", "headers": headers, "rows": rows})
            continue

        # liste a puces
        m = re.match(r"^(\s*)[-*]\s+(.*)$", line)
        if m:
            items: list[tuple[int, str]] = []
            while i < n:
                mm = re.match(r"^(\s*)[-*]\s+(.*)$", lines[i])
                if not mm:
                    # ligne de continuation indentee d'un item ?
                    if lines[i].strip() and re.match(r"^\s+\S", lines[i]) \
                            and items:
                        items[-1] = (items[-1][0],
                                     items[-1][1] + " " + lines[i].strip())
                        i += 1
                        continue
                    break
                indent = len(mm.group(1))
                level = indent // 2
                items.append((level, mm.group(2).strip()))
                i += 1
            blocks.append({"type": "ulist", "items": items})
            continue

        # liste numerotee
        m = re.match(r"^(\s*)\d+\.\s+(.*)$", line)
        if m:
            items2: list[str] = []
            while i < n:
                mm = re.match(r"^(\s*)\d+\.\s+(.*)$", lines[i])
                if not mm:
                    if lines[i].strip() and re.match(r"^\s+\S", lines[i]) \
                            and items2:
                        items2[-1] = items2[-1] + " " + lines[i].strip()
                        i += 1
                        continue
                    break
                items2.append(mm.group(2).strip())
                i += 1
            blocks.append({"type": "olist", "items": items2})
            continue

        # paragraphe (regroupe les lignes consecutives non vides "normales")
        para_lines = [stripped]
        i += 1
        while i < n:
            nxt = lines[i]
            ns = nxt.strip()
            if not ns:
                break
            if (ns.startswith("#") or ns.startswith(">") or ns.startswith("```")
                    or ns.startswith("- ") or ns.startswith("* ")
                    or re.match(r"^\s*\d+\.\s", nxt) or _is_table_row(nxt)
                    or ns == "---"):
                break
            para_lines.append(ns)
            i += 1
        blocks.append({"type": "para", "text": " ".join(para_lines)})

    return blocks


# ---------------------------------------------------------------------------
# Rendu des blocs -> docx
# ---------------------------------------------------------------------------

# Largeurs de colonnes (mm) par nombre de colonnes — total ~170 (page A4 - marges)
_DEFAULT_WIDTHS = {
    2: [62, 108],
    3: [55, 50, 65],
    4: [45, 30, 50, 45],
}

_LANG_TO_FIRST_LINE = {
    "bash": None, "sh": None, "powershell": None, "ps1": None,
    "text": None, "ini": None, "dockerfile": None, "yaml": None,
    "yml": None, "json": None, "": None,
}

_MERMAID_CAPTIONS = {
    0: ("Topologie cote eleve : ton navigateur passe par le coach (sidecar), "
        "qui transmet a l'app OWASP, interroge Ollama (juge + indices) et, en "
        "cohorte, remonte tes events au dashboard du prof."),
}


def _render_quote(doc: Document, qlines: list[str]) -> None:
    """Un blockquote -> note(s). Si une table GFM y est presente, elle est
    rendue apres la note avec son texte de callout."""
    # separer la partie table de la partie texte
    text_lines: list[str] = []
    tbl_header: list[str] | None = None
    tbl_rows: list[list[str]] = []
    j = 0
    while j < len(qlines):
        ln = qlines[j]
        if _is_table_row(ln) and j + 1 < len(qlines) and _is_table_sep(qlines[j + 1]):
            tbl_header = _split_table_row(ln)
            j += 2
            while j < len(qlines) and _is_table_row(qlines[j]):
                tbl_rows.append(_split_table_row(qlines[j]))
                j += 1
            continue
        text_lines.append(ln)
        j += 1

    # regrouper le texte du callout : lignes consecutives -> un seul note box,
    # mais les puces / listes numerotees deviennent des lignes propres.
    buf: list[str] = []

    def flush_buf():
        if buf:
            txt = " ".join(s.strip() for s in buf if s.strip())
            if txt:
                note(doc, txt)
            buf.clear()

    for ln in text_lines:
        s = ln.strip()
        if not s:
            flush_buf()
            continue
        if re.match(r"^\d+\.\s", s) or s.startswith("- ") or s.startswith("* "):
            flush_buf()
            item = re.sub(r"^(\d+\.|[-*])\s+", "", s)
            note(doc, "• " + item)
        else:
            buf.append(s)
    flush_buf()

    if tbl_header is not None:
        widths = _DEFAULT_WIDTHS.get(len(tbl_header))
        add_table(doc, tbl_header, tbl_rows, widths)


def render_blocks(doc: Document, blocks: list[dict], tmp: Path) -> None:
    mermaid_idx = 0
    skipped_first_heading = False

    for blk in blocks:
        t = blk["type"]

        if t == "hr":
            continue

        if t == "heading":
            level = blk["level"]
            text = _strip_links(blk["text"])
            if level == 1 and not skipped_first_heading:
                # H1 = titre du document -> page de titre
                title_block(
                    doc, text,
                    "Installer PwnzzAI + le Coach JuiceLab sur ton poste — "
                    "Windows / macOS / Linux",
                )
                skipped_first_heading = True
                continue
            if level == 2:
                doc.add_heading(text, level=1)
            elif level >= 3:
                doc.add_heading(text, level=2)
            else:
                doc.add_heading(text, level=1)
            continue

        if t == "para":
            rich_para(doc, blk["text"])
            continue

        if t == "quote":
            # ignorer la ligne de lien de langue reciproque (Version anglaise)
            joined = " ".join(blk["lines"]).lower()
            if "version anglaise" in joined or "english version" in joined:
                continue
            _render_quote(doc, blk["lines"])
            continue

        if t == "code":
            code_block(doc, blk["lines"])
            continue

        if t == "mermaid":
            png = tmp / f"mermaid_{mermaid_idx}.png"
            ok = render_mermaid(blk["src"], png, tmp)
            caption = _MERMAID_CAPTIONS.get(
                mermaid_idx,
                "Schema d'architecture cote eleve.",
            )
            if ok:
                add_diagram(doc, png, caption)
            mermaid_idx += 1
            continue

        if t == "image":
            path = blk["path"]
            # resoudre relativement a docs/
            png = (DOCS_DIR / path).resolve()
            add_screenshot(doc, png, _strip_links(blk["alt"]) or "")
            continue

        if t == "table":
            headers = blk["headers"]
            widths = _DEFAULT_WIDTHS.get(len(headers))
            add_table(doc, headers, blk["rows"], widths)
            continue

        if t == "ulist":
            for level, item in blk["items"]:
                rich_bullet(doc, item, level=level)
            continue

        if t == "olist":
            for item in blk["items"]:
                rich_numbered(doc, item)
            continue


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main() -> int:
    if not SOURCE_MD.exists():
        sys.exit(f"Source introuvable : {SOURCE_MD}")

    print(f"Generation de {ELEVE_OUT.name} depuis {SOURCE_MD.name} ...")
    md = SOURCE_MD.read_text(encoding="utf-8")
    blocks = parse_markdown(md)

    doc = Document()
    setup_styles(doc)
    add_footer_pagenum(doc, "Coach JuiceLab pour PwnzzAI - Guide eleve")

    # tmp sous DOCS_DIR (chemin non cache) : le Chromium snap confine ne lit
    # pas les dossiers caches type ~/.nvm ou /tmp restreint.
    with tempfile.TemporaryDirectory(dir=str(DOCS_DIR)) as td:
        tmp = Path(td)
        render_blocks(doc, blocks, tmp)
        doc.save(str(ELEVE_OUT))

    print(f"  [ok] {ELEVE_OUT.name} genere "
          f"({ELEVE_OUT.stat().st_size // 1024} Ko)")
    print("Termine.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
