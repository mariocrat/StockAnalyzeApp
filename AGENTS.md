# StockBoda Agent Instructions

Applies to this repository; read any more specific AGENTS.md or AGENTS.override.md before working in its scope. Explicit user scope and authorization take precedence.

## Start and scope

- Confirm the actual repository root, branch, HEAD, worktree list, and full Git status. Do not infer the checkout from a thread title or an old absolute path.
- Identify existing staged, unstaged, and untracked work. Preserve unrelated files and unrelated hunks in shared files. Do not modify another worktree without explicit authorization.
- Inspect the current implementation. Make the smallest change that satisfies the request; do not add unrequested features or unrelated refactors.
- Report material workspace or plan mismatches before making dependent changes.
- Do not stage, commit, push, merge, rebase, switch branches, or rewrite history without authorization. Before an approved commit, inspect staged names and the full staged diff; use explicit paths or hunks.
- Do not discard existing changes or local data with broad `git clean`, working-tree reset/restore, recursive deletion, database deletion, app uninstall, or app-data clearing unless the exact targets and data-loss impact are explicitly approved.

## Execution and evidence

- Classify commands by filesystem, database, and external-service effects before running them. A test, build, server startup, or GET request is not necessarily read-only.
- After two failures of the same material approach, stop that approach. Report the attempts, errors, evidence, likely cause, current changes/status, and a materially different next step. Fix a shell/tool problem as such; do not mistake it for a product defect.
- Validate in proportion to risk. Distinguish static, unit, HTTP, packaged-artifact, device, and external-system evidence. Never report an unexecuted check as passed.
- Major work and high-risk DB/auth/payment/security/environment/release changes require a persistent plan; high-risk changes also require independent review. Small low-risk edits need no persistent plan.
- New plans belong in docs/exec-plans/. Read and reconcile an explicitly assigned legacy plan in its original worktree. If a user limits files or requests a pre-write stop, that boundary also applies to plan files. Update authorized plans after meaningful steps; read-only reviews do not create or update plans.
- Implementation does not authorize production configuration changes, data changes, deployment, or Play publication.
- Report changed files, validation and limitations, branch/HEAD, staged/unstaged state, and whether other worktrees were affected.

## StockBoda invariants

- Debug, test ads, and mobile:build do not prove environment isolation. Verify the effective API before running an app. Do not use production as the development/test environment; current debug wrappers can select production settings.
- Isolate all relevant data stores, caches, process/file environment, and external requests before DB-backed tests. Existing full-suite isolation is incomplete; see TESTING.md.
- Preserve user ownership checks, storage opt-in, AI consent, server-verified entitlements, and order/user ledger integrity.
- Schema changes require existing-schema upgrade and recovery evidence. Never treat destructive migration/reset helpers as routine setup.
- Preserve existing package/application IDs, OAuth schemes and related identifiers, product IDs, storage keys, and `ALPHAMATE_*` technical identifiers unless the change is explicitly approved in scope and has compatibility/migration, rollback/recovery, and related external-configuration verification plans.
- Capacitor sync can change tracked Gradle files. Review those changes and verify the final APK/AAB, not only source or dist.
- Auth, purchases, ads, and app-return changes need appropriate device/external validation; otherwise report them as unverified.
- Do not put real customer documents, financial records, credentials, tokens, or secrets in source, fixtures, logs, or documentation. Use synthetic data.

## Documentation map

Start with [docs/README.md](docs/README.md), including its open audit findings.

- [Architecture](docs/ARCHITECTURE.md): components, data flow, runtime boundaries.
- [Product rules](docs/PRODUCT_RULES.md): intended behavior and policy decisions.
- [Testing](docs/TESTING.md): command effects, isolation prerequisites, evidence levels.
- [Release](docs/RELEASE.md): environment/build variants and release evidence.
- [Security](docs/SECURITY.md): authentication, privacy, secrets, external trust.
- [Data](docs/DATA.md): storage, ownership, schema, deletion, backup/recovery.
- [Development workflow](docs/DEVELOPMENT_WORKFLOW.md): scope, threads, reviews, Git.
- [Execution plans](docs/exec-plans/README.md): plan lifecycle and handoff.
