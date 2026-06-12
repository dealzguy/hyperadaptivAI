# Document 8 — Software Licensing & Sourcing Reference

*This is the operational reference for selecting, vetting, combining, and shipping third-party software inside the owned AI stack. Where Document 4 governs the legal form of the venture and Document 5 describes the product, this document governs the question underneath both: which software the IP company may legally fold into the stack, modify, combine, and make available to members through the cooperative — and on what terms. It is the founder's working map, not legal advice; the interpretation calls flagged for counsel (the GPL "derivative work" boundary, the AGPL network trigger, and the contribution-licensing model) should be confirmed by an IP/open-source attorney before the product ships. Every tool- and model-specific fact here is a point-in-time snapshot — see the verification log for what was source-confirmed and when. The principles do not move; the licenses of specific tools demonstrably do, in both directions, and must be re-checked at integration and on every upgrade. Compiled May 2026.*

*Scope: this document covers software and model **licensing** only. It does not cover the adjacent legal regimes that also touch a redistributed AI stack — export control and encryption notification, data protection, the EU AI Act, and the sanctions/KYC obligations already addressed in Document 4 — each of which is a separate body of law and a separate conversation with counsel.*

## The default sourcing rule

[PROD] When in doubt, source from the **permissive tier** (MIT, Apache 2.0, BSD, ISC), consume it as an **unmodified, version-pinned dependency** rather than a fork, and keep anything copyleft or source-available as a **separate, arm's-length process** the harness talks to over a clean interface. A sourcing decision that requires cleverness to defend is the wrong one. Everything below is the detail behind that rule.

## The one principle everything rests on

The model ships software onto hardware the member controls and runs for the member's own use. That single fact — **distribution, not hosting** — decides almost every license question, because the licenses that punish commercial activity are mostly triggered by *hosting software for others over a network*, which is not what the stack does. The exception is anything the IP company or the co-op runs centrally and exposes to members remotely (a control plane, a portal); that crosses back into network-use territory and is the one place the friendly distribution analysis stops applying.

Two license questions are easy to collapse into one and must be kept apart:

- **Inbound** — what the license of software *pulled into* the stack permits the IP company to do. Governed by each tool's own license; cannot be overridden by any agreement the founder writes.
- **Outbound** — the license the IP company grants members for its *own* proprietary work (the harness, configuration, control plane, brand): the "modify freely, do not resell" terms.

The most important correction to the working intuition: *"we only sell the configuration and access, not the software"* is a complete shield for permissively-licensed tools and **means nothing** for source-available tools. Source-available licenses restrict the business model — charging for access, hosting, embedding — regardless of what the fee is nominally attached to. The test those licenses apply is whether the value of the paid offering substantially derives from their software, not whether the invoice says "configuration."

## Inbound license tiers — the allow-list

| License | Fork & keep changes proprietary? | Sell access / ship commercially? | What is owed | Fit |
|---|---|---|---|---|
| MIT, BSD-2, BSD-3, ISC, 0BSD, CC0/Unlicense | Yes, fully | Yes | Preserve copyright/license notices | **Green — default** |
| Apache 2.0 | Yes, fully | Yes | Preserve notices + NOTICE file, state changes; includes a patent grant | **Green — best for ML** |
| MPL 2.0 | Partial — new files stay proprietary; changes to MPL files must be published | Yes | Publish modifications to MPL-covered files only | **Yellow — workable** |
| LGPL 2.1 / 3 | Yes, used as a library; library modifications must be shared and relinkable | Yes | Share library changes, allow relinking | **Yellow — with discipline** |
| GPL v2 / v3 | No, if combined into one work | Yes (selling allowed) but full source of the combined/distributed work must be offered | Open the whole distributed work | **Separate process only** |
| AGPL v3 | No — GPL terms plus a network-use trigger | Yes, with the network obligation | Open it, including to remote users | **Separate, unmodified service only** |
| n8n SUL, SSPL, BSL, Elastic v2, Commons Clause, FSL/PolyForm, Open WebUI 0.6.6+ branding | Fork allowed, but the use restriction rides with every copy | Restricted or forbidden — this is the part they block | Varies | **Avoid or license commercially** |

[PROD] **Green tier (permissive).** MIT, Apache 2.0, BSD, ISC and the public-domain dedications are the backbone. Fork freely, wrap in the proprietary harness, relicense the assembled product under the outbound EULA (the original files keep their own notices), ship it on member hardware, charge for access — and upstream has no say over the fork. Apache 2.0 edges out MIT for this stack because of its explicit patent grant, which matters in ML tooling; note that the patent grant terminates automatically if the licensee initiates patent litigation over the software (a defensive clause, not a concern for ordinary use). Obligations are light: keep notices; for Apache, also keep the NOTICE file and state changes.

**Yellow tier (weak copyleft).** MPL 2.0 and LGPL are usable; the obligation is narrow and surgical — publish changes *to their files or their library*, while proprietary additions stay proprietary. Many serious tools live here.

[PROD] **GPL / AGPL (strong copyleft).** Forkable, but the fork cannot stay proprietary. These fit the model only as a **separately-running process** the harness talks to over a clean interface — a model server, a database — shipped unmodified, with its source offer, as "mere aggregation." Woven *into* the harness, GPL forces the harness to become GPL, and AGPL adds the network trigger on top. [PROD] The discipline: never statically link or paste GPL/AGPL source into the proprietary tree; keep it at arm's length as an independent component. Note that the aggregation-versus-derivative-work line is the FSF's position and is fact-specific and largely untested in court for many integration patterns — which is exactly why it goes to counsel rather than being assumed. Several common infrastructure tools (some databases, dashboards, and workflow engines) ship under AGPL; each must be checked individually, not assumed permissive because it is popular and free.

**Red tier (source-available).** Designed specifically to stop a company from charging for access to them — which is the business. They appear on GitHub looking identical to permissive software. Treated in detail in "The traps already in the stack" below.

## Combining components — license compatibility

Picking each tool's license correctly is necessary but not sufficient. The moment two differently-licensed components are combined into a single distributed work, their licenses must be mutually compatible. The rules that matter for this stack:

Permissive licenses (MIT, BSD, ISC, Apache 2.0) combine cleanly with almost everything, including each other and the proprietary harness. The one trap worth memorizing: **Apache 2.0 is compatible with GPLv3 but *incompatible* with GPLv2** (its patent and notice terms add restrictions GPLv2 forbids). So Apache-2.0 code and GPLv2-only code cannot lawfully be merged into one combined work — they can only coexist as separate, aggregated programs. MIT and BSD have no such issue and are compatible with all GPL versions.

When a copyleft component is combined into a single work, the *whole combined work* takes that copyleft license — GPLv3 code pulls the result to GPLv3, AGPL to AGPL. That is the mechanism that would swallow the proprietary harness if GPL code were linked into it. MPL 2.0 and LGPL are gentler: MPL 2.0 includes a compatibility clause allowing combination with GPL/LGPL/AGPL works, and confines its own copyleft to MPL-covered files; LGPL permits linking from proprietary code.

[PROD] The practical consequence, and the reason the default rule above exists: **keeping every copyleft component as a separate process sidesteps the entire compatibility question.** Aggregated programs that merely communicate at runtime are not "combined into one work," so their licenses never have to be reconciled. Compatibility analysis is only forced when code is actually linked or merged — which the architecture should avoid for anything stronger than weak copyleft.

## Forkability — the real question

Forking is permitted by nearly every license, open-source and source-available alike; "is it forkable" is therefore not the useful filter. The filter that matters is: *can it be forked, modified heavily, kept proprietary, shipped inside the paid platform, and run free of upstream constraint?* That property is precisely the **green tier**. Permissive licenses hand over full freedom without obligating anything except notice preservation; that is the cleanest possible fit and where sourcing should default.

The source-available tier is where this question traps people: the code can be forked, but the license restriction travels with every copy, so the fork inherits the prohibition it was meant to escape. Two escape hatches exist, both costly. **Fork from the last truly-open version** (Open WebUI ≤ v0.6.5 is pure BSD-3; some relicensed infrastructure tools were MPL before their change) — but that forfeits all upstream updates and security patches, which directly guts the maintenance value the venture sells. **Fork after a BSL change date** for tools whose Business Source License converts to an open license on a schedule. Neither is attractive for a product whose entire pitch is staying current.

[PROD] **The divergence tax — the venture's own thesis, turned inward.** The plan's core insight is that forking the open core transfers the full maintenance burden onto whoever forks. That applies to the IP company every time it hard-forks an upstream tool: even under a permissive license that allows it, a heavy fork means owning every future merge, security backport, and model-compatibility fix for that component forever. The better default for most of the stack is therefore **not fork — consume upstream as an unmodified, version-pinned dependency and contribute fixes back**, reserving real forks for the few components where divergence is genuinely required. The same permissive licenses allow either path; the choice is an engineering-cost decision, not a licensing one. Fork to control direction; depend-and-pin to merely use.

## The outbound license — what members receive

The "modify freely, do not resell" terms are a coherent proprietary EULA and map cleanly onto the open-core split in Document 5: the open core under a genuine OSS license, the harness, control plane, and premium templates under the restrictive EULA. Constraints that keep it honest:

It binds only the IP company's *own* proprietary work. Bundled MIT/Apache components were received by the member under MIT/Apache and remain redistributable as those parts; "no reselling the platform" therefore means "no reselling our harness, configuration, and brand," not a blanket lock on everything in the box.

It cannot add restrictions on top of any GPL, AGPL, LGPL, or MPL component shipped. Those must flow through under their own terms via a standard "third-party components are licensed under their respective licenses — see NOTICES" carve-out. Attempting to impose "no redistribution" on a GPL component is itself a license violation.

It is not open source, and should never be described as such — the no-resale term is what makes it proprietary, which is correct and intended. The label simply must match.

**Inbound contributions need their own policy.** The open core invites members to modify and contribute back (Document 5). Without a contribution-licensing model, contributed code arrives under the open-core license owned diffusely by contributors, which complicates the IP company's ability to keep its proprietary layer clean, to relicense, or to sell the asset later. The two standard instruments resolve this: a lightweight **Developer Certificate of Origin (DCO)**, where contributors attest they have the right to contribute under the project license, or a **Contributor License Agreement (CLA)**, where contributors grant the IP company broad rights (often including the right to relicense). For a venture whose exit lives in a cleanly-owned IP company, a CLA on the open core is the more protective choice and should be decided with counsel before the first outside contribution is accepted.

## AI model weights — a separate category

Model licenses are not code licenses and must be checked independently and per version. Two operational rules govern everything in this section:

[PROD] **Version-specificity is decisive.** The same family can flip licenses between releases, in either direction. Gemma is the example: releases 1–3 shipped under a restrictive custom "Gemma Terms of Use" that required passing the terms downstream; Gemma 4 (April 2026) switched to clean Apache 2.0. DeepSeek ran the other risk — its older releases split a permissive code license from a more restrictive weights license, while V4 is clean MIT for both. Never record a model family's license without its version, and re-check on every upgrade.

[PROD] **Pull, don't redistribute, where possible.** Having the deployment tooling fetch model weights at deploy time — from the member's chosen source — rather than packaging weights into the shipped product means the weights are never "in" the distributed artifact, which sidesteps redistribution terms on community-licensed models entirely. This should be the default delivery mechanism for any model whose license is not plainly permissive. *(2026-06: the product is API-only — no model weights are pulled, shipped, or stored on the host at all, which sidesteps redistribution terms even more completely. Models are accessed via API at runtime; the API provider is chosen per this document's license criteria. This rule stands as guidance should local serving ever return.)*

The commercially-clean families as of the current research are Qwen 3.x (Apache 2.0), Gemma 4 (Apache 2.0), Phi-4 (MIT), and DeepSeek V4 (MIT). The community-licensed families carry conditions that need real attention:

**Llama 4 is the cautionary case and touches the venture's foreign strategy.** It is the Llama 4 Community License, not OSI-open. Commercial use is permitted below a 700-million-monthly-active-user threshold (irrelevant at this venture's scale, but it terminates the license above it). The conditions that *do* bite: a mandatory "Built with Llama" attribution badge on the product; a requirement that any derivative model's name begin with "Llama"; redistribution of the license text and a Notice file with any distribution; an Acceptable Use Policy incorporated by reference; and — most importantly here — **the multimodal Llama 4 models may not be used by, or distributed to, individuals or companies domiciled in the EU.** That last condition collides directly with the foreign-patron-member path in Document 4: shipping multimodal Llama 4 to an EU-domiciled patron member would breach the license. Prefer the permissive families for anything redistributed to foreign members, and treat Llama as pull-at-deploy with an explicit EU-domicile gate if used at all.

**Mistral varies by model.** The smaller open releases (historically Mistral 7B, Mixtral, Mistral Small) have shipped under Apache 2.0; larger or newer ones under the Mistral Research License (non-commercial) or a paid commercial license. Treat every Mistral model as "verify before use" and assume non-commercial until the specific model's card proves Apache 2.0.

## Container runtime — Podman

Verified clean and the correct default. Podman, Podman Desktop, and the sibling tools (Buildah, Skopeo) are all Apache 2.0 and remain so as of the 5.8.x line (March 2026), developed under the CNCF. Podman sits in the green tier with no commercial-use restriction and a patent grant — it is the *answer* to a licensing problem, not a source of one, since the restrictions people worry about apply to Docker Desktop, not Podman. Three footnotes, none an obstacle:

Apache 2.0 licenses the code, not the name or logo; do not imply Red Hat or CNCF endorsement or brand the product around "Podman." Preserve Podman's LICENSE and NOTICE files in whatever is distributed — satisfied simply by shipping it as an unmodified dependency, which is the right call anyway (depend-and-pin, do not fork). And the real licensing surface is not the runtime but **what runs inside the containers** — base images and containerized software each carry their own license, and moving a payload with Podman does not change the payload's license. The SBOM and vetting effort belong on image contents.

## The traps already in the stack

[PROD] **n8n — Sustainable Use License (source-available).** Listed in Documents 5 and 7. Use is restricted to internal business purposes; it may be provided to others only free of charge for non-commercial purposes; and prohibited uses explicitly include selling a product or service whose value substantially depends on n8n, hosting n8n and charging for access, and embedding n8n in a paid service. The venture's model is squarely what it forbids, and the "we charge for configuration" framing does not help because the test is value-derivation. **Options:** a commercial/embed agreement with n8n, or substitution with a permissive alternative — Node-RED (Apache 2.0) is the closest like-for-like; Windmill and Activepieces are worth evaluating (verify their current licenses, as this is exactly the category that relicenses).

[PROD] **Open WebUI — BSD-3-Clause plus branding clause (v0.6.6+, April 2025).** Also in the stack. The code is permissive, but a branding-protection clause prohibits altering, removing, or obscuring "Open WebUI" branding in any deployment exceeding 50 aggregate users in a 30-day window without an enterprise license. For a white-labeled "platform access interface," that is the snag. **Options:** keep the branding visible, buy the white-label/enterprise license, pin to v0.6.5 or earlier (pure BSD-3 but forfeiting all later features and security updates — not viable for a maintenance-led product), or substitute a fully-permissive UI.

[DEV] The shared lesson: both were permissive once. Pinning a version and watching for relicensing is a standing operational duty, not a one-time check.

## Stack inventory, sorted

*Confidence: items marked ✔ were source-verified in the research behind this document (see log). Unmarked items are general/point-in-time and must be re-confirmed at integration time and on every upgrade.*

| Component | Role | License | Tier | Notes |
|---|---|---|---|---|
| Podman / Buildah / Skopeo | Container runtime | Apache 2.0 ✔ | Green | Default. Ship unmodified; brand caution. |
| Docker Engine / CLI | Container runtime (alt) | Apache 2.0 | Green | Engine is fine. |
| Docker Desktop | Desktop tooling | Commercial above size threshold | — | Avoid shipping; Podman removes the question. |
| Ollama | Single-node model serving | MIT ✔ | Green | No longer shipped — API-only inference (2026-06). License record retained. |
| vLLM | High-throughput serving | Apache 2.0 ✔ | Green | — |
| llama.cpp | Inference / quantization (GGUF) | MIT | Green | The tool is MIT; a quantized GGUF file still carries the underlying *model's* license, not llama.cpp's. |
| Open WebUI (≥ v0.6.6) | Chat/management UI | BSD-3 + branding clause ✔ | Red (for white-label / 50+ users) | Branding must stay, or license/substitute. |
| n8n | Workflow automation | Sustainable Use License ✔ | Red | Forbids the business model. Substitute or license. |
| Node-RED | Workflow automation (alt) | Apache 2.0 ✔ | Green | Permissive substitute for n8n. |
| Ansible (ansible-core) | Deployment tooling | GPLv3 | Green in practice | Used as a tool, not shipped in the product; playbooks are not derivative works. Low risk. Bundled collections may differ — check. |
| Ubuntu (hardened base) | Host OS | Aggregate (kernel GPLv2; userland GPL/LGPL; thousands of per-package licenses) | Yellow if redistributed as an image | Deploying onto a member's own Ubuntu is standard and clean. **Redistributing a customized Ubuntu image** means redistributing its GPL packages — preserve notices and stand ready to provide source for GPL components — and Canonical's "Ubuntu" trademark restricts shipping modified images under the Ubuntu name. Consider deployment scripts over image redistribution. |
| MCP / connectors | Integration layer | Spec is open; connectors vary | Per-connector | Vet each connector individually. |
| Qwen 3.5 / 3.6 | General/agentic model | Apache 2.0 ✔ | Green | Prefer for redistribution. |
| Gemma 4 | Edge/multimodal model | Apache 2.0 ✔ | Green | v4 only — v1–3 were restrictive custom. |
| Phi-4 | Constrained-hardware model | MIT | Green | — |
| DeepSeek V4 | Coding/reasoning model | MIT ✔ | Green | V4 Pro and Flash both MIT; older DeepSeek split code/weights licenses — verify per release. |
| Llama 4 | Model | Llama 4 Community License | Red/Yellow | Not OSI-open. "Built with Llama" badge + "Llama-" name prefix required; AUP incorporated; **multimodal models barred for EU-domiciled users** (see Doc 4 foreign-member path); 700M-MAU ceiling. Prefer pull-at-deploy with an EU gate. |
| Mistral families | Model | Varies (Apache 2.0 small/open; Research License non-commercial; or commercial) | Per-model | Assume non-commercial until the model card proves Apache 2.0. |
| The harness, control plane, premium templates | Proprietary IP | Outbound EULA | — | "Modify freely, no resell." IP company owns. CLA/DCO governs inbound contributions. |

## Vetting workflow for new software

A standing procedure for every tool considered for the stack:

[DEV] 1. **Read the actual LICENSE / COPYING file.** Never trust the repository sidebar, a README badge, or a blog calling it "open source." The license text is the only authority.
[DEV] 2. **Check OSI approval.** If the license is not on the OSI-approved list, treat it as commercially restricted until the text proves otherwise. "Fair-code," "source-available," and "sustainable" are the marketing words that signal a use restriction.
[DEV] 3. **Check compatibility with what it will be combined with.** If the component will be linked or merged rather than run as a separate process, confirm its license is compatible with the others in that work — in particular, never merge Apache-2.0 and GPLv2-only code into one binary.
[DEV] 4. **Check for relicensing history and trajectory.** n8n, Open WebUI, and several infrastructure tools moved from open to source-available; Gemma moved the other way. Pin a known-good version and monitor changes.
[DEV] 5. **Check for sub-licenses.** Plugins, nodes, extensions, Ansible collections, and bundled models inside a single repository can carry different licenses than the core.
[DEV] 6. **Scan the dependency tree.** Because the product is a whole assembled stack, run an automated scanner (ScanCode, FOSSA, or `license-checker` / `licensee`) in CI to flag copyleft and source-available licenses before they ship.
[PROD] 7. **Maintain a NOTICES file and a software bill of materials** (SPDX or CycloneDX format). This satisfies Apache NOTICE and GPL source-offer obligations, documents exactly what is in the box, and doubles as an asset for the "get off rented inference" audit engagements in Document 6.

## Open items for counsel

- The GPL "derivative work" versus "mere aggregation" boundary for any GPL/AGPL component the harness invokes — confirm the separate-process analysis holds for the specific integration pattern used.
- The AGPL network trigger for any component the IP company or co-op runs centrally and exposes to members (control plane, portal), as distinct from components running on member hardware.
- The contribution-licensing model for the open core (CLA versus DCO), decided before the first outside contribution is accepted, to protect the IP company's ownership and future sale.
- The outbound EULA's third-party carve-out language, ensuring it correctly passes through copyleft and source-available components without purporting to restrict them.
- The EU-domicile gate for Llama 4 multimodal models, reconciled with the foreign-patron-member strategy in Document 4.
- Whether any commercial agreement (n8n embed, Open WebUI white-label) is worth its cost versus permissive substitution — a business decision informed by the legal terms.
- Trademark usage for every bundled tool retaining brand marks (Podman, Open WebUI, Ubuntu, Llama), distinct from the copyright license, and protection of the venture's own brand as an IP-company asset (Document 6 open decision).

## Verification log (point-in-time)

Facts source-confirmed during the research behind this document. Anthropic's knowledge baseline ends January 2026; everything below was verified against current sources after that date and remains a snapshot to be re-checked at integration.

- **n8n** — Sustainable Use License; restricted to internal business purposes; hosting-for-fee, value-substantially-derived resale, and paid embedding prohibited. (n8n LICENSE.md / docs.)
- **Open WebUI** — BSD-3-Clause plus branding-protection clause effective v0.6.6 / April 19, 2025; branding removal restricted above 50 aggregate users in 30 days without enterprise license; v0.6.5 and earlier remain pure BSD-3. (Open WebUI docs/license.)
- **Podman** — Apache 2.0, stable line 5.8.x (March 2026), CNCF/Red Hat; Podman Desktop also Apache 2.0; commercial restrictions are Docker Desktop's, not Podman's. (containers/podman LICENSE, podman.io.)
- **Gemma 4** — Apache 2.0 as of April 2026, replacing the restrictive custom license of Gemma 1–3. (Google DeepMind release / coverage.)
- **Qwen 3.x** — all open-weight Qwen3 / 3.5 / 3.6 models Apache 2.0. (QwenLM repos, Hugging Face model cards.)
- **DeepSeek V4** — Pro and Flash both MIT, released April 2026; older releases split code/weights licenses. (Hugging Face model cards, release coverage.)
- **Llama 4** — Llama 4 Community License; not OSI-open; "Built with Llama" badge and "Llama-" naming required; multimodal models barred for EU-domiciled users; 700M-MAU ceiling. (llama.com/llama4 license, Llama FAQ.)
- **Ollama** — MIT. (ollama/ollama LICENSE.)
- **vLLM** — Apache 2.0. (vllm-project repo.)
- **Node-RED** — Apache 2.0, OpenJS Foundation. (Node-RED project.)
- **Apache 2.0 compatibility** — compatible with GPLv3 (combined result is GPLv3); incompatible with GPLv1/GPLv2. (Apache Software Foundation / FSF position.)

All other tool and model licenses recorded here (Phi-4, ansible-core, Docker Engine, Mistral, MCP connectors, llama.cpp) are from Document 7's research or general knowledge, are point-in-time, and must be re-verified at integration and on every upgrade.
