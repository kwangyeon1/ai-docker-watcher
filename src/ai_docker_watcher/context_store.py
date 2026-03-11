from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ContextStore:
    def __init__(self, workspace: Path, artifact_dir: str = ".vibe-docker") -> None:
        self.workspace = workspace
        self.artifact_dir = artifact_dir
        self.vibe = workspace / artifact_dir
        self.context = self.vibe / "context"
        self.state = self.vibe / "state"
        self.reports = self.vibe / "reports"
        self.patches = self.vibe / "patches"
        self.events = self.vibe / "events"

    def ensure(self) -> None:
        for path in [
            self.context,
            self.state,
            self.reports,
            self.patches,
            self.events,
        ]:
            path.mkdir(parents=True, exist_ok=True)

    def write_json(self, relative_path: str, payload: dict[str, Any]) -> None:
        path = self.vibe / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n")

    def read_json(self, relative_path: str, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.vibe / relative_path
        if not path.exists():
            return default or {}
        return json.loads(path.read_text())

    def write_text(self, relative_path: str, text: str) -> None:
        path = self.vibe / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def append_event_log(self, line: str) -> None:
        log = self.events / "events.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def init_default_context(self) -> None:
        defaults = {
            "context/repo_summary.md": "# Repo Summary\n\nAuto-generated placeholder.\n",
            "context/main_agent_brief.md": "# Main Agent Brief\n\nAuto-generated placeholder.\n",
            "context/docker_agent_brief.md": "# Docker Agent Brief\n\nAuto-generated placeholder.\n",
            "context/validator_agent_brief.md": "# Validator Agent Brief\n\nAuto-generated placeholder.\n",
        }
        for rel, body in defaults.items():
            path = self.vibe / rel
            if not path.exists():
                self.write_text(rel, body)

        if not (self.state / "task_state.json").exists():
            self.write_json(
                "state/task_state.json",
                {
                    "task_id": "task-001",
                    "main_agent": "unknown",
                    "docker_status": "pending",
                    "validation_status": "pending",
                    "last_owner": "main-agent",
                },
            )
