# Deploy Bundle — Phase A

Provisional compose bundle for the Phase A walking skeleton.
Quadlet format stays liquid until Phase E host observation (doc 13).

---

## Prerequisites

- Podman >= 4.0 with `podman-compose`, **or** Docker Engine with `docker compose` CLI
- Port availability on the host:
  - `7233` — Temporal gRPC frontend
  - `8080` — Temporal Web UI
  - `11434` — Ollama inference API
  - `5432` — **not** exposed externally (both Postgres instances stay container-internal)
- The `temporal` CLI installed on the host for manual workflow commands
  (install from <https://docs.temporal.io/cli#install>)
- Python 3.12 on the host for running tests

---

## Three-way separation — invariant

This bundle enforces the constraint from `docs/12-initial-build-prompt.md` §6:

| Tier | What goes here | Mechanism |
|------|---------------|-----------|
| **Software** | All executable code and dependencies | OCI images; never in volumes or bind-mounts |
| **Config** | `deploy/config/` templates | Bind-mounted read-only into `harness-worker` at `/app/config` |
| **Data** | Database files and model weights | Named volumes prefixed `data-` |

None of these three tiers ever touch each other's storage.

---

## First-time setup

```bash
# Work from the deploy/ directory for all compose commands
cd /path/to/version1/deploy

# 1. Create the secrets file from the template
cp secrets/secrets.env.template secrets/secrets.env
# Edit secrets/secrets.env — set POSTGRES_PASSWORD to a non-default value.
# This file is gitignored and must never be committed.

# 2. Review the harness config template (adjust LOG_LEVEL if needed)
cat config/harness.env.template
# The compose file injects TEMPORAL_HOST and TEMPORAL_TASK_QUEUE via environment:
# block, so harness.env.template is informational for Phase A.
```

---

## Lay down the bundle

```bash
# From deploy/
podman compose -f compose.yaml up -d --build
```

The `--build` flag builds the `harness-worker` image from `../Dockerfile.harness`
on first run (and after any harness code change).

### Verify all services are running

```bash
podman compose -f compose.yaml ps
```

Expected: all six services show `running` or `healthy`.

| Service | Image | Role |
|---------|-------|------|
| `postgres-business` | `pgvector/pgvector:pg16` | Business data (pgvector) — Temporal never touches this |
| `postgres-temporal` | `postgres:16.3` | Temporal event store — business code never touches this |
| `temporal` | `temporalio/auto-setup:1.27.2` | Temporal server + automatic schema init |
| `temporal-ui` | `temporalio/ui:2.31.2` | Temporal Web UI |
| `ollama` | `ollama/ollama:0.6.5` | Inference pod (behind stub in Phase A) |
| `harness-worker` | built from `Dockerfile.harness` | Temporal worker — HelloWorkflow + hello_activity |

---

## Verify the bundle (Phase A exit gate)

Run these checks in order. All must pass before Phase A is declared done (doc 13).

### 1. Temporal gRPC health

```bash
temporal workflow list --address localhost:7233
# Empty list is fine — the server just needs to respond without error.
```

### 2. Temporal Web UI

Open <http://localhost:8080> in a browser. The Workflows page should load and
show the `default` namespace.

### 3. Unit tests (no running stack required)

From the project root (`version1/`):

```bash
pip install -e ".[dev]"
pytest tests/ -m "not integration" -v
# Expected: all non-integration tests PASSED
```

### 4. Integration test (requires running stack)

```bash
# From version1/
pytest tests/ -m integration -v
# Expected: test_hello_workflow_end_to_end PASSED
```

The integration test starts a `HelloWorkflow`, waits for its result, and asserts
the workflow completed without errors.

### 5. Verify three-way separation

```bash
# Named data volumes exist
podman volume ls | grep data-
# Expected lines (order may vary):
#   local   data-business
#   local   data-temporal-db
#   local   data-ollama

# Config is bind-mounted, not baked in; confirm harness-worker sees /app/config
podman exec deploy_harness-worker_1 ls /app/config
# Expected: harness.env.template (or files you placed there)

# No secrets or config inside the harness image itself
podman run --rm deploy_harness-worker cat /app/secrets.env 2>&1 || true
# Expected: error — file does not exist in the image
```

> **Note on container name prefix.** `podman compose` derives the project name
> from the directory containing `compose.yaml` (`deploy` in this repo).
> Container names therefore follow the pattern `deploy_<service>_1`.
> If you run from a different working directory or set `COMPOSE_PROJECT_NAME`,
> adjust the container names in the commands below accordingly.

---

## Kill-the-worker exact-resume test (Phase A exit gate — clause 3)

This procedure proves Temporal resumes a workflow **exactly where it left off**
after a worker is killed — not from the beginning. It is the definitive
demonstration of durable execution.

The `HelloWorkflow` calls one activity (`hello_activity`). Because the workflow
is trivial and fast, a slow-activity variant is used here to create a window
for the kill. Use a long `start_to_close_timeout` and observe the event history.

### Step 1 — Start a workflow

```bash
temporal workflow start \
  --type HelloWorkflow \
  --task-queue skeleton-queue \
  --workflow-id kill-resume-test-01 \
  --input '"Phase-A"' \
  --address localhost:7233
```

The `--input` value is the JSON-encoded `name` argument to `HelloWorkflow.run`.
With `"Phase-A"` the expected result is `Hello, Phase-A!`.

### Step 2 — Observe it running

Open the Temporal UI at <http://localhost:8080>, navigate to the `default`
namespace, and find `kill-resume-test-01`. Status should be `Running`.

Alternatively:

```bash
temporal workflow describe \
  --workflow-id kill-resume-test-01 \
  --address localhost:7233
```

### Step 3 — Kill the harness-worker container

```bash
podman kill deploy_harness-worker_1
```

### Step 4 — Confirm the workflow is still Running (not Failed)

In the Temporal UI, `kill-resume-test-01` must still show `Running` — not
`Failed` or `Timed Out`. Temporal holds the complete event history in its own
Postgres (`postgres-temporal`); the business container disappearing has no
effect on that record.

```bash
temporal workflow describe \
  --workflow-id kill-resume-test-01 \
  --address localhost:7233
# Status field must read: Running
```

### Step 5 — Restart the worker

```bash
podman start deploy_harness-worker_1
# OR bring it up via compose (preferred — respects depends_on and restart policy):
podman compose -f compose.yaml up -d harness-worker
```

### Step 6 — Confirm the workflow completes

After the worker reconnects, Temporal replays the event history and delivers the
workflow result. In the UI or via CLI:

```bash
temporal workflow show \
  --workflow-id kill-resume-test-01 \
  --address localhost:7233
```

### Pass criteria

| Check | Expected |
|-------|----------|
| Workflow final status | `Completed` |
| Workflow result | `"Hello, Phase-A!"` |
| Activity re-execution | `ActivityTaskCompleted` event in the history **predates** the worker restart timestamp — the activity was **not** re-run |

To confirm the activity was not re-run, open the event history in the Temporal UI
and verify the `ActivityTaskCompleted` event timestamp is **before** the moment
you ran `podman kill`. If the activity result came from history replay, not a
fresh execution, the test passes.

---

## Shut down

```bash
# From deploy/
# Stop and remove containers, networks
podman compose -f compose.yaml down

# Stop and also remove named data volumes (destructive — deletes all data)
podman compose -f compose.yaml down -v
```

> **Warning.** `down -v` permanently deletes `data-business`, `data-temporal-db`,
> and `data-ollama`. Use only when you intend a clean slate.
