# Repro Radar: Metodoloji ve Skorlama Rubriği

## 1. Giriş ve Problem Tanımı

Yapay zekâ ve makine öğrenimi literatüründe her gün yüzlerce yeni bildiri ve makale yayımlanmaktadır. Ancak akademik üretim hacmindeki bu devasa artışa karşın, sonuçların bağımsız ortamlarda yeniden üretilebilirliğini (**reproducibility**) denetleyecek otomatize kapasite son derece yetersizdir. Eksik hiperparametreler, sabitlenmemiş rastgele tohumlar (random seeds), belirsiz kütüphane sürümleri ve tescilli/ulaşılamayan veri setleri, literatürde güvenilirlik erozyonuna yol açmaktadır.

**Repro Radar**, makale ve kod çiftlerini izole sandbox ortamlarında test ederek çok kademeli bir **Reproducibility Skoru** (0–100) ve **AI Karar Katmanı** ile desteklenmiş nesnel bir doğrulama raporu üretir.

---

## 2. Dört Kademeli (4-Tier) Skorlama Mimarisi

Repro Radar, bir çalışmanın tekrarlanabilirliğini yalnızca "çalıştı / çalışmadı" ikiliğine indirgemez. Kapsamlı ve katmanlı bir değerlendirme modeli uygular:

| Kademe | Odak Alanı | Ağırlık | Değerlendirilen Kriterler |
| :--- | :--- | :---: | :--- |
| **Tier 1: Build & Çalıştırma** | Kod ve Ortam Bütünlüğü | **%35** | Depo klonlama, bağımlılık kurulumu, hedef script çağrısı, hatasız çıkış kodu (Exit Code 0) |
| **Tier 2: Metrik Örtüşmesi** | İddia Doğrulama | **%35** | Makalede belirtilen temel iddiaların (accuracy, ROC-AUC, F1, loss vb.) tolerans aralığında tekrarı |
| **Tier 3: Kararlılık (Stability)**| Tohum ve Varyans Dayanımı | **%15** | Çoklu seed (rastgele tohum) altında varyasyon katsayısı (CV) ve deterministik tutarlılık |
| **Tier 4: Dokümantasyon & Lisans**| Açıklık ve Sürdürülebilirlik | **%15** | Açık kaynak lisansı (MIT, Apache, BSD), ortam dosyaları (`requirements.txt`), log/artefakt çıktısı |

---

### Tier 1: Build ve Çalıştırma (%35)

Kod tabanının sıfırdan izole bir ortama kurulabilme kabiliyetini ölçer:
- **Repo Klonlama (+25 Puan):** Depo açık, erişilebilir ve git aracılığıyla hatasız klonlanabiliyor.
- **Bağımlılık Kurulumu (+25 Puan):** Paket yöneticisi (pip, conda, uv) tüm gereksinimleri çakışmasız kurabiliyor.
- **Hedef Script Başlatma (+25 Puan):** Belirtilen giriş noktası (örn. `run.py`, `eval.py`) eksik dosya hatası vermeden başlatılıyor.
- **Hatasız Tamamlanma (+25 Puan):** Süreç, beklenmeyen bir exception/crash olmaksızın çıkış kodu `0` ile sonlanıyor.

$$\text{Tier 1 Skoru} \in [0, 100]$$

---

### Tier 2: Sonuç ve Metrik Örtüşmesi (%35)

Makalede raporlanan deneysel bulgular ile sandbox çalıştırmasından elde edilen çıktılar arasındaki bağıntıyı ölçer:

1. **Bağıl Hata (Relative Error):**
   $$\text{RelError} = \frac{|\text{Reproduced} - \text{Claimed}|}{\max(|\text{Claimed}|, 10^{-6})}$$

2. **Puanlama Mantığı:**
   - $\text{RelError} \le \text{Tolerance}$ (Varsayılan: %5) $\rightarrow$ **Tam Puan (1.0)**
   - $\text{Tolerance} < \text{RelError} \le 2 \times \text{Tolerance}$ $\rightarrow$ **Kısmi Puan (0.5)**
   - $\text{RelError} > 2 \times \text{Tolerance}$ veya Metrik Bulunamadı $\rightarrow$ **0 Puan (0.0)**

$$\text{Tier 2 Skoru} = \left( \frac{\sum \text{Kazanılan Puan}}{\text{Toplam İddia Sayısı}} \right) \times 100$$

---

### Tier 3: Kararlılık ve Tohum Varyansı (%15)

Deneysel sonucun tek bir "şanslı tohum" (cherry-picked seed) sonucunda mı yoksa sağlam bir metodolojiyle mi elde edildiğini inceler:
- Çoklu tohum çalıştırmalarında ($n \ge 3$) **Varyasyon Katsayısı (Coefficient of Variation - CV)** hesaplanır:
  $$\text{CV} = \frac{\sigma}{\mu}$$
- $\text{CV} \le 2\%$: **100 Puan** (Mükemmel stabilite)
- $2\% < \text{CV} \le 5\%$: **85 Puan** (Yüksek stabilite)
- $5\% < \text{CV} \le 10\%$: **65 Puan** (Kabul edilebilir hafif varyans)
- $\text{CV} > 10\%$: **40 Puan** (Yüksek stokastik sapma)
- Tek tohumlu temiz çalıştırma: **75 Puan** (Temel stabilite puanı)

---

### Tier 4: Artefaktlar, Lisans ve Dokümantasyon (%15)

Bilimsel kodun sürdürülebilirliğini ve açık bilim ilkelerine uyumunu denetler:
- **Açık Kaynak Lisansı (+30 Puan):** OSI onaylı serbest lisanslar (MIT, Apache-2.0, BSD-2/3, CC-BY-4.0).
- **Açık Ortam Tanımı (+30 Puan):** `requirements.txt`, `pyproject.toml`, `Pipfile` veya `environment.yml`.
- **Dokümantasyon & Talimatlar (+20 Puan):** Detaylı çalıştırma adımlarını içeren `README.md`.
- **Yapılandırılmış Çıktı ve Loglar (+20 Puan):** Sonuçların JSON, CSV veya açık konsol çıktısı olarak loglanması.

---

## 3. Toplam Skor ve Durum Sınıflandırması

Toplam kompozit skor ağırlıklı toplam formülüyle hesaplanır:

$$\text{Total Score} = 0.35 \times \text{Tier 1} + 0.35 \times \text{Tier 2} + 0.15 \times \text{Tier 3} + 0.15 \times \text{Tier 4}$$

### Nötr ve Bilimsel Durum Etiketleri (Status Labels)

Repro Radar, araştırmacıları suçlayıcı veya sübjektif ifadeler ("Sahte", "Hatalı", "Geçersiz") **kesinlikle kullanmaz**. Tarafsız, bilimsel ve yapıcı etiketler esastır:

1. **Doğrulandı (Verified) [Skor $\ge 85$, Tier 1 $\ge 90$, Tier 2 $\ge 80$]:**
   Kod izole ortamda eksiksiz derlendi, iddia edilen metrikler tolerans sınırları içinde başarıyla elde edildi.
2. **Kısmen Doğrulandı (Partially Verified) [Skor $\ge 60$]:**
   Kod çalıştı, iddiaların büyük çoğunluğu veya bir alt kümesi doğrulandı; küçük tolerans farkı veya eksik çevre konfigürasyonu mevcut.
3. **İncelenmeli (Needs Review / Inconclusive) [Skor $< 60$, Tier 1 $\ge 75$]:**
   Kod başarıyla derlendi ve çalıştı; ancak üretilen metrikler makaledeki iddialardan belirgin şekilde ayrıştı. Donanım farklılığı, veri sürümü veya gizli stokastik süreçlerin manuel denetimini gerektirir.
4. **Tekrarlanamadı (Failed) [Tier 1 $< 50$ veya Kritik Hata]:**
   Eksik bağımlılıklar, kütüphane uyuşmazlığı, kırık linkler veya derleme hataları sebebiyle kod çalıştırılamadı.

---

## 4. Güvenlik, İzolasyon ve Etik Standartları

- **Konteyner Sandbox:** Tüm çalıştırmalar ağ erişimi kısıtlanmış, geçici ve yalıtılmış Docker konteynerlerinde yürütülür. Host sisteme erişim engellenir.
- **Kaynak Sınırları:** Süre aşımı (timeout = 600s), RAM kotası (maks. 8GB) ve CPU sınırlaması uygulanarak kötü niyetli veya sonsuz döngüye giren scriptler engellenir.
- **Yalnızca Açık Lisanslar:** Yalnızca açık lisanslı veya kamusal kod depoları taranır ve çalıştırılır. Telif hakkı saklı kodlar değerlendirmeye alınmaz.
- **Şeffaf Günlükleme:** Başarısızlık durumunda tüm derleme hataları (`stdout`, `stderr`), kullanılan paket sürümleri ve ortam bilgisi araştırmacıyla şeffaf olarak paylaşılır.
