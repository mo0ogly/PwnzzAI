#!/usr/bin/env python3
"""Genere les guides d'installation PwnzzAI au format .docx (eleve + prof).

Decoupe le guide combine (build_coach_guide.py) en DEUX documents distribuables :

    docs/GUIDE-INSTALL-ELEVE.docx   -> eleve, AUCUN contenu prof/dashboard/admin
    docs/GUIDE-INSTALL-PROF.docx    -> prof (deploiement dashboard, events, juge)

Modeles :
    - docs/build_coach_guide.py            (helpers python-docx, palette, mermaid)
    - juice/docs/generate_install_guides.py (structure deux-documents eleve/prof)

Dependances :
    - python-docx               (pip install python-docx)
    - @mermaid-js/mermaid-cli    -> binaire `mmdc` (npm i -g @mermaid-js/mermaid-cli)
      + un Chromium/Chrome (mmdc en a besoin). Si le chromium bundle de puppeteer
      manque, exporter PUPPETEER_EXECUTABLE_PATH vers le binaire systeme.

Usage :
    python3.11 docs/build_install_guides.py

Source de verite : valeurs ci-dessous + docs/STUDENT-INSTALL-FR.md,
docker-compose.yml, .env.example et scripts/{install-student,deploy-dashboard}.*.
Si l'une change, mettre a jour ici et relancer.
"""

from __future__ import annotations

import os
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
        "(ou venv : python3 -m venv .venv && .venv/bin/pip install python-docx)."
    )

# ---------------------------------------------------------------------------
# Constantes projet (alignees sur docker-compose.yml + .env.example + scripts/)
# ---------------------------------------------------------------------------

COACH_PORT = "8095"
RAW_PORT = "8090"
DASHBOARD_PORT = "5000"
COHORT = "M2-IA-2026"
LABEL = "pwnzzai-poste-01"
JUDGE_MODEL = "llama3.2:3b"
LABS_MODEL = "llama3.2:1b"
EXAMPLE_IP = "192.168.1.10"
REPO_URL = "https://github.com/mo0ogly/PwnzzAI.git"
JUICELAB_REPO_URL = "https://github.com/mo0ogly/juicelab.git"

DOCS_DIR = Path(__file__).resolve().parent
IMG_DIR = DOCS_DIR / "img"
ELEVE_OUT = DOCS_DIR / "GUIDE-INSTALL-ELEVE.docx"
PROF_OUT = DOCS_DIR / "GUIDE-INSTALL-PROF.docx"

# Palette (identique au modele JuiceLab, teinte violette du coach pour le titre)
BLUE = RGBColor(0x2E, 0x75, 0xB6)
PURPLE = RGBColor(0x6D, 0x28, 0xD9)
DARK = RGBColor(0x22, 0x22, 0x22)
GREY_FILL = "F2F2F2"
NOTE_FILL = "FFF4D6"
HEAD_FILL = "EDE7FB"

# ---------------------------------------------------------------------------
# Rendu Mermaid -> PNG (repris de build_coach_guide.py)
# ---------------------------------------------------------------------------


def _find_mmdc() -> str:
    """Prefere le mmdc local (docs/node_modules) au mmdc global.

    Sur les distros a snap (Ubuntu), le Chromium snap ne peut pas lire les
    fichiers de mmdc s'il est installe sous un dossier cache comme ~/.nvm.
    Un mmdc installe dans ce dossier (chemin non cache) contourne le souci.
    """
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
# Helpers python-docx (repris de build_coach_guide.py)
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


def bullet(doc: Document, text: str) -> None:
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
    run = p.add_run(text)
    run.font.size = Pt(10.5)


def add_table(doc: Document, headers: list[str], rows: list[list[str]],
              widths_mm: list[int]) -> None:
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    hdr = table.rows[0].cells
    for i, h in enumerate(headers):
        hdr[i].text = ""
        run = hdr[i].paragraphs[0].add_run(h)
        run.bold = True
        run.font.size = Pt(10)
        _shade(hdr[i].paragraphs[0], HEAD_FILL)
    for row in rows:
        cells = table.add_row().cells
        for i, val in enumerate(row):
            cells[i].text = ""
            run = cells[i].paragraphs[0].add_run(val)
            run.font.size = Pt(10)
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
# Diagrammes Mermaid
# ---------------------------------------------------------------------------

MERMAID_ARCHI = """
flowchart LR
    B["Navigateur eleve<br/>:%COACH%"]
    C["pwnzzai-coach<br/>proxy + API"]
    P["pwnzzai-app<br/>:8080 (OWASP intact)"]
    O["ollama"]
    D["Dashboard prof<br/>:%DASH%"]
    B -->|"toutes les requetes"| C
    C -->|"transmises telles quelles"| P
    C -->|"juge + indices"| O
    C -->|"evenements cohorte"| D
    C -. "injecte coach.js" .-> B
""".replace("%COACH%", COACH_PORT).replace("%DASH%", DASHBOARD_PORT)

MERMAID_SEQUENCE = """
sequenceDiagram
    autonumber
    participant E as Eleve
    participant A as Assistant vulnerable
    participant C as coach
    participant O as Ollama (juge)
    participant D as Dashboard prof
    E->>A: prompts d'attaque
    A-->>E: reponses
    Note over E: coach.js capture la conversation
    E->>C: POST /__coach/judge {transcript}
    C->>O: prompt + few-shot + transcript
    O-->>C: VERDICT / SCORE / REASON
    C-->>E: {success, score, reason}
    E->>C: POST /__coach/event (si reussi)
    C->>D: POST /api/sync
"""


# ---------------------------------------------------------------------------
# Sections partagees (DRY) entre eleve et prof
# ---------------------------------------------------------------------------


def section_prerequis(doc: Document) -> None:
    """Prerequis Docker / Compose / Git / RAM — commun eleve et prof."""
    add_table(
        doc, ["Outil", "Version minimum", "Note"],
        [
            ["Docker Desktop (Win/macOS) ou Docker Engine (Linux)", "24+",
             "docker.com"],
            ["Docker Compose v2", "livre avec Docker Desktop",
             "Linux : voir Annexe Docker"],
            ["Git", "version recente", "git-scm.com"],
            ["RAM", "8 Go libres conseilles",
             "Ollama charge le modele du juge en memoire"],
            ["Disque", "6 Go libres", "image PwnzzAI + modeles Ollama"],
        ],
        [70, 45, 55],
    )
    para(doc, "Sanity check rapide :")
    code_block(doc, [
        "docker --version            # 24.x ou plus",
        "docker compose version      # v2.x ou plus",
        "git --version",
    ])
    note(doc, "Si docker compose version echoue, Docker est trop vieux. "
              "Linux : sudo apt install docker-compose-v2 (ou docker-compose-plugin). "
              "Windows / macOS : mettre a jour Docker Desktop.")


def annexe_docker(doc: Document) -> None:
    """Annexe commune : installer Docker + Compose par OS. Appendue aux 2 docs."""
    doc.add_page_break()
    doc.add_heading("Annexe — Installer Docker et Docker Compose", level=1)
    para(doc, "A faire UNE fois par poste, avant la procedure d'installation.")

    doc.add_heading("Windows 10/11", level=2)
    numbered(doc, "Active WSL2 (PowerShell en administrateur), puis redemarre :")
    code_block(doc, ["wsl --install"])
    numbered(doc, "Installe Docker Desktop depuis docker.com (backend WSL2 par defaut).")
    numbered(doc, "Lance Docker Desktop et attends le statut « running ».")
    numbered(doc, "Verifie dans un terminal :")
    code_block(doc, ["docker run --rm hello-world", "docker compose version"])
    note(doc, "Erreur de virtualisation : active « Virtualization / SVM / VT-x » "
              "dans le BIOS/UEFI et la fonctionnalite Windows « Plateforme de "
              "machine virtuelle ». PowerShell 7+ (commande pwsh) est requis pour "
              "les scripts .ps1 ; Windows 10 a PowerShell 5.1 par defaut, trop vieux.")

    doc.add_heading("macOS", level=2)
    numbered(doc, "Telecharge Docker Desktop pour Mac (Apple Silicon ou Intel).")
    numbered(doc, "Glisse Docker dans Applications, lance-le, attends « running ».")
    numbered(doc, "Verifie :")
    code_block(doc, ["docker run --rm hello-world", "docker compose version"])
    note(doc, "Apple Silicon (M1/M2/M3) : l'image se construit en natif arm64, "
              "aucune manipulation Rosetta requise (premier build un peu plus long).")

    doc.add_heading("Linux (Debian / Ubuntu)", level=2)
    para(doc, "Deux methodes mutuellement exclusives. Choisis l'une OU l'autre.")
    para(doc, "Methode A — paquets de la distribution (recommandee pour un TD) :")
    code_block(doc, [
        "sudo apt update",
        "sudo apt install -y docker-compose-v2",
        "sudo usermod -aG docker $USER",
        "newgrp docker   # ou se deconnecter puis se reconnecter",
        "docker compose version",
    ])
    para(doc, "Methode B — depot officiel Docker (derniere version) :")
    code_block(doc, [
        "# configurer le depot : https://docs.docker.com/engine/install/ubuntu/",
        "sudo apt install -y docker-ce docker-ce-cli containerd.io \\",
        "    docker-buildx-plugin docker-compose-plugin",
        "sudo usermod -aG docker $USER",
        "newgrp docker",
        "docker compose version",
    ])
    note(doc, "Les deux paquets sont mutuellement exclusifs. Sur Ubuntu 25.04+, "
              "utilise la methode A (docker-compose-v2). Ne melange jamais les deux.")
    note(doc, "arm64 (Apple Silicon / Snapdragon) : si un build echoue avec "
              "« E: Dynamic MMap ran out of room », c'est le cache APT. Le "
              "Dockerfile du projet integre deja le correctif "
              "(APT::Cache-Start \"100663296\").")


# ---------------------------------------------------------------------------
# Document ELEVE  (AUCUN contenu prof / dashboard-deploy / events / juge)
# ---------------------------------------------------------------------------


def build_eleve(tmp: Path) -> None:
    doc = Document()
    setup_styles(doc)
    add_footer_pagenum(doc, "Coach JuiceLab pour PwnzzAI - Guide eleve")
    title_block(
        doc, "Coach JuiceLab pour PwnzzAI — Guide eleve",
        "Installer PwnzzAI + le coach sur ton poste — Windows / macOS / Linux",
    )

    doc.add_heading("1. Ce qui sera installe", level=1)
    para(doc, "PwnzzAI (la pizza shop OWASP volontairement vulnerable pour "
              "apprendre la securite des LLM) tourne comme une seule stack docker "
              "compose sur ton poste. Le Coach JuiceLab ajoute par-dessus une "
              "sidebar pedagogique (briefing, indices gradues, journal, quiz, "
              "juge automatique, badges) sans modifier le produit OWASP.")
    add_table(
        doc, ["Conteneur", "Port hote", "Role"],
        [
            ["pwnzzai-coach", COACH_PORT + " -> 8090",
             "Entree eleve : proxy + panneau coach"],
            ["pwnzzai-shop", RAW_PORT + " -> 8080",
             "PwnzzAI brut OWASP (intact, pour debug)"],
            ["ollama", "interne",
             "LLM local : modele des labs + modele du juge/indices"],
        ],
        [42, 35, 93],
    )
    note(doc, "Tu utilises uniquement http://localhost:" + COACH_PORT +
              " (le coach). Le port " + RAW_PORT + " reste disponible pour "
              "deboguer PwnzzAI sans le coach. Les trois conteneurs tournent "
              "quel que soit ton mode (cohorte ou solo).")

    png_archi = tmp / "archi.png"
    render_mermaid(MERMAID_ARCHI, png_archi, tmp)
    add_diagram(doc, png_archi, "Le coach est un sidecar place devant PwnzzAI ; "
                                "il transmet tes requetes a l'app, interroge "
                                "Ollama (juge/indices) et, en cohorte, remonte "
                                "tes events au dashboard du prof.")

    doc.add_heading("2. Choisis ton mode AVANT d'installer", level=1)
    para(doc, "Deux modes. La seule difference est la remontee de ta progression "
              "vers le dashboard du prof. La stack lancee chez toi est identique "
              "(3 conteneurs) ; seule la cle JUICELAB_DASHBOARD_URL change.")
    add_table(
        doc, ["Ta situation", "Mode", "Remontee", "Dashboard ?"],
        [
            ["TD avec un enseignant (cas normal)", "Cohorte",
             "Events vers le dashboard du prof",
             "NON — c'est le prof qui l'heberge"],
            ["Seul, sans prof (revision)", "Solo",
             "Aucune remontee",
             "NON — le coach marche en local"],
        ],
        [50, 22, 50, 48],
    )
    note(doc, "ERREUR FREQUENTE A EVITER. Dans AUCUN mode tu n'installes de "
              "dashboard sur ton poste. PwnzzAI n'embarque aucun dashboard eleve. "
              "En TD, c'est le prof qui heberge l'unique dashboard central ; toi, "
              "tu te contentes de pointer dessus avec -d <ip-prof>. En solo, il "
              "n'y a tout simplement pas de reporting.")

    doc.add_heading("3. Prerequis", level=1)
    section_prerequis(doc)
    note(doc, "RAM / Ollama : le modele du juge par defaut (" + JUDGE_MODEL +
              ") tient dans ~3-4 Go de RAM. Ne descends pas a 1b pour le juge "
              "(verdicts non fiables).")

    doc.add_heading("4. Installation en une commande", level=1)
    para(doc, "Meme flux sur Linux, macOS et Windows. Cloner d'abord :")
    code_block(doc, [
        "git clone " + REPO_URL,
        "cd PwnzzAI",
    ])
    para(doc, "Remplace " + COHORT + " par l'identifiant de cohorte donne par "
              "ton enseignant, et " + EXAMPLE_IP + " par l'IP du dashboard prof "
              "qu'il t'a communiquee.")

    doc.add_heading("Mode cohorte — TD avec un enseignant (recommande)", level=2)
    para(doc, "Stack complete, events pousses vers le dashboard du prof. "
              "Tu n'installes PAS de dashboard.")
    code_block(doc, [
        "# Linux / macOS",
        "./scripts/install-student.sh -c " + COHORT + " -d " + EXAMPLE_IP,
    ])
    code_block(doc, [
        "# Windows PowerShell 7+",
        ".\\scripts\\install-student.ps1 -Cohort " + COHORT +
        " -Dashboard " + EXAMPLE_IP,
    ])
    note(doc, "Port du dashboard prof : defaut " + DASHBOARD_PORT + ". La valeur "
              "de -d accepte 192.168.1.10 (-> http://192.168.1.10:" + DASHBOARD_PORT +
              "), 192.168.1.10:5050 (port explicite) ou une URL complete.")

    doc.add_heading("Mode solo — sans prof (autonomie)", level=2)
    para(doc, "La MEME stack complete, mais sans remontee "
              "(JUICELAB_DASHBOARD_URL reste vide). Indices, juge, quiz et badges "
              "fonctionnent quand meme en local.")
    code_block(doc, [
        "# Linux / macOS",
        "./scripts/install-student.sh -c " + COHORT,
    ])
    code_block(doc, [
        "# Windows PowerShell 7+",
        ".\\scripts\\install-student.ps1 -Cohort " + COHORT,
    ])
    note(doc, "Si le script bash n'est pas executable : chmod +x "
              "scripts/install-student.sh. Si PowerShell bloque les scripts, "
              "lance une fois : Set-ExecutionPolicy -Scope CurrentUser "
              "-ExecutionPolicy RemoteSigned. PowerShell 7+ est requis "
              "(Windows 10 a la 5.1 par defaut, trop vieille).")

    doc.add_heading("Ce que fait l'installeur", level=2)
    numbered(doc, "Verifie que Docker et Docker Compose sont disponibles.")
    numbered(doc, "Cree la racine .env depuis .env.example si elle manque.")
    numbered(doc, "Ecrit les cles JUICELAB_* : JUICELAB_COHORT_ID (selon -c), "
                  "JUICELAB_INSTANCE_LABEL (selon -l ou le nom de la machine), "
                  "JUICELAB_DASHBOARD_URL (renseigne en cohorte via -d, vide en solo).")
    numbered(doc, "Lance la stack complete : docker compose up -d --build (3 conteneurs).")
    numbered(doc, "Tire les modeles Ollama (scripts/pull-models.sh : juge puis labs).")
    numbered(doc, "Attend que le coach reponde sur /__coach/health, puis affiche les URLs.")
    note(doc, "Premier build : 5 a 8 min (clone + build de l'image PwnzzAI) puis "
              "~2-3 Go de modeles Ollama. C'est normal et ca n'arrive qu'une fois. "
              "L'installeur est idempotent (le relancer ne casse rien). Reinstall "
              "propre : --reset (bash) ou -Reset (PowerShell).")

    doc.add_heading("5. Verifier l'installation", level=1)
    add_table(
        doc, ["URL", "Attendu"],
        [
            ["http://localhost:" + COACH_PORT,
             "PwnzzAI via le coach (entree eleve). Bouton rond violet « JL » "
             "en bas a droite."],
            ["http://localhost:" + RAW_PORT,
             "PwnzzAI brut OWASP (sans coach, pour debug)."],
            ["http://localhost:" + COACH_PORT + "/__coach/health",
             'JSON {"ok":true,"ollama":true,"dashboard_configured":...}'],
        ],
        [62, 108],
    )
    code_block(doc, [
        "curl -s http://localhost:" + COACH_PORT + "/__coach/health",
        '# {"ok":true,"ollama":true,"dashboard_configured":true}',
    ])
    bullet(doc, "ollama:true -> un modele de juge est tire et disponible (sinon § 7).")
    bullet(doc, "dashboard_configured:true -> remontee activee (cohorte). En solo "
                "c'est false, et c'est NORMAL.")
    note(doc, "Le panneau coach est FERME au depart, il n'apparait pas tout seul. "
              "Pour l'ouvrir : (1) clique le bouton rond violet « JL » en bas a "
              "droite, OU (2) ajoute #coach a la fin de l'URL d'un lab (ex. "
              "http://localhost:" + COACH_PORT + "/direct-prompt-injection#coach). "
              "Verifie d'etre sur le port " + COACH_PORT + " (le coach), pas " +
              RAW_PORT + ". Si rien n'apparait : Ctrl+Shift+R.")
    add_screenshot(doc, IMG_DIR / "coach-closed.png",
                   "Le bouton « JL » ferme, en bas a droite de la page du lab.")
    add_screenshot(doc, IMG_DIR / "coach-panel.png",
                   "Le panneau ouvert : onglets Briefing / Indices / Journal / "
                   "Quiz / Progression.")

    doc.add_heading("Smoke test bout-en-bout", level=2)
    numbered(doc, "Ouvre http://localhost:" + COACH_PORT +
                  " et cree un compte / connecte-toi dans PwnzzAI.")
    numbered(doc, "Va sur un lab (ex. Direct Prompt Injection).")
    numbered(doc, "Clique « JL » : le panneau coach a onglets s'ouvre (bouton FR/EN).")
    numbered(doc, "Onglet Indices : revele l'indice N1 (cout -5 %). Le texte "
                  "s'affiche (genere par le LLM local). « Service coach "
                  "indisponible (Ollama) » -> modeles non tires (§ 7).")
    numbered(doc, "Attaque l'assistant (la conversation est capturee), puis "
                  "Progression -> Verifier ma reussite : le juge rend Reussi / "
                  "Partiel / Pas encore + score + justification.")
    add_screenshot(doc, IMG_DIR / "coach-hints.png",
                   "Onglet Indices : 5 niveaux gradues N1-N5, cout -5/-10/-20/-35/-50 %.")
    add_screenshot(doc, IMG_DIR / "coach-progress.png",
                   "Onglet Progression : score par lab, score moyen, badges, "
                   "rejoindre une cohorte.")
    note(doc, "Scoring : score = max(50, 100 - somme des couts d'indices). "
              "Ta progression (jeton, scores, indices, journaux, quiz, badges) "
              "est stockee cote navigateur (localStorage, cle pwnzzai_coach_v1) "
              "et survit aux redemarrages de conteneurs.")

    doc.add_heading("6. Utilisation au quotidien", level=1)
    para(doc, "La stack survit aux reboots ; pas besoin de relancer l'installeur. "
              "Le plus simple est le launcher pwnzzai.sh (Linux/macOS) ou "
              "pwnzzai.ps1 (Windows) :")
    code_block(doc, [
        "./pwnzzai.sh up         # demarre / reprend la stack (build + up -d)",
        "./pwnzzai.sh down       # arrete (conserve les volumes)",
        "./pwnzzai.sh restart    # down puis up",
        "./pwnzzai.sh status     # docker compose ps",
        "./pwnzzai.sh logs       # logs en direct (coach|app|ollama|all)",
        "./pwnzzai.sh health     # ping coach (JSON) + brut (code HTTP)",
        "./pwnzzai.sh models     # (re)tire les modeles Ollama",
        "./pwnzzai.sh wipe       # DESTRUCTIF : down -v (supprime ollama_data)",
    ])
    code_block(doc, [
        "# Windows PowerShell 7+",
        ".\\pwnzzai.ps1 up | down | restart | status | logs | health | models | wipe",
    ])

    doc.add_heading("7. Depannage", level=1)
    add_table(
        doc, ["Symptome", "Cause / solution"],
        [
            ["Indice ou « Verifier » dit « Service coach indisponible (Ollama) »",
             "Modeles Ollama pas tires (volume neuf). Lance ./pwnzzai.sh models, "
             "puis verifie \"ollama\":true sur /__coach/health."],
            ["health renvoie \"ollama\":false",
             "Aucun modele de juge. ./pwnzzai.sh models. Verifie que le conteneur "
             "ollama tourne et COACH_JUDGE_MODEL (defaut " + JUDGE_MODEL + ")."],
            ["Port " + RAW_PORT + " ou " + COACH_PORT + " deja utilise",
             "Une autre appli squatte le port. Change le mapping hote dans "
             "docker-compose.yml puis ./pwnzzai.sh restart."],
            ["docker compose: command not found",
             "Docker trop vieux / plugin manquant. Linux : sudo apt install "
             "docker-compose-v2. Windows/macOS : mettre a jour Docker Desktop."],
            ["permission denied sur le script (Linux/macOS)",
             "chmod +x scripts/install-student.sh ; chmod +x pwnzzai.sh"],
            ["PowerShell : « l'execution de scripts est desactivee »",
             "Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy "
             "RemoteSigned. PowerShell 7+ requis."],
            ["« Dashboard prof injoignable » (mode cohorte)",
             "NORMAL cote eleve : c'est cote prof / reseau que ca se regle. Pas "
             "de dashboard local a corriger. Rappelle au prof l'IP attendue "
             "(-d <ip-prof>). L'install reste reussie."],
            ["dashboard_configured:false alors que je suis en cohorte",
             "JUICELAB_DASHBOARD_URL vide. Relance avec -d <ip-prof>. En solo, "
             "false est attendu."],
        ],
        [62, 108],
    )

    doc.add_heading("8. Desinstaller", level=1)
    code_block(doc, [
        "./pwnzzai.sh wipe              # down -v : arret + suppression des volumes",
        "cd .. && rm -rf PwnzzAI        # suppression du repo clone",
        "docker image prune            # optionnel, libere du disque",
    ])
    note(doc, "wipe / down -v supprime le volume ollama_data : tous les modeles "
              "tires sont perdus (re-telechargement au prochain up + models).")

    annexe_docker(doc)
    doc.save(str(ELEVE_OUT))
    print(f"  [ok] {ELEVE_OUT.name} genere ({ELEVE_OUT.stat().st_size // 1024} Ko)")


# ---------------------------------------------------------------------------
# Document PROF
# ---------------------------------------------------------------------------


def build_prof(tmp: Path) -> None:
    doc = Document()
    setup_styles(doc)
    add_footer_pagenum(doc, "Coach JuiceLab pour PwnzzAI - Guide prof")
    title_block(
        doc, "Coach JuiceLab pour PwnzzAI — Guide prof",
        "Cohorte PwnzzAI + dashboard central JuiceLab — Windows / macOS / Linux",
    )

    doc.add_heading("1. Ton role et la topologie", level=1)
    para(doc, "Chaque eleve fait tourner la stack PwnzzAI complete (coach + app + "
              "ollama) sur son propre poste. Pendant qu'ils jouent, leurs postes "
              "poussent les events de progression vers UN dashboard central unique. "
              "Tu obtiens une matrice de cohorte (eleves x labs) en temps reel.")
    note(doc, "Le dashboard est central et PARTAGE : une seule instance sert a la "
              "fois les cohortes JuiceLab (Juice Shop) ET les cohortes PwnzzAI — "
              "les deux remontent dans la meme matrice. PwnzzAI ne duplique JAMAIS "
              "le code serveur du dashboard ; il s'y branche comme client via "
              "JUICELAB_DASHBOARD_URL. Anti-pattern a proscrire : deployer un "
              "second dashboard specifique a PwnzzAI.")
    note(doc, "Les eleves ne lancent JAMAIS le dashboard et n'ouvrent jamais son "
              "interface : ils se contentent de pointer dessus avec -d <ip-prof>. "
              "Le deploiement du dashboard (section 4) est exclusivement cote prof.")

    png_archi = tmp / "archi_prof.png"
    render_mermaid(MERMAID_ARCHI, png_archi, tmp)
    add_diagram(doc, png_archi, "Chaque poste eleve : coach -> app/ollama, et "
                                "remontee des events vers le dashboard central.")

    doc.add_heading("2. Prerequis", level=1)
    section_prerequis(doc)
    note(doc, "Le dashboard est leger. Il doit etre joignable par les eleves : "
              "LAN plat et port " + DASHBOARD_PORT + " ouvert dans le pare-feu.")

    doc.add_heading("3. Preparer la cohorte", level=1)
    para(doc, "Choisis un identifiant de cohorte (JUICELAB_COHORT_ID) qui "
              "regroupera les eleves dans la matrice, ex. " + COHORT + ". Distribue "
              "ensuite a chaque eleve DEUX informations :")
    add_table(
        doc, ["A distribuer", "Exemple", "Role"],
        [
            ["Identifiant de cohorte", COHORT,
             "Regroupe la classe (cle -c des eleves)"],
            ["IP/URL du dashboard prof", EXAMPLE_IP,
             "Ou les postes eleves poussent leur progression (cle -d des eleves)"],
        ],
        [50, 45, 75],
    )
    para(doc, "La commande exacte que chaque eleve lance (mode cohorte) :")
    code_block(doc, [
        "# Linux / macOS",
        "./scripts/install-student.sh -c " + COHORT + " -d " + EXAMPLE_IP +
        " -l <prenom>",
        "",
        "# Windows PowerShell 7+",
        ".\\scripts\\install-student.ps1 -Cohort " + COHORT +
        " -Dashboard " + EXAMPLE_IP + " -Label <prenom>",
    ])
    note(doc, "Donne a chaque eleve un label (-l / -Label) unique (ex. son "
              "prenom), sinon deux postes se confondent dans la matrice. Le port "
              "du dashboard est " + DASHBOARD_PORT + " par defaut ; precise "
              "<ip>:<port> si tu en utilises un autre.")

    doc.add_heading("4. Deployer le dashboard central (PROF UNIQUEMENT)", level=1)
    note(doc, "Cette section est reservee au prof. Les eleves ne lancent JAMAIS "
              "ce script : ils n'ont pas de dashboard a deployer.")
    para(doc, "Cas le plus courant : un dashboard central existe deja (instance "
              "JuiceLab partagee). Tu n'as alors qu'a communiquer son IP/URL aux "
              "eleves (section 3). Si le dashboard n'existe pas encore et que tu "
              "veux le deployer DEPUIS cette machine, le script "
              "scripts/deploy-dashboard.sh fait un sparse-checkout pinne du depot "
              "juicelab et ne tire QUE la partie prof (dashboard/, docker/, "
              "scripts/) — l'overlay et le Juice Shop eleve ne sont jamais tires.")
    code_block(doc, [
        "# Linux / macOS",
        "./scripts/deploy-dashboard.sh",
        "",
        "# Windows PowerShell 7+",
        ".\\scripts\\deploy-dashboard.ps1",
    ])
    para(doc, "Le deploiement lit ces cles du .env de PwnzzAI :")
    add_table(
        doc, ["Variable", "Role", "Defaut"],
        [
            ["JUICELAB_REPO_URL", "Depot juicelab (source de la partie prof)",
             JUICELAB_REPO_URL],
            ["JUICELAB_DASHBOARD_REF", "Ref tiree (SHA conseille en prod)", "main"],
        ],
        [60, 65, 65],
    )
    para(doc, "Une fois le dashboard demarre, pointe JUICELAB_DASHBOARD_URL "
              "dessus (cote eleve, c'est la valeur de -d) :")
    add_table(
        doc, ["Variable (.env eleve)", "Role", "Exemple"],
        [
            ["JUICELAB_DASHBOARD_URL",
             "URL du dashboard vue depuis le conteneur",
             "http://host.docker.internal:" + DASHBOARD_PORT],
            ["JUICELAB_COHORT_ID", "Identifiant de la promo", COHORT],
            ["JUICELAB_INSTANCE_LABEL", "Nom du poste eleve dans la matrice", LABEL],
        ],
        [60, 60, 70],
    )
    note(doc, "Dashboard sur la meme machine que le coach : utiliser "
              "host.docker.internal (et non 127.0.0.1). Dashboard distant : l'IP "
              "du prof. Le dashboard enregistre l'eleve automatiquement au premier "
              "evenement.")
    add_screenshot(doc, IMG_DIR / "prof-dashboard-light.png",
                   "Tableau de bord prof - cohorte PwnzzAI sur l'instance "
                   "centrale (theme clair).")
    add_screenshot(doc, IMG_DIR / "prof-dashboard-dark.png",
                   "Meme matrice en theme sombre (bascule via la topbar).")

    doc.add_heading("5. Ce qui remonte : les evenements", level=1)
    para(doc, "Le coach envoie ces evenements via le contrat public POST "
              "/api/sync (le meme que Juice Shop) :")
    add_table(
        doc, ["Evenement", "Declencheur", "Donnees"],
        [
            ["session_start", "ouverture d'une page lab", "chemin, identite si detectee"],
            ["hint_revealed", "revelation d'un indice", "niveau N1-N5, cout, score"],
            ["challenge_solved", "juge -> Reussi", "score, verdict, justification"],
            ["journal_filled", "Journal apres enregistre", "longueur, texte"],
            ["quiz_completed", "validation du quiz", "score, bonnes / total"],
            ["badge_earned", "badge debloque", "identifiant du badge"],
        ],
        [45, 60, 65],
    )

    png_seq = tmp / "sequence.png"
    render_mermaid(MERMAID_SEQUENCE, png_seq, tmp)
    add_diagram(doc, png_seq, "Du transcript au verdict du juge, puis remontee "
                              "au dashboard si reussi.")

    doc.add_heading("6. Choisir le modele du juge", level=1)
    add_table(
        doc, ["Modele", "Verdict", "Recommandation"],
        [
            ["llama3.2:1b", "non fiable (incoherent)", "a eviter pour le juge"],
            ["llama3.2:3b", "fiable sur cas nets", "minimum conseille"],
            ["mistral:7b / llama3.1:8b", "fiable sur cas subtils",
             "ideal si la machine suit"],
        ],
        [50, 60, 60],
    )
    note(doc, "Le modele du juge est independant de celui des labs : labs en 1b "
              "(rapide, " + LABS_MODEL + ") et juge en 3b (fiable, " + JUDGE_MODEL +
              ") sur la meme machine. Regle par COACH_JUDGE_MODEL dans .env.")

    doc.add_heading("7. Teardown", level=1)
    para(doc, "Cote eleve (arret de la stack PwnzzAI sur son poste) :")
    code_block(doc, [
        "./pwnzzai.sh down             # arret (conserve les volumes)",
        "./pwnzzai.sh wipe             # down -v : arret + suppression des volumes",
    ])
    para(doc, "Cote dashboard central deploye depuis cette machine "
              "(dans le repertoire de deploiement, .juicelab-dashboard/docker) :")
    code_block(doc, [
        "docker compose --env-file .env down       # arret du dashboard",
        "docker compose --env-file .env down -v    # arret + efface les donnees cohorte",
    ])
    note(doc, "down -v cote dashboard efface la base SQLite (toute la progression "
              "cohorte). Recupere les preuves avant si besoin.")

    annexe_docker(doc)
    doc.save(str(PROF_OUT))
    print(f"  [ok] {PROF_OUT.name} genere ({PROF_OUT.stat().st_size // 1024} Ko)")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main() -> int:
    print("Generation des guides d'installation PwnzzAI (eleve + prof)...")
    # tmp sous DOCS_DIR (chemin non cache) : le Chromium snap, confine, ne lit
    # pas les dossiers caches type ~/.nvm ou /tmp restreint.
    with tempfile.TemporaryDirectory(dir=str(DOCS_DIR)) as td:
        tmp = Path(td)
        build_eleve(tmp)
        build_prof(tmp)
    print("Termine.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
