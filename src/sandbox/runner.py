"""Sandbox Execution Runners for Repro Radar.

Implements:
- DockerSandboxRunner: Production-grade container isolation with strict security parameters:
  * Network isolation (--network none)
  * Read-only root filesystem (--read-only)
  * In-memory tmpfs (/tmp:rw,noexec,nosuid,size=64m)
  * Hardware resource quotas (--cpus, --memory, --memory-swap, --pids-limit)
  * Privilege escalation prevention (--security-opt no-new-privileges:true)
  * Non-root user execution (--user 1000:1000)
- ProcessSandboxRunner: Unisolated local subprocess runner (timeouts and output capture only).
  DockerSandboxRunner never falls back to it silently: without Docker it raises
  SandboxUnavailableError unless SandboxConfig.allow_unsafe_local is set.
"""

import json
import logging
import os
import posixpath
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.config import DEFAULT_TIMEOUT_SECONDS, SANDBOX_RUNS_DIR

logger = logging.getLogger(__name__)


class SandboxUnavailableError(RuntimeError):
    """Raised when isolated execution is impossible and unisolated execution was not opted into."""


# Docker detection (#164): `docker info` attempts, seconds per attempt, and the wait between attempts.
# Worst case before reporting an unresponsive daemon: 3 x 15 s + 2 x 2 s = 49 s.
DOCKER_DETECT_ATTEMPTS = 3
DOCKER_DETECT_TIMEOUT = 15
DOCKER_DETECT_WAIT_SECONDS = 2.0

# Python versions with a sandbox image (docker/Dockerfile.sandbox, build arg PYTHON_VERSION; #158).
SUPPORTED_PYTHON_VERSIONS = ("3.8", "3.9", "3.11")
DEFAULT_PYTHON_VERSION = "3.11"


def image_for(python_version: str) -> str:
    """Image tag of the sandbox for a Python version (3.11 keeps the historic `latest` tag)."""
    if python_version not in SUPPORTED_PYTHON_VERSIONS:
        raise ValueError(f"no sandbox image for Python {python_version}; supported: {SUPPORTED_PYTHON_VERSIONS}")
    return "repro-radar-sandbox:latest" if python_version == DEFAULT_PYTHON_VERSION else f"repro-radar-sandbox:py{python_version}"


@dataclass
class SandboxConfig:
    """Configuration parameters for isolated execution."""
    python_version: str = DEFAULT_PYTHON_VERSION
    image_name: str = ""  # empty: the image of python_version (image_for)
    cpus: float = 2.0
    memory_limit: str = "8g"
    memory_swap: str = "8g"
    pids_limit: int = 100
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    network_isolated: bool = True
    read_only_root: bool = True
    tmpfs_tmp_size: str = "64m"
    tmpfs_home_size: str = "2048m"
    user_id: int = 1000
    group_id: int = 1000
    env_vars: dict[str, str] = field(default_factory=dict)
    # Run setup of a paper (#166). Working directory relative to the repository root ('' = the root).
    working_dir: str = ""
    # Run on a writable per-run copy of the repository (for papers that write next to their own files).
    writable_repo: bool = False
    # Read-only data mounts: container path (absolute, or relative to /workspace/repo) -> host directory.
    data_mounts: dict[str, str] = field(default_factory=dict)
    # Run on the host without isolation when Docker is unavailable. Only for code you trust.
    allow_unsafe_local: bool = False

    def __post_init__(self) -> None:
        image = image_for(self.python_version)  # also validates the version
        if not self.image_name:
            self.image_name = image
        self.working_dir = repo_relative(self.working_dir, "working_dir")
        self.data_mounts = {container_data_path(target): host for target, host in self.data_mounts.items()}


def repo_relative(path: str, what: str) -> str:
    """A normalized path inside the repository; refuses absolute paths and '..' (#166)."""
    norm = posixpath.normpath(path.replace("\\", "/")) if path else ""
    if norm in ("", "."):
        return ""
    if norm.startswith(("/", "..")):
        raise ValueError(f"{what} must stay inside the repository: {path!r}")
    return norm


# Container paths a data mount may target: inside the repository or the sandbox home (#166).
DATA_MOUNT_ROOTS = ("/workspace/repo/", "/workspace/home/")


def container_data_path(target: str) -> str:
    """Absolute container path of a data mount; a relative target is relative to /workspace/repo."""
    if not target.startswith("/"):
        return "/workspace/repo/" + repo_relative(target, "data mount target")
    norm = posixpath.normpath(target)
    if not norm.startswith(DATA_MOUNT_ROOTS):
        raise ValueError(f"data mount target must be under {DATA_MOUNT_ROOTS}: {target!r}")
    return norm


@dataclass
class SandboxExecutionResult:
    """Structured outcome from a sandbox execution run."""
    status: str  # 'COMPLETED', 'FAILED', 'TIMEOUT', 'OOM_KILLED', 'SKIPPED'
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    command_executed: list[str]
    docker_used: bool
    output_dir: Path
    error_message: str | None = None
    isolated: bool = False  # True only when the code ran inside the Docker sandbox

    def to_dict(self) -> dict[str, Any]:
        """Convert execution result to serializable dictionary."""
        return {
            "status": self.status,
            "exit_code": self.exit_code,
            "duration_seconds": round(self.duration_seconds, 3),
            "command_executed": self.command_executed,
            "docker_used": self.docker_used,
            "isolated": self.isolated,
            "output_dir": str(self.output_dir),
            "error_message": self.error_message,
        }


class DockerSandboxRunner:
    """Manages containerized execution runs with strict sandboxing."""

    def __init__(self, config: SandboxConfig | None = None):
        self.config = config or SandboxConfig()

    @staticmethod
    def is_docker_available(attempts: int = DOCKER_DETECT_ATTEMPTS, timeout: int = DOCKER_DETECT_TIMEOUT,
                            wait_seconds: float = DOCKER_DETECT_WAIT_SECONDS) -> bool:
        """Check whether the Docker CLI and daemon are operational.

        A missing Docker CLI is reported at once. A daemon that does not answer `docker info` in time, or answers
        with an error, is asked again: on slow CI runners the first answer can take longer than a few seconds
        (#164). Only a daemon that stays unavailable for every attempt is reported as unavailable.
        """
        if not shutil.which("docker"):
            return False
        for attempt in range(attempts):
            try:
                res = subprocess.run(["docker", "info"], capture_output=True, text=True, timeout=timeout, check=False)
                if res.returncode == 0:
                    return True
            except (subprocess.SubprocessError, OSError):
                pass
            if attempt < attempts - 1:
                time.sleep(wait_seconds)
        return False

    def build_docker_command(
        self,
        repo_dir: str | Path,
        output_dir: str | Path,
        command: list[str],
        packages_dir: str | Path | None = None,
        deps_dir: str | Path | None = None,
        deps_writable: bool = False,
        extra_env: dict[str, str] | None = None,
    ) -> list[str]:
        """Construct the security-hardened `docker run` command with all isolation flags.

        `deps_dir` is mounted at /workspace/deps: writable only for the dependency install phase,
        read-only (but executable, so compiled extensions load) for the paper run.
        """
        repo_path = Path(repo_dir).resolve()
        output_path = Path(output_dir).resolve()

        docker_cmd = [
            "docker", "run", "--rm",
        ]

        # 1. Network Isolation
        if self.config.network_isolated:
            docker_cmd.extend(["--network", "none"])

        # 2. Filesystem Security (read-only root + writable in-memory tmpfs)
        if self.config.read_only_root:
            docker_cmd.append("--read-only")
        docker_cmd.extend([
            "--tmpfs", f"/tmp:rw,noexec,nosuid,size={self.config.tmpfs_tmp_size}",
            # Writable scratch home owned by the sandbox user (a plain tmpfs is root-owned). Kept noexec:
            # paper code can write here but never execute what it wrote. Dependencies go to /workspace/deps.
            "--tmpfs",
            (
                f"/workspace/home:rw,noexec,nosuid,size={self.config.tmpfs_home_size},"
                f"uid={self.config.user_id},gid={self.config.group_id}"
            ),
        ])

        # 3. Privilege Drop
        docker_cmd.extend([
            "--security-opt", "no-new-privileges:true",
            "--user", f"{self.config.user_id}:{self.config.group_id}",
        ])

        # 4. Resource & Process Quotas
        docker_cmd.extend([
            f"--cpus={self.config.cpus}",
            f"--memory={self.config.memory_limit}",
            f"--memory-swap={self.config.memory_swap}",
            f"--pids-limit={self.config.pids_limit}",
        ])

        # 5. Working Directory & Environment Variables
        workdir = posixpath.join("/workspace/repo", self.config.working_dir) if self.config.working_dir else "/workspace/repo"
        docker_cmd.extend([
            "-w", workdir,
            "-e", f"SANDBOX_WORKDIR={workdir}",
            "-e", f"SANDBOX_TIMEOUT={self.config.timeout_seconds}",
            "-e", "PYTHONUNBUFFERED=1",
            "-e", "PYTHONDONTWRITEBYTECODE=1",
            "-e", "PYTHONUSERBASE=/workspace/home/.local",
            "-e", ("PYTHONPATH=/workspace/repo:/workspace/deps:"
                   f"/workspace/home/.local/lib/python{self.config.python_version}/site-packages"),
        ])
        for k, v in {**self.config.env_vars, **(extra_env or {})}.items():
            docker_cmd.extend(["-e", f"{k}={v}"])

        # 6. Volumes
        repo_mode = "rw" if self.config.writable_repo else "ro"
        docker_cmd.extend([
            "-v", f"{repo_path}:/workspace/repo:{repo_mode}",
            "-v", f"{output_path}:/workspace/output:rw",
        ])
        if packages_dir and Path(packages_dir).exists():
            pkg_path = Path(packages_dir).resolve()
            docker_cmd.extend(["-v", f"{pkg_path}:/workspace/packages:ro"])
        if deps_dir:
            mode = "rw" if deps_writable else "ro"
            docker_cmd.extend(["-v", f"{Path(deps_dir).resolve()}:/workspace/deps:{mode}"])
        for target, host in sorted(self.config.data_mounts.items()):
            docker_cmd.extend(["-v", f"{Path(host).resolve()}:{target}:ro"])

        # 7. Image and Command
        docker_cmd.append(self.config.image_name)
        docker_cmd.extend(command)

        return docker_cmd

    @staticmethod
    def _status_from_meta(output_dir: Path) -> str | None:
        """Status written by the container entrypoint, if execution_meta.json exists and is valid."""
        try:
            status = json.loads((Path(output_dir) / "execution_meta.json").read_text(encoding="utf-8")).get("status")
        except (OSError, ValueError):
            return None
        return status if status in ("COMPLETED", "FAILED", "TIMEOUT", "OOM_KILLED") else None

    @staticmethod
    def _write_host_logs(output_dir: Path, stdout: str, stderr: str) -> None:
        """Write captured logs unless the container entrypoint already wrote them.

        The entrypoint tees stdout/stderr into the mounted output directory as the sandbox user
        (uid 1000). On hosts running as another uid those files cannot be overwritten, so they are
        kept as written, and a failed log write never changes the run's result.
        """
        for name, text in (("stdout.log", stdout), ("stderr.log", stderr)):
            path = output_dir / name
            if path.exists():
                continue
            try:
                path.write_text(text, encoding="utf-8")
            except OSError as exc:
                logger.warning("Could not write %s: %s", path, exc)

    def _install_dependencies(
        self,
        repo_dir: str | Path,
        output_dir: Path,
        packages_dir: str | Path,
    ) -> tuple[Path, str]:
        """Install offline wheels in a separate, network-isolated container (install phase).

        Wheels from /workspace/packages are installed binary-only (no package code runs) into a host
        directory mounted writable at /workspace/deps. The paper run later mounts that directory
        read-only, so compiled extensions can load but paper code cannot modify or add executables.
        Returns the host deps directory and the install status (INSTALLED or FAILED).
        """
        deps_dir = Path(output_dir) / "deps"
        if deps_dir.exists():
            shutil.rmtree(deps_dir)
        deps_dir.mkdir(parents=True)
        deps_dir.chmod(0o777)  # written by the sandbox user (uid 1000) during the install phase only
        meta_path = Path(output_dir) / "install_meta.json"
        meta_path.unlink(missing_ok=True)

        install_cmd = self.build_docker_command(
            repo_dir=repo_dir,
            output_dir=output_dir,
            command=["install-dependencies"],
            packages_dir=packages_dir,
            deps_dir=deps_dir,
            deps_writable=True,
            extra_env={"SANDBOX_PHASE": "install"},
        )
        try:
            subprocess.run(install_cmd, capture_output=True, text=True, timeout=self.config.timeout_seconds + 10, check=False)
        except (subprocess.SubprocessError, OSError) as exc:
            logger.warning("Dependency install phase could not run: %s", exc)
            return deps_dir, "FAILED"
        finally:
            deps_dir.chmod(0o755)  # close the directory again before the run phase
        try:
            status = json.loads(meta_path.read_text(encoding="utf-8")).get("status")
        except (OSError, ValueError) as exc:
            logger.warning("Unreadable install_meta.json: %s", exc)
            status = None
        return deps_dir, status if status in ("INSTALLED", "FAILED") else "FAILED"

    def run(
        self,
        paper_id: str,
        repo_dir: str | Path,
        target_script: str,
        script_args: list[str] | None = None,
        packages_dir: str | Path | None = None,
        command: list[str] | None = None,
    ) -> SandboxExecutionResult:
        """Execute paper code inside the Docker sandbox.

        With `packages_dir`, dependencies are first installed in a separate install-phase container
        (see _install_dependencies) and mounted read-only into the run. `command` replaces
        `python <target_script> <script_args>`, for papers whose entry point is not a script (#166).

        Raises SandboxUnavailableError when Docker is unavailable, unless the config explicitly
        opts into unisolated local execution (allow_unsafe_local), which is only for trusted code.
        """
        output_dir = SANDBOX_RUNS_DIR / paper_id
        output_dir.mkdir(parents=True, exist_ok=True)

        target_cmd = list(command) if command else ["python", f"/workspace/repo/{target_script}"]
        if script_args and not command:
            target_cmd.extend(script_args)

        if not self.is_docker_available():
            if not self.config.allow_unsafe_local:
                raise SandboxUnavailableError(
                    "Docker is not available, so the code cannot be isolated; refusing to run it on the host. "
                    "Install and start Docker, or pass --allow-unsafe-local (SandboxConfig.allow_unsafe_local) "
                    "to run unisolated, only for code you trust."
                )
            if command or self.config.working_dir or self.config.writable_repo or self.config.data_mounts:
                # The local fallback cannot honor a run setup (#166); running without it would be a different run.
                raise SandboxUnavailableError("Docker is not available, and this paper's run setup needs the Docker sandbox.")
            logger.warning("Docker unavailable; running %s WITHOUT isolation (allow_unsafe_local)", paper_id)
            fallback_runner = ProcessSandboxRunner(timeout_seconds=self.config.timeout_seconds)
            return fallback_runner.run(
                paper_id=paper_id,
                repo_dir=repo_dir,
                target_script=target_script,
                script_args=script_args,
                fallback_reason="Docker unavailable; unisolated local run explicitly allowed (allow_unsafe_local)",
            )

        # The containers run as the sandbox user (uid 1000) and write logs and metadata into the
        # output directory. On hosts running as another uid it must be opened for the container
        # phases; it is closed again afterwards, whatever happens.
        output_dir.chmod(0o777)
        try:
            if self.config.writable_repo:
                repo_dir = self._writable_copy(repo_dir, output_dir)
            self._create_mount_points(repo_dir)
            return self._run_docker_phases(repo_dir, output_dir, target_cmd, packages_dir)
        finally:
            output_dir.chmod(0o755)

    @staticmethod
    def _writable_copy(repo_dir: str | Path, output_dir: Path) -> Path:
        """A per-run copy of the repository that the sandbox user may write to (#166).

        The staged repository itself stays read-only and unchanged. The copy lives in the run's output
        directory, so whatever the paper writes next to its own files is kept with the run.
        """
        copy = Path(output_dir) / "repo_copy"
        if copy.exists():
            shutil.rmtree(copy)
        shutil.copytree(repo_dir, copy, ignore=shutil.ignore_patterns(".git"))
        for path in [copy, *copy.rglob("*")]:
            if not path.is_symlink():
                path.chmod(0o777 if path.is_dir() else 0o666)
        return copy

    def _create_mount_points(self, repo_dir: str | Path) -> None:
        """Create the mount points of data mounts inside the repository on the host.

        The repository is mounted read-only, so Docker could not create them inside the container.
        """
        for target in self.config.data_mounts:
            if target.startswith("/workspace/repo/"):
                (Path(repo_dir) / target[len("/workspace/repo/"):]).mkdir(parents=True, exist_ok=True)

    def _run_docker_phases(
        self,
        repo_dir: str | Path,
        output_dir: Path,
        target_cmd: list[str],
        packages_dir: str | Path | None,
    ) -> SandboxExecutionResult:
        """Optional install phase, then the paper run, both in the Docker sandbox."""
        deps_dir = None
        dependency_status = None
        if packages_dir and Path(packages_dir).is_dir() and any(Path(packages_dir).iterdir()):
            deps_dir, dependency_status = self._install_dependencies(repo_dir, output_dir, packages_dir)

        docker_cmd = self.build_docker_command(
            repo_dir=repo_dir,
            output_dir=output_dir,
            command=target_cmd,
            deps_dir=deps_dir,
            extra_env={"SANDBOX_DEPENDENCY_STATUS": dependency_status} if dependency_status else None,
        )

        start_time = time.time()
        try:
            res = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=self.config.timeout_seconds + 10, check=False,  # Buffer for container teardown
            )
            duration = time.time() - start_time
            exit_code = res.returncode
            status = "COMPLETED" if exit_code == 0 else "FAILED"
            if exit_code in (124, 137):
                status = "TIMEOUT"
            # Exit 137 means SIGKILL from either the timeout watchdog or the kernel OOM killer; the
            # entrypoint tells them apart (cgroup oom_kill counter), so its status wins when present.
            status = self._status_from_meta(output_dir) or status

            self._write_host_logs(output_dir, res.stdout, res.stderr)

            return SandboxExecutionResult(
                status=status,
                exit_code=exit_code,
                stdout=res.stdout,
                stderr=res.stderr,
                duration_seconds=duration,
                command_executed=docker_cmd,
                docker_used=True,
                output_dir=output_dir,
                isolated=True,
            )
        except subprocess.TimeoutExpired as exc:
            duration = time.time() - start_time
            return SandboxExecutionResult(
                status="TIMEOUT",
                exit_code=124,
                stdout=exc.stdout or "",
                stderr=exc.stderr or "Container execution exceeded timeout threshold.",
                duration_seconds=duration,
                command_executed=docker_cmd,
                docker_used=True,
                output_dir=output_dir,
                error_message=f"Timeout of {self.config.timeout_seconds}s exceeded.",
                isolated=True,
            )
        except Exception as err:  # noqa: BLE001 - any runner error becomes a FAILED result, never a crash
            duration = time.time() - start_time
            return SandboxExecutionResult(
                status="FAILED",
                exit_code=1,
                stdout="",
                stderr=str(err),
                duration_seconds=duration,
                command_executed=docker_cmd,
                docker_used=True,
                output_dir=output_dir,
                error_message=str(err),
                isolated=True,
            )


class ProcessSandboxRunner:
    """Unisolated local runner: executes targets via subprocess with timeout guards only.

    The code runs on the host with the caller's permissions and network access. Use only for trusted code.
    """

    def __init__(self, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS):
        self.timeout_seconds = timeout_seconds

    def run(
        self,
        paper_id: str,
        repo_dir: str | Path,
        target_script: str,
        script_args: list[str] | None = None,
        fallback_reason: str | None = None,
    ) -> SandboxExecutionResult:
        """Run script using local Python interpreter within a designated sandbox run directory."""
        output_dir = SANDBOX_RUNS_DIR / paper_id
        output_dir.mkdir(parents=True, exist_ok=True)

        script_path = Path(repo_dir) / target_script
        python_bin = sys.executable

        run_cmd = [python_bin, str(script_path)]
        if script_args:
            run_cmd.extend(script_args)

        start_time = time.time()
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["SANDBOX_OUTPUT_DIR"] = str(output_dir)

        if not script_path.exists():
            return SandboxExecutionResult(
                status="FAILED",
                exit_code=2,
                stdout="",
                stderr=f"Target script not found: {script_path}",
                duration_seconds=0.0,
                command_executed=run_cmd,
                docker_used=False,
                output_dir=output_dir,
                error_message=f"Script missing: {script_path} ({fallback_reason or 'local execution'})",
            )

        try:
            proc = subprocess.run(
                run_cmd,
                cwd=str(repo_dir),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                env=env, check=False,
            )
            duration = time.time() - start_time
            status = "COMPLETED" if proc.returncode == 0 else "FAILED"

            # Write logs
            (output_dir / "stdout.log").write_text(proc.stdout, encoding="utf-8")
            (output_dir / "stderr.log").write_text(proc.stderr, encoding="utf-8")

            return SandboxExecutionResult(
                status=status,
                exit_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                duration_seconds=duration,
                command_executed=run_cmd,
                docker_used=False,
                output_dir=output_dir,
                error_message=fallback_reason,
            )
        except subprocess.TimeoutExpired as exc:
            duration = time.time() - start_time
            return SandboxExecutionResult(
                status="TIMEOUT",
                exit_code=124,
                stdout=exc.stdout or "",
                stderr=exc.stderr or "Local execution timed out.",
                duration_seconds=duration,
                command_executed=run_cmd,
                docker_used=False,
                output_dir=output_dir,
                error_message=f"Timeout of {self.timeout_seconds}s exceeded.",
            )
        except Exception as err:  # noqa: BLE001 - any runner error becomes a FAILED result, never a crash
            duration = time.time() - start_time
            return SandboxExecutionResult(
                status="FAILED",
                exit_code=1,
                stdout="",
                stderr=str(err),
                duration_seconds=duration,
                command_executed=run_cmd,
                docker_used=False,
                output_dir=output_dir,
                error_message=str(err),
            )
