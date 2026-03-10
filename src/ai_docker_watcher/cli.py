from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from pathlib import Path

from .context_store import ContextStore
from .events import Event, EventBus
from .registry import ProjectEntry, ProjectRegistry
from .router import EventRouter
from .watchers import FileChangeWatcher


def default_config_path() -> Path:
    return Path.cwd() / "projects.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ai-docker-watcher")
    parser.add_argument("--config", default=str(default_config_path()), help="projects config JSON path")

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="list registered projects")

    add_parser = subparsers.add_parser("add", help="add project to config")
    add_parser.add_argument("--name", required=True, help="project name")
    add_parser.add_argument("--workspace", required=True, help="workspace path")
    add_parser.add_argument("--interval", type=float, default=2.0, help="polling interval seconds")
    add_parser.add_argument("--max-feedback-loops", type=int, default=2, help="validator->docker retry count")
    add_parser.add_argument("--disabled", action="store_true", help="register as disabled")
    add_parser.add_argument("--docker-agent-cmd", help="external docker agent command")
    add_parser.add_argument("--validator-agent-cmd", help="external validator agent command")

    remove_parser = subparsers.add_parser("remove", help="remove project")
    remove_parser.add_argument("--name", required=True, help="project name")

    enable_parser = subparsers.add_parser("enable", help="enable project")
    enable_parser.add_argument("--name", required=True, help="project name")

    disable_parser = subparsers.add_parser("disable", help="disable project")
    disable_parser.add_argument("--name", required=True, help="project name")

    update_parser = subparsers.add_parser("update", help="update project settings")
    update_parser.add_argument("--name", required=True, help="project name")
    update_parser.add_argument("--workspace", help="new workspace path")
    update_parser.add_argument("--interval", type=float, help="new polling interval seconds")
    update_parser.add_argument("--max-feedback-loops", type=int, help="new validator->docker retry count")
    update_parser.add_argument("--docker-agent-cmd", help="set docker agent command")
    update_parser.add_argument("--validator-agent-cmd", help="set validator agent command")
    update_parser.add_argument(
        "--clear-docker-agent-cmd",
        action="store_true",
        help="remove docker agent command from project config",
    )
    update_parser.add_argument(
        "--clear-validator-agent-cmd",
        action="store_true",
        help="remove validator agent command from project config",
    )

    run_parser = subparsers.add_parser("run", help="run watchers")
    run_parser.add_argument("--name", help="run only this project name")
    run_parser.add_argument("--workspace", help="run only this workspace path")
    run_parser.add_argument("--once", action="store_true", help="run single pass")

    return parser.parse_args()


@dataclass
class Runner:
    project: ProjectEntry
    bus: EventBus
    watcher: FileChangeWatcher
    last_tick: float


def _seed_initial_event(bus: EventBus, watcher: FileChangeWatcher) -> None:
    initial_files = sorted(watcher._snapshot().keys())
    if not initial_files:
        return
    bus.publish(
        Event(
            name="files_changed",
            source="main-agent-bridge",
            payload={"changed_files": initial_files},
        )
    )


def _build_runner(project: ProjectEntry) -> Runner:
    workspace = Path(project.workspace).resolve()

    store = ContextStore(workspace)
    store.ensure()
    store.init_default_context()

    bus = EventBus()
    watcher = FileChangeWatcher(workspace)
    watcher.initialize()

    EventRouter(
        workspace=workspace,
        bus=bus,
        store=store,
        max_feedback_loops=project.max_feedback_loops,
        docker_agent_cmd=project.docker_agent_cmd,
        validator_agent_cmd=project.validator_agent_cmd,
    )

    _seed_initial_event(bus, watcher)
    bus.drain()

    return Runner(project=project, bus=bus, watcher=watcher, last_tick=time.monotonic())


def cmd_list(registry: ProjectRegistry) -> int:
    projects = registry.list_projects()
    if not projects:
        print("No projects in registry.")
        return 0

    for p in projects:
        status = "ON" if p.enabled else "OFF"
        print(
            f"- name={p.name} status={status} workspace={p.workspace} "
            f"interval={p.interval}s max_feedback_loops={p.max_feedback_loops} "
            f"docker_agent_cmd={p.docker_agent_cmd or '-'} "
            f"validator_agent_cmd={p.validator_agent_cmd or '-'}"
        )
    return 0


def cmd_add(registry: ProjectRegistry, args: argparse.Namespace) -> int:
    entry = ProjectEntry(
        name=args.name,
        workspace=str(Path(args.workspace).resolve()),
        enabled=not args.disabled,
        interval=args.interval,
        max_feedback_loops=args.max_feedback_loops,
        docker_agent_cmd=args.docker_agent_cmd,
        validator_agent_cmd=args.validator_agent_cmd,
    )
    registry.add_project(entry)
    print(f"Added project: {entry.name}")
    return 0


def cmd_remove(registry: ProjectRegistry, args: argparse.Namespace) -> int:
    registry.remove_project(args.name)
    print(f"Removed project: {args.name}")
    return 0


def cmd_enable(registry: ProjectRegistry, args: argparse.Namespace) -> int:
    registry.set_enabled(args.name, True)
    print(f"Enabled project: {args.name}")
    return 0


def cmd_disable(registry: ProjectRegistry, args: argparse.Namespace) -> int:
    registry.set_enabled(args.name, False)
    print(f"Disabled project: {args.name}")
    return 0


def cmd_update(registry: ProjectRegistry, args: argparse.Namespace) -> int:
    docker_agent_cmd = args.docker_agent_cmd
    validator_agent_cmd = args.validator_agent_cmd
    if args.clear_docker_agent_cmd:
        docker_agent_cmd = ""
    if args.clear_validator_agent_cmd:
        validator_agent_cmd = ""

    workspace = str(Path(args.workspace).resolve()) if args.workspace else None
    registry.update_project(
        name=args.name,
        workspace=workspace,
        interval=args.interval,
        max_feedback_loops=args.max_feedback_loops,
        docker_agent_cmd=docker_agent_cmd,
        validator_agent_cmd=validator_agent_cmd,
    )
    print(f"Updated project: {args.name}")
    return 0


def _select_projects(projects: list[ProjectEntry], args: argparse.Namespace) -> list[ProjectEntry]:
    selected = [p for p in projects if p.enabled]

    if args.name:
        selected = [p for p in selected if p.name == args.name]
    if args.workspace:
        ws = str(Path(args.workspace).resolve())
        selected = [p for p in selected if str(Path(p.workspace).resolve()) == ws]

    return selected


def cmd_run(registry: ProjectRegistry, args: argparse.Namespace) -> int:
    projects = registry.list_projects()
    selected = _select_projects(projects, args)

    if not selected:
        print("No enabled projects matched run filters.")
        return 1

    runners = [_build_runner(project) for project in selected]

    if args.once:
        print(f"Run once completed for {len(runners)} project(s).")
        return 0

    while True:
        now = time.monotonic()
        for runner in runners:
            if now - runner.last_tick < runner.project.interval:
                continue
            event = runner.watcher.poll()
            if event:
                runner.bus.publish(event)
                runner.bus.drain()
            runner.last_tick = now
        time.sleep(0.5)


def main() -> None:
    args = parse_args()
    registry = ProjectRegistry(Path(args.config).resolve())

    try:
        if args.command == "list":
            raise SystemExit(cmd_list(registry))
        if args.command == "add":
            raise SystemExit(cmd_add(registry, args))
        if args.command == "remove":
            raise SystemExit(cmd_remove(registry, args))
        if args.command == "enable":
            raise SystemExit(cmd_enable(registry, args))
        if args.command == "disable":
            raise SystemExit(cmd_disable(registry, args))
        if args.command == "update":
            raise SystemExit(cmd_update(registry, args))
        if args.command == "run":
            raise SystemExit(cmd_run(registry, args))
        raise SystemExit(2)
    except ValueError as exc:
        print(f"Error: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
