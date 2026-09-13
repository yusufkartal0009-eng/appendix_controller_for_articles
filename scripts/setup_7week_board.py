"""Provision 7 weekly milestones and issue tracking on GitHub via GitHub CLI."""
import subprocess
import json

REPO = "yusufkartal0009-eng/appendix_controller_for_articles"

WEEKS = [
    {
        "milestone": "Hafta 1: Çekirdek Altyapı",
        "description": "Çekirdek mimari, veri modelleri, doğrulanmış tohum makale seti ve 4-kademeli skorlama motoru.",
        "issue_title": "feat(core): implement week 1 core infrastructure and discovery baseline",
        "issue_body": """## Hafta 1 Hedefleri
- [x] Depo mimarisi ve dosya hiyerarşisi oluşturuldu
- [x] SQLite şeması ve SQLAlchemy ORM modelleri kuruldu
- [x] 8 adet doğrulanmış açık kaynak makale-repo çifti eklendi
- [x] 4-Kademeli (Tier 1-4) skorlama motoru ve tolerans mantığı geliştirildi
- [x] 24/24 birim test yeşil""",
        "labels": ["area:corpus", "area:scoring", "feat", "priority:high"],
    },
    {
        "milestone": "Hafta 2: Docker Sandbox & İzolasyon",
        "description": "Docker tabanlı izole konteyner ortamı, kaynak sınırları (cgroups), ağ izolasyonu ve zaman aşımı mekanizması.",
        "issue_title": "feat(sandbox): build isolated Docker container sandbox and execution runner",
        "issue_body": """## Hafta 2 Hedefleri
- [ ] Python 3.11 tabanlı Dockerfile ve sandbox imajı
- [ ] CPU (2 vCPU) ve bellek (8GB) kaynak kotaları
- [ ] Ağ kısıtlama politikası (--network none)
- [ ] Konteyner yaşam döngüsü yöneticisi (runner.py)
- [ ] Çoklu rastgele tohum (multi-seed) yürütme mekanizması""",
        "labels": ["area:sandbox", "feat", "priority:high"],
    },
    {
        "milestone": "Hafta 3: Statik Kod Analizi",
        "description": "AST tabanlı import taraması, çoklu format gereksinim ayrıştırıcısı ve otomatik bağımlılık çözücü.",
        "issue_title": "feat(solver): implement AST static analysis and dependency resolution",
        "issue_body": """## Hafta 3 Hedefleri
- [ ] Python AST ile eksik kütüphane tespiti
- [ ] requirements.txt / pyproject.toml / setup.py ayrıştırıcı
- [ ] Sürüm çakışmalarını gideren bağımlılık çözücü
- [ ] GPU-CPU adaptörü ve cihaz bayrakları optimizasyonu
- [ ] Giriş noktası (entrypoint) betiği otomatik tespit edici""",
        "labels": ["area:sandbox", "feat", "priority:medium"],
    },
    {
        "milestone": "Hafta 4: Metrik Çıkarım Motoru",
        "description": "Konsol çıktıları (stdout), JSON/CSV günlükleri ve model çıktılarından ampirik metrik çıkarımı.",
        "issue_title": "feat(scoring): develop empirical metric extraction and parsing engine",
        "issue_body": """## Hafta 4 Hedefleri
- [ ] Regex tabanlı metrik çıkarıcı (accuracy, AUC, loss vb.)
- [ ] Scikit-learn ve PyTorch standart çıktı ayrıştırıcıları
- [ ] Yapısal olmayan loglar için LLM destekli metrik çıkarım motoru
- [ ] Çıkarılan metriklerin claims tablosuna kaydı ve tolerans hesaplaması""",
        "labels": ["area:scoring", "feat", "priority:high"],
    },
    {
        "milestone": "Hafta 5: AI Karar Katmanı",
        "description": "Çalıştırma izleri ve metrik farklarını tarafsız teşhis raporuna dönüştüren AI Karar Katmanı.",
        "issue_title": "feat(ai): integrate AI decision layer and automated diagnostics pipeline",
        "issue_body": """## Hafta 5 Hedefleri
- [ ] Tier 1-4 değerlendiricilerini orkestre eden PipelineController
- [ ] Hata kök-neden sınıflandırıcısı (OOM, sürüm uyuşmazlığı, veri eksikliği)
- [ ] Şablon tabanlı ve LLM destekli teşhis gerekçelendirme sistemi
- [ ] Yapılandırılmış Markdown ve JSON audit raporu çıktısı""",
        "labels": ["area:ai", "feat", "priority:high"],
    },
    {
        "milestone": "Hafta 6: Alan Ölçeğinde Analiz",
        "description": "Makaleler arası yeniden üretilebilirlik oranları, istatistiksel faktör analizi ve makro bulgular.",
        "issue_title": "feat(corpus): conduct field-scale reproducibility study across papers",
        "issue_body": """## Hafta 6 Hedefleri
- [ ] Tüm veri kümesi üzerinde toplu otomatik doğrulama testi
- [ ] İstatistiksel faktör analizi (lisans, framework, seed etkisi)
- [ ] Makaleler arası karşılaştırmalı meta-analiz tablosu
- [ ] REST API liderlik tablosu (leaderboard) ve dinamik SVG rozetleri""",
        "labels": ["area:corpus", "area:web", "feat", "priority:high"],
    },
    {
        "milestone": "Hafta 7: Demo & Rapor",
        "description": "Uçtan uca demo videosu, makale/blog formatında nihai rapor yayını, topluluk rehberi ve v1.0 sürümü.",
        "issue_title": "feat(devops): publish comprehensive research report, demo video, and v1.0 release",
        "issue_body": """## Hafta 7 Hedefleri
- [ ] Uçtan uca çalışan sistemin tanıtım ve demo videosu
- [ ] Yeniden üretilebilirlik bulgularını içeren akademik makale/blog raporu
- [ ] CONTRIBUTING.md ve açık kaynak katkı protokolü
- [ ] GitHub Actions CI/CD hattı ve v1.0.0 semantic versiyon etiketi""",
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
            text=True
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

        res = subprocess.run(cmd, input=week["issue_body"], capture_output=True, text=True)
        if res.returncode == 0:
            print(f"Created issue: {week['issue_title']} -> {res.stdout.strip()}")
        else:
            print(f"Failed to create issue for {week['milestone']}: {res.stderr.strip()}")

    print("\nAll 7-week milestones and tracking issues setup successfully!")

if __name__ == "__main__":
    main()
