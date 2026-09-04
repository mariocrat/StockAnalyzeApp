# StockBoda Agent Instructions

These instructions apply to the entire StockBoda repository unless a more specific AGENTS.md exists in a subdirectory.

## 1. Start by inspecting the workspace

Before making changes:

- Confirm the current worktree path.
- Confirm the current Git branch.
- Inspect `git status`.
- Identify existing unrelated modifications before editing anything.
- Never assume another worktree has the same working-tree state.

If the requested worktree, branch, or repository state does not match expectations, stop and report the mismatch before modifying files.

## 2. Protect unrelated work

- Do not modify, stage, revert, delete, or commit unrelated existing changes.
- Do not modify another worktree unless explicitly requested.
- Keep each task limited to the smallest reasonable set of files.
- Avoid broad refactors unless they are required for the requested task.
- Do not rename stable internal identifiers merely for cosmetic consistency.

## 3. Git safety

Unless the user explicitly requests otherwise:

- Do not stage changes.
- Do not commit.
- Do not push.
- Do not merge.
- Do not rebase.
- Do not force-push.
- Do not rewrite history.

When a commit is explicitly approved:

- Stage only the approved files or hunks.
- Review `git diff --cached` before committing.
- Do not include unrelated changes.
- Report the commit SHA and final Git status.

## 4. Two-failure rule

If the same approach fails twice:

- Do not repeat the same approach a third time.
- Stop and report:
  - the failed step,
  - the exact error,
  - the first attempt,
  - the second attempt,
  - the likely cause,
  - files changed,
  - current Git status,
  - a materially different next approach.

## 5. Implementation discipline

- Inspect the existing implementation before changing it.
- Prefer the smallest change that satisfies the requirement.
- Preserve already verified behavior unless the task explicitly changes it.
- Do not silently expand the scope.
- Do not guess when repository evidence can be inspected.
- If a required environment, service, credential, device, or sample is unavailable, report the limitation instead of claiming success.

## 6. Validation

Run validation appropriate to the files and behavior changed.

Typical checks include:

- targeted tests,
- related regression tests,
- full frontend or backend tests when warranted,
- lint,
- production build,
- `git diff --check`,
- Capacitor sync and Android build when Android packaged assets are affected.

Do not claim a check passed unless it was actually run.

If a generated Android APK/AAB is part of the task, verify the final packaged artifact rather than relying only on source or `dist`.

## 7. Production and release safety

Do not modify or deploy the following unless explicitly requested:

- production infrastructure,
- Render production services,
- production databases,
- production environment variables,
- OAuth production configuration,
- Google Play releases,
- signing configuration,
- release package identity,
- production domains or DNS.

A local implementation being correct does not mean production deployment is approved.

## 8. Privacy and sensitive data

- Do not commit real customer documents, financial statements, account information, credentials, secrets, tokens, or other sensitive data.
- Do not use real personal documents as repository fixtures.
- Keep real test documents outside the repository.
- Do not log personal or financial document contents unless explicitly required for a controlled local diagnosis.
- Prefer sanitized synthetic fixtures for automated tests.

## 9. Execution plans

Major or multi-step feature work should use a plan under:

`docs/plans/`

When an active plan is specified:

Before working:

1. Read this AGENTS.md.
2. Read the relevant plan.
3. Compare the plan's Current Status with the actual Git/worktree state.
4. If they disagree materially, stop and report the mismatch before continuing.

After a meaningful implementation or verification step:

- Update the plan to reflect the actual state.
- Mark only genuinely completed work as complete.
- Record important verification results.
- Keep unresolved or unverified work explicit.
- Set a clear Next Step.

Do not rewrite established product decisions in a plan without explicit user direction.

## 10. Reporting

At the end of a task, report concisely:

- what changed,
- files changed,
- tests/validation performed,
- anything not verified,
- current branch and HEAD,
- staged/unstaged state,
- whether any other worktree was affected.

