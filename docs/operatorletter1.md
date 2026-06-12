# Operator Letter 1
## HyperadaptivAI — What We Built, How It Works, and What You Need to Do

---

## 1. What Was Built

Over four development phases we built a complete AI agent harness for customer-facing operations. Here is what exists today, in plain terms.

**The spine: durable execution.**
Every action the system takes is recorded to a log before it happens. If the server restarts, a network drops, or anything fails mid-task, the system picks up exactly where it left off — no lost work, no duplicate actions, no silent failures. This is provided by Temporal, an open-source workflow engine used in production at Stripe, Coinbase, and Netflix. [PROD] Your business records, configuration, and the agent's memory live on your own machine; the only thing that leaves it is the minimal per-request context sent to the AI API provider you approved.

**The database: your business memory.**
A PostgreSQL database (open-source, free, runs on your host) stores everything the system knows about your customers. It is structured around five things: entities (leads, contacts), relationships between them, events that happen to them, state (where they are in your process), and tasks assigned to people or the agent. The same database holds the agent's memory: what it has done before, the directives you have given it, and a searchable knowledge store for anything you want it to know.

**The agent loop.**
When a lead arrives, an agent wakes up and runs a four-step cycle — read context → decide next action → act → write what happened — repeating until the job is done or it needs a human. At each step it uses a small, low-cost AI model accessed over an API. [PROD] All AI calls go to a single configured API provider, through one controlled interface, using the cheapest/smallest model that meets the quality bar for each task — no GPU and no special hardware on your machine. [PROD] Which provider and which model are configuration you approve; the system never calls any AI service you have not configured.

**The commissioning factory.**
Before the agent touches your business, you run commissioning once. Commissioning is an interview process that reads a description of your business — your lifecycle stages, the vocabulary you use, the consequences of each action — and produces a configuration bundle: a small set of JSON files that tell the agent exactly what it is allowed to do, in what order, with what level of autonomy. The bundle is the agent's instructions. You own it. You can read it, edit it, and version it.

**The safety model.**
Every tool the agent can use is classified by consequence:
- [PROD] **Reversible** (e.g., recording a note): the agent acts automatically.
- [PROD] **Compensable** (e.g., assigning a task, changing a state): requires your approval before it proceeds.
- [PROD] **Irreversible**: always requires your approval.

[PROD] You can pause the agent at any time — per lead or across your whole queue — and resume it when you are ready. [PROD] Every action it takes is written to the episodic memory so you can see exactly what happened and why.

**What it does not do.**
[PROD] It does not email, call, or contact anyone on your behalf unless you build and approve a connector for that. In the current phase it reads your leads, classifies them, transitions their state, and assigns follow-up tasks to your team. Human communication remains with your team. The agent handles the cognitive labour of qualification and routing.

---

## 2. How It Works — The Brief Version

```
Lead arrives
     │
     ▼
Intake event recorded in database
     │
     ▼
Agent loop starts (durable — survives restarts)
     │
     ├─ SITUATE: reads lead data + agent's recent history + your directives
     │
     ├─ DECIDE: AI model (via the configured API) chooses the next action from your approved tool list
     │
     ├─ ACT: executes the action (record an event, change a state, assign a task)
     │         ↑ compensable or irreversible actions → waits for your approval first
     │
     ├─ RECORD: writes what happened to memory
     │
     └─ repeat until: goal reached / budget exhausted / stall detected / you pause it
              │
              ▼
         Escalates to a human task if it cannot proceed with confidence
```

[PROD] The agent knows your business through the **configuration bundle** — not through prompt engineering or fine-tuning. [PROD] If your process changes, you update the bundle (or re-run commissioning) and the next agent instance uses the new rules. [PROD] Nothing in the code changes.

---

## 3. What You Need to Do — Phase E Step by Step

Phase E is the first real deployment. It is performed, not just installed. These are the steps, in order.

---

### Step 1 — Host Preparation

**You provide:** A Linux machine (physical, VM, or VPS) that will run the system. A modest spec is sufficient to start: 4 CPU cores, 8 GB RAM, 50 GB disk. No GPU required — all AI inference runs via the configured API provider.

**What happens:** The founder installs the system on your host from the deployment bundle — containers for the database, the workflow engine, and the agent worker. This takes roughly one session. At the end you have a running system with exactly one external dependency: the AI API provider you approved (everything else runs on your machine).

**You need to have ready:**
- SSH access to the machine (the founder will need it for this session)
- A domain name or fixed IP if you want to access the queue interface from a browser
- Confirmation of which Linux distribution you are running

---

### Step 2 — The Commissioning Interview

**You provide:** A written description of your business process — how leads come in, what stages they move through, what actions your team takes at each stage, what constitutes a qualified lead versus a disqualified one, and any edge cases that matter. This does not need to be long or formal. Two to four pages of plain language is enough. Think of it as explaining your process to a new team member on their first day.

Specifically, the interview extracts:
1. What you sell and to whom
2. The lifecycle stages a lead moves through (e.g. new → qualifying → qualified → disqualified)
3. The vocabulary your team uses (the words that matter in your business)
4. The consequence of each action (which things can be undone, which cannot)
5. Three to five real scenarios — actual cases that represent the range of leads you see

**What happens:** The commissioning workflow reads your description, maps it to the system's primitives, and produces a configuration bundle. The founder walks you through the output and you confirm it reflects your business correctly. If anything is wrong, you correct it and the system re-runs that stage. This correction cycle is built in — it is not an error, it is the expected path.

**You need to have ready:**
- Your written business description (plain language, not technical)
- One hour to review the commissioning output with the founder

---

### Step 3 — Review and Approve the Configuration Bundle

The commissioning process produces a bundle of files that define the agent's behaviour for your business. Before the agent is deployed against your real leads you review and approve this bundle. It specifies:

- What the agent is allowed to do (the tool allowlist)
- What requires your approval before the agent acts (the gate rules)
- When the agent escalates to a human task instead of acting
- The lifecycle stages and vocabulary the agent uses
- Which AI model runs at each decision point

You do not need to read JSON to review this — the founder will present it in plain language. But you have the right to read and edit every field, and you should. This bundle is your agent's standing instructions. [PROD] **One human click promotes it to production.** [PROD] Nothing goes live without that click.

---

### Step 4 — Load Your First Real Leads

**You provide:** Your existing lead data in any common format (CSV, spreadsheet, export from your current CRM). The founder maps your fields to the system's entity schema.

**What happens:** Your leads are imported as entities in the database. The intake event is recorded for each one, which starts the agent loop for each lead in order. The agent begins working through your queue.

**What you will see:** A simple queue view showing each lead, its current state, the agent's last action, and any tasks awaiting your approval. For any action the agent cannot take autonomously (compensable or irreversible consequences), it stops and waits for you. You approve, edit, or reject the proposed action, and it continues.

---

### Step 5 — Probation Period

The system runs in probation for an agreed period (typically two to four weeks). During probation:

- [PROD] **All state transitions require your approval** regardless of consequence class — you see everything before it happens
- You build confidence in what the agent does and does not do correctly
- [PROD] You record corrections: when the agent proposes something wrong, you correct it and the correction is written to memory so it does not happen again
- [PROD] The probation ledger tracks how often you override the agent; as overrides decrease, gates open

You are not automating your team out of their work in this phase. You are training the system on your actual cases while maintaining full control.

[PROD] **Probation ends** when you are satisfied the agent is making correct decisions at an acceptable rate, and you choose to open the gates to the autonomy level specified in your configuration bundle.

---

### Step 6 — Handover and Ongoing Operation

At the end of Phase E the founder hands over:

- The deployment runbook (written as the deployment happened — specific to your host and business)
- The correction discipline: how to pause the agent, record a correction, and resume
- The model migration procedure: how to swap the underlying AI model without touching your data or configuration if a better small model becomes available
- Contact for ongoing support under the charter member arrangement

**Your ongoing responsibilities:**
- [PROD] Review the agent's task queue daily (takes minutes, not hours)
- [PROD] Approve or reject any gated actions
- [PROD] Record corrections when the agent is wrong (this improves its behaviour)
- Notify the founder of any process changes so the configuration bundle can be updated

---

## Summary: What You Decide, What the System Decides

| Decision | Who decides |
|----------|-------------|
| [PROD] What the agent is allowed to do | You (configuration bundle) |
| [PROD] Whether a specific action proceeds | You (gate approval) |
| [PROD] Whether to pause the agent | You (at any time, instantly) |
| Which leads are in the queue | You (import) |
| What the agent does next within its allowlist | The agent |
| [PROD] Whether to escalate to a human | The agent (if confidence is low) |
| [PROD] Which API model runs at each decision point | The founder (cheapest/smallest viable, your approval) |
| [PROD] Any external communication | Your team (the agent does not contact customers) |

---

## A Note on the AI

[PROD] The system uses the cheapest, smallest AI model that can do the job, accessed over an API from a provider you approve. [PROD] Your business data, configuration, and the agent's memory stay on your hardware; only the minimal context needed for each decision is sent to the API provider, under that provider's terms — which you review before approving. [PROD] The system does not train any model on your data. [PROD] It cannot be prompted by your customers. [PROD] It operates within the strict boundaries of the configuration bundle you approved.

[PROD] If a better or cheaper model becomes available, we can swap it behind the inference contract — even across providers — without changing your configuration, your data, or your process. [PROD] Model and provider independence is a design principle, not a feature.

---

*This letter describes the system as it exists at the start of Phase E. The deployment runbook, written as Phase E is performed, will replace this document as the operational reference for your specific deployment.*
