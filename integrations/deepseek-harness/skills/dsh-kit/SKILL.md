---
name: dsh-kit
description: "dsh-kit bundle meta-skill: explains the capability boundaries and origins of this bundle's 95 skills (11 bundled in-house + 84 merged from upstream: ECC 59 / mattpocock 19 / claude-mem 6) and points to rules/ and references/. 说明本包 95 个技能的能力边界与来源（11 个包内自有 + 84 个上游合并：ECC 59 / mattpocock 19 / claude-mem 6），并指引 rules/ 与 references/。用户问\"dsh-kit 有什么\"\"插件能力\"\"包里有哪些技能\"时触发。"
---

# dsh-kit bundle

dsh-kit is a **DeepSeek Harness bundle-shaped** skill bundle shipping **95 skills**. Skills are loaded in isolation from the bundle (provider `dsh-kit`, `includeDefaultRoots: false`) and are never written into canonical skill directories such as `~/.agents/skills`.

## Where the skills come from

| Origin | Count | License | Notes |
|--------|-------|---------|-------|
| Bundled in-house | **9** | MIT | `chrome-devtools-wsl`, `diagnose`, `dsh-kit`, `github-repo`, `grow-dream`, `karpathy-guidelines`, `ssrf-remediation`, `write-a-skill`, `wsl-network` |
| `affaan-m/ECC` | **59** | MIT | General engineering workflow + language ecosystems (Python/Go/Rust/Java/Kotlin/JS/Django/Laravel/Rails) + agent meta-skills |
| `mattpocock/skills` | **19** | MIT | Review, specs, ticket splitting, triage, TDD, grilling-style design |
| `thedotmack/claude-mem` | **6** | Apache-2.0 | Handoff docs, standup, PR babysitting, codebase onboarding, design audit |
| `alibaba/open-code-review` | **0** | Apache-2.0 | Its 2 skills are wrappers around the `ocr` CLI; per "tool runtimes stay out of the skill surface" they are registered as reference material only |

The per-skill list, snapshot SHAs and usage scope are in `../../references/upstream-sources.md` and its four fascicles.

The counts above are this bundle's headline numbers — **recompute, do not trust a copy**:
`node tools/validate-package.ts` (total, D8 list, language/metadata readings) and
`Select-String -Path integrations/deepseek-harness/skills/*/SKILL.md -Pattern '^\s+origin:\s*(\S+)'` grouped by the captured `origin` (per-source counts).

## Find a skill by purpose (excerpt)

| Purpose | Skills |
|---------|--------|
| Verification and review | `code-review`, `verification-loop`, `santa-method`, `production-audit`, `security-review`, `ssrf-remediation` |
| Design and architecture | `codebase-design`, `architecture-decision-records`, `hexagonal-architecture`, `contract-first`, `api-design`, `domain-modeling` |
| Requirements and triage | `to-spec`, `to-tickets`, `triage`, `intent-driven-development`, `grill-with-docs`, `grilling` |
| Implementation and testing | `tdd`, `e2e-testing`, plus `python-testing`, `golang-testing`, `rust-testing`, `kotlin-testing`, `django-tdd`, `react-testing` |
| Context and agents | `strategic-compact`, `context-budget`, `eval-harness`, `prompt-optimizer`, `skill-scout`, `rules-distill` |
| Delivery and repos | `git-workflow`, `pr`, `deployment-patterns`, `database-migrations`, `setup-pre-commit` |
| Environment and tooling | `chrome-devtools-wsl`, `wsl-network`, `docker-patterns`, `mcp-server-patterns`, `kubernetes-patterns` |

The authoritative list of all 93 is the bundle's own `skills/` directory; each skill is triggered by its own `description`.

## Global rules

- The project uses PowerShell (`pwsh`), not bash.
- A skill's `description` decides when DSH loads it. **Bodies are English**: the upstream text verbatim as the base, with only the "minimal adaptation" set applied (`CONTEXT.md` -> "Minimal adaptation (A)"). Bodies whose Chinese content *is* the skill's function are kept and registered as explicit whitelist entries in `tools/validate-package.ts` (the table is the authority — this file does not copy its list or count). Every Apache-2.0 (`claude-mem`) file this bundle modified also carries an in-file §4(b) change notice (see `../../THIRD-PARTY-NOTICES.md`).
- The 84 upstream skill bodies may still describe **Claude Code context mechanics** (e.g. `~/.claude/...`, hooks configuration, `allowed-tools`). Where DSH has an equivalent, the text was rewritten (e.g. `~/.claude/skills` -> `~/.agents/skills`); where there is no equivalent, an **English banner** marks it. Links pointing outside the bundle were neutralized into plain text labelled "upstream reference, not distributed with this bundle" so no unclickable link remains. Per-file disposition is in `../../references/upstream-*.md` and `../../THIRD-PARTY-NOTICES.md`.
- `grill-with-docs` is a **delegating skill**: its whole body is one instruction line (`Call the skill tool twice, for "grilling" and "domain-modeling".`) that chains `grilling` and `domain-modeling`.
- 8 skills are upstream-defined **user-invoked** skills (`disable-model-invocation: true`): `grill-me`, `grill-with-docs`, `handoff`, `improve-codebase-architecture`, `retro`, `triage`, `to-spec`, `to-tickets`. They can **only** be invoked by the user via `/` and do not appear in the model-visible directory; their `description` is written as "a one-line human-readable summary + a mechanics footnote" (the footnote is for humans, not a model trigger phrase).
- That invocation split is upstream's written policy (the upstream repo's `.agents/invocation.md`, **not distributed with this bundle**; the criterion and the list of 8 are in `../../references/upstream-mp-skills.md`). The criterion is "can the model invoke it autonomously and beneficially", not whether the skill historically existed in this bundle.

## Reference documents

Rules and reference files distributed with the bundle live in `rules/` and `references/` at the bundle root:

| Path | File | Purpose |
|------|------|---------|
| `../../rules/` | `wsl-cli-tools.md` | WSL modern CLI toolchain mapping table |
| `../../rules/` | `proxy-management.md` | Proxy management and DSH plugin-bundle operations guide |
| `../../rules/` | `code-layout-and-comments.md` | Surface the core algorithm & spec first (numbered steps, readable without code); push boilerplate/helpers to the end |
| `../../references/` | `grow-dream-types.md` | grow-dream candidate type definitions |
| `../../references/` | `upstream-sources.md` | Upstream source registry index (citation keys / snapshots / licenses / usage scope) |
| `../../references/` | `upstream-ecc.md` | ECC source fascicle (59 skills) |
| `../../references/` | `upstream-mp-skills.md` | mattpocock/skills source fascicle (19 skills) |
| `../../references/` | `upstream-claude-mem.md` | claude-mem source fascicle (6 skills) |
| `../../references/` | `upstream-ocr.md` | open-code-review fascicle (0 skills; explains why it is reference material only) |
