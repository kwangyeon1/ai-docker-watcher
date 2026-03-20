# ai-docker-watcher

Docker 생성과 검증을 파일 변경 기반으로 자동화하는 사이드카 러너입니다.  
메인 AI 편집기나 CLI가 주 작업을 수행하고, `ai-docker-watcher`는 옆에서 Docker 관련 변경을 감지해 `Dockerfile` 생성/수정, 검증, 피드백 루프, 산출물 문서 생성을 담당합니다.

어떤상황에서 사용해야합니까? :
- 사람이 IDE로 코드를 수정하고 개발할때, 코드 수정 내용을 토대로 러너가  `requirements.txt`, `docker-compose.yml`등을 감시하고 Dockerfile을 생성 혹은 수정및 검증까지 자동으로 합니다.

## 한국어 가이드

### 개요

- 워크스페이스의 파일 변경을 감지합니다.
- Docker 관련 영향이 있는 변경이면 Docker agent를 실행합니다.
- Docker agent 결과가 나오면 validator agent가 `docker build` 및 `docker compose config` 검증을 수행합니다.
- 실패 시 validator 결과를 다시 Docker agent에 전달해 재수정 루프를 돌립니다.
- 결과를 기본적으로 `.vibe-docker/` 아래에 저장합니다.
- 메인 AI가 한 번에 읽을 수 있도록 `context/artifact_reference_bundle.md`를 생성합니다.

### 동작 구조

```text
Main AI -> file changes -> watcher -> event bus
                          -> docker agent -> validator -> feedback loop
                                            -> .vibe-docker/context|state|reports|events
```

중요한 점:

- Docker agent와 validator agent가 직접 대화하지는 않습니다.
- `EventRouter`가 각 agent 결과를 받아 다음 단계에 전달합니다.
- 외부 agent를 붙일 때는 stdin/stdout JSON으로 통신합니다.

### 설치

```bash
cd ai-docker-watcher
python -m pip install -e .
```

설치 후 CLI:

```bash
ai-docker-watcher --help
```

### 빠른 시작

1. 프로젝트 등록

```bash
ai-docker-watcher add \
  --name gui-ai-project \
  --workspace /home/kss930/analytics_project/gui-ai-project \
  --artifact-dir .vibe-docker
```

2. 등록된 프로젝트 확인

```bash
ai-docker-watcher list
```

3. 1회 실행

```bash
ai-docker-watcher run \
  --name gui-ai-project \
  --once
```

4. 지속 감시 실행

```bash
ai-docker-watcher run --name gui-ai-project
```

### 프로젝트 관리 명령

프로젝트 추가:

```bash
ai-docker-watcher add \
  --name gui-ai-project \
  --workspace /home/kss930/analytics_project/gui-ai-project \
  --interval 2.0 \
  --max-feedback-loops 2 \
  --artifact-dir .vibe-docker
```

비활성 상태로 등록:

```bash
ai-docker-watcher add \
  --name gui-ai-project \
  --workspace /home/kss930/analytics_project/gui-ai-project \
  --disabled
```

활성/비활성 전환:

```bash
ai-docker-watcher enable --name gui-ai-project
ai-docker-watcher disable --name gui-ai-project
```

설정 업데이트:

```bash
ai-docker-watcher update \
  --name gui-ai-project \
  --interval 1.0 \
  --max-feedback-loops 3 \
  --artifact-dir .vibe-docker
```

외부 agent 명령 직접 지정:

```bash
ai-docker-watcher update \
  --name gui-ai-project \
  --docker-agent-cmd "python /opt/agents/docker_worker.py" \
  --validator-agent-cmd "python /opt/agents/validator_worker.py"
```

외부 agent 명령 제거:

```bash
ai-docker-watcher update --name gui-ai-project --clear-docker-agent-cmd
ai-docker-watcher update --name gui-ai-project --clear-validator-agent-cmd
```

### Bridge 기반 AI 연동

`set-bridge`는 `projects.json`에 bridge 명령을 자동으로 기록합니다.  
지원 provider:

- `codex`
- `claude`
- `custom`

Codex bridge 예시:

```bash
ai-docker-watcher set-bridge \
  --name gui-ai-project \
  --docker-provider codex \
  --validator-provider codex
```

Docker는 Codex, validator는 Claude로 설정:

```bash
ai-docker-watcher set-bridge \
  --name gui-ai-project \
  --docker-provider codex \
  --validator-provider claude
```

Custom provider 예시:

```bash
ai-docker-watcher set-bridge \
  --name gui-ai-project \
  --docker-provider custom \
  --docker-provider-command "my-ai-cli --json"
```

Python 실행 경로를 명시해야 할 때:

```bash
ai-docker-watcher set-bridge \
  --name gui-ai-project \
  --docker-provider codex \
  --validator-provider codex \
  --python-bin python3
```

`set-bridge`가 생성하는 명령 예시:

- `python /abs/path/ai_docker_watcher/bridge.py --role docker --provider codex`
- `python /abs/path/ai_docker_watcher/bridge.py --role validator --provider claude`

### 실행 방법

모든 활성 프로젝트 실행:

```bash
ai-docker-watcher run
```

특정 이름만 실행:

```bash
ai-docker-watcher run --name gui-ai-project
```

특정 workspace만 1회 실행:

```bash
ai-docker-watcher run \
  --workspace /home/kss930/analytics_project/gui-ai-project \
  --once
```

실행 시 artifact 디렉토리만 임시로 덮어쓰기:

```bash
ai-docker-watcher run \
  --name gui-ai-project \
  --artifact-dir .my-artifacts \
  --once
```

다른 설정 파일 사용:

```bash
ai-docker-watcher --config /path/to/projects.json list
```

### `projects.json` 예시

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
      "docker_agent_cmd": "python /abs/path/to/bridge.py --role docker --provider codex",
      "validator_agent_cmd": "python /abs/path/to/bridge.py --role validator --provider codex"
    }
  ]
}
```

### 외부 agent 입출력 형식

각 external command는 stdin으로 JSON을 받고 stdout으로 JSON을 반환해야 합니다.

Docker agent 입력 예시:

```json
{
  "workspace": "/abs/workspace",
  "changed_files": ["requirements.txt", "docker-compose.yml"],
  "validation_feedback": {}
}
```

Docker agent 출력 예시:

```json
{
  "status": "ok",
  "summary": "updated Dockerfile",
  "files": [
    {
      "path": "Dockerfile",
      "content": "FROM python:3.12-slim\nWORKDIR /app\n..."
    }
  ]
}
```

Validator agent 입력 예시:

```json
{
  "workspace": "/abs/workspace"
}
```

Validator agent 출력 예시:

```json
{
  "status": "failed",
  "summary": "docker build failed",
  "owner": "docker-agent"
}
```

### 산출물 구조

기본 산출물 디렉토리:

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

주요 파일 설명:

- `context/artifact_reference_bundle.md`: 메인 AI가 가장 먼저 읽기 좋은 통합 진입점
- `context/agent_brief_bundle_integration_examples.md`: `AGENTS.md`, `CLAUDE.md`, `CODEX.md` 등에 복붙할 예시 문구
- `context/recent_failures.md`: 최근 실패를 사람이 읽기 쉽게 정리
- `reports/docker_report.md`: Docker agent 결과 요약
- `reports/validation_report.json`: validator의 기계 판독용 결과

### 실제 사용 예시

예시 1. 로컬 규칙 기반 fallback만 사용:

```bash
ai-docker-watcher add \
  --name demo \
  --workspace /home/user/demo-app

ai-docker-watcher run --name demo --once
```

이 경우:

- Docker 영향 파일이 있으면 baseline `Dockerfile` 생성 시도
- `docker` CLI가 있으면 validator가 `docker build` 수행
- 결과는 `.vibe-docker/`에 기록

예시 2. Codex bridge를 붙여서 Docker 수정 자동화:

```bash
ai-docker-watcher set-bridge \
  --name gui-ai-project \
  --docker-provider codex \
  --validator-provider codex

ai-docker-watcher run --name gui-ai-project
```

이 경우:

- Docker agent가 AI 추론으로 `Dockerfile` 수정안 생성
- validator가 build 결과를 다시 피드백
- 메인 AI는 `context/artifact_reference_bundle.md`만 읽고 현재 상황을 빠르게 파악 가능

예시 3. 메인 AI 문서에 번들 참조를 넣기:

`AGENTS.md` 예시:

```md
## Docker Sidecar Intake

- For Docker-related tasks, read `context/artifact_reference_bundle.md` first.
- Use the bundle before changing Dockerfile, Compose, or dependency manifests.
```

### 주의사항

- 현재는 MVP 성격의 사이드카 런타임입니다.
- fallback Docker agent는 규칙 기반입니다.
- fallback validator는 `docker build`, `docker compose config` 기반입니다.
- artifact 디렉토리는 watcher 감시 대상에서 제외됩니다.

---

## English Summary

`ai-docker-watcher` is an event-driven sidecar runner for Docker generation and validation.
It watches workspace changes, runs a Docker-focused agent when Docker-related files change,
then runs a validator agent and stores shared artifacts under `.vibe-docker/`.

### Install

```bash
cd ai-docker-watcher
python -m pip install -e .
```

### Typical Flow

```bash
ai-docker-watcher add \
  --name gui-ai-project \
  --workspace /home/kss930/analytics_project/gui-ai-project

ai-docker-watcher set-bridge \
  --name gui-ai-project \
  --docker-provider codex \
  --validator-provider codex

ai-docker-watcher run --name gui-ai-project
```

### Key Commands

```bash
ai-docker-watcher list
ai-docker-watcher enable --name gui-ai-project
ai-docker-watcher disable --name gui-ai-project
ai-docker-watcher run --name gui-ai-project --once
ai-docker-watcher update --name gui-ai-project --artifact-dir .my-artifacts
```

### Key Artifacts

- `context/artifact_reference_bundle.md`
- `context/agent_brief_bundle_integration_examples.md`
- `context/recent_failures.md`
- `reports/docker_report.md`
- `reports/validation_report.json`
- `state/changed_files.json`
- `state/task_state.json`

### External Agent Contract

- External commands receive JSON through stdin.
- External commands must return JSON through stdout.
- Docker agent returns `status`, `summary`, `files`.
- Validator returns `status`, `summary`, `owner`.
