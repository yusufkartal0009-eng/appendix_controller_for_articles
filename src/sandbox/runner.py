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

from dataclasses import dataclass, field
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Union

from src.config import DEFAULT_TIMEOUT_SECONDS, SANDBOX_RUNS_DIR, SANDBOX_TEMP_DIR

logger = logging.getLogger(__name__)


class SandboxUnavailableError(RuntimeError):
    """Raised when isolated execution is impossible and unisolated execution was not opted into."""


@dataclass
class SandboxConfig:
    """Configuration parameters for isolated execution."""
    image_name: str = "repro-radar-sandbox:latest"
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
    env_vars: Dict[str, str] = field(default_factory=dict)
    # Run on the host without isolation when Docker is unavailable. Only for code you trust.
    allow_unsafe_local: bool = False


@dataclass
class SandboxExecutionResult:
    """Structured outcome from a sandbox execution run."""
    status: str  # 'COMPLETED', 'FAILED', 'TIMEOUT', 'SKIPPED'
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    command_executed: List[str]
    docker_used: bool
    output_dir: Path
    error_message: Optional[str] = None
    isolated: bool = False  # True only when the code ran inside the Docker sandbox

    def to_dict(self) -> Dict[str, Any]:
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

    def __init__(self, config: Optional[SandboxConfig] = None):
        self.config = config or SandboxConfig()

    @staticmethod
    def is_docker_available() -> bool:
        """Check whether the Docker CLI and daemon are operational."""
        docker_bin = shutil.which("docker")
        if not docker_bin:
            return False
        try:
            res = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return res.returncode == 0
        except (subprocess.SubprocessError, OSError):
            return False

    def build_docker_command(
        self,
        repo_dir: Union[str, Path],
        output_dir: Union[str, Path],
        command: List[str],
        packages_dir: Optional[Union[str, Path]] = None,
    ) -> List[str]:
        """Construct the security-hardened `docker run` command with all isolation flags."""
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
            "--tmpfs", f"/workspace/home:rw,nosuid,size={self.config.tmpfs_home_size}",
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
        docker_cmd.extend([
            "-w", "/workspace/repo",
            "-e", f"SANDBOX_TIMEOUT={self.config.timeout_seconds}",
            "-e", "PYTHONUNBUFFERED=1",
            "-e", "PYTHONDONTWRITEBYTECODE=1",
            "-e", "PYTHONUSERBASE=/workspace/home/.local",
            "-e", "PYTHONPATH=/workspace/repo:/workspace/home/.local/lib/python3.11/site-packages",
        ])
        for k, v in self.config.env_vars.items():
            docker_cmd.extend(["-e", f"{k}={v}"])

        # 6. Volumes
        docker_cmd.extend([
            "-v", f"{repo_path}:/workspace/repo:ro",
            "-v", f"{output_path}:/workspace/output:rw",
        ])
        if packages_dir and Path(packages_dir).exists():
            pkg_path = Path(packages_dir).resolve()
            docker_cmd.extend(["-v", f"{pkg_path}:/workspace/packages:ro"])

        # 7. Image and Command
        docker_cmd.append(self.config.image_name)
        docker_cmd.extend(command)

        return docker_cmd

    def run(
        self,
        paper_id: str,
        repo_dir: Union[str, Path],
        target_script: str,
        script_args: Optional[List[str]] = None,
        packages_dir: Optional[Union[str, Path]] = None,
    ) -> SandboxExecutionResult:
        """Execute paper code inside the Docker sandbox.

        Raises SandboxUnavailableError when Docker is unavailable, unless the config explicitly
        opts into unisolated local execution (allow_unsafe_local), which is only for trusted code.
        """
        output_dir = SANDBOX_RUNS_DIR / paper_id
        output_dir.mkdir(parents=True, exist_ok=True)

        target_cmd = ["python", f"/workspace/repo/{target_script}"]
        if script_args:
            target_cmd.extend(script_args)

        if not self.is_docker_available():
            if not self.config.allow_unsafe_local:
                raise SandboxUnavailableError(
                    "Docker is not available, so the code cannot be isolated; refusing to run it on the host. "
                    "Install and start Docker, or pass --allow-unsafe-local (SandboxConfig.allow_unsafe_local) "
                    "to run unisolated, only for code you trust."
                )
            logger.warning("Docker unavailable; running %s WITHOUT isolation (allow_unsafe_local)", paper_id)
            fallback_runner = ProcessSandboxRunner(timeout_seconds=self.config.timeout_seconds)
            return fallback_runner.run(
                paper_id=paper_id,
                repo_dir=repo_dir,
                target_script=target_script,
                script_args=script_args,
                fallback_reason="Docker unavailable; unisolated local run explicitly allowed (allow_unsafe_local)",
            )

        docker_cmd = self.build_docker_command(
            repo_dir=repo_dir,
            output_dir=output_dir,
            command=target_cmd,
            packages_dir=packages_dir,
        )

        start_time = time.time()
        try:
            res = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=self.config.timeout_seconds + 10,  # Buffer for container teardown
            )
            duration = time.time() - start_time
            exit_code = res.returncode
            status = "COMPLETED" if exit_code == 0 else "FAILED"
            if exit_code in (124, 137):
                status = "TIMEOUT"

            # Write stdout / stderr logs
            stdout_path = output_dir / "stdout.log"
            stderr_path = output_dir / "stderr.log"
            stdout_path.write_text(res.stdout, encoding="utf-8")
            stderr_path.write_text(res.stderr, encoding="utf-8")

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
        except Exception as err:
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
        repo_dir: Union[str, Path],
        target_script: str,
        script_args: Optional[List[str]] = None,
        fallback_reason: Optional[str] = None,
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
                env=env,
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
        except Exception as err:
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
