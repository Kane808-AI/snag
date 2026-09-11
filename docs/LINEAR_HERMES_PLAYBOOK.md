# Snag Linear + Hermes Playbook

## Operating model

Linear is the visual control layer. It answers: **what is worth doing, in what
order, and what is the current business-facing status?**

Hermes Kanban is the execution layer. It owns the durable task, worker
assignment, dependencies, evidence, review, and completion record. Do not run
Snag work from a Linear issue alone, and do not create untracked execution work
directly in Hermes.

The bridge is intentionally narrow:

```text
Linear issue, in “Snag App — Linear Pilot”, labeled “Hermes Pilot”
  -> held Hermes Kanban task on board “snag”
  -> explicit human release
  -> Hermes worker + review
  -> mapped status shown back in Linear
```

## One-time setup

1. Create or confirm the Linear project named `Snag App — Linear Pilot` in team
   `BRA`.
2. Confirm these Linear workflow states exist: `Todo`, `In Progress`, `Needs
   Approval`, `Changes Requested`, and `Done`.
3. Create the exact label `Hermes Pilot`. This is the only label that permits
   bridge intake.
4. Store the Linear personal API key in macOS Keychain under service
   `hermes-linear-snag-pilot`. Never put it in `.env`, this repository, a task,
   or a log.
5. Validate the bridge without changing its live LaunchAgent:

   ```bash
   /opt/homebrew/bin/python3 -m pytest tests/test_linear_bridge.py -q
   /opt/homebrew/bin/python3 linear_bridge.py --dry-run
   plutil -lint deploy/com.hermes.snag-linear-pilot.plist
   ```

The dry run reads Linear scope but changes neither Linear nor Hermes. When run
from an interactive sandbox, Keychain access can be denied even though the
launchd service has access; use the bridge log as the source of truth in that
case.

## Create work in Linear

Create one issue per independently reviewable outcome. Use this body shape:

```md
## Outcome
<observable result>

## Scope
<included paths, behavior, and exclusions>

## Acceptance checks
- <command or observable check>
- <command or observable check>

## Constraints
- Snag only. No credentials, billing, deployment, public posts, or unrelated entities.
```

Set its state to `Todo` and add `Hermes Pilot`. The bridge will only intake an
issue that meets all three conditions: correct project, `Todo`, exact label.

## Execution lifecycle

| Linear view | Hermes Kanban state | Meaning / required action |
|---|---|---|
| Todo | Not yet bridged | Prioritized, but not approved for execution. |
| Needs Approval | triage | Bridge created the task. Review scope, then promote it in Hermes. |
| In Progress | running or review | A worker is active or the result is being reviewed. |
| Changes Requested | triage | The worker needs the task clarified or reshaped. Update the Hermes task, then re-promote it. |
| Done | done | Hermes recorded completion evidence; bridge reflected it in Linear. |

### Release a held task

1. Open the Hermes task created by the bridge and verify its scope and hard
   exclusions.
2. Add any missing acceptance check as a Hermes comment.
3. Move the Linear issue to `In Progress`. On the next bridge pass, Hermes
   promotes the matching triage task and dispatches the worker.
4. Require the worker report: changed paths, commands run, outputs, unresolved
   risks, and verification steps.
5. Send implementation to Hermes review before marking it done.

To cancel or clean up an issue, remove the `Hermes Pilot` label in Linear. On
the next bridge pass, it archives only that issue’s mapped Hermes task and
forgets the mapping. No terminal action is required.

## Bridge contract

`linear_bridge.py` is idempotent. It records the Linear issue ID to Hermes task
ID mapping in `.linear_bridge_state.json`, which is ignored by Git.

- Intake is opt-in: only the exact project and label are read.
- New tasks are assigned to `builder` and start in native Hermes triage before
  any worker can claim them. The task body states the explicit human-release
  requirement.
- No public listener is opened. The Linear token is read from Keychain only.
- A task status updates its mapped Linear issue only. No other Linear issue is
  changed.
- The live LaunchAgent runs every 60 seconds. It is a bounded reconciliation
  loop, not a worker dispatcher.

The status mapping is:

```text
Hermes running/review -> Linear In Progress
Hermes blocked        -> Linear Needs Approval
Hermes triage         -> Linear Needs Approval
Hermes done           -> Linear Done
```

## Daily operating rhythm

1. In Linear, keep only the next small outcomes in `Todo`; apply `Hermes Pilot`
   only when they are ready for intake.
2. When Linear shows `Needs Approval`, review the issue and move it to `In
   Progress` to release it. Remove `Hermes Pilot` to cancel it.
3. Review finished worker evidence in Hermes. Let the bridge update Linear.
4. At day end, Linear is the portfolio view; Hermes is the audit trail.

## Failure handling

| Symptom | Cause | Recovery |
|---|---|---|
| No Hermes task appears | Issue lacks the project, `Todo`, or exact label | Fix the issue, then run a dry run. |
| Bridge says Keychain key missing | The token is absent or stored under another service name | Add it only to Keychain as `hermes-linear-snag-pilot`. |
| Linear status does not change | Task is not mapped or state is intentionally unmapped | Inspect the Hermes task ID and bridge state; do not edit Linear to fake completion. |
| Task is blocked | A human decision or missing input is required | Record the blocker in Hermes, decide it, then unblock. |

## Safe changes

Test a bridge change locally first:

```bash
/opt/homebrew/bin/python3 -m pytest tests/test_linear_bridge.py -q
/opt/homebrew/bin/python3 linear_bridge.py --dry-run
```

Do not install, unload, restart, or otherwise change the active LaunchAgent
without Chris’s explicit approval. Do not turn this pilot into unattended
worker dispatch without a separate decision.
