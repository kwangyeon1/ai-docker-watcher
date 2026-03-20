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

    def _read_text(self, relative_path: str) -> str:
        path = self.vibe / relative_path
        if not path.exists():
            return ""
        return path.read_text()

    def _format_changed_files(self, payload: dict[str, Any]) -> str:
        changed_files = payload.get("changed_files", [])
        if not changed_files:
            return "- none\n"
        return "".join(f"- `{path}`\n" for path in changed_files)

    def _build_next_action(self, task: dict[str, Any], validation: dict[str, Any]) -> str:
        validation_status = str(task.get("validation_status", "unknown"))
        last_owner = str(task.get("last_owner", "unknown"))
        docker_status = str(task.get("docker_status", "unknown"))

        if validation_status == "failed":
            error_type = str(validation.get("error_type", "unknown"))
            summary = str(validation.get("summary", "")).strip() or "no summary"
            return (
                "Validation is failing.\n"
                f"- last_owner: `{last_owner}`\n"
                f"- error_type: `{error_type}`\n"
                f"- summary: {summary}\n"
                "- Read `context/recent_failures.md` first.\n"
                "- Then inspect `reports/validation_report.json`, `reports/docker_report.md`, and the current `Dockerfile`.\n"
                "- Prioritize fixes in Docker assets and dependency manifests before unrelated app code.\n"
            )

        if docker_status in {"error", "failed"}:
            return (
                "Docker generation did not complete cleanly.\n"
                "- Inspect `reports/docker_report.md` and any external agent stderr summaries.\n"
                "- Verify that the generated `Dockerfile` still matches project manifests.\n"
            )

        return (
            "No active validation failure is recorded.\n"
            "- Use `state/changed_files.json` to see what changed most recently.\n"
            "- If you are about to edit Docker assets, read this bundle first and then update the corresponding agent brief.\n"
        )

    def refresh_reference_bundle(self) -> None:
        task = self.read_json("state/task_state.json", default={})
        changed = self.read_json("state/changed_files.json", default={})
        validation = self.read_json("reports/validation_report.json", default={})
        docker_report = self._read_text("reports/docker_report.md").strip() or "_No docker report yet._"
        recent_failures = self._read_text("context/recent_failures.md").strip() or "_No recent failure note yet._"
        repo_summary = self._read_text("context/repo_summary.md").strip() or "_No repo summary yet._"
        main_brief = self._read_text("context/main_agent_brief.md").strip() or "_No main agent brief yet._"
        docker_brief = self._read_text("context/docker_agent_brief.md").strip() or "_No docker agent brief yet._"
        validator_brief = self._read_text("context/validator_agent_brief.md").strip() or "_No validator agent brief yet._"

        bundle = (
            "# Artifact Reference Bundle\n\n"
            "Use this file as the single entry point for Docker-sidecar artifacts. "
            "A main AI agent can read this bundle first, then follow the linked files to decide what to fix.\n\n"
            "## Current Status\n\n"
            f"- task_id: `{task.get('task_id', 'unknown')}`\n"
            f"- docker_status: `{task.get('docker_status', 'unknown')}`\n"
            f"- validation_status: `{task.get('validation_status', 'unknown')}`\n"
            f"- last_owner: `{task.get('last_owner', 'unknown')}`\n\n"
            "## Recommended Next Action\n\n"
            f"{self._build_next_action(task, validation)}\n"
            "## Artifact Map\n\n"
            "- `context/repo_summary.md`: workspace overview for any agent touching Docker or app code.\n"
            "- `context/main_agent_brief.md`: rules for the main AI editor/CLI.\n"
            "- `context/docker_agent_brief.md`: Docker-generation policy and constraints.\n"
            "- `context/validator_agent_brief.md`: validation policy and expected checks.\n"
            "- `context/recent_failures.md`: latest human-readable failure summary.\n"
            "- `reports/docker_report.md`: latest Docker-agent output summary.\n"
            "- `reports/validation_report.json`: latest machine-readable validation result.\n"
            "- `state/changed_files.json`: latest changed files that triggered the loop.\n"
            "- `state/task_state.json`: current loop state.\n"
            "- `events/events.log`: event history for debugging watcher behavior.\n\n"
            "## Latest Changed Files\n\n"
            f"{self._format_changed_files(changed)}\n"
            "## Latest Docker Report\n\n"
            f"{docker_report}\n\n"
            "## Latest Failure Summary\n\n"
            f"{recent_failures}\n\n"
            "## Existing Briefs\n\n"
            "### Repo Summary\n\n"
            f"{repo_summary}\n\n"
            "### Main Agent Brief\n\n"
            f"{main_brief}\n\n"
            "### Docker Agent Brief\n\n"
            f"{docker_brief}\n\n"
            "### Validator Agent Brief\n\n"
            f"{validator_brief}\n"
        )
        self.write_text("context/artifact_reference_bundle.md", bundle)

    def write_agent_bundle_examples(self) -> None:
        examples = (
            "# Agent Markdown Bundle Integration Examples\n\n"
            "Copy one of the snippets below into your AI instruction markdown files so every agent reads "
            "`context/artifact_reference_bundle.md` before making Docker-related decisions.\n\n"
            "## Example for `AGENTS.md`\n\n"
            "```md\n"
            "## Docker Sidecar Intake\n\n"
            "- Before changing Docker, Compose, manifests, or environment setup, read `context/artifact_reference_bundle.md`.\n"
            "- If `validation_status` is `failed`, prioritize `context/recent_failures.md` and `reports/validation_report.json`.\n"
            "- If the failure points to dependency installation, update project manifests before changing application code.\n"
            "```\n\n"
            "## Example for `CLAUDE.md` or `CODEX.md`\n\n"
            "```md\n"
            "## Docker Repair Workflow\n\n"
            "- Read `context/artifact_reference_bundle.md` first.\n"
            "- Treat `reports/validation_report.json` and `context/recent_failures.md` as the latest repair signal.\n"
            "- When revising the Dockerfile, prefer fixes that align with the changed manifests listed in the bundle.\n"
            "- Summarize the fix in terms consistent with `reports/docker_report.md`.\n"
            "```\n\n"
            "## Example for any other AI instruction markdown\n\n"
            "```md\n"
            "## Docker Context Hook\n\n"
            "- For Docker-related tasks, start with `context/artifact_reference_bundle.md`.\n"
            "- Use the bundle as the single source of truth for latest Docker state, failures, and changed files.\n"
            "- Follow links from the bundle when more detail is required.\n"
            "```\n"
        )
        self.write_text("context/agent_brief_bundle_integration_examples.md", examples)

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
        self.write_agent_bundle_examples()
        self.refresh_reference_bundle()
