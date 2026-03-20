# ai-docker-watcher

Event-driven sidecar agent runner for Docker generation and validation.

## What it does

- Watches workspace file changes
- Publishes events to a lightweight event bus
- Runs a Docker-focused agent when Docker-impacting files change
- Runs a Validator agent before/after build checks
- Persists shared context in `.vibe-docker/` by default (configurable) so your main AI editor/CLI can read it
- Generates a single bundled Markdown entrypoint so the main AI can review Docker-sidecar state from one file

## Architecture

- Main AI editor/CLI remains primary
- `ai-docker-watcher` runs beside it as a sidecar
- Collaboration is indirect via shared state under the configured artifact directory (default: `.vibe-docker/`)

```text
Main AI -> file changes -> watcher -> event bus
                          -> docker agent -> validator -> feedback loop
                                            -> .vibe-docker/context|state|reports|events
```

## Project registry mode

Watcher targets are managed in a JSON file (`projects.json` by default).

```json
{
  "projects": [
    {
      "name": "gui-ai-project",
      "workspace": "/home/kss930/analytics_project/gui-ai-project",
      "enabled": true,
      "interval": 2.0,
      "max_feedback_loops": 2,
      "artifact_dir": ".vibe-docker",
      "docker_agent_cmd": null,
      "validator_agent_cmd": null
    }
  ]
}
```

Register a project:

```bash
cd ai-docker-watcher
python -m pip install -e .
ai-docker-watcher add \
  --name gui-ai-project \
  --workspace /home/kss930/analytics_project/gui-ai-project \
  --artifact-dir .vibe-docker
```

List projects:

```bash
ai-docker-watcher list
```

Enable/disable:

```bash
ai-docker-watcher disable --name gui-ai-project
ai-docker-watcher enable --name gui-ai-project
```

Run all enabled projects:

```bash
ai-docker-watcher run
```

Run one pass for a specific workspace:

```bash
ai-docker-watcher run \
  --workspace /home/kss930/analytics_project/gui-ai-project \
  --once
```

Update project commands/settings:

```bash
ai-docker-watcher update --name gui-ai-project \
  --artifact-dir .vibe-docker \
  --docker-agent-cmd "python /opt/agents/docker_worker.py" \
  --validator-agent-cmd "python /opt/agents/validator_worker.py"
```

Bridge presets (Codex/Claude/Custom) for both agents:

```bash
ai-docker-watcher set-bridge --name gui-ai-project \
  --docker-provider codex \
  --validator-provider claude
```

Custom provider command via bridge:

```bash
ai-docker-watcher set-bridge --name gui-ai-project \
  --docker-provider custom \
  --docker-provider-command "my-ai-cli --json"
```

Remove command settings:

```bash
ai-docker-watcher update --name gui-ai-project --clear-docker-agent-cmd
ai-docker-watcher update --name gui-ai-project --clear-validator-agent-cmd
```

## External AI integration from `projects.json`

Per-project commands are configured in `projects.json` (not environment variables).

Input is provided to each command as JSON through stdin. Output must be JSON.

`set-bridge` generates project commands like:

- `python /abs/path/ai_docker_watcher/bridge.py --role docker --provider codex`
- `python /abs/path/ai_docker_watcher/bridge.py --role validator --provider claude`

`ai_docker_watcher.bridge` is a common adapter:

- reads watcher JSON from stdin
- calls selected provider (codex/claude/custom)
- normalizes provider output to watcher JSON schema

### Docker agent output format

```json
{
  "status": "ok",
  "summary": "updated Dockerfile",
  "files": [{"path": "Dockerfile", "content": "FROM ..."}]
}
```

### Validator output format

```json
{
  "status": "passed",
  "summary": "docker build succeeded",
  "owner": "docker-agent"
}
```

## Artifact layout (default: `.vibe-docker`)

Inside target workspace:

- `.vibe-docker/context/repo_summary.md`
- `.vibe-docker/context/main_agent_brief.md`
- `.vibe-docker/context/docker_agent_brief.md`
- `.vibe-docker/context/validator_agent_brief.md`
- `.vibe-docker/context/artifact_reference_bundle.md`
- `.vibe-docker/context/agent_brief_bundle_integration_examples.md`
- `.vibe-docker/context/recent_failures.md`
- `.vibe-docker/state/changed_files.json`
- `.vibe-docker/state/task_state.json`
- `.vibe-docker/reports/docker_report.md`
- `.vibe-docker/reports/validation_report.json`
- `.vibe-docker/events/events.log`

`context/artifact_reference_bundle.md` is the recommended single file for your main AI to read first.
It summarizes current state, changed files, recent failures, and points at the raw artifacts.

`context/agent_brief_bundle_integration_examples.md` contains ready-to-paste snippets showing how to
reference the bundle from `main_agent_brief.md`, `docker_agent_brief.md`, and `validator_agent_brief.md`.

You can customize the directory per project with:

```bash
ai-docker-watcher update --name gui-ai-project --artifact-dir .my-artifacts
```

## Notes

- This is an MVP sidecar runtime.
- The fallback Docker agent is rule-based.
- The fallback validator is runner-based (`docker build`, `docker compose config` when available).
