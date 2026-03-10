from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ai-docker-watcher bridge worker")
    parser.add_argument("--role", required=True, choices=["docker", "validator"], help="agent role")
    parser.add_argument(
        "--provider",
        required=True,
        choices=["codex", "claude", "custom"],
        help="upstream AI provider",
    )
    parser.add_argument(
        "--provider-command",
        help=(
            "custom provider command. For provider=custom this is required. "
            "The command receives the prompt via stdin and should print a JSON response."
        ),
    )
    return parser.parse_args()


def _build_prompt(role: str, payload: dict[str, Any]) -> str:
    if role == "docker":
        return (
            "You are a Docker specialist AI agent. "
            "Return ONLY valid JSON with keys: status, summary, files. "
            "files must be an array of {path, content}.\n\n"
            f"Input:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )

    return (
        "You are a container validator AI agent. "
        "Return ONLY valid JSON with keys: status, summary, owner. "
        "status should be passed or failed.\n\n"
        f"Input:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def _run_codex(prompt: str, workspace: str) -> str:
    proc = subprocess.run(
        ["codex", "exec", "--cd", workspace, "-"],
        input=prompt,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "codex exec failed")
    return proc.stdout.strip()


def _run_claude(prompt: str, workspace: str) -> str:
    # Claude CLI variants differ. This default assumes `claude -p` prompt mode.
    proc = subprocess.run(
        ["claude", "-p", prompt],
        cwd=workspace,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "claude command failed")
    return proc.stdout.strip()


def _run_custom(prompt: str, workspace: str, command: str) -> str:
    proc = subprocess.run(
        command,
        shell=True,
        cwd=workspace,
        input=prompt,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "custom provider command failed")
    return proc.stdout.strip()


def _parse_json_loose(raw: str) -> dict[str, Any]:
    if not raw:
        raise ValueError("empty provider response")

    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        candidate = raw[start : end + 1]
        parsed = json.loads(candidate)
        if isinstance(parsed, dict):
            return parsed

    raise ValueError("provider response is not valid JSON object")


def _normalize(role: str, data: dict[str, Any], fallback_error: str | None = None) -> dict[str, Any]:
    if role == "docker":
        if fallback_error:
            return {"status": "error", "summary": fallback_error, "files": []}
        files = data.get("files") if isinstance(data.get("files"), list) else []
        return {
            "status": str(data.get("status", "ok")),
            "summary": str(data.get("summary", "docker bridge completed")),
            "files": files,
        }

    if fallback_error:
        return {"status": "failed", "owner": "validator-agent", "summary": fallback_error}

    status = str(data.get("status", "passed"))
    if status not in {"passed", "failed"}:
        status = "passed"

    return {
        "status": status,
        "owner": str(data.get("owner", "validator-agent")),
        "summary": str(data.get("summary", "validator bridge completed")),
    }


def main() -> None:
    args = parse_args()

    payload = json.load(__import__("sys").stdin)
    workspace = str(Path(payload.get("workspace", ".")).resolve())
    prompt = _build_prompt(args.role, payload)

    try:
        if args.provider == "codex":
            raw = _run_codex(prompt, workspace)
        elif args.provider == "claude":
            raw = _run_claude(prompt, workspace)
        else:
            if not args.provider_command:
                raise RuntimeError("provider=custom requires --provider-command")
            raw = _run_custom(prompt, workspace, args.provider_command)

        parsed = _parse_json_loose(raw)
        result = _normalize(args.role, parsed)
    except Exception as exc:  # noqa: BLE001
        result = _normalize(args.role, {}, fallback_error=f"bridge failure: {exc}")

    print(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()
