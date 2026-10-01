"""Provision 7 weekly milestones and issue tracking on GitHub via GitHub CLI."""
import subprocess

REPO = "yusufkartal0009-eng/appendix_controller_for_articles"

WEEKS = [
    {
        "milestone": "Week 1: Core Infrastructure",
        "description": "Core architecture, data models, verified seed paper corpus, and 4-tier reproducibility scoring engine.",
        "issue_title": "feat(core): implement week 1 core infrastructure and discovery baseline",
        "issue_body": """## Week 1 Goals
- [x] Repository architecture & directory hierarchy established
- [x] SQLite schema and SQLAlchemy ORM models configured
- [x] 8 verified open-source paper-repo pairs curated
- [x] 4-Tier (Tier 1-4) scoring engine and tolerance logic developed
- [x] 24/24 unit tests passing cleanly""",
        "labels": ["area:corpus", "area:scoring", "feat", "priority:high"],
    },
    {
        "milestone": "Week 2: Docker Sandbox & Isolation",
        "description": "Docker-based isolated container environment, resource quotas (cgroups), network isolation, and timeout handler.",
        "issue_title": "feat(sandbox): build isolated Docker container sandbox and execution runner",
        "issue_body": """## Week 2 Goals
- [ ] Python 3.11 base Dockerfile and sandbox runtime image
- [ ] Resource quotas: CPU limits (2 vCPUs) and memory caps (8GB)
- [ ] Network isolation policy (--network none during execution)
- [ ] Container lifecycle management runner (runner.py)
- [ ] Multi-seed randomized execution driver""",
        "labels": ["area:sandbox", "feat", "priority:high"],
    },
    {
        "milestone": "Week 3: Static Code Analysis",
        "description": "AST-based import scanning, multi-manifest parser, and automated dependency resolution.",
        "issue_title": "feat(solver): implement AST static analysis and dependency resolution",
        "issue_body": """## Week 3 Goals
- [ ] Python AST parser for missing undeclared packages
- [ ] Multi-format manifest parser (requirements.txt / pyproject.toml / setup.py)
- [ ] Automated dependency conflict solver
- [ ] GPU-to-CPU adapter and hardware flag optimizations
- [ ] Heuristic entrypoint script detector""",
        "labels": ["area:sandbox", "feat", "priority:medium"],
    },
    {
        "milestone": "Week 4: Metric Extraction Engine",
        "description": "Empirical metric extraction from console logs (stdout), JSON/CSV artifacts, and model checkpoints.",
        "issue_title": "feat(scoring): develop empirical metric extraction and parsing engine",
        "issue_body": """## Week 4 Goals
- [ ] Regex-based metric extractor (accuracy, AUC, loss, latency, etc.)
- [ ] Standardized Scikit-learn and PyTorch output parsers
- [ ] LLM fallback parser for unstructured free-text console logs
- [ ] Persist extracted metrics to claims table and compute tolerance bounds""",
        "labels": ["area:scoring", "feat", "priority:high"],
    },
    {
        "milestone": "Week 5: AI Decision Layer",
        "description": "AI Decision Layer converting execution traces and metric deltas into neutral diagnostic reports.",
        "issue_title": "feat(ai): integrate AI decision layer and automated diagnostics pipeline",
        "issue_body": """## Week 5 Goals
- [ ] PipelineController orchestrating Tier 1-4 evaluators
- [ ] Root-cause failure classifier (OOM, dependency conflict, data missing)
- [ ] Rule-based and LLM-assisted diagnostic rationale generator
- [ ] Structured Markdown and JSON audit report outputs""",
        "labels": ["area:ai", "feat", "priority:high"],
    },
    {
        "milestone": "Week 6: Field-Scale Analysis",
        "description": "Cross-paper reproducibility rates, statistical factor analysis, and macro reproducibility study.",
        "issue_title": "feat(corpus): conduct field-scale reproducibility study across papers",
        "issue_body": """## Week 6 Goals
- [ ] Automated batch verification across the full benchmark corpus
- [ ] Statistical factor analysis (license, framework, seed variance effects)
- [ ] Cross-paper comparative meta-analysis matrix
- [ ] REST API paper leaderboard and dynamic SVG badge endpoints""",
        "labels": ["area:corpus", "area:web", "feat", "priority:high"],
    },
    {
        "milestone": "Week 7: Demo & Report",
        "description": "End-to-end demo video, final paper/blog report publication, community guide, and v1.0 release.",
        "issue_title": "feat(devops): publish comprehensive research report, demo video, and v1.0 release",
        "issue_body": """## Week 7 Goals
- [ ] End-to-end interactive system demo video
- [ ] Comprehensive academic/blog report detailing empirical findings
- [ ] CONTRIBUTING.md open-source protocol and paper onboarding specs
- [ ] GitHub Actions CI/CD workflow and v1.0.0 semantic version tag""",
        "labels": ["area:devops", "feat", "priority:high"],
    },
]

def main():
    print("Provisioning 7 weekly milestones on GitHub...")
    for week in WEEKS:
        m_title = week["milestone"]
        m_desc = week["description"]
        # Create milestone via gh api
        res = subprocess.run(
            ["gh", "api", f"repos/{REPO}/milestones", "-f", f"title={m_title}", "-f", f"description={m_desc}"],
            capture_output=True,
            text=True, check=False
        )
        if res.returncode == 0:
            print(f"Created milestone: {m_title}")
        else:
            print(f"Milestone {m_title} already exists or returned: {res.stderr.strip()}")

    print("\nCreating weekly tracking issues on GitHub...")
    for week in WEEKS:
        cmd = [
            "gh", "issue", "create",
            "--title", week["issue_title"],
            "--milestone", week["milestone"],
            "--body-file", "-"
        ]
        for lbl in week["labels"]:
            cmd.extend(["--label", lbl])

        res = subprocess.run(cmd, input=week["issue_body"], capture_output=True, text=True, check=False)
        if res.returncode == 0:
            print(f"Created issue: {week['issue_title']} -> {res.stdout.strip()}")
        else:
            print(f"Failed to create issue for {week['milestone']}: {res.stderr.strip()}")

    print("\nAll 7-week milestones and tracking issues setup successfully!")

if __name__ == "__main__":
    main()
