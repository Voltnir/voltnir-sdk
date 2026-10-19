"""Every enum a response carries is part of the public package surface.

A caller comparing `info.products[0].scale` or a trade-tape event's `type`
needs the enum by name; without the export they reach into `_generated` or
compare against bare ints. Each name below is importable from `voltnir_sdk`,
listed in `__all__`, and is the proto enum itself, so it carries the proto's
values unchanged.
"""

from __future__ import annotations

import pytest

import voltnir_sdk
from voltnir_sdk._generated import voltnir_api_v1_pb2 as pb2

# Exported name -> the proto enum it re-exports.
_RESPONSE_ENUMS = {
    "DeliveryRiskSource": pb2.DeliveryRiskSource,
    "AreaClass": pb2.AreaClass,
    "AreaNameSource": pb2.AreaNameSource,
    "ProductScaleClass": pb2.ProductScaleClass,
    "TradeTapeEventType": pb2.TradeTapeEvent.EventType,
}


@pytest.mark.parametrize("name", sorted(_RESPONSE_ENUMS))
def test_happy_response_enum_is_exported_with_the_proto_values(name):
    exported = getattr(voltnir_sdk, name)
    proto = _RESPONSE_ENUMS[name]
    assert name in voltnir_sdk.__all__
    assert exported is proto
    assert dict(exported.items()) == {
        v.name: v.number for v in proto.DESCRIPTOR.values
    }


def test_fail_an_unknown_member_name_raises():
    with pytest.raises(ValueError):
        voltnir_sdk.ProductScaleClass.Value("PRODUCT_SCALE_CLASS_EXACT")


def test_edge_every_proto_enum_has_an_export():
    """No top-level or nested proto enum is left out of the package."""
    exported = {id(getattr(voltnir_sdk, n)) for n in voltnir_sdk.__all__}
    top = [pb2.DESCRIPTOR.enum_types_by_name[n] for n in pb2.DESCRIPTOR.enum_types_by_name]
    nested = [e for m in pb2.DESCRIPTOR.message_types_by_name.values() for e in m.enum_types]
    missing = sorted(
        e.full_name for e in top + nested
        if id(_wrapper(e)) not in exported
    )
    assert missing == []


def _wrapper(enum_descriptor):
    """The generated `EnumTypeWrapper` for a descriptor, top-level or nested."""
    containing = enum_descriptor.containing_type
    if containing is None:
        return getattr(pb2, enum_descriptor.name)
    return getattr(getattr(pb2, containing.name), enum_descriptor.name)


def test_edge_trade_tape_and_trade_event_types_are_distinct_names():
    """`TradeTapeEventType` (watch_trade_tape) is not `TradeEventType`
    (watch_trades), although both spell SNAPSHOT 0 and UPSERTED 1."""
    assert voltnir_sdk.TradeTapeEventType is not voltnir_sdk.TradeEventType
    assert voltnir_sdk.TradeTapeEventType.SNAPSHOT == 0
    assert voltnir_sdk.TradeTapeEventType.UPSERTED == 1
