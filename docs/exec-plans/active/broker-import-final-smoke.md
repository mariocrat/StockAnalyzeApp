# Broker import final smoke

## Goal

Finish import preparation UX, separate AI failures from approved results, and permit
authenticated server-allowlisted Debug owner testing without quota consumption.

## Scope

Worktree `broker-import-final-smoke`, branch `fix/broker-import-final-smoke`, baseline
`0e01f6506d606e3ef98a912825a24d1bd668124b`. Protect main's unrelated Play README and
the original dirty broker-import worktree. No commit, push, merge or deployment.

## Decisions

- Debug marker is public and never sufficient authority; real session, server user-ID
  allowlist and AI privacy consent are all required. Empty allowlist disables access.
- Tester execution preserves ordinary validation, rate/capacity, idempotency, history
  ownership and approved display boundaries; only wallet/ad consumption is bypassed.
- Parser/completeness/extraction and review-display activation are unchanged.
- Basic: `gpt-6-luna`, none, 1000 output tokens; advanced: `gpt-6.1-sol`, medium,
  3000 tokens; fallback: `gpt-6-luna`, low. Existing environment overrides remain.
- Official OpenAI model pages confirm both Responses model IDs and reasoning support.
  No live model call or credential validity probe is authorized.

## Current Status

- [x] Baseline and protected README hash verified; isolated worktree created clean.
- [x] Implementation and official isolated regression tests.
- [x] Inventory, lint, frontend build and diff check.
- [ ] User independent approval and real-device revalidation.

## Verification

Verified on 2026-10-22 in this worktree, baseline HEAD plus unstaged diff.
Process API key reuse was authorized; no value is copied, logged or persisted.

- Import preparation: primary counted mobile sticky action, readiness from existing
  identity/time validators, effect-driven scroll to review selection after preparation.
  Pending confirmation now follows the same optional/required time control contract as
  the PDF picker. Time input uses wrapping and an em-based native input width.
- Error/request_error responses render only failure/retry, never success body/cards.
  401 prompts login, 402 opens the pass dialog, other failures retain refund guidance;
  an uncertain transport outcome does not claim a confirmed refund.
- Authenticated tester eligibility is loaded via the actual marked entitlement request.
  Wallet refresh preserves the server-issued tester indication. Ordinary sessions,
  Release requests, unlisted Debug users and consent checks keep their existing gates.
- Tester history admission needed exact basic/advanced source additions in writer and
  reader as well as cache. Reader cross-field checks run only for actual tester source;
  existing optional empty access placeholders remain compatible. New-write validation
  stays exact and complete. Actual mocked-model generation -> SQL write -> detail reopen
  and idempotent replay preserve body/access with zero wallet/ad consumption.
- Official H4 Python: **218 distinct direct tests PASS**, covering access 8, persistence 4,
  refund 13, model client 16, transport 10, source admission 23, idempotency 14, execution
  cache 14, activation 14, history adapter 44, history write access 17, prepared content 18,
  coordinator 16 and docs 7. The default/configured/invalid fallback-effort matrix was
  additionally rerun as one existing direct case, not added to the distinct total.
- Official H4 Node: **176 distinct direct tests PASS** across broker 31, PDF binary 5,
  journal mobile 44, OAuth logout 6, selection 5, navigation 5, chart source 46, canonical
  renderer 23 and legacy cross-contract 11. Node coordinator regressions **10/10 PASS**.
  Chart handoff basic/advanced/failures/titles/paired stages PASS within the unchanged
  60-second per-stage budget. No unexpected guarded access; restoration, patch restoration
  and cleanup PASS. Expected negative coordinator probes remain fail-closed.
- Inventory: Python **108 modules / 1082 direct / 18 child probes**; Node **24 / 285**;
  missing/extra/duplicate 0. Existing exact file snapshots only; no broad guard access.
- `npm.cmd run lint`, `npm.cmd run build`, `git diff --check`: PASS. Build used a
  process-local loopback API and no dev tools, never an actual API request or APK sync.
  Existing local dependencies were copied into this worktree, without package download
  or installation and without modifying the main installation.
- Failures diagnosed and resolved: incomplete synthetic manual-cost fixture; stale model,
  CTA/time and failure-copy expectations; stale inventory counts/hashes (Node test hashes
  are LF-normalized, component snapshots are byte-exact); new reader check incorrectly
  dereferencing the existing empty access placeholder. The latter caused a real finalizer
  fail-closed and chart handoff failure, not a timeout. No test skips or timeout changes.
- Model support: https://developers.openai.com/api/docs/models/gpt-6-luna and
  https://developers.openai.com/api/docs/models/gpt-6.1-sol confirm Responses support and
  the requested none/medium/low efforts. Account-specific access and real output quality
  were not probed. Existing single-episode prompt and environment overrides remain.

## Remaining / Unverified

Render tester allowlist configuration and device smoke are follow-ups, not executed.
The public Debug marker can be forged; the authenticated allowlisted account is the
security boundary, not APK attestation.
Browser/native 360-412px layout, sticky CTA with native ads, real authentication and
actual model calls are not verified by the VM/CSS/H4 evidence above. APK was not built.

## Required server configuration (not applied)

Set `ALPHAMATE_DEBUG_REVIEW_TESTER_USER_IDS` to a comma-separated list of exact internal
authenticated `user.id` values, not provider IDs, names or client-supplied user IDs.
An empty/missing list disables the exception. Keep production dev access disabled.
The server needs this implementation before the new Debug client can discover eligibility.
The header does not replace a valid session or AI consent; rate/capacity limits remain.

Existing model environment values take priority over new defaults. After approval,
verify the intended deployment values: `OPENAI_BASIC_REVIEW_MODEL=gpt-6-luna`,
`OPENAI_ADVANCED_REVIEW_MODEL=gpt-6.1-sol`,
`OPENAI_ADVANCED_REVIEW_FALLBACK_MODEL=gpt-6-luna`, basic/advanced reasoning none/medium,
basic/advanced max output tokens 1000/3000 and fallback reasoning low via
`OPENAI_ADVANCED_REVIEW_FALLBACK_REASONING_EFFORT`. No environment was changed here.

## Next Step

Obtain independent approval of this unstaged diff. Only after separately approved
backend deployment/allowlist setup and a new Debug artifact, run owner device smoke.

## Out of Scope

Production settings/data, live AI, APK installation/build, new parsers, v2 activation,
unlimited access for non-allowlisted users, client secrets, and Git publication.
