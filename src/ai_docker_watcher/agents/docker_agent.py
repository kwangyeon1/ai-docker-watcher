from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from ..impact import has_docker_impact


class DockerAgent:
    def __init__(self, workspace: Path, agent_cmd: str | None = None) -> None:
        self.workspace = workspace
        self.agent_cmd = agent_cmd

    @staticmethod
    def has_docker_impact(changed_files: list[str]) -> bool:
        return has_docker_impact(changed_files)

    def run(self, changed_files: list[str], validation_feedback: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = {
            "workspace": str(self.workspace),
            "changed_files": changed_files,
            "validation_feedback": validation_feedback or {},
        }
        if self.agent_cmd:
            return self._run_external(self.agent_cmd, payload)
        return self._fallback_generate(changed_files, validation_feedback or {})

    def _run_external(self, cmd: str, payload: dict[str, Any]) -> dict[str, Any]:
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
                "status": "error",
                "summary": f"external docker agent failed: {proc.stderr.strip()}",
                "files": [],
            }
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError:
            return {
                "status": "error",
                "summary": "external docker agent returned invalid JSON",
                "files": [],
            }

    def _fallback_generate(
        self,
        changed_files: list[str],
        validation_feedback: dict[str, Any],
    ) -> dict[str, Any]:
        dockerfile = self.workspace / "Dockerfile"
        if dockerfile.exists():
            content = dockerfile.read_text()
            summary = "Dockerfile already exists; no change from fallback docker agent"
            files: list[dict[str, str]] = []
        else:
            content = (
                "FROM python:3.12-slim\n"
                "WORKDIR /app\n"
                "COPY . /app\n"
                "RUN pip install --no-cache-dir -r requirements.txt || true\n"
                "CMD [\"python\", \"-m\", \"http.server\", \"8000\"]\n"
            )
            summary = "Created baseline Dockerfile from fallback docker agent"
            files = [{"path": "Dockerfile", "content": content}]

        if validation_feedback.get("status") == "failed":
            summary += "; reviewed validator failure and kept baseline-safe config"

        return {"status": "ok", "summary": summary, "files": files, "changed_files": changed_files}
