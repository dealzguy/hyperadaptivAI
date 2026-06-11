# Deploy bundle — lay-down and verify

This directory is the declarative deploy bundle for Phase A.  `compose.yaml`
describes four pods; `make up` from the repo root brings them all up.

`compose.yaml` uses standard Compose v3 syntax, which Podman handles via
`podman compose` (Podman 4.7+) or `podman-compose` (pip-installable).

---

## Prerequisites

| Requirement | Verified by |
|-------------|-------------|
| Podman 4.7+ installed | `podman --version` |
| Compose support | `podman compose version` — if missing, `pip install podman-compose` |
| Temporal CLI (MIT) | `temporal --version` — install: `curl -sSf https://temporal.download/cli.sh \| sh` |
| `.env` created from `.env.example` | `cp deploy/.env.example deploy/.env && $EDITOR deploy/.env` |

**Note on `podman compose` vs `podman-compose`:**
Podman 4.7+ ships `podman compose` as a built-in subcommand that delegates to
`podman-compose` if installed.  `podman-compose` is GPL-2.0 — a dev-side
deployment tool only, never linked into the harness, never shipped in the
product.  This is the "separate process" case from Doc 8; the GPL does not
propagate into the harness.

The Temporal CLI is used only to trigger and inspect workflows from the host
during verification; it is not part of the deployed bundle.

---

## Lay-down

```bash
# From repo root:
cp deploy/.env.example deploy/.env   # then edit passwords
make up
```

Expected: all 6 services reach **Running** state.  Temporal may take ~30
seconds on first start (schema auto-setup); the harness worker prints
connection retries until Temporal is ready, then "Worker started".

Verify:
```bash
make ps        # or: cd deploy && podman compose ps
make logs      # watch for "Worker started" from the harness service
```

---

## Smoke tests (no containers required)

```bash
make test
```

Both test files run in-process using Temporal's time-skipping test environment.
No running services needed.

---

## Kill-the-worker durability demonstration

Gate evidence for "a worker killed mid-execution resumes exactly."  The kill
target is the **containerized harness worker** — do not start a second worker
on the host; two workers on one task queue would make the demonstration
ambiguous.

**Step 1.** Confirm the stack is up and the harness worker is polling:

```bash
make ps
make logs    # harness service shows "Worker started"; Ctrl-C to detach
```

**Step 2.** Trigger the workflow and kill the worker mid-activity, in one
paste (the activity sleeps 2 seconds; the kill lands inside that window):

```bash
temporal workflow start \
  --type HelloWorkflow \
  --task-queue harness-main \
  --workflow-id durability-demo \
  --input '"world"' \
&& (cd deploy && podman compose kill harness)
```

`podman compose kill` delivers SIGKILL — the worker dies hard, mid-activity,
with no chance to clean up.

**Step 3.** Observe in the Temporal Web UI (http://localhost:8080): workflow
`durability-demo` is **Running** with a pending activity.  The harness
container exited with code 137 (SIGKILL).

**Step 4.** The `restart: unless-stopped` policy resurrects the harness
container automatically.  Within ~10 seconds (the activity's start-to-close
timeout) the activity retry fires on the restarted worker and the workflow
completes.  Nothing is re-entered by hand; the recovery is entirely Temporal's.

**Step 5.** Inspect the event history:

```bash
temporal workflow show --workflow-id durability-demo
```

The history shows the first `ActivityTaskStarted` with no completion (the
kill), then a second attempt that completes, then
`WorkflowExecutionCompleted`.  Exact resume from event history — this is the
exit-gate evidence.

**Optional — slow-motion variant.**  To hold the system in the "no worker"
state and observe it: `cd deploy && podman compose stop harness` (an explicit
stop, so the restart policy stays out of the way), trigger a workflow, watch
it park in the UI with no workers available, then `podman compose start
harness` and watch it complete.

---

## Three-way separation — inspection

Software, configuration, and data live in three demonstrably different places:

```bash
# Data: three named volumes, managed by Podman, never inside an image
podman volume ls | grep hyperadaptivai

# Config: read-only bind mount into the harness pod only
podman inspect hyperadaptivai_harness_1 --format '{{range .Mounts}}{{.Source}} -> {{.Destination}} (RW={{.RW}}){{"\n"}}{{end}}'

# Software: pinned OCI images
podman images | grep -E 'temporal|pgvector|postgres|ollama'
```

(Container name may vary slightly by podman-compose version; `make ps` lists
the actual names.)

---

## Stopping

```bash
make down
# Data volumes are preserved.  To remove volumes too:
# cd deploy && podman compose down -v
```
