#!/usr/bin/env python3
"""Bounded Linear -> Hermes Kanban bridge for the Snag pilot.

The bridge is intentionally an observer unless --allow-create is passed.  Even
then, it only creates a task for an issue in the configured Linear project that
has the explicit ``Hermes Pilot`` label.  It never scans another project, reads
tokens from a file, or starts a public HTTP listener.
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parent
LOG = logging.getLogger("snag.linear_bridge")
LINEAR_ENDPOINT = "https://api.linear.app/graphql"
PILOT_LABEL = "Hermes Pilot"
KANBAN_TO_LINEAR_STATUS = {
    "running": "In Progress",
    "review": "In Progress",
    "blocked": "Needs Approval",
    "triage": "Needs Approval",
    "done": "Done",
}


@dataclass(frozen=True)
class Settings:
    team_key: str = "BRA"
    project_name: str = "Snag App — Linear Pilot"
    board: str = "snag"
    keychain_service: str = "hermes-linear-snag-pilot"
    state_path: Path = ROOT / ".linear_bridge_state.json"


class BridgeError(RuntimeError):
    pass


def keychain_token(service: str) -> str:
    """Read the token from macOS Keychain without printing it."""
    # Keychain Access's "New Password Item" is an application/internet
    # password, while `security add-generic-password` creates a generic item.
    # Support both so the operator never needs to reveal or re-enter a token.
    commands = (
        ["security", "find-generic-password", "-a", "chriskaneshiro", "-s", service, "-w"],
        ["security", "find-internet-password", "-a", "chriskaneshiro", "-s", service, "-w"],
    )
    for command in commands:
        result = subprocess.run(command, check=False, capture_output=True, text=True)
        token = result.stdout.strip()
        if not result.returncode and token:
            return token
    raise BridgeError(
        "Linear pilot key not found in macOS Keychain. "
        "Store it under service 'hermes-linear-snag-pilot' before starting the bridge."
    )


def graphql(token: str, query: str, variables: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    request = urllib.request.Request(
        LINEAR_ENDPOINT,
        data=body,
        headers={
            "Authorization": token,
            "Content-Type": "application/json",
            "User-Agent": "Hermes-Snag-Linear-Pilot/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # Linear's GraphQL validation details are safe to surface and are
        # essential for correcting a schema mismatch. Never include headers.
        detail = exc.read().decode("utf-8", errors="replace").strip()
        raise BridgeError(f"Linear API returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise BridgeError(f"Linear API request failed: {exc.reason}") from exc
    if payload.get("errors"):
        raise BridgeError("Linear API rejected the request: " + str(payload["errors"]))
    data = payload.get("data")
    if not isinstance(data, dict):
        raise BridgeError("Linear API returned no data")
    return data


DISCOVER_QUERY = """
query PilotScope {
  teams(first: 50) { nodes { id key name } }
  projects(first: 50) { nodes { id name teams { nodes { id key } } } }
}
"""

ISSUES_QUERY = """
query PilotIssues($projectId: ID!) {
  issues(first: 100, filter: { project: { id: { eq: $projectId } } }) {
    nodes {
      id identifier title description updatedAt
      state { id name type }
      labels { nodes { name } }
    }
  }
}
"""

TEAM_STATES_QUERY = """
query PilotWorkflowStates {
  teams(first: 50) { nodes { id key states { nodes { id name type } } } }
}
"""

ISSUE_UPDATE_MUTATION = """
mutation PilotIssueState($issueId: String!, $stateId: String!) {
  issueUpdate(id: $issueId, input: { stateId: $stateId }) {
    success
    issue { id state { name } }
  }
}
"""


def discover_project(call: Callable[[str, dict[str, Any]], dict[str, Any]], settings: Settings) -> str:
    data = call(DISCOVER_QUERY, {})
    teams = data.get("teams", {}).get("nodes", [])
    team = next((item for item in teams if item.get("key") == settings.team_key), None)
    if not team:
        raise BridgeError(f"Linear team {settings.team_key!r} was not found")
    projects = data.get("projects", {}).get("nodes", [])
    project = next(
        (
            item for item in projects
            if item.get("name") == settings.project_name
            and any(member.get("id") == team.get("id") for member in item.get("teams", {}).get("nodes", []))
        ),
        None,
    )
    if not project:
        raise BridgeError(
            f"Pilot project {settings.project_name!r} was not found in team {settings.team_key!r}"
        )
    return str(project["id"])


def project_issues(call: Callable[[str, dict[str, Any]], dict[str, Any]], project_id: str) -> list[dict[str, Any]]:
    data = call(ISSUES_QUERY, {"projectId": project_id})
    return list(data.get("issues", {}).get("nodes", []))


def workflow_state_ids(call: Callable[[str, dict[str, Any]], dict[str, Any]], settings: Settings) -> dict[str, str]:
    data = call(TEAM_STATES_QUERY, {})
    teams = data.get("teams", {}).get("nodes", [])
    team = next((item for item in teams if item.get("key") == settings.team_key), None)
    if not team:
        raise BridgeError(f"Linear team {settings.team_key!r} was not found while reading workflow states")
    states = {
        str(item["name"]): str(item["id"])
        for item in team.get("states", {}).get("nodes", [])
        if item.get("name") and item.get("id")
    }
    missing = set(KANBAN_TO_LINEAR_STATUS.values()) - states.keys()
    if missing:
        raise BridgeError("Pilot workflow states are missing: " + ", ".join(sorted(missing)))
    return states


def kanban_task_status(task_id: str, settings: Settings) -> str:
    result = subprocess.run(
        ["hermes", "kanban", "--board", settings.board, "show", task_id, "--json"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise BridgeError(f"Cannot read mapped Hermes task {task_id}: " + result.stderr.strip())
    try:
        return str(json.loads(result.stdout)["task"]["status"])
    except (json.JSONDecodeError, KeyError) as exc:
        raise BridgeError(f"Hermes Kanban returned invalid task JSON for {task_id}") from exc


def update_issue_state(api: Callable[[str, dict[str, Any]], dict[str, Any]], issue_id: str, state_id: str) -> None:
    data = api(ISSUE_UPDATE_MUTATION, {"issueId": issue_id, "stateId": state_id})
    if not data.get("issueUpdate", {}).get("success"):
        raise BridgeError(f"Linear declined status update for issue {issue_id}")


def is_ready(issue: dict[str, Any]) -> bool:
    return has_pilot_label(issue) and issue.get("state", {}).get("name") == "Todo"


def has_pilot_label(issue: dict[str, Any]) -> bool:
    labels = {label.get("name") for label in issue.get("labels", {}).get("nodes", [])}
    return PILOT_LABEL in labels


def load_state(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"tasks": {}}
    except (OSError, json.JSONDecodeError) as exc:
        raise BridgeError(f"Cannot read bridge state {path}: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("tasks", {}), dict):
        raise BridgeError(f"Bridge state {path} has an invalid shape")
    return data


def save_state(path: Path, state: dict[str, Any]) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def task_body(issue: dict[str, Any]) -> str:
    description = issue.get("description") or "No Linear description supplied."
    return f"""Linear pilot issue: {issue['identifier']}
Linear ID: {issue['id']}
Project: Snag App — Linear Pilot

{description}

Hard scope: Snag only. Work only on this task and the files required by it.
Never access another entity/project. Do not touch Telegram, live ingestion,
credentials, deployment, billing, public posts, or GitHub in this pilot.

Report changed paths, commands run, verification result, and any blocker in the
Hermes task before completion.
"""


def create_kanban_task(issue: dict[str, Any], settings: Settings) -> str:
    command = [
        "hermes", "kanban", "--board", settings.board, "create", issue["title"],
        "--body", task_body(issue),
        "--assignee", "builder",
        "--idempotency-key", f"linear:{issue['id']}",
        # Native triage is the non-dispatchable human-release gate. A bare
        # blocked task is auto-promoted by this Hermes gateway version.
        "--triage",
        "--json",
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode:
        raise BridgeError("Hermes Kanban task creation failed: " + result.stderr.strip())
    try:
        payload = json.loads(result.stdout)
        task_id = str(payload["id"])
    except (json.JSONDecodeError, KeyError) as exc:
        raise BridgeError("Hermes Kanban returned invalid task JSON") from exc
    return task_id


def archive_kanban_task(task_id: str, settings: Settings) -> None:
    result = subprocess.run(
        ["hermes", "kanban", "--board", settings.board, "archive", task_id],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise BridgeError("Hermes Kanban task archive failed: " + result.stderr.strip())


def promote_kanban_task(task_id: str, settings: Settings) -> None:
    result = subprocess.run(
        ["hermes", "kanban", "--board", settings.board, "promote", task_id],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise BridgeError("Hermes Kanban task promotion failed: " + result.stderr.strip())


def run_once(settings: Settings, *, allow_create: bool, sync_status: bool, dry_run: bool,
             call: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None,
             create_task: Callable[[dict[str, Any], Settings], str] = create_kanban_task,
             archive_task: Callable[[str, Settings], None] = archive_kanban_task,
             promote_task: Callable[[str, Settings], None] = promote_kanban_task,
             task_status: Callable[[str, Settings], str] = kanban_task_status) -> dict[str, Any]:
    token = keychain_token(settings.keychain_service) if call is None else "test-token"
    api = call or (lambda query, variables: graphql(token, query, variables))
    project_id = discover_project(api, settings)
    issues = project_issues(api, project_id)
    state = load_state(settings.state_path)
    candidates = [issue for issue in issues if is_ready(issue)]
    issues_by_id = {str(issue["id"]): issue for issue in issues}
    created: list[dict[str, str]] = []
    archived: list[dict[str, str]] = []
    promoted: list[dict[str, str]] = []
    status_updates: list[dict[str, str]] = []
    state_changed = False

    # Removing the opt-in label in Linear is the no-terminal cancellation
    # control. Archive only the directly mapped Hermes task, then forget the
    # mapping so a future re-label starts a deliberate new task.
    for issue_id, mapping in list(state["tasks"].items()):
        issue = issues_by_id.get(issue_id)
        if not issue or has_pilot_label(issue):
            continue
        archived.append({"linear": mapping["identifier"], "kanban": mapping["task_id"]})
        if not dry_run:
            archive_task(mapping["task_id"], settings)
            del state["tasks"][issue_id]
            state_changed = True

    if allow_create:
        for issue in candidates:
            if issue["id"] in state["tasks"]:
                continue
            if dry_run:
                created.append({"linear": issue["identifier"], "kanban": "dry-run"})
                continue
            task_id = create_task(issue, settings)
            state["tasks"][issue["id"]] = {
                "identifier": issue["identifier"],
                "task_id": task_id,
                "created_at": int(time.time()),
            }
            state_changed = True
            created.append({"linear": issue["identifier"], "kanban": task_id})
        if not dry_run and state_changed:
            save_state(settings.state_path, state)

    # Linear is the operator UI: moving a held issue to In Progress is the
    # explicit release. Only native triage is eligible, so a blocked task is
    # never accidentally restarted.
    for issue_id, mapping in state["tasks"].items():
        issue = issues_by_id.get(issue_id)
        if not issue or issue.get("state", {}).get("name") != "In Progress":
            continue
        if task_status(mapping["task_id"], settings) != "triage":
            continue
        promoted.append({"linear": mapping["identifier"], "kanban": mapping["task_id"]})
        if not dry_run:
            promote_task(mapping["task_id"], settings)

    if sync_status:
        state_ids = workflow_state_ids(api, settings)
        for issue_id, mapping in state["tasks"].items():
            issue = issues_by_id.get(issue_id)
            if not issue:
                continue
            target_name = KANBAN_TO_LINEAR_STATUS.get(task_status(mapping["task_id"], settings))
            if not target_name or issue.get("state", {}).get("name") == target_name:
                continue
            status_updates.append({"linear": issue["identifier"], "status": target_name})
            if not dry_run:
                update_issue_state(api, issue_id, state_ids[target_name])

    return {
        "project_id": project_id,
        "issues_seen": len(issues),
        "ready_issues": [issue["identifier"] for issue in candidates],
        "created": created,
        "archived": archived,
        "promoted": promoted,
        "status_updates": status_updates,
        "allow_create": allow_create,
        "sync_status": sync_status,
        "dry_run": dry_run,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-create", action="store_true", help="Create only explicitly labelled pilot tasks")
    parser.add_argument("--sync-status", action="store_true", help="Reflect mapped Hermes task statuses in Linear")
    parser.add_argument("--dry-run", action="store_true", help="Discover scope without creating Hermes tasks")
    parser.add_argument("--state-path", type=Path, default=Settings().state_path)
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()
    settings = Settings(state_path=args.state_path)
    try:
        result = run_once(
            settings,
            allow_create=args.allow_create,
            sync_status=args.sync_status,
            dry_run=args.dry_run,
        )
    except BridgeError as exc:
        LOG.error("%s", exc)
        return 2
    LOG.info("Linear pilot poll result: %s", json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
