"""Static checks on every log_event call in the application.

Both conventions this enforces are the kind a reviewer notices four times out of
five, which is not good enough for a table that holds email addresses and IP
addresses. Turning them into a red build costs about fifty lines.

This reads the source rather than the running app on purpose: a call site on a path
no test happens to exercise is exactly the one that will get it wrong.
"""

import ast
from pathlib import Path

from app.utils import activity_events
from app.utils.activity_events import CONTEXT_KEY_EXEMPTIONS, EVENT_TYPES
from app.utils.activity_log import DENIED_KEY_TOKENS, _key_tokens

APP_ROOT = Path(__file__).resolve().parents[2] / "app"


def _log_event_calls():
    """Yield (path, call node) for every log_event(...) call under app/."""
    for source_path in sorted(APP_ROOT.rglob("*.py")):
        tree = ast.parse(source_path.read_text(), filename=str(source_path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            callee = node.func
            name = callee.attr if isinstance(callee, ast.Attribute) else getattr(callee, "id", None)
            if name == "log_event":
                yield source_path, node


def _event_constant_name(call):
    """Return the constant name from `activity_events.NAME`, or None."""
    if not call.args:
        return None

    first_argument = call.args[0]
    if (
        isinstance(first_argument, ast.Attribute)
        and isinstance(first_argument.value, ast.Name)
        and first_argument.value.id == "activity_events"
    ):
        return first_argument.attr

    return None


def _literal_context_keys(call):
    """Return the keys of a literal `context={...}` argument, or None if not literal."""
    for keyword in call.keywords:
        if keyword.arg != "context":
            continue
        if not isinstance(keyword.value, ast.Dict):
            return None
        return [key.value for key in keyword.value.keys if isinstance(key, ast.Constant)]

    return []


def test_the_scan_finds_the_call_sites():
    """Guard against the walk silently matching nothing and passing every test."""
    assert len(list(_log_event_calls())) >= 9


def test_every_call_site_names_an_event_constant():
    offenders = []
    for source_path, call in _log_event_calls():
        constant_name = _event_constant_name(call)
        if constant_name is None:
            offenders.append(f"{source_path.name}:{call.lineno} does not pass activity_events.*")
        elif not hasattr(activity_events, constant_name):
            offenders.append(f"{source_path.name}:{call.lineno} uses unknown {constant_name}")

    assert not offenders, "\n".join(offenders)


def test_every_declared_event_constant_is_registered():
    for name in dir(activity_events):
        if not name.startswith("AUTH_"):
            continue
        assert getattr(activity_events, name) in EVENT_TYPES, f"{name} is missing from EVENT_TYPES"


def test_literal_context_keys_pass_the_denylist():
    offenders = []
    for source_path, call in _log_event_calls():
        keys = _literal_context_keys(call)
        if not keys:
            continue

        constant_name = _event_constant_name(call)
        event_type = getattr(activity_events, constant_name, None) if constant_name else None
        exempt = CONTEXT_KEY_EXEMPTIONS.get(event_type, frozenset())

        for key in keys:
            if key in exempt:
                continue
            if DENIED_KEY_TOKENS.intersection(_key_tokens(key)):
                offenders.append(f"{source_path.name}:{call.lineno} context key {key!r}")

    assert not offenders, (
        "These context keys would be silently dropped at runtime. Either rename them "
        "or, if the value really has to be recorded, add a per-event entry to "
        "CONTEXT_KEY_EXEMPTIONS and say why in the pull request:\n" + "\n".join(offenders)
    )
