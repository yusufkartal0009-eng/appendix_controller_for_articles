#!/usr/bin/env python3
"""Generates the official application cover banner and publication-grade academic

Introduction section as a styled Microsoft Word document (.docx).
"""

from __future__ import annotations

import os
from pathlib import Path
from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Inches, Pt, RGBColor
from PIL import Image, ImageDraw, ImageFont


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"
ASSETS_DIR = DOCS_DIR / "assets"
BANNER_PATH = ASSETS_DIR / "repro_radar_banner.png"
DOCX_PATH = DOCS_DIR / "repro_radar_introduction.docx"


def generate_cover_banner() -> Path:
    """Generate a high-resolution, modern dark-mode application cover banner."""
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    width, height = 1200, 420
    img = Image.new("RGBA", (width, height), (13, 17, 23, 255))  # GitHub Dark Canvas
    draw = ImageDraw.Draw(img)

    # Draw subtle background grid and radar concentric arcs
    center_x, center_y = 1000, 210
    grid_color = (30, 41, 59, 120)
    radar_color = (38, 166, 154, 40)

    # Grid lines
    for x in range(0, width, 50):
        draw.line([(x, 0), (x, height)], fill=grid_color, width=1)
    for y in range(0, height, 50):
        draw.line([(0, y), (width, y)], fill=grid_color, width=1)

    # Concentric radar rings
    for r in [60, 120, 180, 240, 300, 380]:
        draw.ellipse(
            [center_x - r, center_y - r, center_x + r, center_y + r],
            outline=radar_color,
            width=2,
        )

    # Radar sweep line
    draw.line([(center_x, center_y), (center_x - 220, center_y - 120)], fill=(56, 189, 248, 80), width=2)
    draw.line([(center_x, center_y), (center_x - 180, center_y + 150)], fill=(56, 189, 248, 60), width=2)

    # Gradient glow accent bar on the left
    for i in range(8):
        glow_color = (59, 130, 246, 255 - i * 30)
        draw.line([(0, i), (width, i)], fill=glow_color, width=1)
        draw.line([(0, height - 1 - i), (width, height - 1 - i)], fill=(16, 185, 129, 255 - i * 30), width=1)

    # Left accent vertical band
    draw.rectangle([0, 0, 12, height], fill=(59, 130, 246, 255))

    # Text rendering with fallback font
    title_text = "REPRO RADAR"
    subtitle_text = "Container-Isolated Reproducibility Checks for Paper Code"
    mission_text = "DRAFT - pilot study on tabular ML benchmarks"

    # Draw Title
    draw.text((60, 90), title_text, fill=(240, 246, 252), font_size=56)
    # Draw Subtitle
    draw.text((64, 175), subtitle_text, fill=(56, 189, 248), font_size=22)
    # Draw Mission Statement
    draw.text((64, 220), mission_text, fill=(148, 163, 184), font_size=18)

    # Draw Badge Pills
    badges = [
        ("4-Tier Scoring Rubric", (30, 58, 138), (147, 197, 253)),
        ("Isolated Docker Sandbox", (6, 78, 59), (110, 231, 183)),
        ("Multi-Seed Variance Engine", (88, 28, 135), (216, 180, 254)),
        ("Corpus Verification", (124, 45, 18), (253, 186, 116)),
    ]

    badge_x = 64
    badge_y = 300
    for text, bg_color, text_color in badges:
        padding_h = 16
        pill_width = len(text) * 9 + padding_h * 2
        pill_height = 34
        # Draw rounded rectangle
        draw.rounded_rectangle(
            [badge_x, badge_y, badge_x + pill_width, badge_y + pill_height],
            radius=8,
            fill=bg_color,
            outline=text_color,
            width=1,
        )
        draw.text((badge_x + padding_h, badge_y + 8), text, fill=text_color, font_size=13)
        badge_x += pill_width + 16

    img.save(BANNER_PATH, "PNG")
    print(f"Cover banner saved to: {BANNER_PATH}")
    return BANNER_PATH


def set_cell_background(cell, fill_hex: str):
    """Set the background color of a Word table cell."""
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tc_pr.append(shd)


def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    """Set cell internal padding in twips (1 pt = 20 twips)."""
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_mar = parse_xml(
        f'<w:tcMar {nsdecls("w")}>'
        f'  <w:top w:w="{top}" w:type="dxa"/>'
        f'  <w:left w:w="{left}" w:type="dxa"/>'
        f'  <w:bottom w:w="{bottom}" w:type="dxa"/>'
        f'  <w:right w:w="{right}" w:type="dxa"/>'
        f'</w:tcMar>'
    )
    tc_pr.append(tc_mar)


def add_styled_heading(doc: Document, text: str, level: int, space_before: int = 18, space_after: int = 6):
    """Add a formally styled academic heading."""
    h = doc.add_heading(text, level=level)
    h.paragraph_format.space_before = Pt(space_before)
    h.paragraph_format.space_after = Pt(space_after)
    h.paragraph_format.keep_with_next = True

    # Heading color schemes
    color_map = {
        1: RGBColor(26, 54, 93),   # Navy
        2: RGBColor(43, 108, 176),  # Slate Blue
        3: RGBColor(45, 55, 72),   # Dark Charcoal
    }
    for run in h.runs:
        run.font.color.rgb = color_map.get(level, RGBColor(0, 0, 0))
        run.font.name = "Calibri"
    return h


def add_callout(doc: Document, title: str, text: str):
    """Add a styled callout box with a colored left accent border."""
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False
    tbl.columns[0].width = Inches(6.5)

    cell = tbl.cell(0, 0)
    set_cell_background(cell, "F0F4F8")
    set_cell_margins(cell, top=160, bottom=160, left=200, right=200)

    # Left border accent
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = parse_xml(
        f'<w:tcBorders {nsdecls("w")}>'
        f'  <w:top w:val="none"/>'
        f'  <w:left w:val="single" w:sz="24" w:space="0" w:color="2B6CB0"/>'
        f'  <w:bottom w:val="none"/>'
        f'  <w:right w:val="none"/>'
        f'</w:tcBorders>'
    )
    tc_pr.append(borders)

    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(4)
    run_title = p.add_run(f"📌 {title}\n")
    run_title.bold = True
    run_title.font.size = Pt(10.5)
    run_title.font.color.rgb = RGBColor(43, 108, 176)

    run_text = p.add_run(text)
    run_text.font.size = Pt(10)
    run_text.font.color.rgb = RGBColor(45, 55, 72)

    # Spacer after callout
    sp = doc.add_paragraph()
    sp.paragraph_format.space_before = Pt(4)
    sp.paragraph_format.space_after = Pt(4)


def build_academic_introduction_docx(banner_img: Path) -> Path:
    """Build the publication-grade academic Introduction Word document."""
    doc = Document()

    # Configure Margins (1 inch)
    for section in doc.sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)
        section.different_first_page_header_footer = False

        # Header and Footer
        header = section.header
        hp = header.paragraphs[0]
        hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        hrun = hp.add_run("DRAFT - not for citation | Repro Radar introduction | claims and sources: docs/INTRODUCTION_SOURCES.md")
        hrun.font.size = Pt(8.5)
        hrun.font.color.rgb = RGBColor(148, 163, 184)

        footer = section.footer
        fp = footer.paragraphs[0]
        fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        frun = fp.add_run("Repro Radar (appendix_controller_for_articles) - draft introduction")
        frun.font.size = Pt(8.5)
        frun.font.color.rgb = RGBColor(148, 163, 184)

    # 1. Embed Hero Cover Banner
    p_banner = doc.add_paragraph()
    p_banner.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_banner.paragraph_format.space_before = Pt(0)
    p_banner.paragraph_format.space_after = Pt(18)
    run_img = p_banner.add_run()
    run_img.add_picture(str(banner_img), width=Inches(6.5))

    # 2. Document Title & Metadata
    p_title = doc.add_paragraph()
    p_title.paragraph_format.space_before = Pt(10)
    p_title.paragraph_format.space_after = Pt(4)
    run_title = p_title.add_run("DRAFT — Repro Radar: Container-Isolated Reproducibility Checks for Computational Paper Appendices")
    run_title.bold = True
    run_title.font.size = Pt(22)
    run_title.font.color.rgb = RGBColor(26, 54, 93)

    p_sub = doc.add_paragraph()
    p_sub.paragraph_format.space_before = Pt(0)
    p_sub.paragraph_format.space_after = Pt(14)
    run_sub = p_sub.add_run("A sandboxed audit tool and 4-Tier reproducibility rubric, evaluated as a pilot study on tabular ML benchmarks")
    run_sub.font.size = Pt(12)
    run_sub.font.italic = True
    run_sub.font.color.rgb = RGBColor(74, 85, 104)

    # Metadata Table
    meta_table = doc.add_table(rows=2, cols=2)
    meta_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta_table.columns[0].width = Inches(3.25)
    meta_table.columns[1].width = Inches(3.25)

    cell_00 = meta_table.cell(0, 0)
    cell_01 = meta_table.cell(0, 1)
    cell_10 = meta_table.cell(1, 0)
    cell_11 = meta_table.cell(1, 1)

    for c in [cell_00, cell_01, cell_10, cell_11]:
        set_cell_background(c, "F8FAFC")
        set_cell_margins(c, top=80, bottom=80, left=120, right=120)

    cell_00.paragraphs[0].add_run("Author & Lead Architect:\n").bold = True
    cell_00.paragraphs[0].add_run("Yusuf Kartal (yusufkartal0009-eng)\nAutonomous Systems & Empirical AI Research")
    cell_00.paragraphs[0].runs[1].font.size = Pt(9.5)

    cell_01.paragraphs[0].add_run("Repository & Artifact Target:\n").bold = True
    cell_01.paragraphs[0].add_run("appendix_controller_for_articles\nGitHub: yusufkartal0009-eng/appendix_controller_for_articles")
    cell_01.paragraphs[0].runs[1].font.size = Pt(9.5)

    cell_10.paragraphs[0].add_run("Scope:\n").bold = True
    cell_10.paragraphs[0].add_run("Pilot study on tabular ML benchmarks (6 seed papers)")
    cell_10.paragraphs[0].runs[1].font.size = Pt(9.5)

    cell_11.paragraphs[0].add_run("Evaluation Standard:\n").bold = True
    cell_11.paragraphs[0].add_run("4-Tier Weighted Rubric (Build, Metrics, Stability, Artifacts)")
    cell_11.paragraphs[0].runs[1].font.size = Pt(9.5)

    doc.add_paragraph().paragraph_format.space_after = Pt(12)

    # Abstract Box
    add_callout(
        doc,
        "ABSTRACT (DRAFT)",
        "Computational results can only be checked if the code, data, and environment behind them can be run again. Repro Radar is a tool that stages the code of a published paper, runs it inside a restricted Docker container, and compares the numbers it produces with the numbers the paper reports, using a 4-Tier rubric (build, metric agreement, seed stability, software hygiene). This draft describes a pilot study on tabular ML benchmarks. The sandbox's isolation properties are checked against a real Docker daemon in continuous integration; the seed corpus of 6 papers passes automated checks of links, repositories, licenses, and pinned scripts; no paper has been run end to end yet, and the rubric has so far only been exercised with simulated outputs. An AI component for diagnosing failed runs is planned but not implemented.",
    )

    # SECTION 1
    add_styled_heading(doc, "1. The Crisis of Empirical Reproducibility in Scientific Literature", level=1)

    p1 = doc.add_paragraph(
        "Scientific results that depend on computation are only as checkable as the code behind them. Jon Claerbout argued for reproducible computational research in the early 1990s [1]. Donoho later recalled Claerbout's point, in a form paraphrased by Buckheit and Donoho [2]: “an article about computational result is advertising, not scholarship. The actual scholarship is the full software environment, code and data, that produced the result” [3]. Practices and tools for implementing reproducible research have since been collected in book form [4]."
    )
    p1.paragraph_format.line_spacing = 1.15
    p1.paragraph_format.space_after = Pt(8)

    p2 = doc.add_paragraph(
        "Concern about reproducibility is widespread: a Nature survey of 1,500 scientists described a ‘crisis’ in research reproducibility [5], and the NeurIPS 2019 reproducibility program published a report on improving reproducibility in machine learning research [6]. In deep reinforcement learning, reproducing state-of-the-art results is “seldom straightforward” because of non-deterministic benchmark environments and variance intrinsic to the methods [7]. The obstacles this project addresses, with evidence from its own pilot corpus, are:"
    )
    p2.paragraph_format.line_spacing = 1.15
    p2.paragraph_format.space_after = Pt(6)

    # Bullet list of failure modes
    bullet_points = [
        ("Code that moved or changed: ", "in this project's seed corpus, repositories had been renamed and one target script had been deleted by a later rewrite of its code base, so papers must be pinned to an exact commit (docs/CORPUS_VERIFICATION.md)."),
        ("Numbers that do not trace to the paper: ", "in the same corpus, only 2 of 16 recorded claims could be found in their papers; the rest must be re-extracted before they are compared (docs/CORPUS_VERIFICATION.md)."),
        ("Run-to-run and seed variance: ", "results can vary between runs and random seeds, which makes a single reported number hard to interpret [7]."),
        ("Manual effort: ", "re-running a paper requires reconstructing its environment, data, and hardware; this project aims to automate the parts that can be automated and to report the rest."),
    ]

    for title, body in bullet_points:
        bp = doc.add_paragraph(style="List Bullet")
        bp.paragraph_format.space_before = Pt(2)
        bp.paragraph_format.space_after = Pt(4)
        bp.paragraph_format.line_spacing = 1.15
        rt = bp.add_run(title)
        rt.bold = True
        rt.font.color.rgb = RGBColor(26, 54, 93)
        bp.add_run(body)

    # SECTION 2
    add_styled_heading(doc, "2. Architectural Principles of Container-Isolated Sandboxing", level=1)

    p3 = doc.add_paragraph(
        "Running third-party code carries risks: it may make network calls, exhaust memory, or write to the host file system. Repro Radar mitigates these risks by running paper code only inside a restricted Docker container, and it refuses to run the code when Docker is unavailable. Each property in the table below is checked against a real Docker daemon in continuous integration (docs/SANDBOX_ACCEPTANCE.md). The container still shares the host kernel, so these measures reduce the risk but do not eliminate it."
    )
    p3.paragraph_format.line_spacing = 1.15
    p3.paragraph_format.space_after = Pt(8)

    # Sandbox Feature Table
    sb_table = doc.add_table(rows=6, cols=3)
    sb_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    sb_table.columns[0].width = Inches(1.8)
    sb_table.columns[1].width = Inches(2.2)
    sb_table.columns[2].width = Inches(2.5)

    headers = ["Security Dimension", "Implementation Mechanism", "Operational Defense"]
    for idx, name in enumerate(headers):
        cell = sb_table.cell(0, idx)
        set_cell_background(cell, "1A365D")
        set_cell_margins(cell, top=100, bottom=100, left=100, right=100)
        p = cell.paragraphs[0]
        run = p.add_run(name)
        run.bold = True
        run.font.color.rgb = RGBColor(255, 255, 255)
        run.font.size = Pt(9.5)

    table_data = [
        ("Network", "Docker '--network none'", "Outbound TCP, DNS, and HTTPS fail inside the container (acceptance check 2)."),
        ("Filesystem", "'--read-only' root; repository mounted read-only", "Writes to /, /usr, and the paper's repository fail with EROFS (check 3)."),
        ("Writable scratch space", "tmpfs /tmp and /workspace/home: noexec, nosuid", "Code can write scratch files but cannot execute or load what it wrote (check 7)."),
        ("User", "Non-root UID:GID 1000:1000, no-new-privileges", "Code runs without root privileges (check 1); this alone does not prevent container escapes."),
        ("Resources", "--cpus=2.0, --memory=8g, --pids-limit=100", "CPU, memory, and process limits are enforced; an out-of-memory kill is reported as OOM_KILLED (checks 8, 9)."),
    ]

    for row_idx, row in enumerate(table_data, start=1):
        bg = "F8FAFC" if row_idx % 2 == 1 else "FFFFFF"
        for col_idx, text in enumerate(row):
            cell = sb_table.cell(row_idx, col_idx)
            set_cell_background(cell, bg)
            set_cell_margins(cell, top=80, bottom=80, left=100, right=100)
            p = cell.paragraphs[0]
            r = p.add_run(text)
            r.font.size = Pt(9)
            if col_idx == 0:
                r.bold = True

    doc.add_paragraph().paragraph_format.space_after = Pt(10)

    # SECTION 3
    add_styled_heading(doc, "3. The Four-Tier (4-Tier) Reproducibility Rubric", level=1)

    p4 = doc.add_paragraph(
        "Binary classifications of reproducibility ('reproduced' vs. 'not reproduced') fail to capture the nuanced realities of scientific software engineering. A codebase that compiles effortlessly, adheres to open-source licensing standards, and produces metrics within tolerance of the reported claims differs profoundly from one that crashes on import or yields wildly conflicting predictions. Repro Radar evaluates replication fidelity across four weighted tiers. The rubric is implemented in the code base, but at the time of writing it has only been exercised with simulated outputs, not with real paper runs:"
    )
    p4.paragraph_format.line_spacing = 1.15
    p4.paragraph_format.space_after = Pt(8)

    # Rubric Table
    rub_table = doc.add_table(rows=5, cols=4)
    rub_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    rub_table.columns[0].width = Inches(1.5)
    rub_table.columns[1].width = Inches(0.8)
    rub_table.columns[2].width = Inches(2.2)
    rub_table.columns[3].width = Inches(2.0)

    r_headers = ["Evaluation Tier", "Weight", "Evaluated Criteria", "Target Objective"]
    for idx, name in enumerate(r_headers):
        cell = rub_table.cell(0, idx)
        set_cell_background(cell, "2B6CB0")
        set_cell_margins(cell, top=100, bottom=100, left=100, right=100)
        p = cell.paragraphs[0]
        run = p.add_run(name)
        run.bold = True
        run.font.color.rgb = RGBColor(255, 255, 255)
        run.font.size = Pt(9.5)

    r_data = [
        ("Tier 1: Build & Execution", "35%", "Git cloning, dependency resolution, execution exit code 0", "Deterministic codebase compilability"),
        ("Tier 2: Metric Alignment", "35%", "Empirical claim concordance (default 5% tolerance)", "Validation of quantitative findings"),
        ("Tier 3: Seed Stability", "15%", "Multi-seed variance (CV <= 2%), coefficient of variation", "Mitigation of cherry-picked seeds"),
        ("Tier 4: Software Hygiene", "15%", "OSI license compliance, pinned environment files, logs", "Long-term open-science sustainability"),
    ]

    for row_idx, row in enumerate(r_data, start=1):
        bg = "F8FAFC" if row_idx % 2 == 1 else "FFFFFF"
        for col_idx, text in enumerate(row):
            cell = rub_table.cell(row_idx, col_idx)
            set_cell_background(cell, bg)
            set_cell_margins(cell, top=80, bottom=80, left=100, right=100)
            p = cell.paragraphs[0]
            r = p.add_run(text)
            r.font.size = Pt(9)
            if col_idx == 0:
                r.bold = True

    doc.add_paragraph().paragraph_format.space_after = Pt(10)

    # SECTION 4
    add_styled_heading(doc, "4. Scope and Current Status", level=1)

    p5 = doc.add_paragraph(
        "This work is a pilot study on tabular ML benchmarks. The seed corpus contains 6 papers. All 6 pass automated checks of their paper link, repository, license, and target script at a pinned commit, but none has been run end to end yet, and only 2 of their 16 recorded claims have been found in the papers so far (docs/CORPUS_VERIFICATION.md). Other scientific fields are out of scope for this pilot."
    )
    p5.paragraph_format.line_spacing = 1.15
    p5.paragraph_format.space_after = Pt(8)

    p6 = doc.add_paragraph(
        "Planned next steps are a small pilot run of the seed papers in the sandbox, extraction of claims directly from the papers with quoted evidence, and a report of which papers could and could not be reproduced and why."
    )
    p6.paragraph_format.line_spacing = 1.15
    p6.paragraph_format.space_after = Pt(12)

    # SECTION 5
    add_styled_heading(doc, "5. References", level=1)

    references = [
        ("[1] ", "Claerbout, J. F., & Karrenbach, M. (1992). Electronic documents give reproducible research a new meaning. SEG Technical Program Expanded Abstracts 1992, 601–604. https://doi.org/10.1190/1.1822162"),
        ("[2] ", "Buckheit, J. B., & Donoho, D. L. (1995). WaveLab and reproducible research. In Wavelets and Statistics (Lecture Notes in Statistics, pp. 55–81). Springer. https://doi.org/10.1007/978-1-4612-2544-7_5"),
        ("[3] ", "Donoho, D. L. (2010). An invitation to reproducible computational research. Biostatistics, 11(3), 385–388. https://doi.org/10.1093/biostatistics/kxq028"),
        ("[4] ", "Stodden, V., Leisch, F., & Peng, R. D. (Eds.). (2014). Implementing reproducible research. CRC Press. https://doi.org/10.1201/b16868"),
        ("[5] ", "Baker, M. (2016). 1,500 scientists lift the lid on reproducibility. Nature, 533(7604), 452–454. https://doi.org/10.1038/533452a"),
        ("[6] ", "Pineau, J., et al. (2021). Improving reproducibility in machine learning research (a report from the NeurIPS 2019 reproducibility program). Journal of Machine Learning Research, 22(164), 1–20. https://jmlr.org/papers/v22/20-303.html"),
        ("[7] ", "Henderson, P., Islam, R., Bachman, P., et al. (2018). Deep reinforcement learning that matters. Proceedings of the AAAI Conference on Artificial Intelligence, 32(1). https://doi.org/10.1609/aaai.v32i1.11694"),
    ]

    for ref_num, ref_text in references:
        ref_p = doc.add_paragraph()
        ref_p.paragraph_format.space_before = Pt(2)
        ref_p.paragraph_format.space_after = Pt(4)
        ref_p.paragraph_format.line_spacing = 1.15
        ref_p.paragraph_format.left_indent = Inches(0.4)
        ref_p.paragraph_format.first_line_indent = Inches(-0.4)
        r_num = ref_p.add_run(ref_num)
        r_num.bold = True
        r_num.font.size = Pt(9.5)
        r_txt = ref_p.add_run(ref_text)
        r_txt.font.size = Pt(9.5)

    doc.save(DOCX_PATH)
    print(f"Academic Introduction Word document saved to: {DOCX_PATH}")
    return DOCX_PATH


def main():
    print("=== Generating Application Cover Banner & Academic Introduction (.docx) ===")
    banner = generate_cover_banner()
    docx_file = build_academic_introduction_docx(banner)
    print(f"Successfully generated:\n - Banner: {banner}\n - Document: {docx_file}")


if __name__ == "__main__":
    main()
