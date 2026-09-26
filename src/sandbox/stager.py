"""Repository staging, dependency bundling, and execution orchestration for isolated sandboxes."""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from src.sandbox.runner import (
    DockerSandboxRunner,
    ProcessSandboxRunner,
    SandboxConfig,
    SandboxExecutionResult,
)
from src.metric_extractor import MetricExtractor

logger = logging.getLogger(__name__)

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

    requirements_files: List[str] = field(default_factory=list)
    has_pyproject: bool = False
    has_setup_py: bool = False
    has_conda_env: bool = False
    parsed_dependencies: List[str] = field(default_factory=list)
    install_strategy: str = "pip_offline"


@dataclass
class StagedRepo:
    """Metadata describing a staged repository ready for sandboxed execution."""

    paper_id: str
    source: str
    staged_path: Path
    commit_hash: str
    manifest: DependencyManifest
    candidate_scripts: List[str] = field(default_factory=list)
    bundle_dir: Optional[Path] = None


class RepoStager:
    """Clones/copies target paper repositories, analyzes dependencies,
    bundles wheels for offline execution, and runs them inside the sandbox.
    """

    def __init__(self, staging_root: Optional[Union[str, Path]] = None):
        self.staging_root = Path(staging_root or DEFAULT_STAGING_DIR).resolve()
        self.staging_root.mkdir(parents=True, exist_ok=True)

    def is_git_url(self, source: str) -> bool:
        """Determine whether source string is a remote Git repository URL."""
        source_clean = source.strip().lower()
        return (
            source_clean.startswith("http://")
            or source_clean.startswith("https://")
            or source_clean.startswith("git@")
            or source_clean.endswith(".git")
        )

    def stage_repository(
        self,
        paper_id: str,
        source: str,
        commit_or_tag: Optional[str] = None,
        clean: bool = True,
    ) -> StagedRepo:
        """Clone remote git repo or copy local directory into an isolated staging directory."""
        target_dir = self.staging_root / paper_id
        if clean and target_dir.exists():
            shutil.rmtree(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        commit_hash = "unknown"

        if self.is_git_url(source):
            # Clone remote repository
            clone_cmd = ["git", "clone"]
            if not commit_or_tag:
                clone_cmd.extend(["--depth", "1"])
            clone_cmd.extend([source, str(target_dir)])

            try:
                subprocess.run(clone_cmd, check=True, capture_output=True, text=True, timeout=120)
            except (subprocess.SubprocessError, OSError) as exc:
                raise RuntimeError(f"Failed to clone repository from '{source}': {exc}") from exc

            if commit_or_tag:
                try:
                    subprocess.run(
                        ["git", "checkout", commit_or_tag],
                        cwd=str(target_dir),
                        check=True,
                        capture_output=True,
                        text=True,
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
                    text=True,
                    timeout=10,
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
                    text=True,
                    timeout=10,
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
        if (repo_dir / "environment.yml").exists() or (repo_dir / "environment.yaml").exists():
            manifest.has_conda_env = True

        # Deduplicate dependencies
        manifest.parsed_dependencies = sorted(list(set(manifest.parsed_dependencies)))

        return manifest

    def _parse_requirements_file(self, file_path: Path) -> List[str]:
        """Parse requirement lines ignoring comments, flags and local file paths."""
        deps: List[str] = []
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("-"):
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

    def detect_candidate_scripts(self, repo_dir: Path) -> List[str]:
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
    ) -> Dict[str, Any]:
        """Download wheel archives for offline installation inside network-isolated sandbox."""
        bundle_dir = self.staging_root / f"{staged.paper_id}_packages"
        bundle_dir.mkdir(parents=True, exist_ok=True)
        staged.bundle_dir = bundle_dir

        if not staged.manifest.requirements_files:
            return {
                "status": "SKIPPED",
                "message": "No requirements.txt found to bundle",
                "wheel_count": 0,
                "bundle_dir": str(bundle_dir),
            }

        primary_req = staged.staged_path / staged.manifest.requirements_files[0]
        cmd = [
            "pip",
            "download",
            "-r",
            str(primary_req),
            "-d",
            str(bundle_dir),
            "--prefer-binary",
        ]

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            wheels = list(bundle_dir.glob("*.whl")) + list(bundle_dir.glob("*.tar.gz"))
            return {
                "status": "SUCCESS" if res.returncode == 0 else "PARTIAL",
                "wheel_count": len(wheels),
                "bundle_dir": str(bundle_dir),
                "stdout": res.stdout[-1000:] if res.stdout else "",
                "stderr": res.stderr[-1000:] if res.stderr else "",
            }
        except (subprocess.SubprocessError, OSError) as exc:
            return {
                "status": "FAILED",
                "message": f"Dependency bundling failed: {exc}",
                "wheel_count": 0,
                "bundle_dir": str(bundle_dir),
            }

    def execute_staged(
        self,
        staged: StagedRepo,
        target_script: Optional[str] = None,
        script_args: Optional[List[str]] = None,
        config: Optional[SandboxConfig] = None,
    ) -> Dict[str, Any]:
        """Run staged code inside the secure sandbox and return a comprehensive execution summary."""
        # Resolve target script
        if not target_script:
            if staged.candidate_scripts:
                target_script = staged.candidate_scripts[0]
            else:
                raise ValueError(f"No executable script specified or found in staged repo: {staged.staged_path}")

        runner = DockerSandboxRunner(config=config)
        packages_dir = staged.bundle_dir if (staged.bundle_dir and staged.bundle_dir.exists()) else None

        result: SandboxExecutionResult = runner.run(
            paper_id=staged.paper_id,
            repo_dir=staged.staged_path,
            target_script=target_script,
            script_args=script_args,
            packages_dir=packages_dir,
        )

        # Collect generated files and metadata from output_dir
        generated_files = []
        meta = {}
        meta_error: Optional[str] = None
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
        report: Dict[str, Any] = {
            "paper_id": staged.paper_id,
            "source": staged.source,
            "commit_hash": staged.commit_hash,
            "target_script": target_script,
            "status": result.status,
            "exit_code": result.exit_code,
            "duration_seconds": round(result.duration_seconds, 3),
            "docker_used": result.docker_used,
            "isolated": result.isolated,
            "error_message": result.error_message,
            "output_dir": str(result.output_dir),
            "generated_files": generated_files,
            "meta": meta,
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
        except Exception as exc:
            report["metrics_extraction_error"] = str(exc)

        # Persist complete run report
        report_file = result.output_dir / "run_report.json"
        try:
            report_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
            report["run_report_path"] = str(report_file)
        except OSError as exc:
            logger.warning("Could not persist run_report.json: %s", exc)

        return report
