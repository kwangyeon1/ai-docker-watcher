# ai-docker-watcher

Event-driven sidecar agent runner for Docker generation and validation.

## What it does

- Watches workspace file changes
- Publishes events to a lightweight event bus
- Runs a Docker-focused agent when Docker-impacting files change
- Runs a Validator agent before/after build checks
- Persists shared context in `.vibe/` so your main AI editor/CLI can read it

## Architecture

- Main AI editor/CLI remains primary
- `ai-docker-watcher` runs beside it as a sidecar
- Collaboration is indirect via shared state under `.vibe/`

```text
Main AI -> file changes -> watcher -> event bus
                          -> docker agent -> validator -> feedback loop
                                            -> .vibe/context|state|reports|events
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
  --workspace /home/kss930/analytics_project/gui-ai-project
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

## `.vibe` layout

Inside target workspace:

- `.vibe/context/repo_summary.md`
- `.vibe/context/main_agent_brief.md`
- `.vibe/context/docker_agent_brief.md`
- `.vibe/context/validator_agent_brief.md`
- `.vibe/state/changed_files.json`
- `.vibe/state/task_state.json`
- `.vibe/reports/docker_report.md`
- `.vibe/reports/validation_report.json`
- `.vibe/events/events.log`

## Notes

- This is an MVP sidecar runtime.
- The fallback Docker agent is rule-based.
- The fallback validator is runner-based (`docker build`, `docker compose config` when available).
