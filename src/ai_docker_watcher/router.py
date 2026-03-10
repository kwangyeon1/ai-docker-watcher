from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agents import DockerAgent, ValidatorAgent
from .context_store import ContextStore
from .events import Event, EventBus


class EventRouter:
    def __init__(
        self,
        workspace: Path,
        bus: EventBus,
        store: ContextStore,
        max_feedback_loops: int = 2,
        docker_agent_cmd: str | None = None,
        validator_agent_cmd: str | None = None,
    ) -> None:
        self.workspace = workspace
        self.bus = bus
        self.store = store
        self.max_feedback_loops = max_feedback_loops
        self.docker_agent = DockerAgent(workspace, agent_cmd=docker_agent_cmd)
        self.validator_agent = ValidatorAgent(workspace, agent_cmd=validator_agent_cmd)

        self.bus.subscribe("files_changed", self._on_files_changed)
        self.bus.subscribe("docker_agent_completed", self._on_docker_completed)

    def _log_event(self, event: Event) -> None:
        self.store.append_event_log(
            json.dumps(
                {
                    "name": event.name,
                    "source": event.source,
                    "payload": event.payload,
                    "created_at": event.created_at,
                },
                ensure_ascii=True,
            )
        )

    def _apply_files(self, files: list[dict[str, str]]) -> None:
        for f in files:
            p = self.workspace / f["path"]
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(f["content"])

    def _on_files_changed(self, event: Event) -> None:
        self._log_event(event)
        changed_files = event.payload.get("changed_files", [])

        self.store.write_json(
            "state/changed_files.json",
            {
                "changed_files": changed_files,
                "docker_related": DockerAgent.has_docker_impact(changed_files),
            },
        )

        if not DockerAgent.has_docker_impact(changed_files):
            return

        result = self.docker_agent.run(changed_files=changed_files)
        files = result.get("files", [])
        if files:
            self._apply_files(files)
            patch_preview = "\n".join(f"- {f['path']}" for f in files)
        else:
            patch_preview = "- no file changes"

        self.store.write_text(
            "reports/docker_report.md",
            "# Docker Agent Report\n\n"
            f"Summary: {result.get('summary', 'no summary')}\n\n"
            f"Changed files:\n{patch_preview}\n",
        )

        self.store.write_json(
            "state/task_state.json",
            {
                "task_id": "task-001",
                "main_agent": "bridge",
                "docker_status": result.get("status", "unknown"),
                "validation_status": "pending",
                "last_owner": "docker-agent",
            },
        )

        self.bus.publish(
            Event(
                name="docker_agent_completed",
                source="docker-agent",
                payload={"docker_result": result, "feedback_loop": 0},
            )
        )

    def _on_docker_completed(self, event: Event) -> None:
        self._log_event(event)
        loop = int(event.payload.get("feedback_loop", 0))

        validation = self.validator_agent.run()
        self.store.write_json("reports/validation_report.json", validation)

        recent = (
            "# Recent Failures\n\n"
            if validation.get("status") == "failed"
            else "# Recent Failures\n\nNo active failures.\n"
        )
        if validation.get("status") == "failed":
            recent += (
                f"- owner: {validation.get('owner', 'unknown')}\n"
                f"- error_type: {validation.get('error_type', 'unknown')}\n"
                f"- summary: {validation.get('summary', '')}\n"
            )
        self.store.write_text("context/recent_failures.md", recent)

        task = self.store.read_json("state/task_state.json", default={})
        task["validation_status"] = validation.get("status", "unknown")
        task["last_owner"] = validation.get("owner", "validator-agent")
        self.store.write_json("state/task_state.json", task)

        if validation.get("status") != "failed":
            return

        if loop >= self.max_feedback_loops:
            return

        changed = self.store.read_json("state/changed_files.json", default={}).get("changed_files", [])
        result = self.docker_agent.run(changed_files=changed, validation_feedback=validation)
        files = result.get("files", [])
        if files:
            self._apply_files(files)

        self.bus.publish(
            Event(
                name="docker_agent_completed",
                source="docker-agent",
                payload={"docker_result": result, "feedback_loop": loop + 1},
            )
        )
