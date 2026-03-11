from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ProjectEntry:
    name: str
    workspace: str
    enabled: bool = True
    interval: float = 2.0
    max_feedback_loops: int = 2
    artifact_dir: str = ".vibe-docker"
    docker_agent_cmd: str | None = None
    validator_agent_cmd: str | None = None

    @classmethod
    def from_dict(cls, payload: dict) -> "ProjectEntry":
        return cls(
            name=str(payload["name"]),
            workspace=str(payload["workspace"]),
            enabled=bool(payload.get("enabled", True)),
            interval=float(payload.get("interval", 2.0)),
            max_feedback_loops=int(payload.get("max_feedback_loops", 2)),
            artifact_dir=str(payload.get("artifact_dir", ".vibe-docker")),
            docker_agent_cmd=payload.get("docker_agent_cmd"),
            validator_agent_cmd=payload.get("validator_agent_cmd"),
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "workspace": self.workspace,
            "enabled": self.enabled,
            "interval": self.interval,
            "max_feedback_loops": self.max_feedback_loops,
            "artifact_dir": self.artifact_dir,
            "docker_agent_cmd": self.docker_agent_cmd,
            "validator_agent_cmd": self.validator_agent_cmd,
        }


class ProjectRegistry:
    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path

    def _read_raw(self) -> dict:
        if not self.config_path.exists():
            return {"projects": []}
        return json.loads(self.config_path.read_text())

    def _write_raw(self, payload: dict) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n")

    def list_projects(self) -> list[ProjectEntry]:
        raw = self._read_raw()
        return [ProjectEntry.from_dict(p) for p in raw.get("projects", [])]

    def save_projects(self, projects: list[ProjectEntry]) -> None:
        self._write_raw({"projects": [p.to_dict() for p in projects]})

    def add_project(self, project: ProjectEntry) -> None:
        projects = self.list_projects()
        if any(p.name == project.name for p in projects):
            raise ValueError(f"project already exists: {project.name}")
        projects.append(project)
        self.save_projects(projects)

    def remove_project(self, name: str) -> None:
        projects = self.list_projects()
        filtered = [p for p in projects if p.name != name]
        if len(filtered) == len(projects):
            raise ValueError(f"project not found: {name}")
        self.save_projects(filtered)

    def set_enabled(self, name: str, enabled: bool) -> None:
        projects = self.list_projects()
        updated = False
        for p in projects:
            if p.name == name:
                p.enabled = enabled
                updated = True
                break
        if not updated:
            raise ValueError(f"project not found: {name}")
        self.save_projects(projects)

    def update_project(
        self,
        name: str,
        workspace: str | None = None,
        interval: float | None = None,
        max_feedback_loops: int | None = None,
        artifact_dir: str | None = None,
        docker_agent_cmd: str | None = None,
        validator_agent_cmd: str | None = None,
    ) -> None:
        projects = self.list_projects()
        updated = False
        for p in projects:
            if p.name != name:
                continue
            if workspace is not None:
                p.workspace = workspace
            if interval is not None:
                p.interval = interval
            if max_feedback_loops is not None:
                p.max_feedback_loops = max_feedback_loops
            if artifact_dir is not None:
                p.artifact_dir = artifact_dir
            if docker_agent_cmd is not None:
                p.docker_agent_cmd = docker_agent_cmd or None
            if validator_agent_cmd is not None:
                p.validator_agent_cmd = validator_agent_cmd or None
            updated = True
            break
        if not updated:
            raise ValueError(f"project not found: {name}")
        self.save_projects(projects)
