"""Every Python sample in README.md must actually run.

The README is the first thing a customer copies. A sample that raises is worse
than no sample: it burns the first ten minutes of an evaluation and it is the
kind of rot nothing else in the suite would notice, because docs are not
imported by anything.

Samples are extracted from the fenced ```python blocks and executed against the
in-process fake, with `client` / `c` pre-bound. Blocks that are illustrative
rather than runnable (a bare `>>>` transcript showing an intended error, a
snippet with `...` placeholders, a `while` loop that would never return) are
skipped by the markers listed in `_SKIP_MARKERS` — each with a reason, so the
skip list cannot quietly grow to cover a genuinely broken sample.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from voltnir_sdk import VoltnirClient

_README = Path(__file__).resolve().parent.parent / "README.md"

# Substrings that mark a block as illustrative rather than executable, each with
# the reason it cannot simply be run.
_SKIP_MARKERS = {
    ">>>": "a transcript demonstrating an intended failure, not a runnable block",
    "while not shutting_down": "an infinite resubscribe loop with app-level names",
    "apply_delta": "pseudocode for consumer-side state handling",
    "asyncio.run(main())": "runs its own event loop; covered by the async tests",
    "...": "contains an ellipsis placeholder that is not valid in context",
}


def _python_blocks(markdown: str) -> list[tuple[int, str]]:
    """Return (line_number, source) for each fenced ```python block."""
    blocks = []
    for match in re.finditer(r"```python\n(.*?)```", markdown, re.S):
        line_no = markdown[: match.start()].count("\n") + 1
        blocks.append((line_no, match.group(1)))
    return blocks


_BLOCKS = _python_blocks(_README.read_text(encoding="utf-8"))


def _runnable() -> list[tuple[int, str]]:
    out = []
    for line_no, src in _BLOCKS:
        if any(marker in src for marker in _SKIP_MARKERS):
            continue
        out.append((line_no, src))
    return out


_RUNNABLE = _runnable()


def test_happy_readme_has_python_samples_to_check():
    """Guard against the extractor silently matching nothing.

    If the README's fence style ever changes, every sample test would vacuously
    pass. Pin that we found a meaningful number of both total and runnable
    blocks.
    """
    assert len(_BLOCKS) >= 10, f"only found {len(_BLOCKS)} python blocks"
    assert len(_RUNNABLE) >= 3, f"only {len(_RUNNABLE)} runnable blocks"


@pytest.fixture
def readme_env(server, client, monkeypatch):
    """Namespace for executing a sample, with construction redirected to the fake.

    Several samples build their own client (`with VoltnirClient(host="localhost",
    port=3443, ...)`), which is the shape a reader copies and therefore the
    shape most worth verifying. Rather than skipping them, `VoltnirClient` is
    patched on the package so those constructor calls land on the in-process
    fake: connection arguments are dropped, everything else (notably `options=`)
    is passed through so the sample's real content is still exercised.

    Patched on the module, not just seeded into the namespace, because the
    samples do `from voltnir_sdk import VoltnirClient` and that import would
    otherwise rebind the name straight back to the real class.
    """
    import voltnir_sdk

    def _redirected(*args, **kwargs):
        for connection_arg in ("host", "port", "tls", "ca_cert_path"):
            kwargs.pop(connection_arg, None)
        kwargs.setdefault("api_key", "test-key")
        kwargs.setdefault("timeout", 5.0)
        return VoltnirClient(host="127.0.0.1", port=server, **kwargs)

    monkeypatch.setattr(voltnir_sdk, "VoltnirClient", _redirected)
    return {"client": client, "c": client}


@pytest.mark.parametrize(
    "line_no,source", _RUNNABLE, ids=[f"L{n}" for n, _ in _RUNNABLE]
)
def test_happy_readme_sample_executes(readme_env, fake, line_no, source):
    """Happy: the sample runs against a real gRPC channel without raising."""
    try:
        exec(compile(source, f"README.md:{line_no}", "exec"), readme_env)
    except Exception as exc:  # noqa: BLE001 - the point is to surface anything
        pytest.fail(
            f"README.md sample at line {line_no} raised "
            f"{type(exc).__name__}: {exc}\n\n{source}"
        )


def test_edge_api_key_placeholder_is_ascii():
    """Edge: the placeholder must survive a verbatim copy-paste.

    A non-ASCII ellipsis in `api_key="..."` is not valid gRPC metadata, so a
    copied quickstart failed with `INTERNAL: Invalid metadata` before the user
    had done anything wrong. On the async path it escaped translation entirely
    as a raw ExecuteBatchError.
    """
    text = _README.read_text(encoding="utf-8")
    for match in re.finditer(r'api_key="([^"]*)"', text):
        value = match.group(1)
        assert value.isascii(), (
            f"non-ASCII api_key placeholder {value!r} in README: a verbatim "
            f"copy-paste fails with 'Invalid metadata'"
        )


def test_edge_readme_documents_the_unit_suffixed_arguments():
    """Edge: the units section must name the real parameters.

    The single most dangerous call in the SDK went undocumented in the README
    for its whole 1.x life: `submit_order` was mentioned zero times and the
    words "cent" and "MWh" did not appear. If that regresses, the 100x price
    hazard is undocumented again.
    """
    text = _README.read_text(encoding="utf-8")
    # Sending side: the parameters and their units.
    for token in ("price_cents", "quantity_sub_mw", "submit_order"):
        assert token in text, f"README no longer documents {token}"

    # Reading side: all four scales and their helpers must be documented, since
    # a misread costs exactly as much as a mis-send and nothing in the returned
    # integer says which scale produced it.
    for token in (
        "price_to_cents",
        "sub_mw_to_quantity",
        "eur_to_cents",
        "q8_to_eur",
        "realized_pnl",
        "100 000",          # the P&L scale, spelled out
    ):
        assert token in text, f"README no longer documents {token}"

    assert "OrderOutcomeUnknown" in text


def test_fail_no_sample_generates_an_order_id_it_then_modifies():
    """A sample can execute perfectly and still teach a losing habit.

    The modify example once opened with `order_id = new_client_order_id()`
    followed by `modify_order(client_order_id=order_id, ...)`. That runs, and a
    runner checking only that samples execute passes it -- but a freshly
    generated UUID is by definition NOT "the id you submitted with", so the
    sample modifies an order that does not exist. Executability is not
    correctness, and for trading docs the gap between them costs money.
    """
    text = _README.read_text(encoding="utf-8")

    for line_no, src in _BLOCKS:
        if "modify_order(" not in src:
            continue
        # Generating an id is fine WHEN the same block submits with it first,
        # which is the shape that actually teaches the rule. Generating one and
        # going straight to modify is the error.
        if "new_client_order_id()" in src and "submit_order(" not in src:
            raise AssertionError(
                f"README.md sample at line {line_no} generates a fresh "
                f"client_order_id and then modifies it without submitting. A "
                f"new id targets no existing order; reuse the id you submitted "
                f"with."
            )


def test_edge_readme_names_the_distribution_and_import_names():
    """A reader must be able to pin this in requirements.txt from the README.

    Three names are in play -- the distribution, the import, and the repo --
    and the distribution name appeared nowhere in the document.
    """
    text = _README.read_text(encoding="utf-8")
    assert "voltnir-grpc-py-sdk" in text, "the distribution name is not in the README"
    assert "voltnir_sdk" in text


def test_edge_skip_markers_all_still_match_something():
    """Edge: a skip marker that matches nothing is dead weight hiding intent.

    If a sample is rewritten so its marker no longer applies, the entry should
    be removed rather than left implying a block is unrunnable.
    """
    all_source = "\n".join(src for _, src in _BLOCKS)
    unused = [m for m in _SKIP_MARKERS if m not in all_source]
    assert not unused, f"skip markers matching no README block: {unused}"
