# Deploy bundle — lay-down and verify

This directory is the declarative deploy bundle for Phase A.  `compose.yaml`
describes four pods; `make up` from the repo root brings them all up.

`compose.yaml` uses standard Docker Compose v3 syntax, which Podman handles
via `podman compose` (Podman 4.7+) or `podman-compose` (pip-installable).

---

## Prerequisites

| Requirement | Verified by |
|-------------|-------------|
| Podman 4.7+ installed | `podman --version` |
| Compose support | `podman compose version` — if missing, `pip install podman-compose` |
| `.env` created from `.env.example` | `cp deploy/.env.example deploy/.env && $EDITOR deploy/.env` |

**Note on `podman compose` vs `podman-compose`:**
Podman 4.7+ ships `podman compose` as a built-in subcommand.  It delegates
to `podman-compose` if that package is installed.  Install it once:

```bash
pip install podman-compose
```

`podman-compose` is GPL-2.0.  It is a dev-side deployment tool only — never
linked into the harness, never shipped in the product.  This is the "separate
process" case from Doc 8; the GPL does not propagate into the harness.

---

## Lay-down

```bash
# From repo root:
cp deploy/.env.example deploy/.env   # then edit passwords
make up
```

Expected: all 6 services reach **Running** state.  Temporal and its Postgres
may take ~30 seconds to become healthy on first start (schema auto-setup).

Verify:
```bash
podman compose -f deploy/compose.yaml ps
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
uv run --extra dev python -m harness.worker &
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
uv run --extra dev python -m harness.worker &
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
podman compose -f deploy/compose.yaml config | grep -A3 'volumes:'
```

Confirms: named volumes (`business_data`, `temporal_data`, `model_cache`) are
data; the `config/` bind mount is configuration; images are software.  The
three never fuse.

---

## Stopping

```bash
make down
# Data volumes are preserved.  To remove volumes too:
# podman compose -f deploy/compose.yaml down -v
```
