# Deploy bundle — lay-down and verify

This directory is the declarative deploy bundle for Phase A.  `compose.yaml`
describes four pods; `make up` from the repo root brings them all up.

---

## Prerequisites

| Requirement | Verified by |
|-------------|-------------|
| Podman 5.x installed | `podman --version` |
| Docker Compose V2 plugin (Apache 2.0) | `docker compose version` |
| Podman socket enabled | `systemctl --user enable --now podman.socket` |
| `DOCKER_HOST` pointed at Podman socket | `export DOCKER_HOST=unix:///run/user/$(id -u)/podman/podman.sock` |
| `.env` created from `.env.example` | `cp deploy/.env.example deploy/.env && $EDITOR deploy/.env` |

---

## Lay-down

```bash
# From repo root:
export DOCKER_HOST=unix:///run/user/$(id -u)/podman/podman.sock
make up
```

Expected: all 6 services reach **Running** state.  Temporal and its Postgres
may take ~30 seconds to become healthy on first start (schema auto-setup).

Verify:
```bash
docker compose -f deploy/compose.yaml ps
```

All services should show `healthy` or `running`.

---

## Smoke tests (no containers required)

```bash
make test
```

Both test files run in-process using Temporal's time-skipping test environment.
No running services needed.

---

## Kill-the-worker durability demonstration

This procedure is the gate evidence for "a worker killed mid-execution resumes
exactly."  Run it after `make up`.

**Step 1.** Start the harness worker locally (pointing at the containerised
Temporal):

```bash
export TEMPORAL_ADDRESS=localhost:7233
uv run python -m harness.worker &
WORKER_PID=$!
echo "Worker PID: $WORKER_PID"
```

**Step 2.** Trigger the hello-world workflow:

```bash
temporal workflow start \
  --type HelloWorkflow \
  --task-queue harness-main \
  --workflow-id durability-demo \
  --input '"world"'
```

**Step 3.** Kill the worker while the activity is sleeping (you have ~2 seconds):

```bash
kill -9 $WORKER_PID
echo "Worker killed."
```

**Step 4.** Open the Temporal Web UI at http://localhost:8080 and observe
workflow `durability-demo` in **Running** state with no available workers.

**Step 5.** Restart the worker:

```bash
uv run python -m harness.worker &
```

**Step 6.** The workflow resumes from its Temporal event history and completes.
Verify in the Web UI: status changes to **Completed**.

**Step 7.** Inspect the event history:

```bash
temporal workflow show --workflow-id durability-demo
```

The history shows the activity scheduled before the kill and completed after
the restart — deterministic replay.  This is the exit-gate evidence.

---

## Three-way separation — inspection

```bash
docker compose -f deploy/compose.yaml config | grep -A3 'volumes:'
```

Confirms: named volumes (`business_data`, `temporal_data`, `model_cache`) are
data; the `config/` bind mount is configuration; images are software.  The
three never fuse.

---

## Stopping

```bash
make down
# Data volumes are preserved.  To remove volumes too:
# docker compose -f deploy/compose.yaml down -v
```
