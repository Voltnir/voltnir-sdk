from google.protobuf import empty_pb2 as _empty_pb2
from google.protobuf import wrappers_pb2 as _wrappers_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Side(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SIDE_UNSPECIFIED: _ClassVar[Side]
    BUY: _ClassVar[Side]
    SELL: _ClassVar[Side]

class SelfTradePolicy(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SELF_TRADE_POLICY_UNSPECIFIED: _ClassVar[SelfTradePolicy]
    SELF_TRADE_POLICY_OBSERVE: _ClassVar[SelfTradePolicy]
    SELF_TRADE_POLICY_REJECT: _ClassVar[SelfTradePolicy]

class OrderState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ORDER_STATE_UNSPECIFIED: _ClassVar[OrderState]
    PENDING: _ClassVar[OrderState]
    ACTIVE: _ClassVar[OrderState]
    INACTIVE: _ClassVar[OrderState]
    HIBERNATED: _ClassVar[OrderState]
    REJECTED: _ClassVar[OrderState]
    UNKNOWN: _ClassVar[OrderState]

class OrderType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ORDER_TYPE_UNSPECIFIED: _ClassVar[OrderType]
    REGULAR: _ClassVar[OrderType]
    BLOCK: _ClassVar[OrderType]
    ICEBERG: _ClassVar[OrderType]
    BALANCE: _ClassVar[OrderType]
    PRE_ARRANGED: _ClassVar[OrderType]
    EXCHANGE_PRE_ARRANGED: _ClassVar[OrderType]
    PRIVATE: _ClassVar[OrderType]
    STOP: _ClassVar[OrderType]
    UNKNOWN_TYPE: _ClassVar[OrderType]

class ExeRestriction(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    EXE_UNSPECIFIED: _ClassVar[ExeRestriction]
    NON: _ClassVar[ExeRestriction]
    FOK: _ClassVar[ExeRestriction]
    IOC: _ClassVar[ExeRestriction]
    AON: _ClassVar[ExeRestriction]

class ValidityRes(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    VALIDITY_UNSPECIFIED: _ClassVar[ValidityRes]
    GFS: _ClassVar[ValidityRes]
    GTD: _ClassVar[ValidityRes]
    VALIDITY_NON: _ClassVar[ValidityRes]

class ModifyAction(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    MODIFY_UNSPECIFIED: _ClassVar[ModifyAction]
    MODIFY: _ClassVar[ModifyAction]
    ACTIVATE: _ClassVar[ModifyAction]
    DEACTIVATE: _ClassVar[ModifyAction]

class ContractState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    CONTRACT_STATE_UNSPECIFIED: _ClassVar[ContractState]
    ACTI: _ClassVar[ContractState]
    SUSP: _ClassVar[ContractState]
    CLOS: _ClassVar[ContractState]

class ExportFormat(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    FORMAT_UNSPECIFIED: _ClassVar[ExportFormat]
    JSON: _ClassVar[ExportFormat]
    CSV: _ClassVar[ExportFormat]

class MarkSource(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    MARK_SOURCE_UNSPECIFIED: _ClassVar[MarkSource]
    MARK_SOURCE_MID: _ClassVar[MarkSource]
    MARK_SOURCE_LAST: _ClassVar[MarkSource]
    MARK_SOURCE_NONE: _ClassVar[MarkSource]
SIDE_UNSPECIFIED: Side
BUY: Side
SELL: Side
SELF_TRADE_POLICY_UNSPECIFIED: SelfTradePolicy
SELF_TRADE_POLICY_OBSERVE: SelfTradePolicy
SELF_TRADE_POLICY_REJECT: SelfTradePolicy
ORDER_STATE_UNSPECIFIED: OrderState
PENDING: OrderState
ACTIVE: OrderState
INACTIVE: OrderState
HIBERNATED: OrderState
REJECTED: OrderState
UNKNOWN: OrderState
ORDER_TYPE_UNSPECIFIED: OrderType
REGULAR: OrderType
BLOCK: OrderType
ICEBERG: OrderType
BALANCE: OrderType
PRE_ARRANGED: OrderType
EXCHANGE_PRE_ARRANGED: OrderType
PRIVATE: OrderType
STOP: OrderType
UNKNOWN_TYPE: OrderType
EXE_UNSPECIFIED: ExeRestriction
NON: ExeRestriction
FOK: ExeRestriction
IOC: ExeRestriction
AON: ExeRestriction
VALIDITY_UNSPECIFIED: ValidityRes
GFS: ValidityRes
GTD: ValidityRes
VALIDITY_NON: ValidityRes
MODIFY_UNSPECIFIED: ModifyAction
MODIFY: ModifyAction
ACTIVATE: ModifyAction
DEACTIVATE: ModifyAction
CONTRACT_STATE_UNSPECIFIED: ContractState
ACTI: ContractState
SUSP: ContractState
CLOS: ContractState
FORMAT_UNSPECIFIED: ExportFormat
JSON: ExportFormat
CSV: ExportFormat
MARK_SOURCE_UNSPECIFIED: MarkSource
MARK_SOURCE_MID: MarkSource
MARK_SOURCE_LAST: MarkSource
MARK_SOURCE_NONE: MarkSource

class OwnOrder(_message.Message):
    __slots__ = ("order_id", "initial_order_id", "parent_order_id", "revision", "account_id", "contract_id", "delivery_area", "side", "price", "quantity", "initial_quantity", "hidden_quantity", "displayed_quantity", "order_type", "state", "action", "client_order_id", "user_code", "pre_arranged", "timestamp_ms", "validity_time_ms", "last_update_time_ms", "text", "basket_id", "v_member_short_id")
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    INITIAL_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    PARENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    REVISION_FIELD_NUMBER: _ClassVar[int]
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    CONTRACT_ID_FIELD_NUMBER: _ClassVar[int]
    DELIVERY_AREA_FIELD_NUMBER: _ClassVar[int]
    SIDE_FIELD_NUMBER: _ClassVar[int]
    PRICE_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    INITIAL_QUANTITY_FIELD_NUMBER: _ClassVar[int]
    HIDDEN_QUANTITY_FIELD_NUMBER: _ClassVar[int]
    DISPLAYED_QUANTITY_FIELD_NUMBER: _ClassVar[int]
    ORDER_TYPE_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    ACTION_FIELD_NUMBER: _ClassVar[int]
    CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    USER_CODE_FIELD_NUMBER: _ClassVar[int]
    PRE_ARRANGED_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_MS_FIELD_NUMBER: _ClassVar[int]
    VALIDITY_TIME_MS_FIELD_NUMBER: _ClassVar[int]
    LAST_UPDATE_TIME_MS_FIELD_NUMBER: _ClassVar[int]
    TEXT_FIELD_NUMBER: _ClassVar[int]
    BASKET_ID_FIELD_NUMBER: _ClassVar[int]
    V_MEMBER_SHORT_ID_FIELD_NUMBER: _ClassVar[int]
    order_id: int
    initial_order_id: int
    parent_order_id: int
    revision: int
    account_id: str
    contract_id: int
    delivery_area: str
    side: Side
    price: int
    quantity: int
    initial_quantity: int
    hidden_quantity: int
    displayed_quantity: int
    order_type: OrderType
    state: OrderState
    action: str
    client_order_id: str
    user_code: str
    pre_arranged: bool
    timestamp_ms: int
    validity_time_ms: int
    last_update_time_ms: int
    text: str
    basket_id: int
    v_member_short_id: str
    def __init__(self, order_id: _Optional[int] = ..., initial_order_id: _Optional[int] = ..., parent_order_id: _Optional[int] = ..., revision: _Optional[int] = ..., account_id: _Optional[str] = ..., contract_id: _Optional[int] = ..., delivery_area: _Optional[str] = ..., side: _Optional[_Union[Side, str]] = ..., price: _Optional[int] = ..., quantity: _Optional[int] = ..., initial_quantity: _Optional[int] = ..., hidden_quantity: _Optional[int] = ..., displayed_quantity: _Optional[int] = ..., order_type: _Optional[_Union[OrderType, str]] = ..., state: _Optional[_Union[OrderState, str]] = ..., action: _Optional[str] = ..., client_order_id: _Optional[str] = ..., user_code: _Optional[str] = ..., pre_arranged: bool = ..., timestamp_ms: _Optional[int] = ..., validity_time_ms: _Optional[int] = ..., last_update_time_ms: _Optional[int] = ..., text: _Optional[str] = ..., basket_id: _Optional[int] = ..., v_member_short_id: _Optional[str] = ...) -> None: ...

class PendingOrder(_message.Message):
    __slots__ = ("client_order_id", "contract_id", "delivery_area", "side", "price", "quantity", "entry_ts_ms", "v_member_short_id")
    CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    CONTRACT_ID_FIELD_NUMBER: _ClassVar[int]
    DELIVERY_AREA_FIELD_NUMBER: _ClassVar[int]
    SIDE_FIELD_NUMBER: _ClassVar[int]
    PRICE_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    ENTRY_TS_MS_FIELD_NUMBER: _ClassVar[int]
    V_MEMBER_SHORT_ID_FIELD_NUMBER: _ClassVar[int]
    client_order_id: str
    contract_id: int
    delivery_area: str
    side: Side
    price: int
    quantity: int
    entry_ts_ms: int
    v_member_short_id: str
    def __init__(self, client_order_id: _Optional[str] = ..., contract_id: _Optional[int] = ..., delivery_area: _Optional[str] = ..., side: _Optional[_Union[Side, str]] = ..., price: _Optional[int] = ..., quantity: _Optional[int] = ..., entry_ts_ms: _Optional[int] = ..., v_member_short_id: _Optional[str] = ...) -> None: ...

class ObEntry(_message.Message):
    __slots__ = ("price", "quantity", "order_id", "order_entry_time", "order_execution_restriction", "order_type")
    PRICE_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    ORDER_ENTRY_TIME_FIELD_NUMBER: _ClassVar[int]
    ORDER_EXECUTION_RESTRICTION_FIELD_NUMBER: _ClassVar[int]
    ORDER_TYPE_FIELD_NUMBER: _ClassVar[int]
    price: int
    quantity: int
    order_id: int
    order_entry_time: str
    order_execution_restriction: int
    order_type: int
    def __init__(self, price: _Optional[int] = ..., quantity: _Optional[int] = ..., order_id: _Optional[int] = ..., order_entry_time: _Optional[str] = ..., order_execution_restriction: _Optional[int] = ..., order_type: _Optional[int] = ...) -> None: ...

class OwnTrade(_message.Message):
    __slots__ = ("trade_id", "contract_id", "qty", "px", "exec_time", "revision_no", "state", "pre_arranged", "v_member_short_id", "buy", "sell")
    TRADE_ID_FIELD_NUMBER: _ClassVar[int]
    CONTRACT_ID_FIELD_NUMBER: _ClassVar[int]
    QTY_FIELD_NUMBER: _ClassVar[int]
    PX_FIELD_NUMBER: _ClassVar[int]
    EXEC_TIME_FIELD_NUMBER: _ClassVar[int]
    REVISION_NO_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    PRE_ARRANGED_FIELD_NUMBER: _ClassVar[int]
    V_MEMBER_SHORT_ID_FIELD_NUMBER: _ClassVar[int]
    BUY_FIELD_NUMBER: _ClassVar[int]
    SELL_FIELD_NUMBER: _ClassVar[int]
    trade_id: str
    contract_id: int
    qty: int
    px: int
    exec_time: str
    revision_no: int
    state: str
    pre_arranged: bool
    v_member_short_id: str
    buy: _containers.RepeatedCompositeFieldContainer[TradeDetail]
    sell: _containers.RepeatedCompositeFieldContainer[TradeDetail]
    def __init__(self, trade_id: _Optional[str] = ..., contract_id: _Optional[int] = ..., qty: _Optional[int] = ..., px: _Optional[int] = ..., exec_time: _Optional[str] = ..., revision_no: _Optional[int] = ..., state: _Optional[str] = ..., pre_arranged: bool = ..., v_member_short_id: _Optional[str] = ..., buy: _Optional[_Iterable[_Union[TradeDetail, _Mapping]]] = ..., sell: _Optional[_Iterable[_Union[TradeDetail, _Mapping]]] = ...) -> None: ...

class TradeDetail(_message.Message):
    __slots__ = ("order_id", "client_order_id", "delivery_area", "account_id", "user_code")
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    DELIVERY_AREA_FIELD_NUMBER: _ClassVar[int]
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    USER_CODE_FIELD_NUMBER: _ClassVar[int]
    order_id: int
    client_order_id: str
    delivery_area: str
    account_id: str
    user_code: str
    def __init__(self, order_id: _Optional[int] = ..., client_order_id: _Optional[str] = ..., delivery_area: _Optional[str] = ..., account_id: _Optional[str] = ..., user_code: _Optional[str] = ...) -> None: ...

class Contract(_message.Message):
    __slots__ = ("contract_id", "area_id", "prod", "name", "long_name", "dlvry_start", "dlvry_end", "predefined", "revision_no", "revision_ob", "state", "trading_phase", "trading_phase_start", "trading_phase_end", "duration", "last_price", "last_quantity", "last_trade_time", "highest_price", "lowest_price", "price_direction", "best_bid", "best_bid_qty", "best_ask", "best_ask_qty", "buy", "sell", "state_raw")
    CONTRACT_ID_FIELD_NUMBER: _ClassVar[int]
    AREA_ID_FIELD_NUMBER: _ClassVar[int]
    PROD_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    LONG_NAME_FIELD_NUMBER: _ClassVar[int]
    DLVRY_START_FIELD_NUMBER: _ClassVar[int]
    DLVRY_END_FIELD_NUMBER: _ClassVar[int]
    PREDEFINED_FIELD_NUMBER: _ClassVar[int]
    REVISION_NO_FIELD_NUMBER: _ClassVar[int]
    REVISION_OB_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    TRADING_PHASE_FIELD_NUMBER: _ClassVar[int]
    TRADING_PHASE_START_FIELD_NUMBER: _ClassVar[int]
    TRADING_PHASE_END_FIELD_NUMBER: _ClassVar[int]
    DURATION_FIELD_NUMBER: _ClassVar[int]
    LAST_PRICE_FIELD_NUMBER: _ClassVar[int]
    LAST_QUANTITY_FIELD_NUMBER: _ClassVar[int]
    LAST_TRADE_TIME_FIELD_NUMBER: _ClassVar[int]
    HIGHEST_PRICE_FIELD_NUMBER: _ClassVar[int]
    LOWEST_PRICE_FIELD_NUMBER: _ClassVar[int]
    PRICE_DIRECTION_FIELD_NUMBER: _ClassVar[int]
    BEST_BID_FIELD_NUMBER: _ClassVar[int]
    BEST_BID_QTY_FIELD_NUMBER: _ClassVar[int]
    BEST_ASK_FIELD_NUMBER: _ClassVar[int]
    BEST_ASK_QTY_FIELD_NUMBER: _ClassVar[int]
    BUY_FIELD_NUMBER: _ClassVar[int]
    SELL_FIELD_NUMBER: _ClassVar[int]
    STATE_RAW_FIELD_NUMBER: _ClassVar[int]
    contract_id: str
    area_id: str
    prod: str
    name: str
    long_name: str
    dlvry_start: str
    dlvry_end: str
    predefined: bool
    revision_no: int
    revision_ob: int
    state: ContractState
    trading_phase: str
    trading_phase_start: str
    trading_phase_end: str
    duration: str
    last_price: int
    last_quantity: int
    last_trade_time: str
    highest_price: int
    lowest_price: int
    price_direction: int
    best_bid: int
    best_bid_qty: int
    best_ask: int
    best_ask_qty: int
    buy: _containers.RepeatedCompositeFieldContainer[ObEntry]
    sell: _containers.RepeatedCompositeFieldContainer[ObEntry]
    state_raw: str
    def __init__(self, contract_id: _Optional[str] = ..., area_id: _Optional[str] = ..., prod: _Optional[str] = ..., name: _Optional[str] = ..., long_name: _Optional[str] = ..., dlvry_start: _Optional[str] = ..., dlvry_end: _Optional[str] = ..., predefined: bool = ..., revision_no: _Optional[int] = ..., revision_ob: _Optional[int] = ..., state: _Optional[_Union[ContractState, str]] = ..., trading_phase: _Optional[str] = ..., trading_phase_start: _Optional[str] = ..., trading_phase_end: _Optional[str] = ..., duration: _Optional[str] = ..., last_price: _Optional[int] = ..., last_quantity: _Optional[int] = ..., last_trade_time: _Optional[str] = ..., highest_price: _Optional[int] = ..., lowest_price: _Optional[int] = ..., price_direction: _Optional[int] = ..., best_bid: _Optional[int] = ..., best_bid_qty: _Optional[int] = ..., best_ask: _Optional[int] = ..., best_ask_qty: _Optional[int] = ..., buy: _Optional[_Iterable[_Union[ObEntry, _Mapping]]] = ..., sell: _Optional[_Iterable[_Union[ObEntry, _Mapping]]] = ..., state_raw: _Optional[str] = ...) -> None: ...

class ContractDetail(_message.Message):
    __slots__ = ("contract", "orders_acknowledged", "trades", "net_pos", "orders_pending")
    CONTRACT_FIELD_NUMBER: _ClassVar[int]
    ORDERS_ACKNOWLEDGED_FIELD_NUMBER: _ClassVar[int]
    TRADES_FIELD_NUMBER: _ClassVar[int]
    NET_POS_FIELD_NUMBER: _ClassVar[int]
    ORDERS_PENDING_FIELD_NUMBER: _ClassVar[int]
    contract: Contract
    orders_acknowledged: _containers.RepeatedCompositeFieldContainer[OwnOrder]
    trades: _containers.RepeatedCompositeFieldContainer[OwnTrade]
    net_pos: int
    orders_pending: _containers.RepeatedCompositeFieldContainer[PendingOrder]
    def __init__(self, contract: _Optional[_Union[Contract, _Mapping]] = ..., orders_acknowledged: _Optional[_Iterable[_Union[OwnOrder, _Mapping]]] = ..., trades: _Optional[_Iterable[_Union[OwnTrade, _Mapping]]] = ..., net_pos: _Optional[int] = ..., orders_pending: _Optional[_Iterable[_Union[PendingOrder, _Mapping]]] = ...) -> None: ...

class Member(_message.Message):
    __slots__ = ("id", "short_id", "name", "max_position", "active", "cash_limit", "cash_limit_gbp", "eur_consumed_cents", "eur_limit_cents", "eur_remaining_cents", "gbp_consumed_cents", "gbp_limit_cents", "gbp_remaining_cents")
    ID_FIELD_NUMBER: _ClassVar[int]
    SHORT_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    MAX_POSITION_FIELD_NUMBER: _ClassVar[int]
    ACTIVE_FIELD_NUMBER: _ClassVar[int]
    CASH_LIMIT_FIELD_NUMBER: _ClassVar[int]
    CASH_LIMIT_GBP_FIELD_NUMBER: _ClassVar[int]
    EUR_CONSUMED_CENTS_FIELD_NUMBER: _ClassVar[int]
    EUR_LIMIT_CENTS_FIELD_NUMBER: _ClassVar[int]
    EUR_REMAINING_CENTS_FIELD_NUMBER: _ClassVar[int]
    GBP_CONSUMED_CENTS_FIELD_NUMBER: _ClassVar[int]
    GBP_LIMIT_CENTS_FIELD_NUMBER: _ClassVar[int]
    GBP_REMAINING_CENTS_FIELD_NUMBER: _ClassVar[int]
    id: str
    short_id: str
    name: str
    max_position: int
    active: bool
    cash_limit: int
    cash_limit_gbp: int
    eur_consumed_cents: int
    eur_limit_cents: int
    eur_remaining_cents: int
    gbp_consumed_cents: int
    gbp_limit_cents: int
    gbp_remaining_cents: int
    def __init__(self, id: _Optional[str] = ..., short_id: _Optional[str] = ..., name: _Optional[str] = ..., max_position: _Optional[int] = ..., active: bool = ..., cash_limit: _Optional[int] = ..., cash_limit_gbp: _Optional[int] = ..., eur_consumed_cents: _Optional[int] = ..., eur_limit_cents: _Optional[int] = ..., eur_remaining_cents: _Optional[int] = ..., gbp_consumed_cents: _Optional[int] = ..., gbp_limit_cents: _Optional[int] = ..., gbp_remaining_cents: _Optional[int] = ...) -> None: ...

class UserProfile(_message.Message):
    __slots__ = ("id", "username", "permissions", "short_id")
    ID_FIELD_NUMBER: _ClassVar[int]
    USERNAME_FIELD_NUMBER: _ClassVar[int]
    PERMISSIONS_FIELD_NUMBER: _ClassVar[int]
    SHORT_ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    username: str
    permissions: _containers.RepeatedScalarFieldContainer[str]
    short_id: str
    def __init__(self, id: _Optional[str] = ..., username: _Optional[str] = ..., permissions: _Optional[_Iterable[str]] = ..., short_id: _Optional[str] = ...) -> None: ...

class SubmitOrderRequest(_message.Message):
    __slots__ = ("side", "price", "quantity", "delivery_area_id", "contract_id", "order_type", "exe_restriction", "validity_res", "entry_state", "display_qty", "validity_date", "pre_arranged_acct", "v_member_short_id", "product", "delivery_start", "client_order_id")
    SIDE_FIELD_NUMBER: _ClassVar[int]
    PRICE_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    DELIVERY_AREA_ID_FIELD_NUMBER: _ClassVar[int]
    CONTRACT_ID_FIELD_NUMBER: _ClassVar[int]
    ORDER_TYPE_FIELD_NUMBER: _ClassVar[int]
    EXE_RESTRICTION_FIELD_NUMBER: _ClassVar[int]
    VALIDITY_RES_FIELD_NUMBER: _ClassVar[int]
    ENTRY_STATE_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_QTY_FIELD_NUMBER: _ClassVar[int]
    VALIDITY_DATE_FIELD_NUMBER: _ClassVar[int]
    PRE_ARRANGED_ACCT_FIELD_NUMBER: _ClassVar[int]
    V_MEMBER_SHORT_ID_FIELD_NUMBER: _ClassVar[int]
    PRODUCT_FIELD_NUMBER: _ClassVar[int]
    DELIVERY_START_FIELD_NUMBER: _ClassVar[int]
    CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    side: Side
    price: int
    quantity: int
    delivery_area_id: str
    contract_id: int
    order_type: OrderType
    exe_restriction: ExeRestriction
    validity_res: ValidityRes
    entry_state: str
    display_qty: int
    validity_date: str
    pre_arranged_acct: str
    v_member_short_id: str
    product: str
    delivery_start: str
    client_order_id: str
    def __init__(self, side: _Optional[_Union[Side, str]] = ..., price: _Optional[int] = ..., quantity: _Optional[int] = ..., delivery_area_id: _Optional[str] = ..., contract_id: _Optional[int] = ..., order_type: _Optional[_Union[OrderType, str]] = ..., exe_restriction: _Optional[_Union[ExeRestriction, str]] = ..., validity_res: _Optional[_Union[ValidityRes, str]] = ..., entry_state: _Optional[str] = ..., display_qty: _Optional[int] = ..., validity_date: _Optional[str] = ..., pre_arranged_acct: _Optional[str] = ..., v_member_short_id: _Optional[str] = ..., product: _Optional[str] = ..., delivery_start: _Optional[str] = ..., client_order_id: _Optional[str] = ...) -> None: ...

class SubmitOrderResponse(_message.Message):
    __slots__ = ("client_order_id", "state", "reason")
    CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    client_order_id: str
    state: OrderState
    reason: str
    def __init__(self, client_order_id: _Optional[str] = ..., state: _Optional[_Union[OrderState, str]] = ..., reason: _Optional[str] = ...) -> None: ...

class ModifyOrderRequest(_message.Message):
    __slots__ = ("client_order_id", "action", "price", "quantity", "display_qty", "validity_res", "validity_date", "v_member_short_id")
    CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    ACTION_FIELD_NUMBER: _ClassVar[int]
    PRICE_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_QTY_FIELD_NUMBER: _ClassVar[int]
    VALIDITY_RES_FIELD_NUMBER: _ClassVar[int]
    VALIDITY_DATE_FIELD_NUMBER: _ClassVar[int]
    V_MEMBER_SHORT_ID_FIELD_NUMBER: _ClassVar[int]
    client_order_id: str
    action: ModifyAction
    price: _wrappers_pb2.Int64Value
    quantity: _wrappers_pb2.UInt32Value
    display_qty: int
    validity_res: ValidityRes
    validity_date: str
    v_member_short_id: str
    def __init__(self, client_order_id: _Optional[str] = ..., action: _Optional[_Union[ModifyAction, str]] = ..., price: _Optional[_Union[_wrappers_pb2.Int64Value, _Mapping]] = ..., quantity: _Optional[_Union[_wrappers_pb2.UInt32Value, _Mapping]] = ..., display_qty: _Optional[int] = ..., validity_res: _Optional[_Union[ValidityRes, str]] = ..., validity_date: _Optional[str] = ..., v_member_short_id: _Optional[str] = ...) -> None: ...

class ModifyOrderResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class CancelOrderRequest(_message.Message):
    __slots__ = ("client_order_id",)
    CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    client_order_id: str
    def __init__(self, client_order_id: _Optional[str] = ...) -> None: ...

class CancelOrderResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class CancelAllOrdersRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class CancelAllOrdersResponse(_message.Message):
    __slots__ = ("deleted",)
    DELETED_FIELD_NUMBER: _ClassVar[int]
    deleted: int
    def __init__(self, deleted: _Optional[int] = ...) -> None: ...

class GetOrderRequest(_message.Message):
    __slots__ = ("client_order_id",)
    CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    client_order_id: str
    def __init__(self, client_order_id: _Optional[str] = ...) -> None: ...

class GetOrderResponse(_message.Message):
    __slots__ = ("confirmed", "pending")
    CONFIRMED_FIELD_NUMBER: _ClassVar[int]
    PENDING_FIELD_NUMBER: _ClassVar[int]
    confirmed: OwnOrder
    pending: PendingOrder
    def __init__(self, confirmed: _Optional[_Union[OwnOrder, _Mapping]] = ..., pending: _Optional[_Union[PendingOrder, _Mapping]] = ...) -> None: ...

class ListOrdersRequest(_message.Message):
    __slots__ = ("delivery_area", "contract_id", "product", "delivery_start", "v_member_short_id")
    DELIVERY_AREA_FIELD_NUMBER: _ClassVar[int]
    CONTRACT_ID_FIELD_NUMBER: _ClassVar[int]
    PRODUCT_FIELD_NUMBER: _ClassVar[int]
    DELIVERY_START_FIELD_NUMBER: _ClassVar[int]
    V_MEMBER_SHORT_ID_FIELD_NUMBER: _ClassVar[int]
    delivery_area: str
    contract_id: int
    product: str
    delivery_start: str
    v_member_short_id: str
    def __init__(self, delivery_area: _Optional[str] = ..., contract_id: _Optional[int] = ..., product: _Optional[str] = ..., delivery_start: _Optional[str] = ..., v_member_short_id: _Optional[str] = ...) -> None: ...

class ListOrdersResponse(_message.Message):
    __slots__ = ("orders",)
    ORDERS_FIELD_NUMBER: _ClassVar[int]
    orders: _containers.RepeatedCompositeFieldContainer[OwnOrder]
    def __init__(self, orders: _Optional[_Iterable[_Union[OwnOrder, _Mapping]]] = ...) -> None: ...

class ListContractsRequest(_message.Message):
    __slots__ = ("area_id",)
    AREA_ID_FIELD_NUMBER: _ClassVar[int]
    area_id: str
    def __init__(self, area_id: _Optional[str] = ...) -> None: ...

class ListContractsResponse(_message.Message):
    __slots__ = ("contracts",)
    CONTRACTS_FIELD_NUMBER: _ClassVar[int]
    contracts: _containers.RepeatedCompositeFieldContainer[Contract]
    def __init__(self, contracts: _Optional[_Iterable[_Union[Contract, _Mapping]]] = ...) -> None: ...

class GetContractRequest(_message.Message):
    __slots__ = ("area_id", "contract_id")
    AREA_ID_FIELD_NUMBER: _ClassVar[int]
    CONTRACT_ID_FIELD_NUMBER: _ClassVar[int]
    area_id: str
    contract_id: str
    def __init__(self, area_id: _Optional[str] = ..., contract_id: _Optional[str] = ...) -> None: ...

class GetContractByDeliveryRequest(_message.Message):
    __slots__ = ("area_id", "prod", "dlvry_start")
    AREA_ID_FIELD_NUMBER: _ClassVar[int]
    PROD_FIELD_NUMBER: _ClassVar[int]
    DLVRY_START_FIELD_NUMBER: _ClassVar[int]
    area_id: str
    prod: str
    dlvry_start: str
    def __init__(self, area_id: _Optional[str] = ..., prod: _Optional[str] = ..., dlvry_start: _Optional[str] = ...) -> None: ...

class GetHub2HubRequest(_message.Message):
    __slots__ = ("delivery_area_from", "delivery_from", "delivery_to", "delivery_area_to")
    DELIVERY_AREA_FROM_FIELD_NUMBER: _ClassVar[int]
    DELIVERY_FROM_FIELD_NUMBER: _ClassVar[int]
    DELIVERY_TO_FIELD_NUMBER: _ClassVar[int]
    DELIVERY_AREA_TO_FIELD_NUMBER: _ClassVar[int]
    delivery_area_from: str
    delivery_from: str
    delivery_to: str
    delivery_area_to: str
    def __init__(self, delivery_area_from: _Optional[str] = ..., delivery_from: _Optional[str] = ..., delivery_to: _Optional[str] = ..., delivery_area_to: _Optional[str] = ...) -> None: ...

class GetHub2HubResponse(_message.Message):
    __slots__ = ("enabled", "capacity_connected", "data")
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    CAPACITY_CONNECTED_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    enabled: bool
    capacity_connected: bool
    data: _containers.RepeatedCompositeFieldContainer[AtcEntry]
    def __init__(self, enabled: bool = ..., capacity_connected: bool = ..., data: _Optional[_Iterable[_Union[AtcEntry, _Mapping]]] = ...) -> None: ...

class AtcEntry(_message.Message):
    __slots__ = ("source_area", "target_area", "dlvry_start", "dlvry_end", "source_best_bid", "source_best_ask", "dest_best_bid", "dest_best_ask", "atc_out", "atc_in", "revision_no", "timestmp")
    SOURCE_AREA_FIELD_NUMBER: _ClassVar[int]
    TARGET_AREA_FIELD_NUMBER: _ClassVar[int]
    DLVRY_START_FIELD_NUMBER: _ClassVar[int]
    DLVRY_END_FIELD_NUMBER: _ClassVar[int]
    SOURCE_BEST_BID_FIELD_NUMBER: _ClassVar[int]
    SOURCE_BEST_ASK_FIELD_NUMBER: _ClassVar[int]
    DEST_BEST_BID_FIELD_NUMBER: _ClassVar[int]
    DEST_BEST_ASK_FIELD_NUMBER: _ClassVar[int]
    ATC_OUT_FIELD_NUMBER: _ClassVar[int]
    ATC_IN_FIELD_NUMBER: _ClassVar[int]
    REVISION_NO_FIELD_NUMBER: _ClassVar[int]
    TIMESTMP_FIELD_NUMBER: _ClassVar[int]
    source_area: str
    target_area: str
    dlvry_start: str
    dlvry_end: str
    source_best_bid: _wrappers_pb2.Int64Value
    source_best_ask: _wrappers_pb2.Int64Value
    dest_best_bid: _wrappers_pb2.Int64Value
    dest_best_ask: _wrappers_pb2.Int64Value
    atc_out: int
    atc_in: int
    revision_no: int
    timestmp: str
    def __init__(self, source_area: _Optional[str] = ..., target_area: _Optional[str] = ..., dlvry_start: _Optional[str] = ..., dlvry_end: _Optional[str] = ..., source_best_bid: _Optional[_Union[_wrappers_pb2.Int64Value, _Mapping]] = ..., source_best_ask: _Optional[_Union[_wrappers_pb2.Int64Value, _Mapping]] = ..., dest_best_bid: _Optional[_Union[_wrappers_pb2.Int64Value, _Mapping]] = ..., dest_best_ask: _Optional[_Union[_wrappers_pb2.Int64Value, _Mapping]] = ..., atc_out: _Optional[int] = ..., atc_in: _Optional[int] = ..., revision_no: _Optional[int] = ..., timestmp: _Optional[str] = ...) -> None: ...

class GetStateRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class SystemState(_message.Message):
    __slots__ = ("uptime", "operational", "issues", "amqp_connected", "amqp_private_consumer_healthy", "amqp_broadcast_consumer_healthy", "amqp_publisher_healthy", "amqp_publisher_tx_capacity", "amqp_market_active", "ws_order_book_stream_connected", "ws_order_book_sequence_healthy", "ws_order_book_synchronized", "ws_order_book_pong", "ws_order_book_delta", "ws_order_book_delta_per_hour", "ws_order_book_avg_processing_time", "ws_order_book_avg_latency", "ws_private_data_stream_connected", "ws_private_data_sequence_healthy", "ws_private_data_synchronized", "ws_private_data_pong", "ws_private_data_delta_per_hour", "ws_private_data_avg_processing_time", "ws_private_data_avg_latency", "license")
    UPTIME_FIELD_NUMBER: _ClassVar[int]
    OPERATIONAL_FIELD_NUMBER: _ClassVar[int]
    ISSUES_FIELD_NUMBER: _ClassVar[int]
    AMQP_CONNECTED_FIELD_NUMBER: _ClassVar[int]
    AMQP_PRIVATE_CONSUMER_HEALTHY_FIELD_NUMBER: _ClassVar[int]
    AMQP_BROADCAST_CONSUMER_HEALTHY_FIELD_NUMBER: _ClassVar[int]
    AMQP_PUBLISHER_HEALTHY_FIELD_NUMBER: _ClassVar[int]
    AMQP_PUBLISHER_TX_CAPACITY_FIELD_NUMBER: _ClassVar[int]
    AMQP_MARKET_ACTIVE_FIELD_NUMBER: _ClassVar[int]
    WS_ORDER_BOOK_STREAM_CONNECTED_FIELD_NUMBER: _ClassVar[int]
    WS_ORDER_BOOK_SEQUENCE_HEALTHY_FIELD_NUMBER: _ClassVar[int]
    WS_ORDER_BOOK_SYNCHRONIZED_FIELD_NUMBER: _ClassVar[int]
    WS_ORDER_BOOK_PONG_FIELD_NUMBER: _ClassVar[int]
    WS_ORDER_BOOK_DELTA_FIELD_NUMBER: _ClassVar[int]
    WS_ORDER_BOOK_DELTA_PER_HOUR_FIELD_NUMBER: _ClassVar[int]
    WS_ORDER_BOOK_AVG_PROCESSING_TIME_FIELD_NUMBER: _ClassVar[int]
    WS_ORDER_BOOK_AVG_LATENCY_FIELD_NUMBER: _ClassVar[int]
    WS_PRIVATE_DATA_STREAM_CONNECTED_FIELD_NUMBER: _ClassVar[int]
    WS_PRIVATE_DATA_SEQUENCE_HEALTHY_FIELD_NUMBER: _ClassVar[int]
    WS_PRIVATE_DATA_SYNCHRONIZED_FIELD_NUMBER: _ClassVar[int]
    WS_PRIVATE_DATA_PONG_FIELD_NUMBER: _ClassVar[int]
    WS_PRIVATE_DATA_DELTA_PER_HOUR_FIELD_NUMBER: _ClassVar[int]
    WS_PRIVATE_DATA_AVG_PROCESSING_TIME_FIELD_NUMBER: _ClassVar[int]
    WS_PRIVATE_DATA_AVG_LATENCY_FIELD_NUMBER: _ClassVar[int]
    LICENSE_FIELD_NUMBER: _ClassVar[int]
    uptime: str
    operational: bool
    issues: _containers.RepeatedScalarFieldContainer[str]
    amqp_connected: bool
    amqp_private_consumer_healthy: bool
    amqp_broadcast_consumer_healthy: bool
    amqp_publisher_healthy: bool
    amqp_publisher_tx_capacity: int
    amqp_market_active: bool
    ws_order_book_stream_connected: bool
    ws_order_book_sequence_healthy: bool
    ws_order_book_synchronized: bool
    ws_order_book_pong: int
    ws_order_book_delta: int
    ws_order_book_delta_per_hour: int
    ws_order_book_avg_processing_time: str
    ws_order_book_avg_latency: str
    ws_private_data_stream_connected: bool
    ws_private_data_sequence_healthy: bool
    ws_private_data_synchronized: bool
    ws_private_data_pong: int
    ws_private_data_delta_per_hour: int
    ws_private_data_avg_processing_time: str
    ws_private_data_avg_latency: str
    license: LicenseView
    def __init__(self, uptime: _Optional[str] = ..., operational: bool = ..., issues: _Optional[_Iterable[str]] = ..., amqp_connected: bool = ..., amqp_private_consumer_healthy: bool = ..., amqp_broadcast_consumer_healthy: bool = ..., amqp_publisher_healthy: bool = ..., amqp_publisher_tx_capacity: _Optional[int] = ..., amqp_market_active: bool = ..., ws_order_book_stream_connected: bool = ..., ws_order_book_sequence_healthy: bool = ..., ws_order_book_synchronized: bool = ..., ws_order_book_pong: _Optional[int] = ..., ws_order_book_delta: _Optional[int] = ..., ws_order_book_delta_per_hour: _Optional[int] = ..., ws_order_book_avg_processing_time: _Optional[str] = ..., ws_order_book_avg_latency: _Optional[str] = ..., ws_private_data_stream_connected: bool = ..., ws_private_data_sequence_healthy: bool = ..., ws_private_data_synchronized: bool = ..., ws_private_data_pong: _Optional[int] = ..., ws_private_data_delta_per_hour: _Optional[int] = ..., ws_private_data_avg_processing_time: _Optional[str] = ..., ws_private_data_avg_latency: _Optional[str] = ..., license: _Optional[_Union[LicenseView, _Mapping]] = ...) -> None: ...

class GetStatusRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class SystemStatus(_message.Message):
    __slots__ = ("throttling", "trading_enabled", "operational", "cash_limits", "order_pos_limit", "cash_limit", "license")
    THROTTLING_FIELD_NUMBER: _ClassVar[int]
    TRADING_ENABLED_FIELD_NUMBER: _ClassVar[int]
    OPERATIONAL_FIELD_NUMBER: _ClassVar[int]
    CASH_LIMITS_FIELD_NUMBER: _ClassVar[int]
    ORDER_POS_LIMIT_FIELD_NUMBER: _ClassVar[int]
    CASH_LIMIT_FIELD_NUMBER: _ClassVar[int]
    LICENSE_FIELD_NUMBER: _ClassVar[int]
    throttling: ThrottlingStatus
    trading_enabled: bool
    operational: bool
    cash_limits: _containers.RepeatedCompositeFieldContainer[CashLimit]
    order_pos_limit: int
    cash_limit: CashLimitStatus
    license: LicenseView
    def __init__(self, throttling: _Optional[_Union[ThrottlingStatus, _Mapping]] = ..., trading_enabled: bool = ..., operational: bool = ..., cash_limits: _Optional[_Iterable[_Union[CashLimit, _Mapping]]] = ..., order_pos_limit: _Optional[int] = ..., cash_limit: _Optional[_Union[CashLimitStatus, _Mapping]] = ..., license: _Optional[_Union[LicenseView, _Mapping]] = ...) -> None: ...

class CashLimitStatus(_message.Message):
    __slots__ = ("eur_limit_cents", "eur_consumed_cents", "eur_remaining_cents", "gbp_limit_cents", "gbp_consumed_cents", "gbp_remaining_cents")
    EUR_LIMIT_CENTS_FIELD_NUMBER: _ClassVar[int]
    EUR_CONSUMED_CENTS_FIELD_NUMBER: _ClassVar[int]
    EUR_REMAINING_CENTS_FIELD_NUMBER: _ClassVar[int]
    GBP_LIMIT_CENTS_FIELD_NUMBER: _ClassVar[int]
    GBP_CONSUMED_CENTS_FIELD_NUMBER: _ClassVar[int]
    GBP_REMAINING_CENTS_FIELD_NUMBER: _ClassVar[int]
    eur_limit_cents: int
    eur_consumed_cents: int
    eur_remaining_cents: int
    gbp_limit_cents: int
    gbp_consumed_cents: int
    gbp_remaining_cents: int
    def __init__(self, eur_limit_cents: _Optional[int] = ..., eur_consumed_cents: _Optional[int] = ..., eur_remaining_cents: _Optional[int] = ..., gbp_limit_cents: _Optional[int] = ..., gbp_consumed_cents: _Optional[int] = ..., gbp_remaining_cents: _Optional[int] = ...) -> None: ...

class LicenseView(_message.Message):
    __slots__ = ("status_kind", "status_days", "license_id", "mode", "environment", "expires_at", "issued_at", "schema_version", "issuer", "signing_key_id", "holder", "epex_any", "epex_identities")
    STATUS_KIND_FIELD_NUMBER: _ClassVar[int]
    STATUS_DAYS_FIELD_NUMBER: _ClassVar[int]
    LICENSE_ID_FIELD_NUMBER: _ClassVar[int]
    MODE_FIELD_NUMBER: _ClassVar[int]
    ENVIRONMENT_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    ISSUED_AT_FIELD_NUMBER: _ClassVar[int]
    SCHEMA_VERSION_FIELD_NUMBER: _ClassVar[int]
    ISSUER_FIELD_NUMBER: _ClassVar[int]
    SIGNING_KEY_ID_FIELD_NUMBER: _ClassVar[int]
    HOLDER_FIELD_NUMBER: _ClassVar[int]
    EPEX_ANY_FIELD_NUMBER: _ClassVar[int]
    EPEX_IDENTITIES_FIELD_NUMBER: _ClassVar[int]
    status_kind: str
    status_days: int
    license_id: str
    mode: str
    environment: str
    expires_at: str
    issued_at: str
    schema_version: int
    issuer: str
    signing_key_id: str
    holder: LicenseHolder
    epex_any: bool
    epex_identities: _containers.RepeatedCompositeFieldContainer[EpexIdentityView]
    def __init__(self, status_kind: _Optional[str] = ..., status_days: _Optional[int] = ..., license_id: _Optional[str] = ..., mode: _Optional[str] = ..., environment: _Optional[str] = ..., expires_at: _Optional[str] = ..., issued_at: _Optional[str] = ..., schema_version: _Optional[int] = ..., issuer: _Optional[str] = ..., signing_key_id: _Optional[str] = ..., holder: _Optional[_Union[LicenseHolder, _Mapping]] = ..., epex_any: bool = ..., epex_identities: _Optional[_Iterable[_Union[EpexIdentityView, _Mapping]]] = ...) -> None: ...

class LicenseHolder(_message.Message):
    __slots__ = ("legal_entity", "portal_user_id")
    LEGAL_ENTITY_FIELD_NUMBER: _ClassVar[int]
    PORTAL_USER_ID_FIELD_NUMBER: _ClassVar[int]
    legal_entity: str
    portal_user_id: str
    def __init__(self, legal_entity: _Optional[str] = ..., portal_user_id: _Optional[str] = ...) -> None: ...

class EpexIdentityView(_message.Message):
    __slots__ = ("account_id", "user_id")
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    account_id: str
    user_id: str
    def __init__(self, account_id: _Optional[str] = ..., user_id: _Optional[str] = ...) -> None: ...

class GetThrottlingRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ThrottlingStatus(_message.Message):
    __slots__ = ("mbr_id", "timestamp", "status", "short_observation_period", "short_tolerance_period", "short_reconnection_cool_down", "short_omt_limit_l1", "short_omt_limit_l2", "short_status", "short_current_omt_count", "long_observation_period", "long_tolerance_period", "long_reconnection_cool_down", "long_omt_limit_l1", "long_omt_limit_l2", "long_status", "long_current_omt_count")
    MBR_ID_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    SHORT_OBSERVATION_PERIOD_FIELD_NUMBER: _ClassVar[int]
    SHORT_TOLERANCE_PERIOD_FIELD_NUMBER: _ClassVar[int]
    SHORT_RECONNECTION_COOL_DOWN_FIELD_NUMBER: _ClassVar[int]
    SHORT_OMT_LIMIT_L1_FIELD_NUMBER: _ClassVar[int]
    SHORT_OMT_LIMIT_L2_FIELD_NUMBER: _ClassVar[int]
    SHORT_STATUS_FIELD_NUMBER: _ClassVar[int]
    SHORT_CURRENT_OMT_COUNT_FIELD_NUMBER: _ClassVar[int]
    LONG_OBSERVATION_PERIOD_FIELD_NUMBER: _ClassVar[int]
    LONG_TOLERANCE_PERIOD_FIELD_NUMBER: _ClassVar[int]
    LONG_RECONNECTION_COOL_DOWN_FIELD_NUMBER: _ClassVar[int]
    LONG_OMT_LIMIT_L1_FIELD_NUMBER: _ClassVar[int]
    LONG_OMT_LIMIT_L2_FIELD_NUMBER: _ClassVar[int]
    LONG_STATUS_FIELD_NUMBER: _ClassVar[int]
    LONG_CURRENT_OMT_COUNT_FIELD_NUMBER: _ClassVar[int]
    mbr_id: str
    timestamp: str
    status: str
    short_observation_period: int
    short_tolerance_period: int
    short_reconnection_cool_down: int
    short_omt_limit_l1: int
    short_omt_limit_l2: int
    short_status: str
    short_current_omt_count: int
    long_observation_period: int
    long_tolerance_period: int
    long_reconnection_cool_down: int
    long_omt_limit_l1: int
    long_omt_limit_l2: int
    long_status: str
    long_current_omt_count: int
    def __init__(self, mbr_id: _Optional[str] = ..., timestamp: _Optional[str] = ..., status: _Optional[str] = ..., short_observation_period: _Optional[int] = ..., short_tolerance_period: _Optional[int] = ..., short_reconnection_cool_down: _Optional[int] = ..., short_omt_limit_l1: _Optional[int] = ..., short_omt_limit_l2: _Optional[int] = ..., short_status: _Optional[str] = ..., short_current_omt_count: _Optional[int] = ..., long_observation_period: _Optional[int] = ..., long_tolerance_period: _Optional[int] = ..., long_reconnection_cool_down: _Optional[int] = ..., long_omt_limit_l1: _Optional[int] = ..., long_omt_limit_l2: _Optional[int] = ..., long_status: _Optional[str] = ..., long_current_omt_count: _Optional[int] = ...) -> None: ...

class GetSystemInfoRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class RequestLimit(_message.Message):
    __slots__ = ("message", "duration_ms", "rate")
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    DURATION_MS_FIELD_NUMBER: _ClassVar[int]
    RATE_FIELD_NUMBER: _ClassVar[int]
    message: str
    duration_ms: int
    rate: int
    def __init__(self, message: _Optional[str] = ..., duration_ms: _Optional[int] = ..., rate: _Optional[int] = ...) -> None: ...

class SystemInfo(_message.Message):
    __slots__ = ("market_id", "backend_version", "backend_time_zone", "backend_market_time_zone", "contract_store_time_in_days", "trade_pool_store_time_in_hours", "max_orders", "capabilities", "allowed_clearing_acct_types", "request_limits", "voltnir_version")
    MARKET_ID_FIELD_NUMBER: _ClassVar[int]
    BACKEND_VERSION_FIELD_NUMBER: _ClassVar[int]
    BACKEND_TIME_ZONE_FIELD_NUMBER: _ClassVar[int]
    BACKEND_MARKET_TIME_ZONE_FIELD_NUMBER: _ClassVar[int]
    CONTRACT_STORE_TIME_IN_DAYS_FIELD_NUMBER: _ClassVar[int]
    TRADE_POOL_STORE_TIME_IN_HOURS_FIELD_NUMBER: _ClassVar[int]
    MAX_ORDERS_FIELD_NUMBER: _ClassVar[int]
    CAPABILITIES_FIELD_NUMBER: _ClassVar[int]
    ALLOWED_CLEARING_ACCT_TYPES_FIELD_NUMBER: _ClassVar[int]
    REQUEST_LIMITS_FIELD_NUMBER: _ClassVar[int]
    VOLTNIR_VERSION_FIELD_NUMBER: _ClassVar[int]
    market_id: str
    backend_version: str
    backend_time_zone: str
    backend_market_time_zone: str
    contract_store_time_in_days: int
    trade_pool_store_time_in_hours: int
    max_orders: int
    capabilities: str
    allowed_clearing_acct_types: str
    request_limits: _containers.RepeatedCompositeFieldContainer[RequestLimit]
    voltnir_version: str
    def __init__(self, market_id: _Optional[str] = ..., backend_version: _Optional[str] = ..., backend_time_zone: _Optional[str] = ..., backend_market_time_zone: _Optional[str] = ..., contract_store_time_in_days: _Optional[int] = ..., trade_pool_store_time_in_hours: _Optional[int] = ..., max_orders: _Optional[int] = ..., capabilities: _Optional[str] = ..., allowed_clearing_acct_types: _Optional[str] = ..., request_limits: _Optional[_Iterable[_Union[RequestLimit, _Mapping]]] = ..., voltnir_version: _Optional[str] = ...) -> None: ...

class GetContractLimitRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class SetContractLimitRequest(_message.Message):
    __slots__ = ("quantity",)
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    quantity: int
    def __init__(self, quantity: _Optional[int] = ...) -> None: ...

class ContractLimitResponse(_message.Message):
    __slots__ = ("quantity",)
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    quantity: int
    def __init__(self, quantity: _Optional[int] = ...) -> None: ...

class GetCashLimitRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class SetCashLimitRequest(_message.Message):
    __slots__ = ("cents", "currency")
    CENTS_FIELD_NUMBER: _ClassVar[int]
    CURRENCY_FIELD_NUMBER: _ClassVar[int]
    cents: int
    currency: str
    def __init__(self, cents: _Optional[int] = ..., currency: _Optional[str] = ...) -> None: ...

class CashLimitResponse(_message.Message):
    __slots__ = ("cents", "gbp_cents")
    CENTS_FIELD_NUMBER: _ClassVar[int]
    GBP_CENTS_FIELD_NUMBER: _ClassVar[int]
    cents: int
    gbp_cents: int
    def __init__(self, cents: _Optional[int] = ..., gbp_cents: _Optional[int] = ...) -> None: ...

class GetCashFailClosedRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class SetCashFailClosedRequest(_message.Message):
    __slots__ = ("enabled",)
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    enabled: bool
    def __init__(self, enabled: bool = ...) -> None: ...

class CashFailClosedResponse(_message.Message):
    __slots__ = ("enabled",)
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    enabled: bool
    def __init__(self, enabled: bool = ...) -> None: ...

class Holiday(_message.Message):
    __slots__ = ("date", "label")
    DATE_FIELD_NUMBER: _ClassVar[int]
    LABEL_FIELD_NUMBER: _ClassVar[int]
    date: str
    label: str
    def __init__(self, date: _Optional[str] = ..., label: _Optional[str] = ...) -> None: ...

class GetHolidaysRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class HolidaysResponse(_message.Message):
    __slots__ = ("eur", "gbp")
    EUR_FIELD_NUMBER: _ClassVar[int]
    GBP_FIELD_NUMBER: _ClassVar[int]
    eur: _containers.RepeatedCompositeFieldContainer[Holiday]
    gbp: _containers.RepeatedCompositeFieldContainer[Holiday]
    def __init__(self, eur: _Optional[_Iterable[_Union[Holiday, _Mapping]]] = ..., gbp: _Optional[_Iterable[_Union[Holiday, _Mapping]]] = ...) -> None: ...

class SetHolidaysRequest(_message.Message):
    __slots__ = ("currency", "holidays")
    CURRENCY_FIELD_NUMBER: _ClassVar[int]
    HOLIDAYS_FIELD_NUMBER: _ClassVar[int]
    currency: str
    holidays: _containers.RepeatedCompositeFieldContainer[Holiday]
    def __init__(self, currency: _Optional[str] = ..., holidays: _Optional[_Iterable[_Union[Holiday, _Mapping]]] = ...) -> None: ...

class AddHolidayRequest(_message.Message):
    __slots__ = ("currency", "date", "label")
    CURRENCY_FIELD_NUMBER: _ClassVar[int]
    DATE_FIELD_NUMBER: _ClassVar[int]
    LABEL_FIELD_NUMBER: _ClassVar[int]
    currency: str
    date: str
    label: str
    def __init__(self, currency: _Optional[str] = ..., date: _Optional[str] = ..., label: _Optional[str] = ...) -> None: ...

class RemoveHolidayRequest(_message.Message):
    __slots__ = ("currency", "date")
    CURRENCY_FIELD_NUMBER: _ClassVar[int]
    DATE_FIELD_NUMBER: _ClassVar[int]
    currency: str
    date: str
    def __init__(self, currency: _Optional[str] = ..., date: _Optional[str] = ...) -> None: ...

class GetTradingAllowedRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class SetTradingAllowedRequest(_message.Message):
    __slots__ = ("allowed",)
    ALLOWED_FIELD_NUMBER: _ClassVar[int]
    allowed: bool
    def __init__(self, allowed: bool = ...) -> None: ...

class TradingAllowedResponse(_message.Message):
    __slots__ = ("allowed",)
    ALLOWED_FIELD_NUMBER: _ClassVar[int]
    allowed: bool
    def __init__(self, allowed: bool = ...) -> None: ...

class GetSelfTradePolicyRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class SetSelfTradePolicyRequest(_message.Message):
    __slots__ = ("policy",)
    POLICY_FIELD_NUMBER: _ClassVar[int]
    policy: SelfTradePolicy
    def __init__(self, policy: _Optional[_Union[SelfTradePolicy, str]] = ...) -> None: ...

class SelfTradePolicyResponse(_message.Message):
    __slots__ = ("policy",)
    POLICY_FIELD_NUMBER: _ClassVar[int]
    policy: SelfTradePolicy
    def __init__(self, policy: _Optional[_Union[SelfTradePolicy, str]] = ...) -> None: ...

class RestartRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class RestartResponse(_message.Message):
    __slots__ = ("message",)
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    message: str
    def __init__(self, message: _Optional[str] = ...) -> None: ...

class GetCashLimitsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class CashLimit(_message.Message):
    __slots__ = ("currency", "current_limit", "current_revision", "configured_limit", "dec_shft", "lmt_id", "state", "start_date", "revision_no")
    CURRENCY_FIELD_NUMBER: _ClassVar[int]
    CURRENT_LIMIT_FIELD_NUMBER: _ClassVar[int]
    CURRENT_REVISION_FIELD_NUMBER: _ClassVar[int]
    CONFIGURED_LIMIT_FIELD_NUMBER: _ClassVar[int]
    DEC_SHFT_FIELD_NUMBER: _ClassVar[int]
    LMT_ID_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    START_DATE_FIELD_NUMBER: _ClassVar[int]
    REVISION_NO_FIELD_NUMBER: _ClassVar[int]
    currency: str
    current_limit: int
    current_revision: int
    configured_limit: int
    dec_shft: int
    lmt_id: str
    state: str
    start_date: str
    revision_no: int
    def __init__(self, currency: _Optional[str] = ..., current_limit: _Optional[int] = ..., current_revision: _Optional[int] = ..., configured_limit: _Optional[int] = ..., dec_shft: _Optional[int] = ..., lmt_id: _Optional[str] = ..., state: _Optional[str] = ..., start_date: _Optional[str] = ..., revision_no: _Optional[int] = ...) -> None: ...

class GetCashLimitsResponse(_message.Message):
    __slots__ = ("limits",)
    LIMITS_FIELD_NUMBER: _ClassVar[int]
    limits: _containers.RepeatedCompositeFieldContainer[CashLimit]
    def __init__(self, limits: _Optional[_Iterable[_Union[CashLimit, _Mapping]]] = ...) -> None: ...

class ListPermissionsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class PermissionInfo(_message.Message):
    __slots__ = ("code", "description")
    CODE_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    code: str
    description: str
    def __init__(self, code: _Optional[str] = ..., description: _Optional[str] = ...) -> None: ...

class ListPermissionsResponse(_message.Message):
    __slots__ = ("permissions",)
    PERMISSIONS_FIELD_NUMBER: _ClassVar[int]
    permissions: _containers.RepeatedCompositeFieldContainer[PermissionInfo]
    def __init__(self, permissions: _Optional[_Iterable[_Union[PermissionInfo, _Mapping]]] = ...) -> None: ...

class GetPnlRequest(_message.Message):
    __slots__ = ("v_member_short_id",)
    V_MEMBER_SHORT_ID_FIELD_NUMBER: _ClassVar[int]
    v_member_short_id: str
    def __init__(self, v_member_short_id: _Optional[str] = ...) -> None: ...

class PnlSnapshot(_message.Message):
    __slots__ = ("per_contract", "per_area_prod", "per_vm", "per_vm_area_prod", "computed_at_ms", "compute_us")
    PER_CONTRACT_FIELD_NUMBER: _ClassVar[int]
    PER_AREA_PROD_FIELD_NUMBER: _ClassVar[int]
    PER_VM_FIELD_NUMBER: _ClassVar[int]
    PER_VM_AREA_PROD_FIELD_NUMBER: _ClassVar[int]
    COMPUTED_AT_MS_FIELD_NUMBER: _ClassVar[int]
    COMPUTE_US_FIELD_NUMBER: _ClassVar[int]
    per_contract: _containers.RepeatedCompositeFieldContainer[ContractPnl]
    per_area_prod: _containers.RepeatedCompositeFieldContainer[AreaProductPnl]
    per_vm: _containers.RepeatedCompositeFieldContainer[VmContractPnl]
    per_vm_area_prod: _containers.RepeatedCompositeFieldContainer[VmAreaProductPnl]
    computed_at_ms: int
    compute_us: int
    def __init__(self, per_contract: _Optional[_Iterable[_Union[ContractPnl, _Mapping]]] = ..., per_area_prod: _Optional[_Iterable[_Union[AreaProductPnl, _Mapping]]] = ..., per_vm: _Optional[_Iterable[_Union[VmContractPnl, _Mapping]]] = ..., per_vm_area_prod: _Optional[_Iterable[_Union[VmAreaProductPnl, _Mapping]]] = ..., computed_at_ms: _Optional[int] = ..., compute_us: _Optional[int] = ...) -> None: ...

class ContractPnl(_message.Message):
    __slots__ = ("area_id", "contract_id", "product", "signed_position", "avg_open_px", "mark_px", "mark_source", "realized_pnl", "unrealized_pnl")
    AREA_ID_FIELD_NUMBER: _ClassVar[int]
    CONTRACT_ID_FIELD_NUMBER: _ClassVar[int]
    PRODUCT_FIELD_NUMBER: _ClassVar[int]
    SIGNED_POSITION_FIELD_NUMBER: _ClassVar[int]
    AVG_OPEN_PX_FIELD_NUMBER: _ClassVar[int]
    MARK_PX_FIELD_NUMBER: _ClassVar[int]
    MARK_SOURCE_FIELD_NUMBER: _ClassVar[int]
    REALIZED_PNL_FIELD_NUMBER: _ClassVar[int]
    UNREALIZED_PNL_FIELD_NUMBER: _ClassVar[int]
    area_id: str
    contract_id: int
    product: str
    signed_position: int
    avg_open_px: int
    mark_px: int
    mark_source: MarkSource
    realized_pnl: int
    unrealized_pnl: int
    def __init__(self, area_id: _Optional[str] = ..., contract_id: _Optional[int] = ..., product: _Optional[str] = ..., signed_position: _Optional[int] = ..., avg_open_px: _Optional[int] = ..., mark_px: _Optional[int] = ..., mark_source: _Optional[_Union[MarkSource, str]] = ..., realized_pnl: _Optional[int] = ..., unrealized_pnl: _Optional[int] = ...) -> None: ...

class AreaProductPnl(_message.Message):
    __slots__ = ("area_id", "product", "realized_pnl", "unrealized_pnl")
    AREA_ID_FIELD_NUMBER: _ClassVar[int]
    PRODUCT_FIELD_NUMBER: _ClassVar[int]
    REALIZED_PNL_FIELD_NUMBER: _ClassVar[int]
    UNREALIZED_PNL_FIELD_NUMBER: _ClassVar[int]
    area_id: str
    product: str
    realized_pnl: int
    unrealized_pnl: int
    def __init__(self, area_id: _Optional[str] = ..., product: _Optional[str] = ..., realized_pnl: _Optional[int] = ..., unrealized_pnl: _Optional[int] = ...) -> None: ...

class VmContractPnl(_message.Message):
    __slots__ = ("v_member_short_id", "area_id", "contract_id", "product", "signed_position", "avg_open_px", "mark_px", "mark_source", "realized_pnl", "unrealized_pnl")
    V_MEMBER_SHORT_ID_FIELD_NUMBER: _ClassVar[int]
    AREA_ID_FIELD_NUMBER: _ClassVar[int]
    CONTRACT_ID_FIELD_NUMBER: _ClassVar[int]
    PRODUCT_FIELD_NUMBER: _ClassVar[int]
    SIGNED_POSITION_FIELD_NUMBER: _ClassVar[int]
    AVG_OPEN_PX_FIELD_NUMBER: _ClassVar[int]
    MARK_PX_FIELD_NUMBER: _ClassVar[int]
    MARK_SOURCE_FIELD_NUMBER: _ClassVar[int]
    REALIZED_PNL_FIELD_NUMBER: _ClassVar[int]
    UNREALIZED_PNL_FIELD_NUMBER: _ClassVar[int]
    v_member_short_id: str
    area_id: str
    contract_id: int
    product: str
    signed_position: int
    avg_open_px: int
    mark_px: int
    mark_source: MarkSource
    realized_pnl: int
    unrealized_pnl: int
    def __init__(self, v_member_short_id: _Optional[str] = ..., area_id: _Optional[str] = ..., contract_id: _Optional[int] = ..., product: _Optional[str] = ..., signed_position: _Optional[int] = ..., avg_open_px: _Optional[int] = ..., mark_px: _Optional[int] = ..., mark_source: _Optional[_Union[MarkSource, str]] = ..., realized_pnl: _Optional[int] = ..., unrealized_pnl: _Optional[int] = ...) -> None: ...

class VmAreaProductPnl(_message.Message):
    __slots__ = ("v_member_short_id", "area_id", "product", "realized_pnl", "unrealized_pnl")
    V_MEMBER_SHORT_ID_FIELD_NUMBER: _ClassVar[int]
    AREA_ID_FIELD_NUMBER: _ClassVar[int]
    PRODUCT_FIELD_NUMBER: _ClassVar[int]
    REALIZED_PNL_FIELD_NUMBER: _ClassVar[int]
    UNREALIZED_PNL_FIELD_NUMBER: _ClassVar[int]
    v_member_short_id: str
    area_id: str
    product: str
    realized_pnl: int
    unrealized_pnl: int
    def __init__(self, v_member_short_id: _Optional[str] = ..., area_id: _Optional[str] = ..., product: _Optional[str] = ..., realized_pnl: _Optional[int] = ..., unrealized_pnl: _Optional[int] = ...) -> None: ...

class ListPublicTradesRequest(_message.Message):
    __slots__ = ("limit", "contract_id", "area_id")
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    CONTRACT_ID_FIELD_NUMBER: _ClassVar[int]
    AREA_ID_FIELD_NUMBER: _ClassVar[int]
    limit: int
    contract_id: int
    area_id: str
    def __init__(self, limit: _Optional[int] = ..., contract_id: _Optional[int] = ..., area_id: _Optional[str] = ...) -> None: ...

class PublicTrade(_message.Message):
    __slots__ = ("trade_id", "contract_id", "qty", "px", "exec_time", "exec_time_ms", "revision_no", "state", "buy_dlvry_area", "sell_dlvry_area", "self_trade")
    TRADE_ID_FIELD_NUMBER: _ClassVar[int]
    CONTRACT_ID_FIELD_NUMBER: _ClassVar[int]
    QTY_FIELD_NUMBER: _ClassVar[int]
    PX_FIELD_NUMBER: _ClassVar[int]
    EXEC_TIME_FIELD_NUMBER: _ClassVar[int]
    EXEC_TIME_MS_FIELD_NUMBER: _ClassVar[int]
    REVISION_NO_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    BUY_DLVRY_AREA_FIELD_NUMBER: _ClassVar[int]
    SELL_DLVRY_AREA_FIELD_NUMBER: _ClassVar[int]
    SELF_TRADE_FIELD_NUMBER: _ClassVar[int]
    trade_id: str
    contract_id: int
    qty: int
    px: int
    exec_time: str
    exec_time_ms: int
    revision_no: int
    state: str
    buy_dlvry_area: str
    sell_dlvry_area: str
    self_trade: bool
    def __init__(self, trade_id: _Optional[str] = ..., contract_id: _Optional[int] = ..., qty: _Optional[int] = ..., px: _Optional[int] = ..., exec_time: _Optional[str] = ..., exec_time_ms: _Optional[int] = ..., revision_no: _Optional[int] = ..., state: _Optional[str] = ..., buy_dlvry_area: _Optional[str] = ..., sell_dlvry_area: _Optional[str] = ..., self_trade: bool = ...) -> None: ...

class ListPublicTradesResponse(_message.Message):
    __slots__ = ("trades",)
    TRADES_FIELD_NUMBER: _ClassVar[int]
    trades: _containers.RepeatedCompositeFieldContainer[PublicTrade]
    def __init__(self, trades: _Optional[_Iterable[_Union[PublicTrade, _Mapping]]] = ...) -> None: ...

class GetMeRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetMyMembersRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ListUsersRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ListUsersResponse(_message.Message):
    __slots__ = ("users",)
    USERS_FIELD_NUMBER: _ClassVar[int]
    users: _containers.RepeatedCompositeFieldContainer[UserProfile]
    def __init__(self, users: _Optional[_Iterable[_Union[UserProfile, _Mapping]]] = ...) -> None: ...

class CreateUserRequest(_message.Message):
    __slots__ = ("username", "permissions")
    USERNAME_FIELD_NUMBER: _ClassVar[int]
    PERMISSIONS_FIELD_NUMBER: _ClassVar[int]
    username: str
    permissions: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, username: _Optional[str] = ..., permissions: _Optional[_Iterable[str]] = ...) -> None: ...

class CreateUserResponse(_message.Message):
    __slots__ = ("user", "api_key")
    USER_FIELD_NUMBER: _ClassVar[int]
    API_KEY_FIELD_NUMBER: _ClassVar[int]
    user: UserProfile
    api_key: str
    def __init__(self, user: _Optional[_Union[UserProfile, _Mapping]] = ..., api_key: _Optional[str] = ...) -> None: ...

class DeleteUserRequest(_message.Message):
    __slots__ = ("user_id",)
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    def __init__(self, user_id: _Optional[str] = ...) -> None: ...

class SetPermissionsRequest(_message.Message):
    __slots__ = ("user_id", "permissions")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    PERMISSIONS_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    permissions: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, user_id: _Optional[str] = ..., permissions: _Optional[_Iterable[str]] = ...) -> None: ...

class RotateApiKeyRequest(_message.Message):
    __slots__ = ("user_id",)
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    def __init__(self, user_id: _Optional[str] = ...) -> None: ...

class RotateApiKeyResponse(_message.Message):
    __slots__ = ("api_key",)
    API_KEY_FIELD_NUMBER: _ClassVar[int]
    api_key: str
    def __init__(self, api_key: _Optional[str] = ...) -> None: ...

class GetUserMembersRequest(_message.Message):
    __slots__ = ("user_id",)
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    def __init__(self, user_id: _Optional[str] = ...) -> None: ...

class UserMembersResponse(_message.Message):
    __slots__ = ("member_ids",)
    MEMBER_IDS_FIELD_NUMBER: _ClassVar[int]
    member_ids: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, member_ids: _Optional[_Iterable[str]] = ...) -> None: ...

class SetUserMembersRequest(_message.Message):
    __slots__ = ("user_id", "member_ids")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    MEMBER_IDS_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    member_ids: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, user_id: _Optional[str] = ..., member_ids: _Optional[_Iterable[str]] = ...) -> None: ...

class ListMembersRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class MemberListResponse(_message.Message):
    __slots__ = ("members",)
    MEMBERS_FIELD_NUMBER: _ClassVar[int]
    members: _containers.RepeatedCompositeFieldContainer[Member]
    def __init__(self, members: _Optional[_Iterable[_Union[Member, _Mapping]]] = ...) -> None: ...

class CreateMemberRequest(_message.Message):
    __slots__ = ("name", "max_position", "cash_limit", "cash_limit_gbp")
    NAME_FIELD_NUMBER: _ClassVar[int]
    MAX_POSITION_FIELD_NUMBER: _ClassVar[int]
    CASH_LIMIT_FIELD_NUMBER: _ClassVar[int]
    CASH_LIMIT_GBP_FIELD_NUMBER: _ClassVar[int]
    name: str
    max_position: int
    cash_limit: int
    cash_limit_gbp: int
    def __init__(self, name: _Optional[str] = ..., max_position: _Optional[int] = ..., cash_limit: _Optional[int] = ..., cash_limit_gbp: _Optional[int] = ...) -> None: ...

class PatchMemberRequest(_message.Message):
    __slots__ = ("id", "name", "max_position", "active", "cash_limit", "cash_limit_gbp")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    MAX_POSITION_FIELD_NUMBER: _ClassVar[int]
    ACTIVE_FIELD_NUMBER: _ClassVar[int]
    CASH_LIMIT_FIELD_NUMBER: _ClassVar[int]
    CASH_LIMIT_GBP_FIELD_NUMBER: _ClassVar[int]
    id: str
    name: _wrappers_pb2.StringValue
    max_position: _wrappers_pb2.Int64Value
    active: _wrappers_pb2.BoolValue
    cash_limit: _wrappers_pb2.Int64Value
    cash_limit_gbp: _wrappers_pb2.Int64Value
    def __init__(self, id: _Optional[str] = ..., name: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., max_position: _Optional[_Union[_wrappers_pb2.Int64Value, _Mapping]] = ..., active: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ..., cash_limit: _Optional[_Union[_wrappers_pb2.Int64Value, _Mapping]] = ..., cash_limit_gbp: _Optional[_Union[_wrappers_pb2.Int64Value, _Mapping]] = ...) -> None: ...

class AuditOrdersRequest(_message.Message):
    __slots__ = ("cursor", "limit", "date_from", "date_to", "area", "product", "status", "user_code", "v_member_short_id", "voltnir_user_short_id", "voltnir_username")
    CURSOR_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    DATE_FROM_FIELD_NUMBER: _ClassVar[int]
    DATE_TO_FIELD_NUMBER: _ClassVar[int]
    AREA_FIELD_NUMBER: _ClassVar[int]
    PRODUCT_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    USER_CODE_FIELD_NUMBER: _ClassVar[int]
    V_MEMBER_SHORT_ID_FIELD_NUMBER: _ClassVar[int]
    VOLTNIR_USER_SHORT_ID_FIELD_NUMBER: _ClassVar[int]
    VOLTNIR_USERNAME_FIELD_NUMBER: _ClassVar[int]
    cursor: str
    limit: int
    date_from: str
    date_to: str
    area: str
    product: str
    status: str
    user_code: str
    v_member_short_id: str
    voltnir_user_short_id: str
    voltnir_username: str
    def __init__(self, cursor: _Optional[str] = ..., limit: _Optional[int] = ..., date_from: _Optional[str] = ..., date_to: _Optional[str] = ..., area: _Optional[str] = ..., product: _Optional[str] = ..., status: _Optional[str] = ..., user_code: _Optional[str] = ..., v_member_short_id: _Optional[str] = ..., voltnir_user_short_id: _Optional[str] = ..., voltnir_username: _Optional[str] = ...) -> None: ...

class AuditOrderItem(_message.Message):
    __slots__ = ("json",)
    JSON_FIELD_NUMBER: _ClassVar[int]
    json: str
    def __init__(self, json: _Optional[str] = ...) -> None: ...

class AuditOrdersResponse(_message.Message):
    __slots__ = ("items", "next_cursor", "total_hint")
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    NEXT_CURSOR_FIELD_NUMBER: _ClassVar[int]
    TOTAL_HINT_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[AuditOrderItem]
    next_cursor: str
    total_hint: int
    def __init__(self, items: _Optional[_Iterable[_Union[AuditOrderItem, _Mapping]]] = ..., next_cursor: _Optional[str] = ..., total_hint: _Optional[int] = ...) -> None: ...

class AuditTradesRequest(_message.Message):
    __slots__ = ("cursor", "limit", "date_from", "date_to", "area", "product", "user_code", "v_member_short_id", "time_basis", "voltnir_user_short_id", "voltnir_username")
    CURSOR_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    DATE_FROM_FIELD_NUMBER: _ClassVar[int]
    DATE_TO_FIELD_NUMBER: _ClassVar[int]
    AREA_FIELD_NUMBER: _ClassVar[int]
    PRODUCT_FIELD_NUMBER: _ClassVar[int]
    USER_CODE_FIELD_NUMBER: _ClassVar[int]
    V_MEMBER_SHORT_ID_FIELD_NUMBER: _ClassVar[int]
    TIME_BASIS_FIELD_NUMBER: _ClassVar[int]
    VOLTNIR_USER_SHORT_ID_FIELD_NUMBER: _ClassVar[int]
    VOLTNIR_USERNAME_FIELD_NUMBER: _ClassVar[int]
    cursor: str
    limit: int
    date_from: str
    date_to: str
    area: str
    product: str
    user_code: str
    v_member_short_id: str
    time_basis: str
    voltnir_user_short_id: str
    voltnir_username: str
    def __init__(self, cursor: _Optional[str] = ..., limit: _Optional[int] = ..., date_from: _Optional[str] = ..., date_to: _Optional[str] = ..., area: _Optional[str] = ..., product: _Optional[str] = ..., user_code: _Optional[str] = ..., v_member_short_id: _Optional[str] = ..., time_basis: _Optional[str] = ..., voltnir_user_short_id: _Optional[str] = ..., voltnir_username: _Optional[str] = ...) -> None: ...

class AuditTradeItem(_message.Message):
    __slots__ = ("json",)
    JSON_FIELD_NUMBER: _ClassVar[int]
    json: str
    def __init__(self, json: _Optional[str] = ...) -> None: ...

class AuditTradesResponse(_message.Message):
    __slots__ = ("items", "next_cursor", "total_hint")
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    NEXT_CURSOR_FIELD_NUMBER: _ClassVar[int]
    TOTAL_HINT_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[AuditTradeItem]
    next_cursor: str
    total_hint: int
    def __init__(self, items: _Optional[_Iterable[_Union[AuditTradeItem, _Mapping]]] = ..., next_cursor: _Optional[str] = ..., total_hint: _Optional[int] = ...) -> None: ...

class AuditPublicTradesRequest(_message.Message):
    __slots__ = ("cursor", "limit", "date_from", "date_to", "area", "product", "state")
    CURSOR_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    DATE_FROM_FIELD_NUMBER: _ClassVar[int]
    DATE_TO_FIELD_NUMBER: _ClassVar[int]
    AREA_FIELD_NUMBER: _ClassVar[int]
    PRODUCT_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    cursor: str
    limit: int
    date_from: str
    date_to: str
    area: str
    product: str
    state: str
    def __init__(self, cursor: _Optional[str] = ..., limit: _Optional[int] = ..., date_from: _Optional[str] = ..., date_to: _Optional[str] = ..., area: _Optional[str] = ..., product: _Optional[str] = ..., state: _Optional[str] = ...) -> None: ...

class AuditPublicTradeItem(_message.Message):
    __slots__ = ("json",)
    JSON_FIELD_NUMBER: _ClassVar[int]
    json: str
    def __init__(self, json: _Optional[str] = ...) -> None: ...

class AuditPublicTradesResponse(_message.Message):
    __slots__ = ("items", "next_cursor", "total_hint")
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    NEXT_CURSOR_FIELD_NUMBER: _ClassVar[int]
    TOTAL_HINT_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[AuditPublicTradeItem]
    next_cursor: str
    total_hint: int
    def __init__(self, items: _Optional[_Iterable[_Union[AuditPublicTradeItem, _Mapping]]] = ..., next_cursor: _Optional[str] = ..., total_hint: _Optional[int] = ...) -> None: ...

class AuditEventsRequest(_message.Message):
    __slots__ = ("cursor", "limit", "date_from", "date_to", "action", "target_type", "actor_short_id", "outcome")
    CURSOR_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    DATE_FROM_FIELD_NUMBER: _ClassVar[int]
    DATE_TO_FIELD_NUMBER: _ClassVar[int]
    ACTION_FIELD_NUMBER: _ClassVar[int]
    TARGET_TYPE_FIELD_NUMBER: _ClassVar[int]
    ACTOR_SHORT_ID_FIELD_NUMBER: _ClassVar[int]
    OUTCOME_FIELD_NUMBER: _ClassVar[int]
    cursor: str
    limit: int
    date_from: str
    date_to: str
    action: str
    target_type: str
    actor_short_id: str
    outcome: str
    def __init__(self, cursor: _Optional[str] = ..., limit: _Optional[int] = ..., date_from: _Optional[str] = ..., date_to: _Optional[str] = ..., action: _Optional[str] = ..., target_type: _Optional[str] = ..., actor_short_id: _Optional[str] = ..., outcome: _Optional[str] = ...) -> None: ...

class AuditEventItem(_message.Message):
    __slots__ = ("json",)
    JSON_FIELD_NUMBER: _ClassVar[int]
    json: str
    def __init__(self, json: _Optional[str] = ...) -> None: ...

class AuditEventsResponse(_message.Message):
    __slots__ = ("items", "next_cursor", "total_hint")
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    NEXT_CURSOR_FIELD_NUMBER: _ClassVar[int]
    TOTAL_HINT_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[AuditEventItem]
    next_cursor: str
    total_hint: int
    def __init__(self, items: _Optional[_Iterable[_Union[AuditEventItem, _Mapping]]] = ..., next_cursor: _Optional[str] = ..., total_hint: _Optional[int] = ...) -> None: ...

class M7ErrorsRequest(_message.Message):
    __slots__ = ("cursor", "limit", "date_from", "date_to", "kind", "category", "err_code")
    CURSOR_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    DATE_FROM_FIELD_NUMBER: _ClassVar[int]
    DATE_TO_FIELD_NUMBER: _ClassVar[int]
    KIND_FIELD_NUMBER: _ClassVar[int]
    CATEGORY_FIELD_NUMBER: _ClassVar[int]
    ERR_CODE_FIELD_NUMBER: _ClassVar[int]
    cursor: str
    limit: int
    date_from: str
    date_to: str
    kind: str
    category: str
    err_code: int
    def __init__(self, cursor: _Optional[str] = ..., limit: _Optional[int] = ..., date_from: _Optional[str] = ..., date_to: _Optional[str] = ..., kind: _Optional[str] = ..., category: _Optional[str] = ..., err_code: _Optional[int] = ...) -> None: ...

class M7ErrorItem(_message.Message):
    __slots__ = ("json",)
    JSON_FIELD_NUMBER: _ClassVar[int]
    json: str
    def __init__(self, json: _Optional[str] = ...) -> None: ...

class M7ErrorsResponse(_message.Message):
    __slots__ = ("items", "next_cursor", "total_hint")
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    NEXT_CURSOR_FIELD_NUMBER: _ClassVar[int]
    TOTAL_HINT_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[M7ErrorItem]
    next_cursor: str
    total_hint: int
    def __init__(self, items: _Optional[_Iterable[_Union[M7ErrorItem, _Mapping]]] = ..., next_cursor: _Optional[str] = ..., total_hint: _Optional[int] = ...) -> None: ...

class ExportRequest(_message.Message):
    __slots__ = ("format", "to", "area", "product")
    FORMAT_FIELD_NUMBER: _ClassVar[int]
    FROM_FIELD_NUMBER: _ClassVar[int]
    TO_FIELD_NUMBER: _ClassVar[int]
    AREA_FIELD_NUMBER: _ClassVar[int]
    PRODUCT_FIELD_NUMBER: _ClassVar[int]
    format: ExportFormat
    to: str
    area: str
    product: str
    def __init__(self, format: _Optional[_Union[ExportFormat, str]] = ..., to: _Optional[str] = ..., area: _Optional[str] = ..., product: _Optional[str] = ..., **kwargs) -> None: ...

class ExportChunk(_message.Message):
    __slots__ = ("data",)
    DATA_FIELD_NUMBER: _ClassVar[int]
    data: bytes
    def __init__(self, data: _Optional[bytes] = ...) -> None: ...

class WatchContractRequest(_message.Message):
    __slots__ = ("area_id", "contract_id")
    AREA_ID_FIELD_NUMBER: _ClassVar[int]
    CONTRACT_ID_FIELD_NUMBER: _ClassVar[int]
    area_id: str
    contract_id: str
    def __init__(self, area_id: _Optional[str] = ..., contract_id: _Optional[str] = ...) -> None: ...

class ContractEvent(_message.Message):
    __slots__ = ("type", "contract")
    class EventType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        SNAPSHOT: _ClassVar[ContractEvent.EventType]
        ORDER_BOOK_UPDATE: _ClassVar[ContractEvent.EventType]
        STATE_CHANGE: _ClassVar[ContractEvent.EventType]
        TRADE: _ClassVar[ContractEvent.EventType]
    SNAPSHOT: ContractEvent.EventType
    ORDER_BOOK_UPDATE: ContractEvent.EventType
    STATE_CHANGE: ContractEvent.EventType
    TRADE: ContractEvent.EventType
    TYPE_FIELD_NUMBER: _ClassVar[int]
    CONTRACT_FIELD_NUMBER: _ClassVar[int]
    type: ContractEvent.EventType
    contract: Contract
    def __init__(self, type: _Optional[_Union[ContractEvent.EventType, str]] = ..., contract: _Optional[_Union[Contract, _Mapping]] = ...) -> None: ...

class WatchOrderRequest(_message.Message):
    __slots__ = ("client_order_id",)
    CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    client_order_id: str
    def __init__(self, client_order_id: _Optional[str] = ...) -> None: ...

class OrderEvent(_message.Message):
    __slots__ = ("type", "order")
    class EventType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        SNAPSHOT: _ClassVar[OrderEvent.EventType]
        UPDATE: _ClassVar[OrderEvent.EventType]
        FILLED: _ClassVar[OrderEvent.EventType]
        CANCELLED: _ClassVar[OrderEvent.EventType]
        REJECTED: _ClassVar[OrderEvent.EventType]
    SNAPSHOT: OrderEvent.EventType
    UPDATE: OrderEvent.EventType
    FILLED: OrderEvent.EventType
    CANCELLED: OrderEvent.EventType
    REJECTED: OrderEvent.EventType
    TYPE_FIELD_NUMBER: _ClassVar[int]
    ORDER_FIELD_NUMBER: _ClassVar[int]
    type: OrderEvent.EventType
    order: OwnOrder
    def __init__(self, type: _Optional[_Union[OrderEvent.EventType, str]] = ..., order: _Optional[_Union[OwnOrder, _Mapping]] = ...) -> None: ...

class WatchOrdersRequest(_message.Message):
    __slots__ = ("delivery_area", "contract_id", "v_member_short_id")
    DELIVERY_AREA_FIELD_NUMBER: _ClassVar[int]
    CONTRACT_ID_FIELD_NUMBER: _ClassVar[int]
    V_MEMBER_SHORT_ID_FIELD_NUMBER: _ClassVar[int]
    delivery_area: str
    contract_id: str
    v_member_short_id: str
    def __init__(self, delivery_area: _Optional[str] = ..., contract_id: _Optional[str] = ..., v_member_short_id: _Optional[str] = ...) -> None: ...

class OrdersEvent(_message.Message):
    __slots__ = ("type", "orders")
    class EventType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        SNAPSHOT: _ClassVar[OrdersEvent.EventType]
        ADDED: _ClassVar[OrdersEvent.EventType]
        MODIFIED: _ClassVar[OrdersEvent.EventType]
        CANCELLED: _ClassVar[OrdersEvent.EventType]
        FILLED: _ClassVar[OrdersEvent.EventType]
    SNAPSHOT: OrdersEvent.EventType
    ADDED: OrdersEvent.EventType
    MODIFIED: OrdersEvent.EventType
    CANCELLED: OrdersEvent.EventType
    FILLED: OrdersEvent.EventType
    TYPE_FIELD_NUMBER: _ClassVar[int]
    ORDERS_FIELD_NUMBER: _ClassVar[int]
    type: OrdersEvent.EventType
    orders: _containers.RepeatedCompositeFieldContainer[OwnOrder]
    def __init__(self, type: _Optional[_Union[OrdersEvent.EventType, str]] = ..., orders: _Optional[_Iterable[_Union[OwnOrder, _Mapping]]] = ...) -> None: ...

class WatchTradesRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class TradeEvent(_message.Message):
    __slots__ = ("type", "trades")
    class EventType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        SNAPSHOT: _ClassVar[TradeEvent.EventType]
        UPSERTED: _ClassVar[TradeEvent.EventType]
    SNAPSHOT: TradeEvent.EventType
    UPSERTED: TradeEvent.EventType
    TYPE_FIELD_NUMBER: _ClassVar[int]
    TRADES_FIELD_NUMBER: _ClassVar[int]
    type: TradeEvent.EventType
    trades: _containers.RepeatedCompositeFieldContainer[OwnTrade]
    def __init__(self, type: _Optional[_Union[TradeEvent.EventType, str]] = ..., trades: _Optional[_Iterable[_Union[OwnTrade, _Mapping]]] = ...) -> None: ...

class WatchPublicTradesRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class WatchPnlRequest(_message.Message):
    __slots__ = ("v_member_short_id",)
    V_MEMBER_SHORT_ID_FIELD_NUMBER: _ClassVar[int]
    v_member_short_id: str
    def __init__(self, v_member_short_id: _Optional[str] = ...) -> None: ...

class WatchStateRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class WatchStatusRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class WatchMessagesRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class MessageItem(_message.Message):
    __slots__ = ("json",)
    JSON_FIELD_NUMBER: _ClassVar[int]
    json: str
    def __init__(self, json: _Optional[str] = ...) -> None: ...

class WatchAuditEventsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class WatchM7ErrorsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...
