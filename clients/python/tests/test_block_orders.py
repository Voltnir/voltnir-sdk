"""User-defined block orders: the request a block create builds, and the
block rules checked before dispatch, each named by the gateway's own code."""

from __future__ import annotations

import pytest

from voltnir_sdk import OrderValidationError
from voltnir_sdk._generated import voltnir_api_v1_pb2 as pb2
from voltnir_sdk._orders import build_submit_order_request

_OID = "11111111-1111-4111-8111-111111111111"
_AREA = "10YDE-EON------1"
_START = "2026-10-05T10:00:00Z"
_END = "2026-10-05T13:00:00Z"


def _block(**overrides):
    base = dict(
        client_order_id=_OID,
        side=pb2.Side.BUY,
        delivery_area_id=_AREA,
        price_cents=5000,
        quantity_sub_mw=1000,
        product="Intraday_Hour_Power",
        delivery_start=_START,
        delivery_end=_END,
        order_type=pb2.OrderType.BLOCK,
        exe_restriction=pb2.ExeRestriction.AON,
    )
    base.update(overrides)
    return build_submit_order_request(**base)


def test_happy_a_block_create_names_its_window_and_no_contract():
    req = _block()
    assert req.delivery_end == _END
    assert req.delivery_start == _START
    assert req.contract_id == 0
    assert req.order_type == pb2.OrderType.BLOCK
    assert req.exe_restriction == pb2.ExeRestriction.AON


def test_happy_a_fok_block_create_with_validity_non():
    req = _block(
        exe_restriction=pb2.ExeRestriction.FOK,
        validity_res=pb2.ValidityRes.VALIDITY_NON,
    )
    assert req.exe_restriction == pb2.ExeRestriction.FOK


@pytest.mark.parametrize(
    "overrides",
    [
        {"order_type": pb2.OrderType.REGULAR, "exe_restriction": pb2.ExeRestriction.NON},
        {"contract_id": 42},
        {"product": ""},
        {"delivery_start": "", "contract_id": 42},
    ],
)
def test_fail_delivery_end_outside_a_block_create(overrides):
    with pytest.raises(OrderValidationError, match="^BLOCK_DELIVERY_END_INVALID: "):
        _block(**overrides)


def test_fail_a_block_with_non_is_refused_on_a_create_and_a_join():
    with pytest.raises(OrderValidationError, match="^BLOCK_RESTRICTION_NON: "):
        _block(exe_restriction=pb2.ExeRestriction.NON)
    with pytest.raises(OrderValidationError, match="^BLOCK_RESTRICTION_NON: "):
        _block(
            delivery_end="",
            contract_id=42,
            exe_restriction=pb2.ExeRestriction.NON,
        )


def test_fail_a_block_with_ioc_is_a_sweep_and_is_refused():
    with pytest.raises(OrderValidationError, match="^BLOCK_SWEEP_UNSUPPORTED: "):
        _block(
            exe_restriction=pb2.ExeRestriction.IOC,
            validity_res=pb2.ValidityRes.VALIDITY_NON,
        )


def test_edge_joining_a_block_by_contract_id_needs_no_window():
    req = _block(delivery_end="", product="", delivery_start="", contract_id=42)
    assert req.contract_id == 42
    assert req.delivery_end == ""


def test_edge_a_regular_order_without_delivery_end_is_unaffected():
    req = _block(
        delivery_end="",
        product="",
        delivery_start="",
        contract_id=7,
        order_type=pb2.OrderType.REGULAR,
        exe_restriction=pb2.ExeRestriction.NON,
    )
    assert req.order_type == pb2.OrderType.REGULAR


def test_fail_the_restriction_is_named_before_a_misplaced_delivery_end():
    """A block with NON, a window and a contract_id breaks two rules; the
    restriction is named first, as the gateway names it."""
    with pytest.raises(OrderValidationError, match="^BLOCK_RESTRICTION_NON: "):
        _block(exe_restriction=pb2.ExeRestriction.NON, contract_id=5)


def test_happy_a_product_carries_its_published_block_settings():
    product = pb2.Product(
        name="Intraday_Hour_Power",
        block_order_product=True,
        block_maximum_hours=6,
        dst_block_product=True,
    )
    wire = pb2.Product.FromString(product.SerializeToString())
    assert wire.HasField("block_order_product")
    assert wire.block_order_product is True
    assert wire.HasField("block_maximum_hours")
    assert wire.block_maximum_hours == 6
    assert wire.HasField("dst_block_product")
    assert wire.dst_block_product is True


def test_edge_an_unpublished_block_setting_is_unset_not_a_default():
    """A product publishing no block setting reads as unset, which restricts
    nothing; the zero defaults (False, 0) must not be read as the settings."""
    wire = pb2.Product.FromString(pb2.Product(name="Bare").SerializeToString())
    assert not wire.HasField("block_order_product")
    assert not wire.HasField("block_maximum_hours")
    assert not wire.HasField("dst_block_product")


def test_edge_a_product_that_takes_no_blocks_is_an_explicit_false():
    """False is a published setting, told apart from an unpublished one."""
    wire = pb2.Product.FromString(
        pb2.Product(
            name="NoBlocks", block_order_product=False, dst_block_product=False
        ).SerializeToString()
    )
    assert wire.HasField("block_order_product")
    assert wire.block_order_product is False
    assert not wire.HasField("block_maximum_hours")
    assert wire.HasField("dst_block_product")
    assert wire.dst_block_product is False
