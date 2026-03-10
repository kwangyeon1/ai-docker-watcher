from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


class ValidatorAgent:
    def __init__(self, workspace: Path, agent_cmd: str | None = None) -> None:
        self.workspace = workspace
        self.agent_cmd = agent_cmd

    def run(self) -> dict[str, Any]:
        if self.agent_cmd:
            return self._run_external(self.agent_cmd)
        return self._fallback_validate()

    def _run_external(self, cmd: str) -> dict[str, Any]:
        payload = {"workspace": str(self.workspace)}
        proc = subprocess.run(
            cmd,
            shell=True,
            cwd=self.workspace,
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            return {
                "status": "failed",
                "owner": "validator-agent",
                "summary": f"external validator failed: {proc.stderr.strip()}",
            }
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError:
            return {
                "status": "failed",
                "owner": "validator-agent",
                "summary": "external validator returned invalid JSON",
            }

    def _fallback_validate(self) -> dict[str, Any]:
        dockerfile = self.workspace / "Dockerfile"
        if not dockerfile.exists():
            return {
                "status": "failed",
                "owner": "docker-agent",
                "error_type": "dockerfile_missing",
                "summary": "Dockerfile not found",
                "next_action": "docker-agent-revise",
            }

        docker_bin = shutil.which("docker")
        if not docker_bin:
            return {
                "status": "passed",
                "owner": "validator-agent",
                "summary": "Dockerfile exists; docker CLI unavailable so runtime validation skipped",
            }

        build = subprocess.run(
            [docker_bin, "build", "-f", "Dockerfile", "."],
            cwd=self.workspace,
            text=True,
            capture_output=True,
            check=False,
        )
        if build.returncode != 0:
            return {
                "status": "failed",
                "owner": "docker-agent",
                "error_type": "docker_build_failed",
                "summary": (build.stderr or build.stdout)[-800:],
                "next_action": "docker-agent-revise",
            }

        compose_file = None
        for candidate in ["docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"]:
            p = self.workspace / candidate
            if p.exists():
                compose_file = candidate
                break

        if compose_file:
            compose_check = subprocess.run(
                [docker_bin, "compose", "-f", compose_file, "config"],
                cwd=self.workspace,
                text=True,
                capture_output=True,
                check=False,
            )
            if compose_check.returncode != 0:
                return {
                    "status": "failed",
                    "owner": "docker-agent",
                    "error_type": "compose_config_invalid",
                    "summary": (compose_check.stderr or compose_check.stdout)[-800:],
                    "next_action": "docker-agent-revise",
                }

        return {
            "status": "passed",
            "owner": "validator-agent",
            "summary": "docker build passed",
        }
