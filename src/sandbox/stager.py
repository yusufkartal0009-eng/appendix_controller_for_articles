"""Repository staging, dependency bundling, and execution orchestration for isolated sandboxes."""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.metric_extractor import MetricExtractor
from src.sandbox.conda_env import convert_env_file, find_conda_env_files
from src.sandbox.dependency_conflicts import (
    name_requirement_lines,
    parse_dependency_conflicts,
)
from src.sandbox.installed_versions import read_installed, requested_vs_installed
from src.sandbox.runner import (
    DEFAULT_PYTHON_VERSION,
    DockerSandboxRunner,
    SandboxConfig,
    SandboxExecutionResult,
    image_for,
)
from src.sandbox.sdist import download_sdist

logger = logging.getLogger(__name__)

DOCKER_USER_ID = 1000  # the sandbox user (docker/Dockerfile.sandbox)


def remove_tree(path: str | Path) -> None:
    """Delete a directory tree, also on Windows, where git's pack files are read-only (#217).

    `shutil.rmtree` stops with `[WinError 5] Access denied` on them; clearing the read-only bit and retrying fixes it.
    """
    def clear_and_retry(func, failed_path, _exc_info):
        os.chmod(failed_path, stat.S_IWRITE)
        func(failed_path)

    shutil.rmtree(path, onerror=clear_and_retry)

DEFAULT_STAGING_DIR = Path(".sandbox_staging")
DEFAULT_CANDIDATE_SCRIPTS = [
    "reproduce.py",
    "main.py",
    "run.py",
    "evaluate.py",
    "eval.py",
    "benchmark.py",
    "test.py",
    "demo.py",
]


@dataclass
class DependencyManifest:
    """Analysis result of repository dependency definitions."""

    requirements_files: list[str] = field(default_factory=list)
    has_pyproject: bool = False
    has_setup_py: bool = False
    has_conda_env: bool = False
    conda_env_files: list[str] = field(default_factory=list)
    parsed_dependencies: list[str] = field(default_factory=list)
    install_strategy: str = "pip_offline"


@dataclass
class StagedRepo:
    """Metadata describing a staged repository ready for sandboxed execution."""

    paper_id: str
    source: str
    staged_path: Path
    commit_hash: str
    manifest: DependencyManifest
    candidate_scripts: list[str] = field(default_factory=list)
    bundle_dir: Path | None = None
    # Wheels built from source in the build phase (#193), added to the bundle
    built_dir: Path | None = None


def gpu_summary(requested: str, meta: dict[str, Any]) -> dict[str, Any]:
    """Whether the run asked for a GPU, which GPUs it could see, and whether GPU memory use rose during the run."""
    devices = meta.get("gpu_devices") or []
    peak = meta.get("gpu_peak_memory_used_mib")
    before = max((d.get("memory_used_before_mib", 0) for d in devices), default=None)
    used = None if peak is None or before is None else peak > before
    return {"requested": requested or None, "available": bool(devices), "devices": devices,
            "peak_memory_used_mib": peak, "used": used}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


class RepoStager:
    """Clones/copies target paper repositories, analyzes dependencies,
    bundles wheels for offline execution, and runs them inside the sandbox.
    """

    def __init__(self, staging_root: str | Path | None = None, bundle_in_docker: bool = False):
        self.staging_root = Path(staging_root or DEFAULT_STAGING_DIR).resolve()
        self.staging_root.mkdir(parents=True, exist_ok=True)
        # Run `pip download` inside the paper's sandbox image instead of on the host (#215): pip evaluates
        # environment markers (platform_system, python_version) where it runs, so only the container gives the
        # right answer for the sandbox's Linux and Python. Binary wheels only: no package code runs.
        self.bundle_in_docker = bundle_in_docker

    def is_git_url(self, source: str) -> bool:
        """Determine whether source string is a remote Git repository URL."""
        source_clean = source.strip().lower()
        return (
            source_clean.startswith(("http://", "https://", "git@"))
            or source_clean.endswith(".git")
        )

    def stage_repository(
        self,
        paper_id: str,
        source: str,
        commit_or_tag: str | None = None,
        clean: bool = True,
    ) -> StagedRepo:
        """Clone remote git repo or copy local directory into an isolated staging directory."""
        target_dir = self.staging_root / paper_id
        if clean and target_dir.exists():
            remove_tree(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        commit_hash = "unknown"

        if self.is_git_url(source):
            # Clone remote repository
            clone_cmd = ["git", "clone"]
            if not commit_or_tag:
                clone_cmd.extend(["--depth", "1"])
            clone_cmd.extend([source, str(target_dir)])

            try:
                subprocess.run(clone_cmd, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
            except (subprocess.SubprocessError, OSError) as exc:
                raise RuntimeError(f"Failed to clone repository from '{source}': {exc}") from exc

            if commit_or_tag:
                try:
                    subprocess.run(
                        ["git", "checkout", commit_or_tag],
                        cwd=str(target_dir),
                        check=True,
                        capture_output=True,
                        text=True, encoding="utf-8", errors="replace",
                        timeout=30,
                    )
                except (subprocess.SubprocessError, OSError) as exc:
                    raise RuntimeError(f"Failed to checkout commit/tag '{commit_or_tag}': {exc}") from exc

            # Read resolved HEAD commit
            try:
                res = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=str(target_dir),
                    capture_output=True,
                    text=True, encoding="utf-8", errors="replace",
                    timeout=10, check=False,
                )
                if res.returncode == 0:
                    commit_hash = res.stdout.strip()
            except (subprocess.SubprocessError, OSError):
                pass

        else:
            # Source is a local directory
            source_path = Path(source).resolve()
            if not source_path.exists() or not source_path.is_dir():
                raise FileNotFoundError(f"Local source directory not found: {source_path}")

            # Copy contents to target_dir
            for item in source_path.iterdir():
                dest = target_dir / item.name
                if item.is_dir():
                    shutil.copytree(item, dest, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, dest)

            # Check if source has git commit
            try:
                res = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=str(source_path),
                    capture_output=True,
                    text=True, encoding="utf-8", errors="replace",
                    timeout=10, check=False,
                )
                if res.returncode == 0:
                    commit_hash = res.stdout.strip()
            except (subprocess.SubprocessError, OSError):
                pass

        manifest = self.analyze_dependencies(target_dir)
        candidate_scripts = self.detect_candidate_scripts(target_dir)

        return StagedRepo(
            paper_id=paper_id,
            source=source,
            staged_path=target_dir,
            commit_hash=commit_hash,
            manifest=manifest,
            candidate_scripts=candidate_scripts,
        )

    def analyze_dependencies(self, repo_dir: Path) -> DependencyManifest:
        """Identify manifest files and extract requirements."""
        manifest = DependencyManifest()

        # Check for requirements.txt variations
        for req_file in repo_dir.glob("*requirements*.txt"):
            rel_name = req_file.name
            manifest.requirements_files.append(rel_name)
            manifest.parsed_dependencies.extend(self._parse_requirements_file(req_file))

        if (repo_dir / "pyproject.toml").exists():
            manifest.has_pyproject = True
        if (repo_dir / "setup.py").exists():
            manifest.has_setup_py = True
        manifest.conda_env_files = find_conda_env_files(repo_dir)
        manifest.has_conda_env = bool(manifest.conda_env_files)

        # Deduplicate dependencies
        manifest.parsed_dependencies = sorted(set(manifest.parsed_dependencies))

        return manifest

    def _parse_requirements_file(self, file_path: Path) -> list[str]:
        """Parse requirement lines ignoring comments, flags and local file paths."""
        deps: list[str] = []
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith(("#", "-")):
                    continue
                # Split off environment markers or inline comments
                line = line.split(";")[0].split("#")[0].strip()
                # Extract package name part
                pkg_match = re.match(r"^([A-Za-z0-9_\-\.]+)", line)
                if pkg_match:
                    deps.append(pkg_match.group(1).lower())
        except OSError as exc:
            logger.warning("Error reading requirements file %s: %s", file_path, exc)
        return deps

    def detect_candidate_scripts(self, repo_dir: Path) -> list[str]:
        """Detect potential target scripts in repository root and immediate subdirs."""
        detected = []
        for candidate in DEFAULT_CANDIDATE_SCRIPTS:
            target = repo_dir / candidate
            if target.exists() and target.is_file():
                detected.append(candidate)

        # Also search for any .py file directly under repo_dir if none detected
        if not detected:
            for py_file in sorted(repo_dir.glob("*.py")):
                if not py_file.name.startswith("__"):
                    detected.append(py_file.name)

        return detected

    def bundle_dependencies(
        self,
        staged: StagedRepo,
        timeout: int = 180,
        python_version: str = DEFAULT_PYTHON_VERSION,
        extra_requirements: list[str] | None = None,
        constraints: list[str] | None = None,
    ) -> dict[str, Any]:
        """Download wheel archives for offline installation inside network-isolated sandbox.

        Run setup options (#193): `extra_requirements` are resolved together with the repository's requirements,
        `constraints` (pip constraints) limit versions the repository leaves open, and wheels built in the build
        phase (`staged.built_dir`) are offered to the resolver and copied into the bundle.
        """
        bundle_dir = self.staging_root / f"{staged.paper_id}_packages"
        bundle_dir.mkdir(parents=True, exist_ok=True)
        staged.bundle_dir = bundle_dir
        options = self._run_setup_options(staged, bundle_dir, extra_requirements, constraints)

        if not staged.manifest.requirements_files and staged.manifest.conda_env_files:
            report = self._bundle_conda_env(staged, bundle_dir, timeout, python_version, options)
            return self._with_extras(report, staged, bundle_dir, timeout, python_version, options, extra_requirements)
        if not staged.manifest.requirements_files:
            return {
                "status": "SKIPPED",
                "message": "No requirements.txt found to bundle",
                "wheel_count": 0,
                "bundle_dir": str(bundle_dir),
            }

        req_paths = [staged.staged_path / name for name in staged.manifest.requirements_files]
        cmd = self._pip_download_command(bundle_dir, python_version) + options
        for req in req_paths:
            cmd.extend(["-r", str(req)])
        cmd.extend(extra_requirements or [])

        try:
            res = self._run_pip(cmd, timeout)
            needs_sdist_build: list[dict[str, str]] = []
            if res.returncode != 0:
                needs_sdist_build = self._find_requirements_without_wheels(req_paths, bundle_dir, timeout, python_version)
            self._copy_built_wheels(staged, bundle_dir)
            wheels = list(bundle_dir.glob("*.whl"))
            return {
                "status": "SUCCESS" if res.returncode == 0 else "PARTIAL",
                "python_version": python_version,
                "extra_requirements": list(extra_requirements or []),
                "constraints": list(constraints or []),
                "built_wheels": sorted(p.name for p in (staged.built_dir or Path("/nonexistent")).glob("*.whl")),
                "wheel_count": len(wheels),
                "bundle_dir": str(bundle_dir),
                "requirements_files": list(staged.manifest.requirements_files),
                "needs_sdist_build": needs_sdist_build,
                # Parsed from the full output: pip prints the ERROR line to stderr and the cause lines to stdout, and
                # the stored excerpts below are cut (#160)
                "dependency_conflicts": name_requirement_lines(
                    parse_dependency_conflicts((res.stderr or "") + "\n" + (res.stdout or "")), staged.staged_path
                ),
                "stdout": res.stdout[-1000:] if res.stdout else "",
                "stderr": res.stderr[-1000:] if res.stderr else "",
            }
        except (subprocess.SubprocessError, OSError) as exc:
            return {
                "status": "FAILED",
                "message": f"Dependency bundling failed: {exc}",
                "wheel_count": 0,
                "bundle_dir": str(bundle_dir),
                "needs_sdist_build": [],
            }

    def _bundle_conda_env(
        self, staged: StagedRepo, bundle_dir: Path, timeout: int, python_version: str, options: list[str] | None = None
    ) -> dict[str, Any]:
        """Bundle a conda-only repository through its pinned Python packages (#159; src/sandbox/conda_env.py).

        Each converted requirement is downloaded alone with --no-deps: the environment file already pins every
        dependency. Requirements without a wheel for the sandbox's Python and platform are reported as conda_only.
        """
        conversions = [convert_env_file(staged.staged_path / name) for name in staged.manifest.conda_env_files]
        requirements = list(dict.fromkeys(r for c in conversions for r in c.requirements))
        downloaded: list[str] = []
        conda_only: list[dict[str, str]] = []
        for requirement in requirements:
            cmd = self._pip_download_command(bundle_dir, python_version) + (options or []) + ["--no-deps", requirement]
            try:
                res = self._run_pip(cmd, timeout)
            except (subprocess.SubprocessError, OSError) as exc:
                conda_only.append({"requirement": requirement, "reason": str(exc)})
                continue
            if res.returncode == 0:
                downloaded.append(requirement)
            else:
                lines = [line for line in (res.stderr or "").splitlines() if line.strip()]
                conda_only.append({"requirement": requirement,
                                   "reason": lines[-1] if lines else f"pip exited {res.returncode}"})
        self._copy_built_wheels(staged, bundle_dir)
        env_versions = sorted({c.python_version for c in conversions if c.python_version})
        status = "SUCCESS" if requirements and not conda_only else ("PARTIAL" if downloaded else "FAILED")
        return {
            "status": status,
            "source": "conda_env",
            "python_version": python_version,
            "env_python_versions": env_versions,
            "conda_env_files": list(staged.manifest.conda_env_files),
            "converted": len(requirements),
            "downloaded": downloaded,
            "conda_only": conda_only,
            "skipped": [s for c in conversions for s in c.skipped],
            "wheel_count": len(list(bundle_dir.glob("*.whl"))),
            "bundle_dir": str(bundle_dir),
            "needs_sdist_build": [],
        }

    @staticmethod
    def _run_setup_options(staged: StagedRepo, bundle_dir: Path, extra_requirements: list[str] | None,
                           constraints: list[str] | None) -> list[str]:
        """pip options for the run setup: built wheels as find-links, constraints as a file (#193)."""
        options: list[str] = []
        if staged.built_dir and staged.built_dir.is_dir():
            # Wheels built in the sandbox carry the plain linux_x86_64 tag (no auditwheel), so allow that platform
            options += ["--find-links", str(staged.built_dir), "--platform", "linux_x86_64"]
        if constraints:
            path = bundle_dir.parent / f"{staged.paper_id}_constraints.txt"
            path.write_text("\n".join(constraints) + "\n", encoding="utf-8")
            options += ["-c", str(path)]
        return options

    @staticmethod
    def _copy_built_wheels(staged: StagedRepo, bundle_dir: Path) -> None:
        for wheel in (staged.built_dir.glob("*.whl") if staged.built_dir and staged.built_dir.is_dir() else []):
            shutil.copy2(wheel, bundle_dir / wheel.name)

    def _with_extras(self, report: dict[str, Any], staged: StagedRepo, bundle_dir: Path, timeout: int,
                     python_version: str, options: list[str], extra_requirements: list[str] | None) -> dict[str, Any]:
        """Download the run setup's extra requirements (with their dependencies) for a conda-only repository."""
        report["extra_requirements"] = list(extra_requirements or [])
        if not extra_requirements:
            return report
        cmd = self._pip_download_command(bundle_dir, python_version) + options + list(extra_requirements)
        try:
            res = self._run_pip(cmd, timeout)
            ok = res.returncode == 0
            reason = "" if ok else ((res.stderr or "").strip().splitlines() or [f"pip exited {res.returncode}"])[-1]
        except (subprocess.SubprocessError, OSError) as exc:
            ok, reason = False, str(exc)
        if not ok:
            report["status"] = "PARTIAL"
            report["extra_requirements_error"] = reason
        report["wheel_count"] = len(list(bundle_dir.glob("*.whl")))
        return report

    def build_from_source(self, staged: StagedRepo, build: dict[str, Any], config: SandboxConfig) -> dict[str, Any]:
        """Build phase of a run setup (#193): sdists and/or the repository itself, built into wheels in the sandbox.

        The sdists are downloaded on the host from the PyPI JSON API (verified, never run); build requirements are
        downloaded as binary wheels. The wheels built in the sandbox are kept in `staged.built_dir` for bundling.
        """
        inputs = self.staging_root / f"{staged.paper_id}_build_inputs"
        if inputs.exists():
            remove_tree(inputs)
        inputs.mkdir(parents=True)
        sdists = [download_sdist(req, inputs) for req in build.get("sdists", [])]
        build_requirements = list(build.get("build_requirements", []))
        if build_requirements:
            cmd = self._pip_download_command(inputs, config.python_version) + build_requirements
            res = self._run_pip(cmd, 600)
            if res.returncode != 0:
                return {"status": "FAILED", "stage": "download build requirements",
                        "error": (res.stderr or "").strip()[-1000:]}
        targets = [f"/workspace/packages/{p.name}" for p in sdists]
        if build.get("from_repo"):
            targets.append("/workspace/repo")
        result = DockerSandboxRunner(config).build_wheels(
            staged.paper_id, staged.staged_path, inputs, targets, build_requirements, bool(build.get("from_repo")))
        built = self.staging_root / f"{staged.paper_id}_built"
        if built.exists():
            remove_tree(built)
        built.mkdir(parents=True)
        for wheel in result["wheels"]:
            shutil.copy2(wheel, built / Path(wheel).name)
        staged.built_dir = built
        result["sdists"] = [p.name for p in sdists]
        return result

    def _run_pip(self, cmd: list[str], timeout: int) -> subprocess.CompletedProcess:
        """Run a `pip download` command: on the host, or inside the paper's sandbox image (`bundle_in_docker`)."""
        if self.bundle_in_docker:
            cmd = self._docker_pip_command(cmd)
        return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, check=False)

    def _docker_pip_command(self, cmd: list[str]) -> list[str]:
        """Rewrite a host `pip download` command to run inside the sandbox image of its Python version (#215).

        The host's interpreter and the platform flags are dropped (the container is the target, so pip picks its own
        tags and evaluates markers for it), and the paths of the staging directory are mapped to /staging. The
        container has the network on for this step only, runs as the sandbox user, and downloads binary wheels only.
        """
        python_version = DEFAULT_PYTHON_VERSION
        args: list[str] = []
        skip_next = False
        translate_next = False
        for i, arg in enumerate(cmd[4:], start=4):  # cmd[:4] is [python, -m, pip, download]
            if skip_next:
                skip_next = False
                continue
            if arg in ("--platform", "--implementation"):
                skip_next = True
                continue
            if arg == "--python-version":
                python_version = cmd[i + 1]
                skip_next = True
                continue
            if translate_next:
                arg = self._to_container_path(arg)
                translate_next = False
            elif arg in ("-d", "-r", "-c", "--find-links"):
                translate_next = True
            args.append(arg)
        self.staging_root.chmod(0o777)  # written by the sandbox user (uid 1000) on hosts with another uid
        return [
            "docker", "run", "--rm", "--user", f"{DOCKER_USER_ID}:{DOCKER_USER_ID}",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
            "-v", f"{self.staging_root}:/staging", "-w", "/staging",
            "-e", "PIP_CACHE_DIR=/staging/.pip-cache", "-e", "PIP_DISABLE_PIP_VERSION_CHECK=1",
            "--entrypoint", "python", image_for(python_version), "-m", "pip", "download", *args,
        ]

    def _to_container_path(self, arg: str) -> str:
        try:
            relative = Path(arg).resolve().relative_to(self.staging_root)
        except ValueError as exc:
            raise ValueError(f"path outside the staging directory cannot be used in the bundling container: {arg}") from exc
        return "/staging/" + relative.as_posix() if relative.parts else "/staging"

    @staticmethod
    def _pip_download_command(bundle_dir: Path, python_version: str = DEFAULT_PYTHON_VERSION) -> list[str]:
        # Wheels are installed in the Linux sandbox image (CPython `python_version`, glibc), not on the host, so
        # download for that platform. Binary wheels only: installing a wheel runs no package code,
        # while building an sdist would execute its setup.py on the host.
        return [
            sys.executable, "-m", "pip", "download",
            "-d", str(bundle_dir),
            "--only-binary=:all:",
            "--platform", "manylinux_2_28_x86_64",
            "--platform", "manylinux2014_x86_64",
            "--python-version", python_version,
            "--implementation", "cp",
        ]

    def _find_requirements_without_wheels(
        self, req_paths: list[Path], bundle_dir: Path, timeout: int, python_version: str = DEFAULT_PYTHON_VERSION
    ) -> list[dict[str, str]]:
        """Probe each requirement alone (binary-only, --no-deps) to name the ones that have no wheel.

        They are reported as NEEDS_SDIST_BUILD instead of being built on the host.
        """
        flagged: list[dict[str, str]] = []
        for req_path in req_paths:
            for requirement in self._requirement_lines(req_path):
                probe = self._pip_download_command(bundle_dir, python_version) + ["--no-deps", requirement]
                try:
                    res = self._run_pip(probe, timeout)
                except (subprocess.SubprocessError, OSError) as exc:
                    flagged.append({"requirement": requirement, "status": "NEEDS_SDIST_BUILD", "reason": str(exc)})
                    continue
                if res.returncode != 0:
                    lines = [line for line in (res.stderr or "").splitlines() if line.strip()]
                    flagged.append({
                        "requirement": requirement,
                        "status": "NEEDS_SDIST_BUILD",
                        "reason": lines[-1] if lines else f"pip exited {res.returncode}",
                    })
        return flagged

    def _requested_requirements(self, staged: StagedRepo) -> list[str]:
        """What the repository asks for: its requirement files, or the pins of its conda environment file."""
        if staged.manifest.requirements_files:
            return [line for name in staged.manifest.requirements_files
                    for line in self._requirement_lines(staged.staged_path / name)]
        return [r for name in staged.manifest.conda_env_files
                for r in convert_env_file(staged.staged_path / name).requirements]

    @staticmethod
    def _requirement_lines(req_path: Path) -> list[str]:
        """Requirement specifiers of a requirements file, without comments and pip options."""
        lines: list[str] = []
        for raw in req_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.split(" #")[0].strip()
            if line and not line.startswith(("#", "-")):
                lines.append(line)
        return lines

    def execute_staged(
        self,
        staged: StagedRepo,
        target_script: str | None = None,
        script_args: list[str] | None = None,
        config: SandboxConfig | None = None,
        command: list[str] | None = None,
    ) -> dict[str, Any]:
        """Run staged code inside the secure sandbox and return a comprehensive execution summary."""
        # Resolve target script
        if not target_script:
            if staged.candidate_scripts:
                target_script = staged.candidate_scripts[0]
            else:
                raise ValueError(f"No executable script specified or found in staged repo: {staged.staged_path}")

        config = config or SandboxConfig()
        runner = DockerSandboxRunner(config=config)
        packages_dir = staged.bundle_dir if (staged.bundle_dir and staged.bundle_dir.exists()) else None

        result: SandboxExecutionResult = runner.run(
            paper_id=staged.paper_id,
            repo_dir=staged.staged_path,
            target_script=target_script,
            script_args=script_args,
            packages_dir=packages_dir,
            command=command,
        )

        # Collect generated files and metadata from output_dir
        generated_files = []
        meta = {}
        meta_error: str | None = None
        if result.output_dir.exists():
            generated_files = [f.name for f in result.output_dir.iterdir() if f.is_file()]
            meta_file = result.output_dir / "execution_meta.json"
            if meta_file.exists():
                try:
                    meta = json.loads(meta_file.read_text(encoding="utf-8"))
                except (OSError, ValueError) as exc:
                    meta_error = f"Unreadable execution_meta.json: {exc}"
                    logger.warning(meta_error)

        # Collect structured results
        report: dict[str, Any] = {
            "paper_id": staged.paper_id,
            "source": staged.source,
            "commit_hash": staged.commit_hash,
            "target_script": target_script,
            # Run setup (#166): the command when it replaces the target script, and the sandbox options
            "command": command,
            "working_dir": config.working_dir,
            "writable_repo": config.writable_repo,
            "data_mounts": sorted(config.data_mounts),
            # Sandbox image and its Python version (#158)
            "python_version": config.python_version,
            "image": config.image_name,
            "status": result.status,
            "exit_code": result.exit_code,
            "duration_seconds": round(result.duration_seconds, 3),
            "docker_used": result.docker_used,
            "isolated": result.isolated,
            "error_message": result.error_message,
            "output_dir": str(result.output_dir),
            "generated_files": generated_files,
            # Top level so scoring (Tier 1: dependencies installed) does not have to dig into `meta`.
            # UNKNOWN when the container wrote no execution metadata.
            "dependency_install_status": meta.get("dependency_install_status", "UNKNOWN"),
            # GPU (#169): requested, visible inside the container, and used (GPU memory rose during the run)
            "gpu": gpu_summary(config.gpus, meta),
            # Conflicts named from the install phase log, if pip could not resolve the requirements (#160)
            "dependency_conflicts": name_requirement_lines(
                parse_dependency_conflicts(_read_text(result.output_dir / "install.log")), staged.staged_path),
            "meta": meta,
            # What was installed, and how it compares with what the repository asks for (#161)
            "installed_packages": (installed := read_installed(result.output_dir / "installed_packages.json")),
            "requested_vs_installed": requested_vs_installed(self._requested_requirements(staged), installed),
            "stdout_preview": result.stdout[:2000] if result.stdout else "",
            "stderr_preview": result.stderr[:2000] if result.stderr else "",
        }
        if meta_error:
            report["meta_error"] = meta_error

        # Extract empirical metrics from output_dir (files and logs)
        extractor = MetricExtractor()
        try:
            extracted_metrics = extractor.extract_from_run_dir(result.output_dir)
            if extracted_metrics:
                report["metrics"] = extracted_metrics
        except Exception as exc:  # noqa: BLE001 - extraction errors are recorded in the run report, never fatal
            report["metrics_extraction_error"] = str(exc)

        # Persist complete run report
        report_file = result.output_dir / "run_report.json"
        try:
            report_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
            report["run_report_path"] = str(report_file)
        except OSError as exc:
            logger.warning("Could not persist run_report.json: %s", exc)

        return report
