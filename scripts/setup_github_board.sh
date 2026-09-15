#!/usr/bin/env bash
# ==============================================================================
# Repro Radar: 7-Week Milestone & Issue Tracking Provisioning Script
# Provisions weekly milestones and core tracking issues on GitHub using `gh`.
# ==============================================================================

set -euo pipefail

REPO="yusufkartal0009-eng/appendix_controller_for_articles"

echo "Setting up 7-week milestones on GitHub for ${REPO}..."

# 1. Create 7-Week Milestones
declare -A MILESTONES=(
  ["Week 1: Core Infrastructure"]="Week 1: Core Infrastructure, Data Schemas, Verification Models, and 4-Tier Scoring Engine"
  ["Week 2: Docker Sandbox & Isolation"]="Week 2: Docker-based Isolated Container Sandbox and Security Boundaries"
  ["Week 3: Static Code Analysis"]="Week 3: Static Code Analysis, AST Scanning, and Automated Dependency Resolver"
  ["Week 4: Metric Extraction Engine"]="Week 4: Empirical Metric Extraction Engine and Output Parsers"
  ["Week 5: AI Decision Layer"]="Week 5: AI Decision Layer, Root-Cause Diagnostics, and Automation Pipeline"
  ["Week 6: Field-Scale Analysis"]="Week 6: Field-Scale Analysis, Cross-Paper Study, and Statistical Factor Analysis"
  ["Week 7: Demo & Report"]="Week 7: Demo Video Walkthrough, Empirical Report Publication, Community Protocol, and v1.0 Release"
)

for title in "${!MILESTONES[@]}"; do
  desc="${MILESTONES[$title]}"
  echo "Ensuring milestone: ${title}"
  gh api "repos/${REPO}/milestones" -f title="${title}" -f description="${desc}" -f state="open" 2>/dev/null || true
done

echo "7-Week milestones provisioned."
