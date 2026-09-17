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
    subtitle_text = "Autonomous Scientific Replication & Multi-Tier Verification Platform"
    mission_text = "Auditing Empirical Research Codebases Across IEEE, ACM, NeurIPS & Open Science"

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
        ("AI Decision Layer", (124, 45, 18), (253, 186, 116)),
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
        hrun = hp.add_run("Repro Radar | Academic Introduction & System Architecture")
        hrun.font.size = Pt(8.5)
        hrun.font.color.rgb = RGBColor(148, 163, 184)

        footer = section.footer
        fp = footer.paragraphs[0]
        fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        frun = fp.add_run("Appendix Controller for Empirical Scientific Research Articles • Open Science Specification")
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
    run_title = p_title.add_run("Repro Radar: Automated Empirical Replication and Multi-Tier Verification for Scientific Codebases")
    run_title.bold = True
    run_title.font.size = Pt(22)
    run_title.font.color.rgb = RGBColor(26, 54, 93)

    p_sub = doc.add_paragraph()
    p_sub.paragraph_format.space_before = Pt(0)
    p_sub.paragraph_format.space_after = Pt(14)
    run_sub = p_sub.add_run("An Autonomous, Container-Isolated Audit Engine and 4-Tier Reproducibility Evaluation Rubric for Empirical AI, Machine Learning, and Scientific Computing Articles")
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

    cell_10.paragraphs[0].add_run("Publication Scope:\n").bold = True
    cell_10.paragraphs[0].add_run("Universal Scientific Appendix Auditor (IEEE, ACM, NeurIPS, ICML)")
    cell_10.paragraphs[0].runs[1].font.size = Pt(9.5)

    cell_11.paragraphs[0].add_run("Evaluation Standard:\n").bold = True
    cell_11.paragraphs[0].add_run("4-Tier Weighted Rubric (Build, Metrics, Stability, Artifacts)")
    cell_11.paragraphs[0].runs[1].font.size = Pt(9.5)

    doc.add_paragraph().paragraph_format.space_after = Pt(12)

    # Abstract Box
    add_callout(
        doc,
        "EXECUTIVE ABSTRACT",
        "Empirical scientific disciplines face a profound replication bottleneck. While publication velocity has accelerated exponentially, independent computational reproducibility has lagged severely behind. Published claims frequently fail verification due to unversioned dependencies, hidden random seeds, hardware-dependent microarchitecture variations, and non-deterministic execution environments. Repro Radar introduces a domain-agnostic, container-isolated automated verification platform designed to evaluate research codebases and their accompanying numerical claims. Operating across a hardened Docker sandbox with zero network egress, CPU/memory quotas, and ephemeral user namespaces, the system executes paper-code pairs and applies a rigorous 4-Tier Reproducibility Rubric (Build Integrity, Metric Concordance, Multi-Seed Variance, and Software Hygiene). Rather than assigning punitive labels, an AI Decision Layer generates objective, diagnostic evaluations ('Verified', 'Partially Verified', 'Needs Review', 'Failed') that assist peer reviewers, academic funding agencies, and downstream practitioners in certifying research integrity.",
    )

    # SECTION 1
    add_styled_heading(doc, "1. The Crisis of Empirical Reproducibility in Scientific Literature", level=1)

    p1 = doc.add_paragraph(
        "Scientific discovery relies fundamentally on independent verifiability. In 1995, geophysicist Jon Claerbout formulated a founding tenet of computational science: 'An article about computational science in a scientific publication is not the scholarship itself, it is merely advertising of the scholarship. The actual scholarship is the complete software development environment and the complete set of instructions which generated the figures.' Over the subsequent three decades, the transition from closed computational models to open scientific software has produced unprecedented scientific advances. However, this expansion has concurrently catalyzed a pervasive replication crisis across empirical computing, statistical modeling, and machine learning."
    )
    p1.paragraph_format.line_spacing = 1.15
    p1.paragraph_format.space_after = Pt(8)

    p2 = doc.add_paragraph(
        "Recent large-scale replication initiatives conducted across flagship conferences (including NeurIPS, ICML, ICLR, and IEEE Transactions) reveal that fewer than 35% of published empirical papers can be independently reproduced from their repository artifacts without substantial manual interventions by domain experts. The root causes of this failure mode are multifaceted and systemic:"
    )
    p2.paragraph_format.line_spacing = 1.15
    p2.paragraph_format.space_after = Pt(6)

    # Bullet list of failure modes
    bullet_points = [
        ("The Silent Decay of Dependency Ecosystems: ", "Academic research repositories routinely omit version pinning in manifest files, or fail to document system-level library dependencies (e.g. CUDA drivers, OpenBLAS, compiler flags). Within 6 to 18 months of publication, breaking API changes in upstream libraries render research code entirely uncompilable."),
        ("Stochastic Cherry-Picking and Seed Fragility: ", "Empirical improvements in deep learning and statistical models frequently hold true only under a singular, undisclosed random seed. In the absence of multi-seed variance analysis, minor statistical fluctuations are mistakenly celebrated as novel theoretical breakthroughs."),
        ("Hardware Confounding and Floating-Point Drift: ", "Non-deterministic GPU reduction algorithms, non-associative floating-point summation (IEEE 754 standards), and differing CPU instruction sets (AVX-512 vs. ARM NEON) produce numerical variations that cause naive verification tools to reject valid scientific replications."),
        ("Absence of Automated Verification Infrastructure: ", "Peer reviewers and journal editors operate under severe time constraints. Manually provisioning isolated hardware environments, debugging path errors, and executing hours of training runs is untenable for human reviewers without dedicated automation."),
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
        "Executing third-party scientific code poses acute operational risks. Untrusted research scripts may invoke unvetted system commands, initiate arbitrary network calls, consume boundless memory, or overwrite host filesystems. Repro Radar resolves this tension by decoupling execution from the host operating system through a defense-in-depth sandbox topology."
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
        ("Network Egress & Ingress", "Docker '--network none'", "Completely prevents unauthorized data exfiltration and eliminates hidden dependencies on dynamic external web services."),
        ("Filesystem Immutability", "'--read-only' Root + Read-only Repo", "Locks container root. Source code is mounted under '/workspace/repo:ro' to guarantee that audited code cannot mutate its own source."),
        ("Temporary Memory Jails", "'--tmpfs /tmp:rw,noexec,nosuid'", "In-memory scratchpad that strictly prohibits executable binaries or setuid elevation within temporary workspaces."),
        ("User Space Isolation", "Non-Root UID:GID 1000:1000", "Enforces the principle of least privilege. Prevents container breakout vulnerabilities through Linux kernel capabilities."),
        ("Resource Bounds", "--cpus=2.0, --memory=8g, --pids-limit=100", "Prevents host resource starvation, CPU monopolization, and malicious fork-bomb recursion."),
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
        "Binary classifications of reproducibility ('reproduced' vs. 'not reproduced') fail to capture the nuanced realities of scientific software engineering. A codebase that compiles effortlessly, adheres to open-source licensing standards, and produces metrics within 2% of reported claims differs profoundly from one that crashes on import or yields wildly conflicting predictions. Repro Radar evaluates replication fidelity across four structured, weighted tiers:"
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
        ("Tier 2: Metric Alignment", "35%", "Empirical claim concordance (relative & absolute tolerance)", "Validation of quantitative findings"),
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
    add_styled_heading(doc, "4. Domain-Agnostic Scientific Auditing Scope", level=1)

    p5 = doc.add_paragraph(
        "A foundational design objective of Repro Radar is domain independence. While initial development and calibration leveraged empirical machine learning and tabular classification benchmarks, the underlying verification engine is architecturally universal. Any peer-reviewed scientific paper that bundles an executable computational appendix—whether in IEEE Transactions on Signal Processing, bioinformatics gene expression pipelines, computational economics, physical simulations, or cryptography—can be formally audited through this infrastructure."
    )
    p5.paragraph_format.line_spacing = 1.15
    p5.paragraph_format.space_after = Pt(8)

    p6 = doc.add_paragraph(
        "By enforcing a strict separation between domain-specific mathematical parsing and general sandbox orchestration, Repro Radar provides a standardized verification protocol that bridges the gap between academic authors, conference program committees, and the broader global scientific community."
    )
    p6.paragraph_format.line_spacing = 1.15
    p6.paragraph_format.space_after = Pt(12)

    # SECTION 5
    add_styled_heading(doc, "5. References & Academic Bibliography", level=1)

    references = [
        ("1. Claerbout, J. F., & Karrenbach, M. (1992). ", "Electronic documents give reproducible research a new meaning. In SEG Technical Program Expanded Abstracts (pp. 601-604). Society of Exploration Geophysicists."),
        ("2. Donoho, D. L. (2010). ", "An invitation to reproducible computational research. Biostatistics, 11(3), 385-388."),
        ("3. Pineau, J., et al. (2021). ", "Improving reproducibility in machine learning research (a report from the NeurIPS 2019 reproducibility program). Journal of Machine Learning Research, 22(164), 1-20."),
        ("4. Stodden, V., Leisch, F., & Peng, R. D. (Eds.). (2014). ", "Implementing reproducible research. CRC Press."),
        ("5. Baker, M. (2016). ", "1,500 scientists lift the lid on reproducibility. Nature, 533(7604), 452-454."),
        ("6. Henderson, P., et al. (2018). ", "Deep reinforcement learning that matters. In Proceedings of the AAAI Conference on Artificial Intelligence (Vol. 32, No. 1)."),
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
