import sys
from pathlib import Path

SN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SN))

import linear_bridge  # noqa: E402


def _scope(project_id="project-1"):
    return {
        "teams": {"nodes": [{"id": "team-1", "key": "BRA", "name": "Brand75"}]},
        "projects": {"nodes": [{
            "id": project_id,
            "name": "Snag App — Linear Pilot",
            "teams": {"nodes": [{"id": "team-1", "key": "BRA"}]},
        }]},
    }


def _issue(identifier="BRA-1", label="Hermes Pilot", state="Todo"):
    return {
        "id": "issue-1", "identifier": identifier, "title": "Safe pilot task",
        "description": "Local web viewer only.", "updatedAt": "2026-08-31T00:00:00Z",
        "state": {"id": "state-1", "name": state, "type": "unstarted"},
        "labels": {"nodes": [{"name": label}] if label else []},
    }


def test_discovers_only_named_project_in_bra_team():
    settings = linear_bridge.Settings()
    assert linear_bridge.discover_project(lambda *_: _scope(), settings) == "project-1"


def test_keychain_supports_generic_or_application_password(monkeypatch):
    calls = []

    class Result:
        def __init__(self, code, stdout):
            self.returncode = code
            self.stdout = stdout

    def run(command, **_kwargs):
        calls.append(command)
        return Result(1, "") if "find-generic-password" in command else Result(0, "token-value\n")

    monkeypatch.setattr(linear_bridge.subprocess, "run", run)
    assert linear_bridge.keychain_token("hermes-linear-snag-pilot") == "token-value"
    assert [command[1] for command in calls] == ["find-generic-password", "find-internet-password"]


def test_ready_requires_explicit_label_and_todo():
    assert linear_bridge.is_ready(_issue())
    assert not linear_bridge.is_ready(_issue(label="Other"))
    assert not linear_bridge.is_ready(_issue(state="In Progress"))


def test_observer_mode_never_creates_tasks(tmp_path):
    calls = []

    def api(query, _variables):
        return _scope() if "PilotScope" in query else {"issues": {"nodes": [_issue()]}}

    def create(issue, _settings):
        calls.append(issue)
        return "t_test"

    result = linear_bridge.run_once(
        linear_bridge.Settings(state_path=tmp_path / "state.json"),
        allow_create=False, sync_status=False, dry_run=False, call=api, create_task=create,
    )
    assert result["ready_issues"] == ["BRA-1"]
    assert result["created"] == []
    assert calls == []


def test_dry_run_reports_candidate_without_writing_state(tmp_path):
    path = tmp_path / "state.json"

    def api(query, _variables):
        return _scope() if "PilotScope" in query else {"issues": {"nodes": [_issue()]}}

    result = linear_bridge.run_once(
        linear_bridge.Settings(state_path=path),
        allow_create=True, sync_status=False, dry_run=True, call=api,
    )
    assert result["created"] == [{"linear": "BRA-1", "kanban": "dry-run"}]
    assert not path.exists()


def test_create_is_idempotent_across_polls(tmp_path):
    path = tmp_path / "state.json"
    created = []

    def api(query, _variables):
        return _scope() if "PilotScope" in query else {"issues": {"nodes": [_issue()]}}

    def create(issue, _settings):
        created.append(issue["id"])
        return "t_test"

    settings = linear_bridge.Settings(state_path=path)
    first = linear_bridge.run_once(settings, allow_create=True, sync_status=False, dry_run=False, call=api, create_task=create)
    second = linear_bridge.run_once(settings, allow_create=True, sync_status=False, dry_run=False, call=api, create_task=create)
    assert first["created"] == [{"linear": "BRA-1", "kanban": "t_test"}]
    assert second["created"] == []
    assert created == ["issue-1"]


def test_removing_pilot_label_archives_only_the_mapped_task(tmp_path):
    path = tmp_path / "state.json"
    path.write_text('{"tasks": {"issue-1": {"identifier": "BRA-1", "task_id": "t_test"}}}')
    archived = []

    def api(query, _variables):
        return _scope() if "PilotScope" in query else {"issues": {"nodes": [_issue(label=None)]}}

    result = linear_bridge.run_once(
        linear_bridge.Settings(state_path=path),
        allow_create=True,
        sync_status=False,
        dry_run=False,
        call=api,
        archive_task=lambda task_id, _settings: archived.append(task_id),
    )
    assert result["archived"] == [{"linear": "BRA-1", "kanban": "t_test"}]
    assert archived == ["t_test"]
    assert linear_bridge.load_state(path) == {"tasks": {}}


def test_linear_in_progress_promotes_only_a_triage_task(tmp_path):
    path = tmp_path / "state.json"
    path.write_text('{"tasks": {"issue-1": {"identifier": "BRA-1", "task_id": "t_test"}}}')
    promoted = []

    def api(query, _variables):
        if "PilotScope" in query:
            return _scope()
        return {"issues": {"nodes": [_issue(state="In Progress")]}}

    result = linear_bridge.run_once(
        linear_bridge.Settings(state_path=path),
        allow_create=True,
        sync_status=False,
        dry_run=False,
        call=api,
        promote_task=lambda task_id, _settings: promoted.append(task_id),
        task_status=lambda *_: "triage",
    )
    assert result["promoted"] == [{"linear": "BRA-1", "kanban": "t_test"}]
    assert promoted == ["t_test"]


def test_new_task_is_created_in_triage_for_explicit_human_release(monkeypatch):
    calls = []

    class Result:
        returncode = 0
        stdout = '{"id": "t_test"}'
        stderr = ""

    def run(command, **_kwargs):
        calls.append(command)
        return Result()

    monkeypatch.setattr(linear_bridge.subprocess, "run", run)
    assert linear_bridge.create_kanban_task(_issue(), linear_bridge.Settings()) == "t_test"
    assert "--triage" in calls[0]
    assert "--initial-status" not in calls[0]
    assert len(calls) == 1


def test_task_body_carries_scope_and_never_mentions_credentials():
    body = linear_bridge.task_body(_issue())
    assert "Snag only" in body
    assert "credentials" in body
    assert "Linear ID: issue-1" in body


def test_sync_status_updates_only_mapped_pilot_task(tmp_path):
    path = tmp_path / "state.json"
    path.write_text('{"tasks": {"issue-1": {"identifier": "BRA-1", "task_id": "t_test"}}}')
    updates = []

    def api(query, variables):
        if "PilotScope" in query:
            return _scope()
        if "PilotIssues" in query:
            return {"issues": {"nodes": [_issue(state="Todo")]}}
        if "PilotWorkflowStates" in query:
            return {"teams": {"nodes": [{"key": "BRA", "states": {"nodes": [
                {"id": "todo", "name": "Todo"},
                {"id": "progress", "name": "In Progress"},
                {"id": "approval", "name": "Needs Approval"},
                {"id": "changes", "name": "Changes Requested"},
                {"id": "done", "name": "Done"},
            ]}}]}}
        if "PilotIssueState" in query:
            updates.append(variables)
            return {"issueUpdate": {"success": True, "issue": {"id": "issue-1", "state": {"name": "Done"}}}}
        raise AssertionError(query)

    result = linear_bridge.run_once(
        linear_bridge.Settings(state_path=path),
        allow_create=False,
        sync_status=True,
        dry_run=False,
        call=api,
        task_status=lambda *_: "done",
    )
    assert result["status_updates"] == [{"linear": "BRA-1", "status": "Done"}]
    assert updates == [{"issueId": "issue-1", "stateId": "done"}]


def test_sync_status_dry_run_does_not_mutate_linear(tmp_path):
    path = tmp_path / "state.json"
    path.write_text('{"tasks": {"issue-1": {"identifier": "BRA-1", "task_id": "t_test"}}}')

    def api(query, _variables):
        if "PilotScope" in query:
            return _scope()
        if "PilotIssues" in query:
            return {"issues": {"nodes": [_issue(state="Todo")]}}
        if "PilotWorkflowStates" in query:
            return {"teams": {"nodes": [{"key": "BRA", "states": {"nodes": [
                {"id": "todo", "name": "Todo"}, {"id": "progress", "name": "In Progress"},
                {"id": "approval", "name": "Needs Approval"}, {"id": "changes", "name": "Changes Requested"},
                {"id": "done", "name": "Done"},
            ]}}]}}
        raise AssertionError("dry run should not mutate Linear")

    result = linear_bridge.run_once(
        linear_bridge.Settings(state_path=path),
        allow_create=False,
        sync_status=True,
        dry_run=True,
        call=api,
        task_status=lambda *_: "blocked",
    )
    assert result["status_updates"] == [{"linear": "BRA-1", "status": "Needs Approval"}]
