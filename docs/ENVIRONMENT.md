# Repro Radar — Environment & Dependency Inventory

> Everything a fresh machine needs to develop, test, and run Repro Radar, in one place.
> For the architectural stack map see [`STACK.md`](STACK.md); for sandbox internals see
> [`SANDBOX_GUIDE.md`](SANDBOX_GUIDE.md).

---

## 1. System Programs & CLI Tools

| Tool | Required? | Version | Used by | Purpose |
|---|---|---|---|---|
| **Python** | Required | 3.11 recommended (3.10+ supported) | everything | Runtime for `cli.py`, `src/`, `scripts/`, `tests/` |
| **pip / venv** | Required | bundled with Python | setup | Isolated `.venv` and package install |
| **Git** | Required | any recent | `src/sandbox/stager.py` (`git clone`, `git checkout`, `git rev-parse`) | Source control and staging paper repositories |
| **Docker Engine / Docker Desktop** | Required to execute paper code (not for tests) | 24.x+ | `src/sandbox/runner.py` (`docker info`, `docker run`) | Isolated sandbox execution. Without it, execution is refused; `--allow-unsafe-local` runs trusted code unisolated on the host |
| **GitHub CLI (`gh`)** | Optional (maintainers) | any recent, authenticated | `scripts/setup_github_backlog.py`, `scripts/setup_7week_board.py`, `scripts/setup_github_board.sh` | Labels, milestones, issues, PRs |
| **Bash** | Optional | 4+ (Git Bash on Windows) | `scripts/setup_github_board.sh`, `docker/entrypoint.sh` (inside the container) | Shell scripts |

On Windows, Docker Desktop additionally requires WSL 2 and hardware virtualization enabled in the BIOS/UEFI.

---

## 2. Python Packages

### Runtime (`requirements.txt`)

| Package | Constraint | Imported by | Role |
|---|---|---|---|
| `pydantic` | `>=2.6.0` | `src/models.py` | Schema validation for papers and claims |
| `sqlalchemy` | `>=2.0.25` | `src/database.py`, `src/models.py` | SQLite ORM and sessions |
| `tabulate` | `>=0.9.0` | `cli.py` | Terminal tables |
| `pypdf` | `>=6.0.0` | `src/pdf_text.py` | Page-by-page text of paper PDFs (claim extraction) |
| `anthropic` | `>=1.11.0` | `src/claim_extraction.py` | Claude API client for claim extraction; reads `ANTHROPIC_API_KEY` |
| `fastapi` | `>=0.115` | `src/web/app.py` | Local dashboard API and page (D0) |
| `uvicorn` | `>=0.30` | `src/web/__main__.py` | Serves the dashboard on `127.0.0.1` |
| `pyyaml` | `>=6.0` | `src/sandbox/conda_env.py` | Reads conda environment files (#159) |
| `packaging` | `>=23.0` | `src/sandbox/installed_versions.py` | Compares requested and installed versions (#161) |

### Development (`requirements-dev.txt`, includes `requirements.txt`)

| Package | Constraint | Used by | Role |
|---|---|---|---|
| `pytest` | `>=8.0.0` | `tests/` | Test runner |
| `pytest-cov` | `>=5.0.0` | `pytest --cov` | Coverage reports |
| `ruff` | `==0.16.9` | `ruff check .` | Lint gate configured in `pyproject.toml` |
| `python-docx` | `>=1.1.0` | `scripts/generate_academic_introduction_doc.py`, `tests/test_academic_doc.py` | Academic introduction `.docx` generation |
| `pillow` | `>=10.0.0` | `scripts/generate_academic_introduction_doc.py`, `tests/test_academic_doc.py` | Banner image rendering |

`ruff` is pinned so the lint gate gives the same result on every machine.
All other imports are from the Python standard library (`argparse`, `json`, `logging`, `pathlib`,
`shutil`, `subprocess`, `tempfile`, `unittest`, `uuid`, …).

---

## 3. Sandbox Image (`docker/Dockerfile.sandbox`)

Built as `repro-radar-sandbox:latest` (the default `SandboxConfig.image_name`).

| Layer | Contents |
|---|---|
| Base image | `python:3.11-slim` |
| apt packages | `bash`, `ca-certificates`, `coreutils`, `procps`, `bc` |
| Pre-baked Python packages | `numpy>=1.24.0`, `scipy>=1.10.0`, `pandas>=2.0.0`, `scikit-learn>=1.3.0`, `tabulate>=0.9.0`, `pytest>=7.4.0` |
| Runtime user | `sandboxuser` (UID/GID 1000, non-root) |
| Entrypoint | `docker/entrypoint.sh` (offline wheel install, timeout guard, log capture, `execution_meta.json`) |

Container limits (from `docker/docker-compose.sandbox.yml` and `SandboxConfig`): 2 CPUs, 8 GB RAM,
100 PIDs, `--network none`, read-only root filesystem, `no-new-privileges`, all capabilities dropped (`--cap-drop ALL`).

Build it once Docker is installed (`.dockerignore` keeps the build context to `docker/entrypoint.sh`):

```bash
docker build -f docker/Dockerfile.sandbox -t repro-radar-sandbox:latest .
```

Smoke-test the image; `execution_meta.json` should report `"status": "COMPLETED"` and
`"dependency_install_status": "SKIPPED"` (no bundled wheels were mounted):

```bash
mkdir -p sandbox_runs/smoke
docker run --rm -v "$PWD/sandbox_runs/smoke:/workspace/output" repro-radar-sandbox:latest python -c "print('ok')"
cat sandbox_runs/smoke/execution_meta.json
```

`dependency_install_status` is `INSTALLED` or `FAILED` when the runner installed offline wheels in its
separate install phase (see `docs/SANDBOX_GUIDE.md`); a `FAILED` install does not stop the run.

### Local GPU (opt-in, #169)

A run gets the local NVIDIA GPU only when `SandboxConfig.gpus` is set (`"all"`, a count, or `"device=0[,1]"`). It
is passed to `docker run --gpus`; every other isolation flag stays the same. This needs Docker Desktop with the WSL2
backend and the NVIDIA Windows driver; no CUDA toolkit is needed inside the image, because the NVIDIA runtime adds
the driver libraries and `nvidia-smi` to the container. The run records `gpu_requested`, the GPUs it could see
(`gpu_devices`), and the peak GPU memory in use, sampled once per second (`gpu_peak_memory_used_mib`), in
`execution_meta.json`. `run_report.json` summarizes this as `gpu` (`available`, `used` = memory rose above its value
before the run). Other programs on the host that use the GPU can raise that value too.

Check it on the machine with the GPU:

```bash
python scripts/gpu_check.py            # --gpus all; exit 0 only if the GPU is visible and the isolation holds
```

The RTX 5070 (Blackwell) needs a PyTorch build for CUDA 12.8 or newer; papers that pin PyTorch 1.x cannot use it and
run on the CPU.

---

## 4. Environment Variables

| Variable | Default | Read by | Purpose |
|---|---|---|---|
| `REPRO_RADAR_DB_URL` | `sqlite:///data/repro_radar.db` | `src/config.py` | Database connection URL |
| `SANDBOX_TIMEOUT` | `600` | `docker/entrypoint.sh` | Per-run timeout (seconds) inside the container |

No API keys or secrets are required at this stage.

---

## 5. Local Paths Created at Runtime (gitignored)

| Path | Created by |
|---|---|
| `.venv/` | setup |
| `data/repro_radar.db` | `python cli.py init-db` |
| `temp_clones/` | `RepoStager` (staged paper repositories) |
| `sandbox_runs/` | sandbox runners (logs and `execution_meta.json`) |

---

## 6. Setup on a Fresh Machine

### Windows 11 (PowerShell)

```powershell
# 1. System tools
winget install --id Python.Python.3.11 -e --scope user
winget install --id Git.Git -e
winget install --id GitHub.cli -e          # optional, maintainers
winget install --id Docker.DockerDesktop -e # optional, sandbox

# 2. Project
git clone https://github.com/yusufkartal0009-eng/appendix_controller_for_articles.git
cd appendix_controller_for_articles
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt

# 3. Verify
.venv\Scripts\ruff.exe check .
.venv\Scripts\pytest.exe tests/ -v
.venv\Scripts\python.exe cli.py init-db
.venv\Scripts\python.exe cli.py list-papers
```

Use `requirements.txt` instead of `requirements-dev.txt` for a runtime-only install (no tests,
lint, or document tooling).

New terminals pick up `git`, `gh`, and `python` from `PATH` only after the installers finish;
open a fresh PowerShell window after step 1.

If `python` opens the Microsoft Store, the App Execution Alias stub is shadowing the real
interpreter: use `py -3.11` or disable the alias under *Settings → Apps → Advanced app settings →
App execution aliases*.

### Linux / macOS

```bash
git clone https://github.com/yusufkartal0009-eng/appendix_controller_for_articles.git
cd appendix_controller_for_articles
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements-dev.txt
ruff check .
pytest tests/ -v
```

### Clean-install test (2026-10-15, #301)

The steps of the README (clone, virtual environment, `pip install -r requirements-dev.txt`, `cli.py init-db`, `list-papers`,
`inspect`, `ruff`, `pytest`) were followed as written in an empty temporary folder, from a fresh clone of commit `c8a99f8`
on Windows 11 Home with Python 3.11.9, without Docker running:

- `pip install -r requirements-dev.txt` exit 0 (no manual step needed)
- `cli.py init-db` loaded 6 papers; `list-papers` and `inspect paper_002` worked; no `-X utf8` flag was needed
- `ruff check .` -> All checks passed; `pytest tests/` -> 542 passed, 9 skipped (12 s)
- `python -m src.web --port 8191`: `/`, `/papers/paper_002`, `/api/v1/papers`, `/api/v1/scores`, `/api/v1/badges/paper_002.svg`,
  `/api/v1/papers/paper_002/report.md`, `/api/v1/papers/paper_002/report.pdf`, and `/docs` all answered 200
- Found and fixed: `CONTRIBUTING.md` still said GitHub Actions was disabled; this baseline was from 2026-09-25 (below).
- Not tried: Linux or macOS, a machine without the Python 3.11 launcher, and running a paper (needs the Docker image).
  `/docs` loads its page assets from a CDN, so it needs the network.

### Earlier baseline (2026-09-25)

Clean Windows 11 Home machine, Python 3.11.9, fresh `.venv` from `requirements-dev.txt` (2026-09-25):

- `ruff check .` → **All checks passed**
- `pytest tests/` → **52 passed**
- `cli.py init-db` → schema initialized, 8 seed papers loaded
- Docker not installed → the suite still passes: sandbox tests mock the Docker availability check and
  opt into `ProcessSandboxRunner` explicitly, so Docker is not needed to run tests
