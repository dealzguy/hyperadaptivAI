# Deployment Runbook — [OPERATOR NAME] — [DATE]

*This template is filled during Phase E deployment with a real operator.
It becomes the operational reference for that specific deployment.*

---

## Host specification

- Machine: [VM/VPS/physical — spec]
- OS: [Linux distribution and version]
- IP/domain: [...]
- Podman version: [...]

---

## Pre-deployment checklist

- [ ] SSH access confirmed
- [ ] Podman installed and running
- [ ] `deploy/secrets/secrets.env` populated with `ANTHROPIC_API_KEY` and Postgres credentials
- [ ] `INFER_ALLOWED_PREFIXES` set in `secrets.env` (default: `anthropic/`)
- [ ] Domain/IP configured for Temporal UI access (optional)
- [ ] Host meets minimum spec: 4 CPU cores, 8 GB RAM, 50 GB disk

---

## Deployment steps

1. Clone the repo or copy the deploy bundle to the host
2. `cd version1/deploy && podman compose -f compose.yaml up -d`
3. Wait for `postgres-business` to be healthy: `podman compose ps`
4. Run bootstrap: `podman exec harness-worker python -m harness.shared.persistence.bootstrap`
5. Verify Temporal UI at `http://[host]:8080`

---

## Commissioning

1. Run the commissioning workflow with the operator's business description
2. Review the generated config bundle with the operator (INTERVIEW → DISSECT → CONSTRUCT → VALIDATE stages)
3. One-click promote to production (one human action required — never auto-promote)

---

## Post-deployment verification

- [ ] Temporal worker connected and polling (visible in Temporal UI under Workers)
- [ ] Bootstrap completed (system entity created, schema applied)
- [ ] Test lead intake: submit one lead via the intake form
- [ ] Verify the lead appears in the Temporal UI as a running `LeadIntakeWorkflow`
- [ ] Verify gate fires for compensable actions (check `list-gates` output)

---

## Operator CLI setup

```bash
export TEMPORAL_HOST=localhost:7233
export DB_HOST=localhost
export DB_PORT=5433
export POSTGRES_USER=[from secrets.env]
export POSTGRES_PASSWORD=[from secrets.env]
export POSTGRES_DB=[from secrets.env]

# List open gate approvals
python -m harness.operations.operator_cli list-gates

# Show full detail of a single pending gate
python -m harness.operations.operator_cli show-gate <decision_id>

# Approve a gate decision
python -m harness.operations.operator_cli approve <decision_id>

# Reject a gate decision
python -m harness.operations.operator_cli reject <decision_id>

# Edit and approve (supply modified action type and JSON payload)
python -m harness.operations.operator_cli edit <decision_id> --action-type <type> --action-payload '{"stage_id": "qualified"}'
```

---

## Ongoing operations

- Daily: `python -m harness.operations.operator_cli digest`
- Gate approvals: `python -m harness.operations.operator_cli list-gates` → approve/reject/edit
- Pause a flow: `python -m harness.operations.operator_cli pause-flow lead-intake-first-follow-up`
- Resume a flow: `python -m harness.operations.operator_cli resume-flow lead-intake-first-follow-up`

---

## Model migration procedure

Change `model_policy.decide` and `model_policy.escalate` in the config bundle JSON,
re-run the `construct` commissioning stage, one-click promote. No data or workflow code
changes required — model IDs are config, not code (invariant 2).

---

## Incident procedures

[TO BE FILLED during first live deployment]

Suggested outline:
- Worker down: `podman compose restart harness-worker` → verify reconnection in Temporal UI
- DB unavailable: check `podman compose ps`, inspect `postgres-business` container logs
- Stuck workflow: use Temporal UI → terminate or reset the workflow; investigate activity errors
- Gate queue backlog: run `list-gates`; batch-approve or reject as appropriate
- Model API outage: update `ANTHROPIC_API_KEY` or switch `INFER_ALLOWED_PREFIXES` to a
  backup provider in `secrets.env`; restart worker

---

## Secrets rotation

1. Update `deploy/secrets/secrets.env` with new credentials
2. `podman compose restart harness-worker` — worker reloads env on start
3. For Postgres password rotation: also update the Postgres container env and re-apply;
   coordinate with any open workflow instances to avoid mid-flight DB auth failure

---

## Scaling notes

[TO BE FILLED]

- Additional workers: add replicas in `compose.yaml` (same task queue, Temporal handles
  distribution automatically)
- Separate commissioning queue: resolve the `commissioning task queue` liquid in
  `docs/LIQUID-RESOLUTIONS.md` before scaling commissioning independently
