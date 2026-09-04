# StockBoda Development Plans

This directory contains persistent execution plans for major StockBoda features and multi-step work.

The purpose of a plan is to let a new development or verification thread recover the current project state without depending on a long conversation history.

## One feature, one plan

Use a separate plan for each significant feature or workstream.

Examples:

- `broker-import.md`
- `oauth.md`
- `billing.md`

Do not put unrelated feature histories into one global `plan.md`.

## Recommended structure

Each active plan should contain these sections:

### Goal

What the feature is intended to achieve.

### Scope

What is currently included.

### Confirmed Decisions

Product and technical decisions that should not be silently changed.

### Current Status

A concise checklist of what has actually been implemented.

### Verification

Tests and real-world checks that have actually been completed.

### Remaining / Unverified

Known work or verification that is still outstanding.

### Next Step

The single most useful next action.

### Out of Scope

Things intentionally postponed or excluded from the current work.

## Plan update rules

- Plans describe the actual repository state, not the desired state.
- Never mark an item complete merely because code was written.
- Distinguish implementation, automated verification, independent review, device testing, and production verification when relevant.
- Keep unverified items explicit.
- Do not silently remove unresolved problems.
- Keep the plan concise enough for a new Codex thread to read quickly.
- Detailed historical discussion belongs in Git history or other documentation, not in the active plan.

## Starting a development thread

A typical instruction can be:

`Read AGENTS.md and the relevant file under docs/plans/. Compare the plan with the actual Git state. If they match, perform only the documented Next Step.`

## Starting an independent verification thread

A typical instruction can be:

`Read AGENTS.md and the relevant plan. Independently verify the current uncommitted diff against the plan and report Blocker/Major/Minor/Unverified without modifying the code.`

