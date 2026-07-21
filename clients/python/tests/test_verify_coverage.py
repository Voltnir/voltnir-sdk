"""Guards on `verify.py`, the live-server runner, that work without a server.

Its subject is a single file rather than a single technique, so there are two
kinds of check here:

1. **Static** (the majority): parse `verify.py` as source and assert it has a
   call site for every RPC the proto declares. Builds nothing, connects to
   nothing.
2. **Executable** (one test): actually run the runner against the in-process
   fake from `conftest.py` and assert no step blew up on a wrong keyword
   argument or a wrong response field name.

Why any of this exists: `verify.py` is hand-written and linear, so unlike the
descriptor-driven suite in `test_rpcs.py` it cannot notice a new RPC on its
own. Without these, an RPC could be added to the proto and wrapped in the SDK
while the live-server runner silently never exercised it.

The static checks assert the weakest useful property on purpose. "There is a
call site" is not "the step is correct" -- only a live run proves that -- but
it is cheap, has no false positives, and catches the failure that matters.
"""

from __future__ import annotations

import ast
import concurrent.futures
import re
import sys
from pathlib import Path

import grpc
import pytest

from voltnir_sdk._generated import voltnir_api_v1_pb2 as pb2
from voltnir_sdk._generated import voltnir_api_v1_pb2_grpc as pb2_grpc

from conftest import FakeVoltAPI

_VERIFY = Path(__file__).resolve().parent.parent / "verify.py"
_SVC = pb2.DESCRIPTOR.services_by_name["VoltAPI"]


def _snake(name: str) -> str:
    """PascalCase RPC name -> the SDK's snake_case wrapper name.

    Intentionally duplicated from `test_rpcs.py` rather than imported: these are
    separate modules by design and a cross-test import would couple them for
    three lines.
    """
    s = re.sub(r"(?<!^)(?=[A-Z0-9])", "_", name).lower()
    return s.replace("m_7", "m7").replace("hub_2_hub", "hub2hub").replace("a_p_i", "api")


def _attributes_accessed(source: str) -> set[str]:
    """Every attribute name accessed anywhere in the file.

    Deliberately ignores *what* it was accessed on. `verify.py` reaches the
    wrappers through several receivers (`client`, `aclient`, `c`, and locals
    inside nested smoke closures), so pinning the receiver would make this
    guard brittle in exchange for precision it does not need: no non-wrapper
    attribute in this file collides with an RPC wrapper name.
    """
    return {
        node.attr
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Attribute)
    }


def test_happy_verify_has_a_call_site_for_every_rpc() -> None:
    """Happy: all 63 wrappers are referenced somewhere in verify.py."""
    accessed = _attributes_accessed(_VERIFY.read_text(encoding="utf-8"))

    expected = {_snake(m.name): m.name for m in _SVC.methods}
    missing = sorted(
        rpc for wrapper, rpc in expected.items() if wrapper not in accessed
    )

    assert not missing, (
        f"verify.py has no call site for {len(missing)} RPC(s): {missing}. "
        "Every RPC in the proto needs a step in the live-server runner; add "
        "one (and a [SKIP] path if it is permission-gated or mutating)."
    )


def test_edge_every_rpc_maps_to_a_real_wrapper_name() -> None:
    """Edge: the PascalCase -> snake_case mapping is itself correct.

    If `_snake` were wrong, the happy test above could pass or fail for the
    wrong reason. Pin it against the actual client, which is the definition of
    a correct wrapper name.
    """
    from voltnir_sdk import VoltnirClient

    bad = [
        m.name for m in _SVC.methods if not callable(getattr(VoltnirClient, _snake(m.name), None))
    ]
    assert not bad, f"_snake produced a name that is not a client method: {bad}"


def test_fail_detector_reports_a_wrapper_with_no_call_site() -> None:
    """Fail: the detector must actually fire on an absent call site.

    Without this, a bug in `_attributes_accessed` (returning everything, or
    parsing the wrong file) would make the happy test vacuously green.
    """
    accessed = _attributes_accessed("client.get_me()\nclient.get_state()\n")

    assert "get_me" in accessed
    assert "get_state" in accessed
    assert "watch_pnl" not in accessed


def test_edge_parsed_the_real_runner_not_an_empty_path() -> None:
    """Edge: prove the scan read a substantial real file.

    A moved or renamed `verify.py` would otherwise surface as a confusing
    "every RPC is missing" failure, or worse, an empty set that trivially
    satisfies nothing.
    """
    assert _VERIFY.is_file(), f"{_VERIFY} missing; the guard would scan nothing"

    source = _VERIFY.read_text(encoding="utf-8")
    assert len(source) > 10_000, "verify.py unexpectedly small"
    assert len(_attributes_accessed(source)) > 50


# ── executable guard: the runner actually runs ──────────────────────────────


def _import_verify():
    """Import `verify.py` as a module (it lives beside the package, not in it)."""
    sdk_root = _VERIFY.parent
    if str(sdk_root) not in sys.path:
        sys.path.insert(0, str(sdk_root))
    import verify  # noqa: PLC0415

    return verify


def test_happy_runner_executes_every_step_without_blowing_up(monkeypatch, capsys):
    """Happy: a full --mutate run against the fake raises nothing per-step.

    The fake has no semantics, so PASS/FAIL counts here are meaningless and are
    deliberately NOT asserted on: a step can legitimately report FAIL because
    the fake returned an empty message. What this pins is the failure mode that
    writing live-server code without a live server actually produces, and which
    the static guard above cannot see: a typo'd keyword argument or a response
    field that does not exist. Those surface as TypeError / AttributeError /
    NameError / ValueError, and `step()` catches them into `Result.failures`, so
    they would otherwise be silently absorbed into a FAIL count nobody reads.

    ValueError is in that list for a specific reason: protobuf raises it, not
    TypeError, for an unknown field name (`Protocol message X has no "quantiy"
    field`). Omitting it would let a misnamed keyword in any `**kwargs` call
    site pass silently.
    """
    verify = _import_verify()

    fake = FakeVoltAPI()
    srv = grpc.server(concurrent.futures.ThreadPoolExecutor(max_workers=8))
    pb2_grpc.add_VoltAPIServicer_to_server(fake, srv)
    port = srv.add_insecure_port("127.0.0.1:0")
    srv.start()

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "verify.py",
            "--host", "127.0.0.1",
            "--port", str(port),
            "--api-key", "fake-key",
            "--area", "10YBE----------2",
            "--mutate",
            "--timeout", "5",
        ],
    )

    try:
        verify.main()
    finally:
        srv.stop(None)

    out = capsys.readouterr().out

    # The interpreter-level errors that mean a step is simply wrong code.
    for marker in (
        "TypeError",
        "AttributeError",
        "NameError",
        "ValueError",
        "UnitConversionError",
        "Traceback",
    ):
        assert marker not in out, (
            f"a verify.py step raised {marker} against the fake server, which "
            f"means the step itself is broken, not the server:\n{out}"
        )


def test_edge_runner_reports_its_rpc_coverage(monkeypatch, capsys):
    """Edge: the run ends with a coverage line naming what it never attempted.

    This is the runtime half of the drift defence. It is informational rather
    than pass/fail (a partial run legitimately misses RPCs), so nothing else
    would notice if it silently stopped being printed.
    """
    verify = _import_verify()

    fake = FakeVoltAPI()
    srv = grpc.server(concurrent.futures.ThreadPoolExecutor(max_workers=8))
    pb2_grpc.add_VoltAPIServicer_to_server(fake, srv)
    port = srv.add_insecure_port("127.0.0.1:0")
    srv.start()

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "verify.py",
            "--host", "127.0.0.1",
            "--port", str(port),
            "--api-key", "fake-key",
            "--area", "10YBE----------2",
            "--timeout", "5",
        ],
    )

    try:
        verify.main()
    finally:
        srv.stop(None)

    out = capsys.readouterr().out
    total = len(_SVC.methods)

    assert f"/{total} RPCs" in out, f"no coverage line in output:\n{out}"
    # A read-only run cannot reach the write surface, so the "not attempted"
    # list must be present and must name something. If this ever goes empty on
    # a read-only run, the recorder is over-reporting.
    assert "not attempted" in out


def test_fail_recorder_counts_an_rpc_as_attempted_even_when_denied():
    """Fail: a PERMISSION_DENIED still counts toward coverage.

    The recorder answers "does this runner have a step for every RPC", not "did
    the key hold every permission". If a denied call did not count, a run with
    a read-only key would report false drift and train the reader to ignore the
    coverage line.
    """
    verify = _import_verify()

    fake = FakeVoltAPI()
    fake.abort_code = grpc.StatusCode.PERMISSION_DENIED
    srv = grpc.server(concurrent.futures.ThreadPoolExecutor(max_workers=4))
    pb2_grpc.add_VoltAPIServicer_to_server(fake, srv)
    port = srv.add_insecure_port("127.0.0.1:0")
    srv.start()

    from voltnir_sdk import PermissionDenied, VoltnirClient

    recorder = verify._CallRecorder()
    recorder.install(VoltnirClient)
    try:
        with VoltnirClient(host="127.0.0.1", port=port, api_key="k", timeout=5.0) as c:
            with pytest.raises(PermissionDenied):
                c.get_status()
    finally:
        recorder.uninstall()
        srv.stop(None)

    assert "GetStatus" in recorder.attempted


def test_edge_recorder_uninstall_restores_the_original_methods():
    """Edge: instrumentation must not leak into the rest of the process.

    The recorder patches class attributes on the shared client classes, so a
    missed uninstall would silently instrument every later test in the session.
    """
    verify = _import_verify()

    from voltnir_sdk import AsyncVoltnirClient, VoltnirClient

    before = (VoltnirClient._unary, VoltnirClient._stream,
              AsyncVoltnirClient._unary, AsyncVoltnirClient._stream)

    recorder = verify._CallRecorder()
    recorder.install(VoltnirClient, AsyncVoltnirClient)
    assert VoltnirClient._unary is not before[0], "install did not patch"
    recorder.uninstall()

    after = (VoltnirClient._unary, VoltnirClient._stream,
             AsyncVoltnirClient._unary, AsyncVoltnirClient._stream)
    assert before == after


# ── the reconciliation pass: exercised offline against a slow server ────────
#
# verify.py's reconciliation pass only does anything interesting when a submit
# actually times out, which never happens against a fast in-process fake: it
# reports [SKIP] and proves nothing. These drive it against a deliberately slow
# fake so the ambiguous-failure branches execute, offline and on every run.
#
# This is the highest-consequence path in the SDK and the one a fake normally
# cannot reach, so it is worth the setup.


class _SlowFake(FakeVoltAPI):
    """SubmitOrder outlives the probe deadline; the order still lands.

    That is precisely the ambiguous state a real gateway produces on a slow
    link: the client gave up, but the order exists. `seen` tracks
    client_order_ids so a reused one can be rejected the way the gateway does.
    """

    def __init__(self) -> None:
        super().__init__()
        self.seen: set[str] = set()
        self.submit_delay = 0.5

    def SubmitOrder(self, request, context):
        import time as _t

        _t.sleep(self.submit_delay)
        self._record("SubmitOrder", request, context)
        if request.client_order_id in self.seen and self.reject_duplicates:
            context.abort(
                grpc.StatusCode.ABORTED, "client_order_id already in use"
            )
        self.seen.add(request.client_order_id)
        return pb2.SubmitOrderResponse(client_order_id=request.client_order_id)

    reject_duplicates = True

    def GetOrder(self, request, context):
        self._record("GetOrder", request, context)
        if request.client_order_id not in self.seen:
            context.abort(grpc.StatusCode.NOT_FOUND, "no such order")
        return pb2.GetOrderResponse(
            confirmed=pb2.OwnOrder(
                client_order_id=request.client_order_id,
                order_id=987654,
                contract_id=12345,
                delivery_area="10YBE----------2",
                side=pb2.Side.BUY,
                price=100,
                quantity=100,
            )
        )


def _run_reconciliation(fake):
    """Run verify.py's reconciliation pass against `fake`, return its Result."""
    verify = _import_verify()
    from voltnir_sdk import VoltnirClient

    srv = grpc.server(concurrent.futures.ThreadPoolExecutor(max_workers=16))
    pb2_grpc.add_VoltAPIServicer_to_server(fake, srv)
    port = srv.add_insecure_port("127.0.0.1:0")
    srv.start()
    try:
        c = VoltnirClient(host="127.0.0.1", port=port, api_key="k", timeout=5.0)
        try:
            return verify.run_sync_reconciliation(c, "10YBE----------2")
        finally:
            c.close()
    finally:
        srv.stop(None)


def test_happy_reconciliation_pass_resolves_an_ambiguous_failure(capsys):
    """Happy: timeout -> OrderOutcomeUnknown -> definitive answer -> cleanup.

    Against a gateway that behaves correctly (slow submit, order lands, reused
    key refused) every probe must pass and nothing may be left resting.
    """
    result = _run_reconciliation(_SlowFake())
    out = capsys.readouterr().out

    assert result.failed == 0, f"unexpected failures: {result.failures}\n{out}"
    assert "OrderOutcomeUnknown as expected" in out
    assert "definitive: order IS live" in out
    assert "correctly refused" in out
    assert "cancelled probe order" in out


def test_fail_reconciliation_pass_catches_a_lost_idempotency_guarantee(capsys):
    """Fail: if a reused client_order_id is ACCEPTED, the pass must fail loudly.

    That guarantee is the entire reason the SDK tells a desk it may retry after
    an ambiguous failure. A gateway that did not honour it would let a retry
    double the position, and this is the only check that would notice.
    """
    fake = _SlowFake()
    fake.reject_duplicates = False

    result = _run_reconciliation(fake)

    assert result.failed >= 1
    assert any("idempotency guarantee" in f for f in result.failures), result.failures


def test_fail_reconciliation_pass_catches_a_misclassified_timeout(capsys, monkeypatch):
    """Fail: a deadline surfacing as DeadlineExceeded must fail the pass.

    This is the misclassification the whole pass exists to detect: a desk
    reading "deadline exceeded" as "definitely failed" resubmits and doubles up.
    Simulated by disabling the order-mutating classification.
    """
    import voltnir_sdk.errors as errors

    monkeypatch.setattr(errors, "UNCERTAIN_CODES", frozenset())

    result = _run_reconciliation(_SlowFake())

    assert result.failed >= 1
    assert any("DeadlineExceeded" in f for f in result.failures), result.failures


def test_edge_reconciliation_pass_skips_when_the_server_answers_in_time(capsys):
    """Edge: a fast server means the ambiguity was never exercised.

    That must read as [SKIP] with the reason, not as a pass. A pass here would
    be the most misleading possible result: the run looks green while the path
    it exists to test never executed.
    """
    fake = _SlowFake()
    fake.submit_delay = 0.0

    result = _run_reconciliation(fake)
    out = capsys.readouterr().out

    assert result.failed == 0
    assert "ambiguity not exercised" in out
    assert result.skipped >= 2
