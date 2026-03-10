from __future__ import annotations

from pathlib import Path

DOCKER_IMPACT_FILES = {
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
    "requirements.txt",
    "pyproject.toml",
    "poetry.lock",
    "package.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "package-lock.json",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "go.mod",
    "Cargo.toml",
    "application.yml",
    "application.yaml",
}


def has_docker_impact(changed_files: list[str]) -> bool:
    for f in changed_files:
        if Path(f).name in DOCKER_IMPACT_FILES:
            return True
        if f.startswith("Dockerfile") or f.startswith("docker/"):
            return True
    return False
