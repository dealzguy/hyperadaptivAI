# Alpha Deployment — Phase E Dev Server

*This document records the initial dev-server deployment for Phase E operator testing.
It is NOT the operator commissioning record (that is `DEPLOYMENT-RUNBOOK.md`).
Update this file as facts are confirmed or change.*

---

## Deployment topology

```
Local machine (Claude Code dev)
│
├── /home/dealzguy/projects/hyperadaptivAI/version1/   ← source of truth (git)
│   └── deploy/secrets/secrets.env                      ← GITIGNORED, real keys here
│
└─── SSH ──► VPS: root@72.60.66.27
               │   Hostinger KVM 2, Ubuntu 22.04, 2 vCPU, 8 GB RAM, ~97 GB SSD
               │   Firewall: UFW — ports 22/80/443 only inbound
               │
               ├── /opt/harness/                 ← harness code (rsync'd from local)
               │   ├── venv/                     ← Python 3.10 venv
               │   └── deploy/secrets/secrets.env ← GITIGNORED, real keys on VPS
               │
               ├── Podman: harness-postgres       ← business DB, port 127.0.0.1:5433→5432
               ├── Process: temporal server start-dev  ← Temporal dev server, ports 7233 + 8233
               ├── Process: harness.worker        ← Temporal worker, task queue: skeleton-queue
               │
               ├── Podman: docuseal              ← EXISTING, DO NOT TOUCH, port 127.0.0.1:3000
               │
               └── nginx (existing)
                   ├── [existing vhosts — prlwarehouse.com, forwardandreversemortgage.com, demos]
                   └── harness.prlwarehouse.com  ← NEW vhost, proxy → localhost:8233
```

---

## VPS access

```bash
# SSH (key auth only — password auth disabled)
ssh -i /home/dealzguy/projects/vps/hostinger/credentials/claude_automation_ed25519 \
  -o StrictHostKeyChecking=no root@72.60.66.27

# SSH ControlMaster (ALWAYS use this for scripted/parallel access — avoids UFW 6-conn/30s limit)
ssh -M -S /tmp/ssh-ctl-harness \
  -i /home/dealzguy/projects/vps/hostinger/credentials/claude_automation_ed25519 \
  -o StrictHostKeyChecking=no -o ControlPersist=7200 -fN root@72.60.66.27
# Then each subsequent command:
ssh -S /tmp/ssh-ctl-harness root@72.60.66.27 'command'
```

**UFW rate-limit trap**: parallel SSH agents (>6 conn/30s from one IP) trip the UFW LIMIT
rule on port 22 and get banned. Always use ControlMaster for multi-agent VPS work.
Our IP `37.19.210.183` has been whitelisted in UFW (`ufw allow from 37.19.210.183 to any port 22`).
If banned: `fail2ban-client unban 37.19.210.183` via Hostinger web console.

---

## Harness on VPS

| Item | Value |
|------|-------|
| Code root | `/opt/harness/` |
| Python venv | `/opt/harness/venv/` |
| Secrets | `/opt/harness/deploy/secrets/secrets.env` (chmod 600) |
| Worker log | `/var/log/harness-worker.log` |
| Temporal log | `/var/log/temporal-dev.log` |
| Worker PID | `/tmp/harness-worker.pid` |
| Temporal PID | `/tmp/temporal-dev.pid` |

---

## Processes and ports

| Process | Port | Binding | Notes |
|---------|------|---------|-------|
| `temporal server start-dev` | 7233 (gRPC), 8233 (UI) | localhost only | Dev server — in-memory, not persistent across restarts |
| `harness-postgres` (Podman) | 5433 → 5432 | 127.0.0.1 only | Business DB; persistent via Podman volume |
| `harness.worker` | (connects to 7233 + 5433) | — | Task queue: `skeleton-queue` |
| `docuseal` (Podman, existing) | 3000 | 127.0.0.1 only | DO NOT TOUCH |
| nginx | 80, 443 | 0.0.0.0 | Existing sites + new `harness.prlwarehouse.com` vhost |

---

## Temporal UI access

**Option A — SSH tunnel (dev access, no DNS needed):**
```bash
# Run locally — creates local port forwarding
ssh -N -L 8233:localhost:8233 -L 7233:localhost:7233 \
  -i /home/dealzguy/projects/vps/hostinger/credentials/claude_automation_ed25519 \
  root@72.60.66.27
# Then open: http://localhost:8233
```

**Option B — nginx vhost (after DNS propagates):**
- URL: `http://harness.prlwarehouse.com` (HTTP until certbot runs)
- After certbot: `https://harness.prlwarehouse.com`
- Certbot command: `certbot --nginx -d harness.prlwarehouse.com --non-interactive --agree-tos --email dealzguy@gmail.com`

---

## Operator CLI usage (on VPS)

**Critical:** `source secrets.env` without `export` creates shell variables, NOT env vars — Python
`os.environ` won't see them. Always use `set -a` before sourcing:

```bash
# SSH to VPS, then:
cd /opt/harness
source venv/bin/activate
set -a && source deploy/secrets/secrets.env && set +a

# List all pending gate approvals
python3 harness/operations/operator_cli.py list-gates

# Show one gate task in detail
python3 harness/operations/operator_cli.py show-gate <decision_id>

# Approve a gate decision
python3 harness/operations/operator_cli.py approve <decision_id>

# Reject a gate decision
python3 harness/operations/operator_cli.py reject <decision_id>

# Edit and approve with a modified action
python3 harness/operations/operator_cli.py edit <decision_id>

# Pause a specific workflow instance
python3 harness/operations/operator_cli.py pause <workflow_id>

# Resume a specific workflow instance
python3 harness/operations/operator_cli.py resume <workflow_id>

# Pause ALL instances of a flow class
python3 harness/operations/operator_cli.py pause-flow <flow_class>

# Resume ALL instances of a flow class
python3 harness/operations/operator_cli.py resume-flow <flow_class>

# Today's activity digest (transitions / completions / waiting gates)
python3 harness/operations/operator_cli.py digest
```

Complete command list: `list-gates`, `show-gate`, `approve`, `reject`, `edit`, `pause`, `resume`,
`pause-flow`, `resume-flow`, `digest`.

---

## Cloudflare DNS

| Account | Token file | Zones |
|---------|-----------|-------|
| prlwarehouse / hollysanches | `CloudFlair-hollysanches-account.key` | prlwarehouse.com, forwardandreversemortgage.com, note-acquisition-specialists.com, sovereignstackco-op.com, solidezindustrial.com |

**BOTH CF tokens (cfut_7latNZg4... and kVAJlTTueYA...) access the same account.**

Key zone IDs:
- `prlwarehouse.com`: `0beb6b9b6d7edf1fb94f7e402ade1ea7`
- `sovereignstackco-op.com`: `a66ae3472538eefbf16a77449c73c322` (ACTIVE)
- `sovereignstackcoop.com`: PENDING (NS delegation not yet at registrar)

DNS record added: `harness.prlwarehouse.com` → `72.60.66.27` (DNS-only, proxied=false)

---

## Backup (2026-06-12)

Created at `/root/vps-backup-2026-06-12/` on the VPS:

| Archive | Contents |
|---------|---------|
| `sites.tar.gz` | `/var/www/sites/` — all 7 website content dirs |
| `nginx-php.tar.gz` | `/etc/nginx/` + `/etc/php/` |
| `security.tar.gz` | `/etc/fail2ban/` + `/etc/ufw/` |
| `iptables.txt` | iptables-save snapshot |
| `ufw-status.txt` | UFW status verbose |
| `letsencrypt.tar.gz` | `/etc/letsencrypt/` |
| `certbot-status.txt` | certbot certificates output |
| `docuseal.tar.gz` | `/var/docuseal/` (SQLite + all data) |
| `systemd-traps.tar.gz` | `/usr/local/lib/cache-mgr/` + systemd trap units |
| `services-running.txt` | systemctl running services snapshot |
| `email.tar.gz` | `/etc/postfix/` + `/etc/opendkim/` |
| `crontab.txt` | root crontab |
| `nginx-sites-enabled.txt` | plain-text vhost listing |

---

## Restart runbook (if VPS reboots)

The `temporal server start-dev` and `harness.worker` are background processes (not systemd
services). They will NOT survive a VPS reboot. Restart them:

```bash
ssh -i /home/dealzguy/projects/vps/hostinger/credentials/claude_automation_ed25519 root@72.60.66.27

# 1. Start harness-postgres (Podman — restart policy: unless-stopped, auto-restarts)
podman start harness-postgres  # only needed if it didn't auto-restart

# 2. Start Temporal dev server
export PATH=$HOME/.temporalio/bin:/usr/local/bin:$PATH
nohup temporal server start-dev --port 7233 --ui-port 8233 --namespace default \
  > /var/log/temporal-dev.log 2>&1 &
echo $! > /tmp/temporal-dev.pid

# 3. Run bootstrap (safe to re-run — idempotent)
# NOTE: set -a auto-exports all vars from secrets.env so Python os.environ sees them
cd /opt/harness && source venv/bin/activate && set -a && source deploy/secrets/secrets.env && set +a
python3 -m harness.shared.persistence.bootstrap

# 4. Start worker
nohup python3 -m harness.worker > /var/log/harness-worker.log 2>&1 &
echo $! > /tmp/harness-worker.pid
```

---

## Deployment state (confirmed 2026-06-12)

All services confirmed UP and working:

| Service | Status | Notes |
|---------|--------|-------|
| Temporal dev server | UP — port 7233/8233 | HTTP 200 on 8233 |
| harness-postgres | UP — 127.0.0.1:5433 | Podman container `deploy_postgres-business_1`, healthy |
| harness.worker | UP — PID at `/tmp/harness-worker.pid` | Task queue: skeleton-queue |
| nginx | UP — 80/443 | Config valid; vhost created at `/etc/nginx/sites-available/harness.prlwarehouse.com` |
| harness.prlwarehouse.com | HTTPS 200 via CF proxy | TLS cert: Let's Encrypt, expires 2026-09-11 |
| operator CLI `digest` | Working | Confirmed: 0 gates, 0 active workflows |
| Backup | Complete | 887MB at `/root/vps-backup-2026-06-12/` |

## Open items (Phase F)

- [ ] Pin `litellm` to exact version used in this deployment (open liquid in `LIQUID-RESOLUTIONS.md`)
- [ ] Systemd service units for Temporal dev server and harness worker (survive reboots)
- [x] Certbot for `harness.prlwarehouse.com` — DONE (cert expires 2026-09-11)
- [x] Enable CF proxy (orange cloud) on `harness.prlwarehouse.com` — DONE
- [ ] Audit-log operator verdicts to `event` table (P1-8 from Phase E supervisor review)
- [ ] Token budget undercount on gate-reject/timeout paths (P1-5)
- [ ] Close stale gate task rows on workflow timeout/end
- [ ] Decide on sovereignstackco-op.com — full CF zone active, nginx vhost ready, needs certbot
