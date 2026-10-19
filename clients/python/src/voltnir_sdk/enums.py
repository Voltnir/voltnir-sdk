"""Re-exports of the generated proto enums under a friendly module path.

Users compare with `Side.BUY`, `OrderType.REGULAR`, etc. These are integer
enum wrappers from the underlying `_pb2` module, not Python `enum.IntEnum`,
so they pass directly into request constructors.
"""

from ._generated import voltnir_api_v1_pb2 as _pb2
from ._generated.voltnir_api_v1_pb2 import (
    AreaClass,
    AreaNameSource,
    ContractState,
    DeliveryRiskSource,
    ExeRestriction,
    MarkSource,
    ModifyAction,
    OrderState,
    OrderType,
    Outcome,
    ProductScaleClass,
    SelfTradePolicy,
    Side,
    SlotLimitMode,
    ValidityRes,
)

# Nested stream-event enums, exposed as module-level names.
#
# CAREFUL: `OrderEventType` and `OrdersEventType` differ by one letter and are
# both exported, because they belong to two different streams -- `watch_order`
# (one order) and `watch_orders` (your whole book). Mixing them up compiles and
# runs, since both are ints; check which stream you subscribed to.
ContractsEventType = _pb2.ContractsEvent.EventType
OrderEventType = _pb2.OrderEvent.EventType
OrdersEventType = _pb2.OrdersEvent.EventType
TradeEventType = _pb2.TradeEvent.EventType
TradeTapeEventType = _pb2.TradeTapeEvent.EventType

__all__ = [
    "AreaClass",
    "AreaNameSource",
    "ContractState",
    "ContractsEventType",
    "DeliveryRiskSource",
    "ExeRestriction",
    "MarkSource",
    "ModifyAction",
    "OrderEventType",
    "OrderState",
    "OrderType",
    "OrdersEventType",
    "Outcome",
    "ProductScaleClass",
    "SelfTradePolicy",
    "Side",
    "SlotLimitMode",
    "TradeEventType",
    "TradeTapeEventType",
    "ValidityRes",
]
