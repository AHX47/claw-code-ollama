"""
sandbox_skill.py
────────────────
Execute untrusted code in an isolated Docker container.

Dependencies
------------
    Docker daemon running locally.
    No Python packages beyond stdlib required.

Usage
-----
    from skills.sandbox_skill import SandboxSkill

    sb = SandboxSkill()

    # Run Python code
    result = sb.run_python("print(2 ** 32)")
    print(result.stdout)    # "4294967296"
    print(result.returncode)

    # Run Bash
    result = sb.run_bash("echo hello && ls /tmp")

    # Run arbitrary code with a custom image
    result = sb.run_code("node -e 'console.log(42)'", image="node:20-alpine")
"""

from __future__ import annotations

import shlex
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


@dataclass
class SandboxResult:
    stdout: str
    stderr: str
    returncode: int

    @property
    def success(self) -> bool:
        return self.returncode == 0


class SandboxSkill:
    """
    Thin wrapper around ``docker run --rm`` for sandboxed execution.

    Parameters
    ----------
    default_image   : Docker image used when none is specified
    timeout         : max wall-clock seconds for a container (default 30)
    network         : Docker network mode; "none" = fully air-gapped
    memory          : container memory limit (Docker format, e.g. "256m")
    cpus            : fractional CPU limit (e.g. 1.0)
    """

    def __init__(
        self,
        default_image: str = "python:3.12-slim",
        timeout: int = 30,
        network: str = "none",
        memory: str = "256m",
        cpus: float = 1.0,
    ) -> None:
        self.default_image = default_image
        self.timeout = timeout
        self.network = network
        self.memory = memory
        self.cpus = cpus

    # ── internal runner ─────────────────────────────────────────────────────

    def _docker_available(self) -> bool:
        try:
            subprocess.run(
                ["docker", "info"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
                timeout=5,
            )
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    def _run(
        self,
        cmd: Sequence[str],
        image: str,
        mount_dir: Path | None = None,
    ) -> SandboxResult:
        if not self._docker_available():
            return SandboxResult(
                stdout="",
                stderr="Docker is not available. Install Docker to use SandboxSkill.",
                returncode=1,
            )

        docker_cmd = [
            "docker", "run", "--rm",
            f"--network={self.network}",
            f"--memory={self.memory}",
            f"--cpus={self.cpus}",
            "--security-opt=no-new-privileges",
            "--cap-drop=ALL",
        ]

        if mount_dir:
            docker_cmd += ["-v", f"{mount_dir}:/workspace:ro", "-w", "/workspace"]

        docker_cmd.append(image)
        docker_cmd.extend(cmd)

        try:
            proc = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            return SandboxResult(
                stdout=proc.stdout,
                stderr=proc.stderr,
                returncode=proc.returncode,
            )
        except subprocess.TimeoutExpired:
            return SandboxResult(
                stdout="",
                stderr=f"[sandbox] Execution timed out after {self.timeout}s",
                returncode=124,
            )
        except Exception as exc:  # noqa: BLE001
            return SandboxResult(stdout="", stderr=str(exc), returncode=1)

    # ── public API ───────────────────────────────────────────────────────────

    def run_python(
        self,
        code: str,
        image: str = "python:3.12-slim",
        extra_packages: list[str] | None = None,
    ) -> SandboxResult:
        """
        Execute *code* (a Python string) inside a fresh container.

        If *extra_packages* are given they are pip-installed before running.
        """
        install = ""
        if extra_packages:
            pkgs = " ".join(shlex.quote(p) for p in extra_packages)
            install = f"pip install --quiet {pkgs} && "

        wrapped = f"{install}python -c {shlex.quote(code)}"
        return self._run(["sh", "-c", wrapped], image=image)

    def run_python_file(self, path: str | Path,
                        image: str = "python:3.12-slim") -> SandboxResult:
        """Mount a local Python file (read-only) and run it."""
        p = Path(path).resolve()
        return self._run(
            ["python", p.name],
            image=image,
            mount_dir=p.parent,
        )

    def run_bash(
        self,
        script: str,
        image: str = "alpine:latest",
    ) -> SandboxResult:
        """Execute a Bash/sh *script* string inside a container."""
        return self._run(["sh", "-c", script], image=image)

    def run_code(
        self,
        command: str,
        image: str | None = None,
    ) -> SandboxResult:
        """
        Run an arbitrary shell *command* in *image*.
        Useful for Node, Ruby, Go, etc.
        """
        return self._run(
            ["sh", "-c", command],
            image=image or self.default_image,
        )

    def check(self) -> dict[str, bool | str]:
        """Return a status dict for the skill health-check."""
        ok = self._docker_available()
        return {
            "docker_available": ok,
            "default_image": self.default_image,
            "network_mode": self.network,
            "memory_limit": self.memory,
        }
