"""Operator CLI — human interface to the consequence-gate approval queue.

Allows a business operator to:
  - List / inspect pending gate-approval tasks
  - Approve, reject, or edit proposed actions
  - Pause / resume individual workflow instances
  - Toggle flow-class pause (parks all instances at the next safe boundary)
  - Get a daily operational digest

Entry points:
  python -m harness.operations.operator_cli <command> [args]
  python harness/operations/operator_cli.py <command> [args]

Connection config (env vars, with defaults for local dev):
  TEMPORAL_HOST          — Temporal frontend address (default: localhost:7233)
  TEMPORAL_TASK_QUEUE    — task queue name (default: skeleton-queue)
  DB_HOST                — Postgres host (default: localhost)
  DB_PORT                — Postgres port (default: 5433, matching compose.dev.yaml)
  POSTGRES_DB            — database name (default: hyperadaptiv)
  POSTGRES_USER          — database user (default: "")
  POSTGRES_PASSWORD      — database password (default: "")
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import date, datetime, timezone

import asyncpg
from temporalio.client import Client
from temporalio.service import RPCError

from harness.operations.workflows.agent_loop import AgentLoopWorkflow
from harness.shared.persistence.constants import SYSTEM_ENTITY_ID

logger = logging.getLogger(__name__)

# ── Connection config ─────────────────────────────────────────────────────────

TEMPORAL_HOST = os.environ.get("TEMPORAL_HOST", "localhost:7233")
TEMPORAL_TASK_QUEUE = os.environ.get("TEMPORAL_TASK_QUEUE", "skeleton-queue")
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", "5433"))
DB_NAME = os.environ.get("POSTGRES_DB", "hyperadaptiv")
DB_USER = os.environ.get("POSTGRES_USER", "")
DB_PASS = os.environ.get("POSTGRES_PASSWORD", "")


# ── Connection helpers ────────────────────────────────────────────────────────

async def make_client() -> Client:
    """Connect to Temporal and return the client."""
    return await Client.connect(TEMPORAL_HOST)


async def make_pool() -> asyncpg.Pool:
    """Create a fresh asyncpg pool for CLI use."""
    return await asyncpg.create_pool(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        min_size=1,
        max_size=5,
    )


# ── Formatting helpers ────────────────────────────────────────────────────────

def _fmt_ts(ts: datetime | None) -> str:
    if ts is None:
        return "—"
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.strftime("%Y-%m-%d %H:%M:%S UTC")


def _print_table(headers: list[str], rows: list[list[str]]) -> None:
    """Print a simple fixed-width table to stdout."""
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))

    sep = "  ".join("-" * w for w in col_widths)
    header_line = "  ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
    print(header_line)
    print(sep)
    for row in rows:
        print("  ".join(str(cell).ljust(col_widths[i]) for i, cell in enumerate(row)))


# ── Command implementations ───────────────────────────────────────────────────

async def run_list_gates(args: argparse.Namespace, client: Client, pool: asyncpg.Pool) -> None:
    """List all open gate-approval tasks with their workflow state."""
    rows = await pool.fetch(
        """
        SELECT id, entity_id, attributes, created_at
        FROM task
        WHERE type = 'agent_gate_approval' AND status = 'open'
        ORDER BY created_at ASC
        """
    )

    if not rows:
        print("No open gate-approval tasks.")
        return

    # Batch-fetch workflow state for each unique workflow_id
    workflow_states: dict[str, dict] = {}
    seen_wf_ids: set[str] = set()
    for row in rows:
        attrs = row["attributes"] or {}
        wf_id = attrs.get("workflow_id")
        if wf_id and wf_id not in seen_wf_ids:
            seen_wf_ids.add(wf_id)
            try:
                handle = client.get_workflow_handle(wf_id)
                state = await handle.query(AgentLoopWorkflow.get_state)
                workflow_states[wf_id] = state
            except RPCError as exc:
                workflow_states[wf_id] = {"error": str(exc)}
            except Exception as exc:
                workflow_states[wf_id] = {"error": str(exc)}

    headers = [
        "decision_id",
        "action_type",
        "consequence",
        "entity_id",
        "workflow_id",
        "wf_paused",
        "created_at",
    ]
    table_rows = []
    for row in rows:
        attrs = row["attributes"] or {}
        wf_id = attrs.get("workflow_id", "")
        state = workflow_states.get(wf_id, {})
        paused_str = str(state.get("paused", "?")) if "error" not in state else "ERR"
        table_rows.append([
            attrs.get("decision_id", ""),
            attrs.get("action_type", ""),
            attrs.get("consequence_class", ""),
            str(row["entity_id"]),
            wf_id,
            paused_str,
            _fmt_ts(row["created_at"]),
        ])

    _print_table(headers, table_rows)
    print(f"\n{len(rows)} open gate(s).")


async def run_show_gate(args: argparse.Namespace, client: Client, pool: asyncpg.Pool) -> None:
    """Show full detail of a single pending gate by decision_id."""
    row = await pool.fetchrow(
        """
        SELECT id, entity_id, attributes, created_at
        FROM task
        WHERE type = 'agent_gate_approval'
          AND status = 'open'
          AND attributes->>'decision_id' = $1
        """,
        args.decision_id,
    )

    if row is None:
        print(f"No open gate found for decision_id={args.decision_id!r}")
        return

    attrs = row["attributes"] or {}
    print("=== Gate Detail ===")
    print(f"decision_id      : {attrs.get('decision_id', '')}")
    print(f"action_type      : {attrs.get('action_type', '')}")
    print(f"consequence_class: {attrs.get('consequence_class', '')}")
    print(f"entity_id        : {row['entity_id']}")
    print(f"workflow_id      : {attrs.get('workflow_id', '')}")
    print(f"created_at       : {_fmt_ts(row['created_at'])}")
    print()
    print("--- action_payload ---")
    print(json.dumps(attrs.get("action_payload", {}), indent=2))
    print()

    wf_id = attrs.get("workflow_id")
    if wf_id:
        try:
            handle = client.get_workflow_handle(wf_id)
            state = await handle.query(AgentLoopWorkflow.get_state)
            print("--- workflow state ---")
            print(json.dumps(state, indent=2))
        except RPCError as exc:
            print(f"[workflow query failed: {exc}]")
        except Exception as exc:
            print(f"[workflow query failed: {exc}]")


async def run_approve(args: argparse.Namespace, client: Client, pool: asyncpg.Pool) -> None:
    """Approve a pending gate by decision_id."""
    row = await pool.fetchrow(
        """
        SELECT attributes
        FROM task
        WHERE type = 'agent_gate_approval'
          AND status = 'open'
          AND attributes->>'decision_id' = $1
        """,
        args.decision_id,
    )

    if row is None:
        print(f"No open gate found for decision_id={args.decision_id!r}")
        return

    attrs = row["attributes"] or {}
    wf_id = attrs.get("workflow_id")

    await pool.execute(
        """
        UPDATE task
        SET status = 'approved'
        WHERE type = 'agent_gate_approval'
          AND status = 'open'
          AND attributes->>'decision_id' = $1
        """,
        args.decision_id,
    )

    if wf_id:
        try:
            handle = client.get_workflow_handle(wf_id)
            await handle.signal(
                AgentLoopWorkflow.resolve_gate,
                {"decision_id": args.decision_id, "verdict": "approve"},
            )
            print(f"Approved decision_id={args.decision_id!r}. Signal sent to workflow {wf_id!r}.")
        except RPCError as exc:
            print(
                f"DB updated to 'approved' but workflow signal failed "
                f"(workflow may have ended): {exc}"
            )
    else:
        print(f"Approved decision_id={args.decision_id!r} (no workflow_id in task attributes).")


async def run_reject(args: argparse.Namespace, client: Client, pool: asyncpg.Pool) -> None:
    """Reject a pending gate by decision_id."""
    row = await pool.fetchrow(
        """
        SELECT attributes
        FROM task
        WHERE type = 'agent_gate_approval'
          AND status = 'open'
          AND attributes->>'decision_id' = $1
        """,
        args.decision_id,
    )

    if row is None:
        print(f"No open gate found for decision_id={args.decision_id!r}")
        return

    attrs = row["attributes"] or {}
    wf_id = attrs.get("workflow_id")

    await pool.execute(
        """
        UPDATE task
        SET status = 'rejected'
        WHERE type = 'agent_gate_approval'
          AND status = 'open'
          AND attributes->>'decision_id' = $1
        """,
        args.decision_id,
    )

    if wf_id:
        try:
            handle = client.get_workflow_handle(wf_id)
            await handle.signal(
                AgentLoopWorkflow.resolve_gate,
                {"decision_id": args.decision_id, "verdict": "reject"},
            )
            print(f"Rejected decision_id={args.decision_id!r}. Signal sent to workflow {wf_id!r}.")
        except RPCError as exc:
            print(
                f"DB updated to 'rejected' but workflow signal failed "
                f"(workflow may have ended): {exc}"
            )
    else:
        print(f"Rejected decision_id={args.decision_id!r} (no workflow_id in task attributes).")


async def run_edit(args: argparse.Namespace, client: Client, pool: asyncpg.Pool) -> None:
    """Approve a gate with an edited action payload."""
    # Parse the JSON payload before touching the DB so we can fail early
    try:
        edited_payload = json.loads(args.action_payload)
    except json.JSONDecodeError as exc:
        print(f"Error: --action-payload is not valid JSON: {exc}")
        sys.exit(1)

    row = await pool.fetchrow(
        """
        SELECT attributes
        FROM task
        WHERE type = 'agent_gate_approval'
          AND status = 'open'
          AND attributes->>'decision_id' = $1
        """,
        args.decision_id,
    )

    if row is None:
        print(f"No open gate found for decision_id={args.decision_id!r}")
        return

    attrs = row["attributes"] or {}
    wf_id = attrs.get("workflow_id")

    await pool.execute(
        """
        UPDATE task
        SET status = 'approved'
        WHERE type = 'agent_gate_approval'
          AND status = 'open'
          AND attributes->>'decision_id' = $1
        """,
        args.decision_id,
    )

    resolution = {
        "decision_id": args.decision_id,
        "verdict": "edit",
        "edited_action": {
            "action_type": args.action_type,
            "action_payload": edited_payload,
        },
    }

    if wf_id:
        try:
            handle = client.get_workflow_handle(wf_id)
            await handle.signal(AgentLoopWorkflow.resolve_gate, resolution)
            print(
                f"Edited and approved decision_id={args.decision_id!r}. "
                f"Signal sent to workflow {wf_id!r}."
            )
            print(f"  action_type   : {args.action_type}")
            print(f"  action_payload: {json.dumps(edited_payload)}")
        except RPCError as exc:
            print(
                f"DB updated to 'approved' but workflow signal failed "
                f"(workflow may have ended): {exc}"
            )
    else:
        print(f"Edited and approved decision_id={args.decision_id!r} (no workflow_id).")


async def run_pause(args: argparse.Namespace, client: Client, pool: asyncpg.Pool) -> None:
    """Pause a single workflow instance by workflow_id."""
    try:
        handle = client.get_workflow_handle(args.workflow_id)
        await handle.signal(AgentLoopWorkflow.pause_instance)
        print(f"Pause signal sent to workflow {args.workflow_id!r}.")
        print("The instance will park at the top of its next iteration.")
    except RPCError as exc:
        print(f"Error sending pause signal to {args.workflow_id!r}: {exc}")


async def run_resume(args: argparse.Namespace, client: Client, pool: asyncpg.Pool) -> None:
    """Resume a paused workflow instance by workflow_id."""
    try:
        handle = client.get_workflow_handle(args.workflow_id)
        await handle.signal(AgentLoopWorkflow.resume_instance)
        print(f"Resume signal sent to workflow {args.workflow_id!r}.")
    except RPCError as exc:
        print(f"Error sending resume signal to {args.workflow_id!r}: {exc}")


async def run_pause_flow(args: argparse.Namespace, client: Client, pool: asyncpg.Pool) -> None:
    """Insert a flow-class pause state row so all instances park at the next safe boundary."""
    machine = f"flow_pause:{args.flow_id}"
    idem_key = f"flow_pause:{args.flow_id}:{int(time.time())}"

    await pool.execute(
        """
        INSERT INTO state (entity_id, machine, position, attributes, idempotency_key)
        VALUES ($1::uuid, $2, $3, $4::jsonb, $5)
        """,
        SYSTEM_ENTITY_ID,
        machine,
        "paused",
        json.dumps({}),
        idem_key,
    )
    print(f"Flow '{args.flow_id}' paused. Running instances will park at the next safe boundary.")


async def run_resume_flow(args: argparse.Namespace, client: Client, pool: asyncpg.Pool) -> None:
    """Insert a flow-class 'running' state row to lift the flow-class pause."""
    machine = f"flow_pause:{args.flow_id}"
    idem_key = f"flow_running:{args.flow_id}:{int(time.time())}"

    await pool.execute(
        """
        INSERT INTO state (entity_id, machine, position, attributes, idempotency_key)
        VALUES ($1::uuid, $2, $3, $4::jsonb, $5)
        """,
        SYSTEM_ENTITY_ID,
        machine,
        "running",
        json.dumps({}),
        idem_key,
    )
    print(
        f"Flow '{args.flow_id}' resumed. "
        "Paused instances need explicit `resume <workflow_id>` to wake up."
    )


async def run_digest(args: argparse.Namespace, client: Client, pool: asyncpg.Pool) -> None:
    """Print a daily operational digest."""
    today_start = datetime.combine(date.today(), datetime.min.time()).replace(
        tzinfo=timezone.utc
    )

    # Open gates
    open_gates_count = await pool.fetchval(
        "SELECT COUNT(*) FROM task WHERE type = 'agent_gate_approval' AND status = 'open'"
    )

    # Completed today (agent_loop_completed events)
    completed_today = await pool.fetchval(
        """
        SELECT COUNT(*)
        FROM event
        WHERE type = 'agent_loop_completed'
          AND occurred_at >= $1
        """,
        today_start,
    )

    # Autonomy transitions today
    autonomy_shifts = await pool.fetchval(
        """
        SELECT COUNT(*)
        FROM event
        WHERE type = 'autonomy_transition'
          AND occurred_at >= $1
        """,
        today_start,
    )

    # Active workflows — list running AgentLoopWorkflows via Temporal API
    active_count = 0
    try:
        async for _ in client.list_workflows(
            query="WorkflowType='AgentLoopWorkflow' AND ExecutionStatus='Running'"
        ):
            active_count += 1
    except Exception as exc:
        active_count = -1
        logger.warning("Could not list active workflows from Temporal: %s", exc)

    active_str = str(active_count) if active_count >= 0 else "ERR"

    print("=== Operator Digest ===")
    print(f"Open gates:        {open_gates_count}")
    print(f"Completed today:   {completed_today}")
    print(f"Active workflows:  {active_str}")
    print(f"Autonomy shifts:   {autonomy_shifts}")


# ── Argument parser ───────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="operator_cli",
        description="HyperadaptivAI operator CLI — manage agent approvals and flow control.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # list-gates
    sub.add_parser("list-gates", help="List all open gate-approval tasks")

    # show-gate
    p_show = sub.add_parser("show-gate", help="Show full detail of one pending gate")
    p_show.add_argument("decision_id", help="The decision_id from the gate task")

    # approve
    p_approve = sub.add_parser("approve", help="Approve a pending gate")
    p_approve.add_argument("decision_id", help="The decision_id to approve")

    # reject
    p_reject = sub.add_parser("reject", help="Reject a pending gate")
    p_reject.add_argument("decision_id", help="The decision_id to reject")

    # edit
    p_edit = sub.add_parser("edit", help="Approve a gate with an edited action")
    p_edit.add_argument("decision_id", help="The decision_id to edit-approve")
    p_edit.add_argument("--action-type", required=True, help="Replacement action type")
    p_edit.add_argument(
        "--action-payload",
        required=True,
        help="Replacement action payload as a JSON string",
    )

    # pause
    p_pause = sub.add_parser("pause", help="Pause a single workflow instance")
    p_pause.add_argument("workflow_id", help="Temporal workflow ID to pause")

    # resume
    p_resume = sub.add_parser("resume", help="Resume a paused workflow instance")
    p_resume.add_argument("workflow_id", help="Temporal workflow ID to resume")

    # pause-flow
    p_pf = sub.add_parser("pause-flow", help="Pause all instances of a flow class")
    p_pf.add_argument("flow_id", help="Flow class identifier (e.g. 'lead-intake')")

    # resume-flow
    p_rf = sub.add_parser("resume-flow", help="Resume a paused flow class")
    p_rf.add_argument("flow_id", help="Flow class identifier (e.g. 'lead-intake')")

    # digest
    sub.add_parser("digest", help="Show today's operational summary")

    return parser


# ── Dispatch table ────────────────────────────────────────────────────────────

_COMMANDS: dict[str, object] = {
    "list-gates": run_list_gates,
    "show-gate": run_show_gate,
    "approve": run_approve,
    "reject": run_reject,
    "edit": run_edit,
    "pause": run_pause,
    "resume": run_resume,
    "pause-flow": run_pause_flow,
    "resume-flow": run_resume_flow,
    "digest": run_digest,
}


# ── Async entry point ─────────────────────────────────────────────────────────

async def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    parser = build_parser()
    args = parser.parse_args()

    handler = _COMMANDS.get(args.command)
    if handler is None:
        parser.print_help()
        sys.exit(1)

    client = await make_client()
    pool = await make_pool()
    try:
        await handler(args, client, pool)  # type: ignore[operator]
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
