"""Operator toggles: the bank-holiday calendars, the trading kill switch, and
the self-trade policy. Every test restores the value it changed, and the
holiday tests use a far-future sentinel date that touches no real calendar."""

from __future__ import annotations

import pytest

from voltnir_sdk import (
    OrderValidationError,
    PermissionDenied,
    SelfTradePolicy,
    Unauthenticated,
)

_SENTINEL = "2099-07-01"

_POLICY_NAME = {
    SelfTradePolicy.SELF_TRADE_POLICY_REJECT: "reject",
    SelfTradePolicy.SELF_TRADE_POLICY_OBSERVE: "observe",
}


# ── GetHolidays (authenticated) ─────────────────────────────────────────────


@pytest.mark.rpc("GetHolidays")
def test_happy_get_holidays(admin):
    resp = admin.get_holidays()
    assert isinstance(len(resp.eur), int)
    assert isinstance(len(resp.gbp), int)


@pytest.mark.rpc("GetHolidays")
def test_fail_get_holidays_unauthenticated(badkey):
    with pytest.raises(Unauthenticated):
        badkey.get_holidays()


@pytest.mark.rpc("GetHolidays")
def test_edge_get_holidays_dates_are_iso(admin):
    for h in list(admin.get_holidays().eur)[:5]:
        assert len(h.date) == 10 and h.date[4] == "-"


# ── AddHoliday (gated) ──────────────────────────────────────────────────────


@pytest.mark.rpc("AddHoliday")
def test_happy_add_holiday(admin):
    try:
        resp = admin.add_holiday(currency="eur", date=_SENTINEL, label="sdk-it")
        assert _SENTINEL in [h.date for h in resp.eur]
    finally:
        admin.remove_holiday(currency="eur", date=_SENTINEL)


@pytest.mark.rpc("AddHoliday")
def test_fail_add_holiday_denied(lowperm):
    with pytest.raises(PermissionDenied):
        lowperm.add_holiday(currency="eur", date=_SENTINEL, label="x")


@pytest.mark.rpc("AddHoliday")
def test_edge_add_holiday_keeps_its_label(admin):
    try:
        resp = admin.add_holiday(currency="eur", date=_SENTINEL, label="labelled")
        match = [h for h in resp.eur if h.date == _SENTINEL]
        assert match and match[0].label == "labelled"
    finally:
        admin.remove_holiday(currency="eur", date=_SENTINEL)


# ── RemoveHoliday (gated) ───────────────────────────────────────────────────


@pytest.mark.rpc("RemoveHoliday")
def test_happy_remove_holiday(admin):
    admin.add_holiday(currency="eur", date=_SENTINEL, label="sdk-it")
    resp = admin.remove_holiday(currency="eur", date=_SENTINEL)
    assert _SENTINEL not in [h.date for h in resp.eur]


@pytest.mark.rpc("RemoveHoliday")
def test_fail_remove_holiday_denied(lowperm):
    with pytest.raises(PermissionDenied):
        lowperm.remove_holiday(currency="eur", date=_SENTINEL)


@pytest.mark.rpc("RemoveHoliday")
def test_edge_remove_absent_holiday_leaves_it_absent(admin):
    # Removing a date that is not on the calendar either no-ops or is refused;
    # either way the date is not on the calendar and nothing else is disturbed.
    from voltnir_sdk import VoltnirError

    try:
        resp = admin.remove_holiday(currency="eur", date="2099-12-31")
        assert "2099-12-31" not in [h.date for h in resp.eur]
    except VoltnirError as e:
        assert e.rpc == "RemoveHoliday"


# ── SetHolidays (gated) ─────────────────────────────────────────────────────


@pytest.mark.rpc("SetHolidays")
def test_happy_set_holidays_writes_back_the_current_calendar(admin):
    current = list(admin.get_holidays().eur)
    resp = admin.set_holidays(currency="eur", holidays=current)
    assert len(resp.eur) == len(current)


@pytest.mark.rpc("SetHolidays")
def test_fail_set_holidays_denied(lowperm):
    with pytest.raises(PermissionDenied):
        lowperm.set_holidays(currency="eur", holidays=[])


@pytest.mark.rpc("SetHolidays")
def test_edge_set_holidays_replaces_wholesale(admin):
    # set_holidays is a full replacement: adding a sentinel to the current set
    # and writing it makes the sentinel present; restoring the original set
    # removes it again.
    original = list(admin.get_holidays().eur)
    from voltnir_sdk._generated import voltnir_api_v1_pb2 as pb2

    try:
        extended = original + [pb2.Holiday(date=_SENTINEL, label="sdk-it")]
        resp = admin.set_holidays(currency="eur", holidays=extended)
        assert _SENTINEL in [h.date for h in resp.eur]
    finally:
        admin.set_holidays(currency="eur", holidays=original)


# ── SetTradingAllowed (gated) ───────────────────────────────────────────────


@pytest.mark.rpc("SetTradingAllowed")
def test_happy_set_trading_allowed_toggles_and_restores(admin):
    prior = admin.get_trading_allowed().allowed
    try:
        resp = admin.set_trading_allowed(allowed=not prior)
        assert resp.allowed == (not prior)
    finally:
        admin.set_trading_allowed(allowed=prior)


@pytest.mark.rpc("SetTradingAllowed")
def test_fail_set_trading_allowed_denied(lowperm):
    with pytest.raises(PermissionDenied):
        lowperm.set_trading_allowed(allowed=True)


@pytest.mark.rpc("SetTradingAllowed")
def test_edge_set_trading_allowed_to_current_is_idempotent(admin):
    current = admin.get_trading_allowed().allowed
    assert admin.set_trading_allowed(allowed=current).allowed == current


# ── SetSelfTradePolicy (gated) ──────────────────────────────────────────────


@pytest.mark.rpc("SetSelfTradePolicy")
def test_happy_set_self_trade_policy_round_trips(admin):
    prior = admin.get_self_trade_policy().policy
    try:
        admin.set_self_trade_policy(policy="reject")
        assert (
            admin.get_self_trade_policy().policy
            == SelfTradePolicy.SELF_TRADE_POLICY_REJECT
        )
    finally:
        admin.set_self_trade_policy(policy=_POLICY_NAME.get(prior, "observe"))


@pytest.mark.rpc("SetSelfTradePolicy")
def test_fail_set_self_trade_policy_denied(lowperm):
    with pytest.raises(PermissionDenied):
        lowperm.set_self_trade_policy(policy="observe")


@pytest.mark.rpc("SetSelfTradePolicy")
def test_edge_set_self_trade_policy_rejects_an_unknown_string(admin):
    # The wrapper validates the policy locally, so a bad value never reaches the
    # gateway.
    with pytest.raises(OrderValidationError):
        admin.set_self_trade_policy(policy="sometimes")