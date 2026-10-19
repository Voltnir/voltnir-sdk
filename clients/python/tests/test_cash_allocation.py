"""The cash-allocation shape a client reads back off the wire.

A virtual member's cash limit is its **allocation** out of the desk's limit, not
an override of it: per currency the allocations of all members sum to at most
the desk's limit, so a member can only ever spend its own slice. Two things make
that visible to a client, and both are asserted here:

    Member.cash_limit == Member.eur_limit_cents    the allocation IS the limit
    CashPool.unallocated_cents                     what the House account has left

Neither is a display extra. A client that reads `eur_limit_cents` and finds the
desk's limit rather than the member's would size an order against headroom the
member does not have; one that cannot see `unallocated_cents` cannot tell
whether an untagged order will be admitted at all.
"""

from __future__ import annotations

from voltnir_sdk._generated import voltnir_api_v1_pb2 as pb2


def test_happy_a_members_allocation_is_its_enforced_limit() -> None:
    # The two fields carry the same number by construction: there is no
    # inheritance from the desk and no clamping to it.
    m = pb2.Member(
        short_id="VM001",
        cash_limit=500_000,
        cash_limit_gbp=250_000,
        eur_limit_cents=500_000,
        eur_consumed_cents=200_000,
        eur_remaining_cents=300_000,
        gbp_limit_cents=250_000,
    )
    assert m.eur_limit_cents == m.cash_limit
    assert m.gbp_limit_cents == m.cash_limit_gbp
    assert m.eur_remaining_cents == m.eur_limit_cents - m.eur_consumed_cents


def test_fail_no_allocation_reads_as_a_hard_zero() -> None:
    # `0` is no allocation, not "unset, inherit the desk's limit". A member
    # left at zero cannot add exposure, and any consumption it still carries
    # reads as negative remaining rather than being clamped away.
    m = pb2.Member(
        short_id="VM002",
        cash_limit=0,
        eur_limit_cents=0,
        eur_consumed_cents=50_000,
        eur_remaining_cents=-50_000,
    )
    assert m.eur_limit_cents == 0
    assert m.eur_remaining_cents < 0


def test_happy_cash_pool_reports_the_allocation_split() -> None:
    pool = pb2.CashPool(
        house_cents=1_000_000,
        allocated_cents=750_000,
        unallocated_cents=250_000,
        over_allocated=False,
    )
    assert pool.unallocated_cents == pool.house_cents - pool.allocated_cents
    assert not pool.over_allocated


def test_edge_an_over_allocated_pool_carries_a_negative_remainder() -> None:
    # Reachable only from the exchange side: the desk's limit was lowered under
    # allocations already granted. The allocations stand, so the remainder goes
    # negative and the House account can add nothing until the desk rebalances.
    pool = pb2.CashPool(
        house_cents=600_000,
        allocated_cents=1_000_000,
        unallocated_cents=-400_000,
        over_allocated=True,
    )
    assert pool.unallocated_cents < 0
    assert pool.over_allocated


def test_edge_the_two_pools_are_independent() -> None:
    # EUR fully allocated says nothing about GBP: the exchange settles the two
    # separately and they never net against each other.
    resp = pb2.CashLimitResponse(
        eur=pb2.CashPool(
            house_cents=1_000_000, allocated_cents=1_000_000, unallocated_cents=0
        ),
        gbp=pb2.CashPool(
            house_cents=500_000, allocated_cents=0, unallocated_cents=500_000
        ),
    )
    assert resp.eur.unallocated_cents == 0
    assert resp.gbp.unallocated_cents == resp.gbp.house_cents
