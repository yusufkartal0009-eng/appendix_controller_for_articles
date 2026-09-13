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
  ["Hafta 1: Çekirdek Altyapı"]="Hafta 1: Çekirdek Altyapı, Veri Şeması, Doğrulama Modelleri ve 4-Kademeli Skorlama Motoru"
  ["Hafta 2: Docker Sandbox & İzolasyon"]="Hafta 2: Docker Tabanlı İzole Konteyner Sandbox ve Güvenlik Sınırları"
  ["Hafta 3: Statik Kod Analizi"]="Hafta 3: Statik Kod Analizi, AST Taraması ve Otomatik Bağımlılık Çözücü"
  ["Hafta 4: Metrik Çıkarım Motoru"]="Hafta 4: Ampirik Metrik Çıkarım Motoru ve Çıktı Ayrıştırıcıları"
  ["Hafta 5: AI Karar Katmanı"]="Hafta 5: AI Karar Katmanı, Hata Kök-Neden Teşhisi ve Otomasyon Hattı"
  ["Hafta 6: Alan Ölçeğinde Analiz"]="Hafta 6: Alan Ölçeğinde Analiz, Makaleler Arası Çapraz Çalışma ve İstatistiksel Faktör Analizi"
  ["Hafta 7: Demo & Rapor"]="Hafta 7: Demo Videosu, Makale Raporu Yayını, Topluluk Protokolü ve V1.0 Yayını"
)

for title in "${!MILESTONES[@]}"; do
  desc="${MILESTONES[$title]}"
  echo "Ensuring milestone: ${title}"
  gh api "repos/${REPO}/milestones" -f title="${title}" -f description="${desc}" -f state="open" 2>/dev/null || true
done

echo "7-Week milestones provisioned."
