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

class SlotLimitMode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SLOT_LIMIT_MODE_UNSPECIFIED: _ClassVar[SlotLimitMode]
    SLOT_LIMIT_MODE_OFF: _ClassVar[SlotLimitMode]
    SLOT_LIMIT_MODE_OBSERVE: _ClassVar[SlotLimitMode]
    SLOT_LIMIT_MODE_REJECT: _ClassVar[SlotLimitMode]

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

class MarkSource(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    MARK_SOURCE_UNSPECIFIED: _ClassVar[MarkSource]
    MARK_SOURCE_MID: _ClassVar[MarkSource]
    MARK_SOURCE_LAST: _ClassVar[MarkSource]
    MARK_SOURCE_NONE: _ClassVar[MarkSource]
    MARK_SOURCE_CLOSE: _ClassVar[MarkSource]
    MARK_SOURCE_CLOSE_LAST: _ClassVar[MarkSource]

class Outcome(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    CONFIRMED: _ClassVar[Outcome]
    ACKNOWLEDGED: _ClassVar[Outcome]

class DeliveryRiskSource(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    DELIVERY_RISK_SOURCE_UNSPECIFIED: _ClassVar[DeliveryRiskSource]
    DELIVERY_RISK_SOURCE_CONFIG: _ClassVar[DeliveryRiskSource]
    DELIVERY_RISK_SOURCE_EXCHANGE: _ClassVar[DeliveryRiskSource]

class AreaClass(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    AREA_CLASS_UNSPECIFIED: _ClassVar[AreaClass]
    AREA_CLASS_BIDDING_ZONE: _ClassVar[AreaClass]
    AREA_CLASS_VIRTUAL_OPTIMISATION: _ClassVar[AreaClass]
    AREA_CLASS_BORDER_COUPLING: _ClassVar[AreaClass]
    AREA_CLASS_CONTROL_AREA: _ClassVar[AreaClass]

class AreaNameSource(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    AREA_NAME_SOURCE_STATIC: _ClassVar[AreaNameSource]
    AREA_NAME_SOURCE_EXCHANGE: _ClassVar[AreaNameSource]

class ProductScaleClass(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    PRODUCT_SCALE_CLASS_UNSPECIFIED: _ClassVar[ProductScaleClass]
    PRODUCT_SCALE_CLASS_REPRESENTABLE: _ClassVar[ProductScaleClass]
    PRODUCT_SCALE_CLASS_UNREPRESENTABLE: _ClassVar[ProductScaleClass]
    PRODUCT_SCALE_CLASS_UNKNOWN: _ClassVar[ProductScaleClass]
SIDE_UNSPECIFIED: Side
BUY: Side
SELL: Side
SELF_TRADE_POLICY_UNSPECIFIED: SelfTradePolicy
SELF_TRADE_POLICY_OBSERVE: SelfTradePolicy
SELF_TRADE_POLICY_REJECT: SelfTradePolicy
SLOT_LIMIT_MODE_UNSPECIFIED: SlotLimitMode
SLOT_LIMIT_MODE_OFF: SlotLimitMode
SLOT_LIMIT_MODE_OBSERVE: SlotLimitMode
SLOT_LIMIT_MODE_REJECT: SlotLimitMode
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
MARK_SOURCE_UNSPECIFIED: MarkSource
MARK_SOURCE_MID: MarkSource
MARK_SOURCE_LAST: MarkSource
MARK_SOURCE_NONE: MarkSource
MARK_SOURCE_CLOSE: MarkSource
MARK_SOURCE_CLOSE_LAST: MarkSource
CONFIRMED: Outcome
ACKNOWLEDGED: Outcome
DELIVERY_RISK_SOURCE_UNSPECIFIED: DeliveryRiskSource
DELIVERY_RISK_SOURCE_CONFIG: DeliveryRiskSource
DELIVERY_RISK_SOURCE_EXCHANGE: DeliveryRiskSource
AREA_CLASS_UNSPECIFIED: AreaClass
AREA_CLASS_BIDDING_ZONE: AreaClass
AREA_CLASS_VIRTUAL_OPTIMISATION: AreaClass
AREA_CLASS_BORDER_COUPLING: AreaClass
AREA_CLASS_CONTROL_AREA: AreaClass
AREA_NAME_SOURCE_STATIC: AreaNameSource
AREA_NAME_SOURCE_EXCHANGE: AreaNameSource
PRODUCT_SCALE_CLASS_UNSPECIFIED: ProductScaleClass
PRODUCT_SCALE_CLASS_REPRESENTABLE: ProductScaleClass
PRODUCT_SCALE_CLASS_UNREPRESENTABLE: ProductScaleClass
PRODUCT_SCALE_CLASS_UNKNOWN: ProductScaleClass

class OwnOrder(_message.Message):
    __slots__ = ("order_id", "initial_order_id", "parent_order_id", "revision", "account_id", "contract_id", "delivery_area", "side", "price", "quantity", "initial_quantity", "hidden_quantity", "displayed_quantity", "order_type", "state", "action", "client_order_id", "user_code", "pre_arranged", "timestamp_ms", "validity_time_ms", "last_update_time_ms", "text", "basket_id", "v_member_short_id", "remote_order_id", "voltnir_user_short_id", "voltnir_username", "v_member_name", "basket_ref", "list_exec_inst")
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
    REMOTE_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    VOLTNIR_USER_SHORT_ID_FIELD_NUMBER: _ClassVar[int]
    VOLTNIR_USERNAME_FIELD_NUMBER: _ClassVar[int]
    V_MEMBER_NAME_FIELD_NUMBER: _ClassVar[int]
    BASKET_REF_FIELD_NUMBER: _ClassVar[int]
    LIST_EXEC_INST_FIELD_NUMBER: _ClassVar[int]
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
    remote_order_id: int
    voltnir_user_short_id: str
    voltnir_username: str
    v_member_name: str
    basket_ref: str
    list_exec_inst: str
    def __init__(self, order_id: _Optional[int] = ..., initial_order_id: _Optional[int] = ..., parent_order_id: _Optional[int] = ..., revision: _Optional[int] = ..., account_id: _Optional[str] = ..., contract_id: _Optional[int] = ..., delivery_area: _Optional[str] = ..., side: _Optional[_Union[Side, str]] = ..., price: _Optional[int] = ..., quantity: _Optional[int] = ..., initial_quantity: _Optional[int] = ..., hidden_quantity: _Optional[int] = ..., displayed_quantity: _Optional[int] = ..., order_type: _Optional[_Union[OrderType, str]] = ..., state: _Optional[_Union[OrderState, str]] = ..., action: _Optional[str] = ..., client_order_id: _Optional[str] = ..., user_code: _Optional[str] = ..., pre_arranged: bool = ..., timestamp_ms: _Optional[int] = ..., validity_time_ms: _Optional[int] = ..., last_update_time_ms: _Optional[int] = ..., text: _Optional[str] = ..., basket_id: _Optional[int] = ..., v_member_short_id: _Optional[str] = ..., remote_order_id: _Optional[int] = ..., voltnir_user_short_id: _Optional[str] = ..., voltnir_username: _Optional[str] = ..., v_member_name: _Optional[str] = ..., basket_ref: _Optional[str] = ..., list_exec_inst: _Optional[str] = ...) -> None: ...

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
    __slots__ = ("trade_id", "contract_id", "qty", "px", "exec_time", "revision_no", "state", "pre_arranged", "v_member_short_id", "buy", "sell", "attribution", "voltnir_user_short_id", "voltnir_username", "v_member_name", "recall_req_time", "recall_granted_time", "recall_rejected_time", "latest_recall_process_time", "recall_requestor", "parent_trade_id", "prearrange_type")
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
    ATTRIBUTION_FIELD_NUMBER: _ClassVar[int]
    VOLTNIR_USER_SHORT_ID_FIELD_NUMBER: _ClassVar[int]
    VOLTNIR_USERNAME_FIELD_NUMBER: _ClassVar[int]
    V_MEMBER_NAME_FIELD_NUMBER: _ClassVar[int]
    RECALL_REQ_TIME_FIELD_NUMBER: _ClassVar[int]
    RECALL_GRANTED_TIME_FIELD_NUMBER: _ClassVar[int]
    RECALL_REJECTED_TIME_FIELD_NUMBER: _ClassVar[int]
    LATEST_RECALL_PROCESS_TIME_FIELD_NUMBER: _ClassVar[int]
    RECALL_REQUESTOR_FIELD_NUMBER: _ClassVar[int]
    PARENT_TRADE_ID_FIELD_NUMBER: _ClassVar[int]
    PREARRANGE_TYPE_FIELD_NUMBER: _ClassVar[int]
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
    attribution: str
    voltnir_user_short_id: str
    voltnir_username: str
    v_member_name: str
    recall_req_time: str
    recall_granted_time: str
    recall_rejected_time: str
    latest_recall_process_time: str
    recall_requestor: str
    parent_trade_id: str
    prearrange_type: str
    def __init__(self, trade_id: _Optional[str] = ..., contract_id: _Optional[int] = ..., qty: _Optional[int] = ..., px: _Optional[int] = ..., exec_time: _Optional[str] = ..., revision_no: _Optional[int] = ..., state: _Optional[str] = ..., pre_arranged: bool = ..., v_member_short_id: _Optional[str] = ..., buy: _Optional[_Iterable[_Union[TradeDetail, _Mapping]]] = ..., sell: _Optional[_Iterable[_Union[TradeDetail, _Mapping]]] = ..., attribution: _Optional[str] = ..., voltnir_user_short_id: _Optional[str] = ..., voltnir_username: _Optional[str] = ..., v_member_name: _Optional[str] = ..., recall_req_time: _Optional[str] = ..., recall_granted_time: _Optional[str] = ..., recall_rejected_time: _Optional[str] = ..., latest_recall_process_time: _Optional[str] = ..., recall_requestor: _Optional[str] = ..., parent_trade_id: _Optional[str] = ..., prearrange_type: _Optional[str] = ...) -> None: ...

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
    __slots__ = ("contract_id", "area_id", "prod", "name", "long_name", "dlvry_start", "dlvry_end", "predefined", "revision_no", "revision_ob", "state", "trading_phase", "trading_phase_start", "trading_phase_end", "duration", "last_price", "last_quantity", "last_trade_time", "highest_price", "lowest_price", "price_direction", "best_bid", "best_bid_qty", "best_ask", "best_ask_qty", "buy", "sell", "state_raw", "ref_px_cents", "ref_px_type", "ref_px_date", "ref_px_updated_ms")
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
    REF_PX_CENTS_FIELD_NUMBER: _ClassVar[int]
    REF_PX_TYPE_FIELD_NUMBER: _ClassVar[int]
    REF_PX_DATE_FIELD_NUMBER: _ClassVar[int]
    REF_PX_UPDATED_MS_FIELD_NUMBER: _ClassVar[int]
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
    ref_px_cents: int
    ref_px_type: str
    ref_px_date: str
    ref_px_updated_ms: int
    def __init__(self, contract_id: _Optional[str] = ..., area_id: _Optional[str] = ..., prod: _Optional[str] = ..., name: _Optional[str] = ..., long_name: _Optional[str] = ..., dlvry_start: _Optional[str] = ..., dlvry_end: _Optional[str] = ..., predefined: bool = ..., revision_no: _Optional[int] = ..., revision_ob: _Optional[int] = ..., state: _Optional[_Union[ContractState, str]] = ..., trading_phase: _Optional[str] = ..., trading_phase_start: _Optional[str] = ..., trading_phase_end: _Optional[str] = ..., duration: _Optional[str] = ..., last_price: _Optional[int] = ..., last_quantity: _Optional[int] = ..., last_trade_time: _Optional[str] = ..., highest_price: _Optional[int] = ..., lowest_price: _Optional[int] = ..., price_direction: _Optional[int] = ..., best_bid: _Optional[int] = ..., best_bid_qty: _Optional[int] = ..., best_ask: _Optional[int] = ..., best_ask_qty: _Optional[int] = ..., buy: _Optional[_Iterable[_Union[ObEntry, _Mapping]]] = ..., sell: _Optional[_Iterable[_Union[ObEntry, _Mapping]]] = ..., state_raw: _Optional[str] = ..., ref_px_cents: _Optional[int] = ..., ref_px_type: _Optional[str] = ..., ref_px_date: _Optional[str] = ..., ref_px_updated_ms: _Optional[int] = ...) -> None: ...

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
    __slots__ = ("id", "short_id", "name", "max_position", "active", "cash_limit", "cash_limit_gbp", "eur_consumed_cents", "eur_limit_cents", "eur_remaining_cents", "gbp_consumed_cents", "gbp_limit_cents", "gbp_remaining_cents", "max_slot_position", "delivery_areas")
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
    MAX_SLOT_POSITION_FIELD_NUMBER: _ClassVar[int]
    DELIVERY_AREAS_FIELD_NUMBER: _ClassVar[int]
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
    max_slot_position: int
    delivery_areas: DeliveryAreaScope
    def __init__(self, id: _Optional[str] = ..., short_id: _Optional[str] = ..., name: _Optional[str] = ..., max_position: _Optional[int] = ..., active: bool = ..., cash_limit: _Optional[int] = ..., cash_limit_gbp: _Optional[int] = ..., eur_consumed_cents: _Optional[int] = ..., eur_limit_cents: _Optional[int] = ..., eur_remaining_cents: _Optional[int] = ..., gbp_consumed_cents: _Optional[int] = ..., gbp_limit_cents: _Optional[int] = ..., gbp_remaining_cents: _Optional[int] = ..., max_slot_position: _Optional[int] = ..., delivery_areas: _Optional[_Union[DeliveryAreaScope, _Mapping]] = ...) -> None: ...

class DeliveryAreaScope(_message.Message):
    __slots__ = ("all", "area_ids")
    ALL_FIELD_NUMBER: _ClassVar[int]
    AREA_IDS_FIELD_NUMBER: _ClassVar[int]
    all: bool
    area_ids: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, all: bool = ..., area_ids: _Optional[_Iterable[str]] = ...) -> None: ...

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
    __slots__ = ("side", "price", "quantity", "delivery_area_id", "contract_id", "order_type", "exe_restriction", "validity_res", "entry_state", "display_qty", "validity_date", "pre_arranged_acct", "v_member_short_id", "product", "delivery_start", "client_order_id", "ack_only", "delivery_end")
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
    ACK_ONLY_FIELD_NUMBER: _ClassVar[int]
    DELIVERY_END_FIELD_NUMBER: _ClassVar[int]
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
    ack_only: bool
    delivery_end: str
    def __init__(self, side: _Optional[_Union[Side, str]] = ..., price: _Optional[int] = ..., quantity: _Optional[int] = ..., delivery_area_id: _Optional[str] = ..., contract_id: _Optional[int] = ..., order_type: _Optional[_Union[OrderType, str]] = ..., exe_restriction: _Optional[_Union[ExeRestriction, str]] = ..., validity_res: _Optional[_Union[ValidityRes, str]] = ..., entry_state: _Optional[str] = ..., display_qty: _Optional[int] = ..., validity_date: _Optional[str] = ..., pre_arranged_acct: _Optional[str] = ..., v_member_short_id: _Optional[str] = ..., product: _Optional[str] = ..., delivery_start: _Optional[str] = ..., client_order_id: _Optional[str] = ..., ack_only: bool = ..., delivery_end: _Optional[str] = ...) -> None: ...

class SubmitOrderResponse(_message.Message):
    __slots__ = ("client_order_id", "state", "reason", "err_code")
    CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    ERR_CODE_FIELD_NUMBER: _ClassVar[int]
    client_order_id: str
    state: OrderState
    reason: str
    err_code: int
    def __init__(self, client_order_id: _Optional[str] = ..., state: _Optional[_Union[OrderState, str]] = ..., reason: _Optional[str] = ..., err_code: _Optional[int] = ...) -> None: ...

class ModifyOrderRequest(_message.Message):
    __slots__ = ("client_order_id", "action", "price", "quantity", "display_qty", "validity_res", "validity_date", "v_member_short_id", "ack_only")
    CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    ACTION_FIELD_NUMBER: _ClassVar[int]
    PRICE_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_QTY_FIELD_NUMBER: _ClassVar[int]
    VALIDITY_RES_FIELD_NUMBER: _ClassVar[int]
    VALIDITY_DATE_FIELD_NUMBER: _ClassVar[int]
    V_MEMBER_SHORT_ID_FIELD_NUMBER: _ClassVar[int]
    ACK_ONLY_FIELD_NUMBER: _ClassVar[int]
    client_order_id: str
    action: ModifyAction
    price: _wrappers_pb2.Int64Value
    quantity: _wrappers_pb2.UInt32Value
    display_qty: int
    validity_res: ValidityRes
    validity_date: str
    v_member_short_id: str
    ack_only: bool
    def __init__(self, client_order_id: _Optional[str] = ..., action: _Optional[_Union[ModifyAction, str]] = ..., price: _Optional[_Union[_wrappers_pb2.Int64Value, _Mapping]] = ..., quantity: _Optional[_Union[_wrappers_pb2.UInt32Value, _Mapping]] = ..., display_qty: _Optional[int] = ..., validity_res: _Optional[_Union[ValidityRes, str]] = ..., validity_date: _Optional[str] = ..., v_member_short_id: _Optional[str] = ..., ack_only: bool = ...) -> None: ...

class ModifyOrderResponse(_message.Message):
    __slots__ = ("outcome",)
    OUTCOME_FIELD_NUMBER: _ClassVar[int]
    outcome: Outcome
    def __init__(self, outcome: _Optional[_Union[Outcome, str]] = ...) -> None: ...

class CancelOrderRequest(_message.Message):
    __slots__ = ("client_order_id", "ack_only")
    CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    ACK_ONLY_FIELD_NUMBER: _ClassVar[int]
    client_order_id: str
    ack_only: bool
    def __init__(self, client_order_id: _Optional[str] = ..., ack_only: bool = ...) -> None: ...

class CancelOrderResponse(_message.Message):
    __slots__ = ("outcome",)
    OUTCOME_FIELD_NUMBER: _ClassVar[int]
    outcome: Outcome
    def __init__(self, outcome: _Optional[_Union[Outcome, str]] = ...) -> None: ...

class CancelAllOrdersRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class CancelAllOrdersResponse(_message.Message):
    __slots__ = ("deleted",)
    DELETED_FIELD_NUMBER: _ClassVar[int]
    deleted: int
    def __init__(self, deleted: _Optional[int] = ...) -> None: ...

class SubmitBasketRequest(_message.Message):
    __slots__ = ("basket_ref", "list_exec_inst", "orders")
    BASKET_REF_FIELD_NUMBER: _ClassVar[int]
    LIST_EXEC_INST_FIELD_NUMBER: _ClassVar[int]
    ORDERS_FIELD_NUMBER: _ClassVar[int]
    basket_ref: str
    list_exec_inst: str
    orders: _containers.RepeatedCompositeFieldContainer[SubmitOrderRequest]
    def __init__(self, basket_ref: _Optional[str] = ..., list_exec_inst: _Optional[str] = ..., orders: _Optional[_Iterable[_Union[SubmitOrderRequest, _Mapping]]] = ...) -> None: ...

class SubmitBasketResponse(_message.Message):
    __slots__ = ("basket_ref", "list_exec_inst", "basket_id", "orders")
    BASKET_REF_FIELD_NUMBER: _ClassVar[int]
    LIST_EXEC_INST_FIELD_NUMBER: _ClassVar[int]
    BASKET_ID_FIELD_NUMBER: _ClassVar[int]
    ORDERS_FIELD_NUMBER: _ClassVar[int]
    basket_ref: str
    list_exec_inst: str
    basket_id: int
    orders: _containers.RepeatedCompositeFieldContainer[SubmitOrderResponse]
    def __init__(self, basket_ref: _Optional[str] = ..., list_exec_inst: _Optional[str] = ..., basket_id: _Optional[int] = ..., orders: _Optional[_Iterable[_Union[SubmitOrderResponse, _Mapping]]] = ...) -> None: ...

class CancelBasketRequest(_message.Message):
    __slots__ = ("basket_ref",)
    BASKET_REF_FIELD_NUMBER: _ClassVar[int]
    basket_ref: str
    def __init__(self, basket_ref: _Optional[str] = ...) -> None: ...

class BasketCancelResult(_message.Message):
    __slots__ = ("client_order_id", "cancelled", "code", "error")
    CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    CANCELLED_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    client_order_id: str
    cancelled: bool
    code: str
    error: str
    def __init__(self, client_order_id: _Optional[str] = ..., cancelled: bool = ..., code: _Optional[str] = ..., error: _Optional[str] = ...) -> None: ...

class CancelBasketResponse(_message.Message):
    __slots__ = ("basket_ref", "cancelled", "orders")
    BASKET_REF_FIELD_NUMBER: _ClassVar[int]
    CANCELLED_FIELD_NUMBER: _ClassVar[int]
    ORDERS_FIELD_NUMBER: _ClassVar[int]
    basket_ref: str
    cancelled: int
    orders: _containers.RepeatedCompositeFieldContainer[BasketCancelResult]
    def __init__(self, basket_ref: _Optional[str] = ..., cancelled: _Optional[int] = ..., orders: _Optional[_Iterable[_Union[BasketCancelResult, _Mapping]]] = ...) -> None: ...

class RecallTradeRequest(_message.Message):
    __slots__ = ("trade_id", "client_order_id", "revision_no")
    TRADE_ID_FIELD_NUMBER: _ClassVar[int]
    CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    REVISION_NO_FIELD_NUMBER: _ClassVar[int]
    trade_id: str
    client_order_id: str
    revision_no: int
    def __init__(self, trade_id: _Optional[str] = ..., client_order_id: _Optional[str] = ..., revision_no: _Optional[int] = ...) -> None: ...

class RecallTradeResult(_message.Message):
    __slots__ = ("trade_id", "outcome", "state", "revision_no", "recall_req_time", "latest_recall_process_time", "m7_err_code", "m7_error_key", "reason", "cascaded_with")
    TRADE_ID_FIELD_NUMBER: _ClassVar[int]
    OUTCOME_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    REVISION_NO_FIELD_NUMBER: _ClassVar[int]
    RECALL_REQ_TIME_FIELD_NUMBER: _ClassVar[int]
    LATEST_RECALL_PROCESS_TIME_FIELD_NUMBER: _ClassVar[int]
    M7_ERR_CODE_FIELD_NUMBER: _ClassVar[int]
    M7_ERROR_KEY_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    CASCADED_WITH_FIELD_NUMBER: _ClassVar[int]
    trade_id: str
    outcome: str
    state: str
    revision_no: int
    recall_req_time: str
    latest_recall_process_time: str
    m7_err_code: int
    m7_error_key: str
    reason: str
    cascaded_with: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, trade_id: _Optional[str] = ..., outcome: _Optional[str] = ..., state: _Optional[str] = ..., revision_no: _Optional[int] = ..., recall_req_time: _Optional[str] = ..., latest_recall_process_time: _Optional[str] = ..., m7_err_code: _Optional[int] = ..., m7_error_key: _Optional[str] = ..., reason: _Optional[str] = ..., cascaded_with: _Optional[_Iterable[str]] = ...) -> None: ...

class RecallTradeResponse(_message.Message):
    __slots__ = ("client_order_id", "results", "counts")
    class CountsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: int
        def __init__(self, key: _Optional[str] = ..., value: _Optional[int] = ...) -> None: ...
    CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    RESULTS_FIELD_NUMBER: _ClassVar[int]
    COUNTS_FIELD_NUMBER: _ClassVar[int]
    client_order_id: str
    results: _containers.RepeatedCompositeFieldContainer[RecallTradeResult]
    counts: _containers.ScalarMap[str, int]
    def __init__(self, client_order_id: _Optional[str] = ..., results: _Optional[_Iterable[_Union[RecallTradeResult, _Mapping]]] = ..., counts: _Optional[_Mapping[str, int]] = ...) -> None: ...

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

class ContractSummary(_message.Message):
    __slots__ = ("contract_id", "area_id", "prod", "name", "long_name", "dlvry_start", "dlvry_end", "duration", "predefined", "state", "state_raw", "trading_phase", "trading_phase_start", "trading_phase_end")
    CONTRACT_ID_FIELD_NUMBER: _ClassVar[int]
    AREA_ID_FIELD_NUMBER: _ClassVar[int]
    PROD_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    LONG_NAME_FIELD_NUMBER: _ClassVar[int]
    DLVRY_START_FIELD_NUMBER: _ClassVar[int]
    DLVRY_END_FIELD_NUMBER: _ClassVar[int]
    DURATION_FIELD_NUMBER: _ClassVar[int]
    PREDEFINED_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    STATE_RAW_FIELD_NUMBER: _ClassVar[int]
    TRADING_PHASE_FIELD_NUMBER: _ClassVar[int]
    TRADING_PHASE_START_FIELD_NUMBER: _ClassVar[int]
    TRADING_PHASE_END_FIELD_NUMBER: _ClassVar[int]
    contract_id: str
    area_id: str
    prod: str
    name: str
    long_name: str
    dlvry_start: str
    dlvry_end: str
    duration: str
    predefined: bool
    state: ContractState
    state_raw: str
    trading_phase: str
    trading_phase_start: str
    trading_phase_end: str
    def __init__(self, contract_id: _Optional[str] = ..., area_id: _Optional[str] = ..., prod: _Optional[str] = ..., name: _Optional[str] = ..., long_name: _Optional[str] = ..., dlvry_start: _Optional[str] = ..., dlvry_end: _Optional[str] = ..., duration: _Optional[str] = ..., predefined: bool = ..., state: _Optional[_Union[ContractState, str]] = ..., state_raw: _Optional[str] = ..., trading_phase: _Optional[str] = ..., trading_phase_start: _Optional[str] = ..., trading_phase_end: _Optional[str] = ...) -> None: ...

class ListContractsResponse(_message.Message):
    __slots__ = ("contracts",)
    CONTRACTS_FIELD_NUMBER: _ClassVar[int]
    contracts: _containers.RepeatedCompositeFieldContainer[ContractSummary]
    def __init__(self, contracts: _Optional[_Iterable[_Union[ContractSummary, _Mapping]]] = ...) -> None: ...

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
    __slots__ = ("uptime", "operational", "issues", "amqp_connected", "amqp_private_consumer_healthy", "amqp_broadcast_consumer_healthy", "amqp_publisher_healthy", "amqp_publisher_tx_capacity", "amqp_market_active", "amqp_broadcast_sequence_healthy", "ws_order_book_stream_connected", "ws_order_book_sequence_healthy", "ws_order_book_synchronized", "ws_order_book_pong", "ws_order_book_delta", "ws_order_book_delta_per_hour", "ws_order_book_avg_processing_time", "ws_order_book_avg_latency", "ws_private_data_stream_connected", "ws_private_data_sequence_healthy", "ws_private_data_synchronized", "ws_private_data_pong", "ws_private_data_delta_per_hour", "ws_private_data_avg_processing_time", "ws_private_data_avg_latency", "license", "trades_received", "trades_persisted", "trades_persist_failed", "writes_dropped", "trade_reports_refused", "product_parameters_loaded", "product_scale_unrepresentable", "product_scale_frames_dropped", "product_scale_orders_refused", "product_scale_changes", "contracts_awaiting_definition", "contract_reports_broadcast", "last_update_pass_refused", "admission")
    UPTIME_FIELD_NUMBER: _ClassVar[int]
    OPERATIONAL_FIELD_NUMBER: _ClassVar[int]
    ISSUES_FIELD_NUMBER: _ClassVar[int]
    AMQP_CONNECTED_FIELD_NUMBER: _ClassVar[int]
    AMQP_PRIVATE_CONSUMER_HEALTHY_FIELD_NUMBER: _ClassVar[int]
    AMQP_BROADCAST_CONSUMER_HEALTHY_FIELD_NUMBER: _ClassVar[int]
    AMQP_PUBLISHER_HEALTHY_FIELD_NUMBER: _ClassVar[int]
    AMQP_PUBLISHER_TX_CAPACITY_FIELD_NUMBER: _ClassVar[int]
    AMQP_MARKET_ACTIVE_FIELD_NUMBER: _ClassVar[int]
    AMQP_BROADCAST_SEQUENCE_HEALTHY_FIELD_NUMBER: _ClassVar[int]
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
    TRADES_RECEIVED_FIELD_NUMBER: _ClassVar[int]
    TRADES_PERSISTED_FIELD_NUMBER: _ClassVar[int]
    TRADES_PERSIST_FAILED_FIELD_NUMBER: _ClassVar[int]
    WRITES_DROPPED_FIELD_NUMBER: _ClassVar[int]
    TRADE_REPORTS_REFUSED_FIELD_NUMBER: _ClassVar[int]
    PRODUCT_PARAMETERS_LOADED_FIELD_NUMBER: _ClassVar[int]
    PRODUCT_SCALE_UNREPRESENTABLE_FIELD_NUMBER: _ClassVar[int]
    PRODUCT_SCALE_FRAMES_DROPPED_FIELD_NUMBER: _ClassVar[int]
    PRODUCT_SCALE_ORDERS_REFUSED_FIELD_NUMBER: _ClassVar[int]
    PRODUCT_SCALE_CHANGES_FIELD_NUMBER: _ClassVar[int]
    CONTRACTS_AWAITING_DEFINITION_FIELD_NUMBER: _ClassVar[int]
    CONTRACT_REPORTS_BROADCAST_FIELD_NUMBER: _ClassVar[int]
    LAST_UPDATE_PASS_REFUSED_FIELD_NUMBER: _ClassVar[int]
    ADMISSION_FIELD_NUMBER: _ClassVar[int]
    uptime: str
    operational: bool
    issues: _containers.RepeatedScalarFieldContainer[str]
    amqp_connected: bool
    amqp_private_consumer_healthy: bool
    amqp_broadcast_consumer_healthy: bool
    amqp_publisher_healthy: bool
    amqp_publisher_tx_capacity: int
    amqp_market_active: bool
    amqp_broadcast_sequence_healthy: bool
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
    trades_received: int
    trades_persisted: int
    trades_persist_failed: int
    writes_dropped: int
    trade_reports_refused: int
    product_parameters_loaded: bool
    product_scale_unrepresentable: int
    product_scale_frames_dropped: int
    product_scale_orders_refused: int
    product_scale_changes: int
    contracts_awaiting_definition: int
    contract_reports_broadcast: int
    last_update_pass_refused: bool
    admission: str
    def __init__(self, uptime: _Optional[str] = ..., operational: bool = ..., issues: _Optional[_Iterable[str]] = ..., amqp_connected: bool = ..., amqp_private_consumer_healthy: bool = ..., amqp_broadcast_consumer_healthy: bool = ..., amqp_publisher_healthy: bool = ..., amqp_publisher_tx_capacity: _Optional[int] = ..., amqp_market_active: bool = ..., amqp_broadcast_sequence_healthy: bool = ..., ws_order_book_stream_connected: bool = ..., ws_order_book_sequence_healthy: bool = ..., ws_order_book_synchronized: bool = ..., ws_order_book_pong: _Optional[int] = ..., ws_order_book_delta: _Optional[int] = ..., ws_order_book_delta_per_hour: _Optional[int] = ..., ws_order_book_avg_processing_time: _Optional[str] = ..., ws_order_book_avg_latency: _Optional[str] = ..., ws_private_data_stream_connected: bool = ..., ws_private_data_sequence_healthy: bool = ..., ws_private_data_synchronized: bool = ..., ws_private_data_pong: _Optional[int] = ..., ws_private_data_delta_per_hour: _Optional[int] = ..., ws_private_data_avg_processing_time: _Optional[str] = ..., ws_private_data_avg_latency: _Optional[str] = ..., license: _Optional[_Union[LicenseView, _Mapping]] = ..., trades_received: _Optional[int] = ..., trades_persisted: _Optional[int] = ..., trades_persist_failed: _Optional[int] = ..., writes_dropped: _Optional[int] = ..., trade_reports_refused: _Optional[int] = ..., product_parameters_loaded: bool = ..., product_scale_unrepresentable: _Optional[int] = ..., product_scale_frames_dropped: _Optional[int] = ..., product_scale_orders_refused: _Optional[int] = ..., product_scale_changes: _Optional[int] = ..., contracts_awaiting_definition: _Optional[int] = ..., contract_reports_broadcast: _Optional[int] = ..., last_update_pass_refused: bool = ..., admission: _Optional[str] = ...) -> None: ...

class GetStatusRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class SystemStatus(_message.Message):
    __slots__ = ("throttling", "trading_enabled", "operational", "cash_limits", "order_pos_limit", "cash_limit", "license", "stranded_pending_count", "stranded_pending_qty", "claims_count", "claims_qty", "claims_held_count", "claims_held_qty", "license_summary", "accounts", "admission", "m7_client_cert")
    THROTTLING_FIELD_NUMBER: _ClassVar[int]
    TRADING_ENABLED_FIELD_NUMBER: _ClassVar[int]
    OPERATIONAL_FIELD_NUMBER: _ClassVar[int]
    CASH_LIMITS_FIELD_NUMBER: _ClassVar[int]
    ORDER_POS_LIMIT_FIELD_NUMBER: _ClassVar[int]
    CASH_LIMIT_FIELD_NUMBER: _ClassVar[int]
    LICENSE_FIELD_NUMBER: _ClassVar[int]
    STRANDED_PENDING_COUNT_FIELD_NUMBER: _ClassVar[int]
    STRANDED_PENDING_QTY_FIELD_NUMBER: _ClassVar[int]
    CLAIMS_COUNT_FIELD_NUMBER: _ClassVar[int]
    CLAIMS_QTY_FIELD_NUMBER: _ClassVar[int]
    CLAIMS_HELD_COUNT_FIELD_NUMBER: _ClassVar[int]
    CLAIMS_HELD_QTY_FIELD_NUMBER: _ClassVar[int]
    LICENSE_SUMMARY_FIELD_NUMBER: _ClassVar[int]
    ACCOUNTS_FIELD_NUMBER: _ClassVar[int]
    ADMISSION_FIELD_NUMBER: _ClassVar[int]
    M7_CLIENT_CERT_FIELD_NUMBER: _ClassVar[int]
    throttling: ThrottlingStatus
    trading_enabled: bool
    operational: bool
    cash_limits: _containers.RepeatedCompositeFieldContainer[CashLimit]
    order_pos_limit: int
    cash_limit: CashLimitStatus
    license: LicenseView
    stranded_pending_count: int
    stranded_pending_qty: int
    claims_count: int
    claims_qty: int
    claims_held_count: int
    claims_held_qty: int
    license_summary: LicenseSummary
    accounts: _containers.RepeatedCompositeFieldContainer[AccountView]
    admission: str
    m7_client_cert: M7ClientCert
    def __init__(self, throttling: _Optional[_Union[ThrottlingStatus, _Mapping]] = ..., trading_enabled: bool = ..., operational: bool = ..., cash_limits: _Optional[_Iterable[_Union[CashLimit, _Mapping]]] = ..., order_pos_limit: _Optional[int] = ..., cash_limit: _Optional[_Union[CashLimitStatus, _Mapping]] = ..., license: _Optional[_Union[LicenseView, _Mapping]] = ..., stranded_pending_count: _Optional[int] = ..., stranded_pending_qty: _Optional[int] = ..., claims_count: _Optional[int] = ..., claims_qty: _Optional[int] = ..., claims_held_count: _Optional[int] = ..., claims_held_qty: _Optional[int] = ..., license_summary: _Optional[_Union[LicenseSummary, _Mapping]] = ..., accounts: _Optional[_Iterable[_Union[AccountView, _Mapping]]] = ..., admission: _Optional[str] = ..., m7_client_cert: _Optional[_Union[M7ClientCert, _Mapping]] = ...) -> None: ...

class M7ClientCert(_message.Message):
    __slots__ = ("status_kind", "status_days", "status_reason", "not_after")
    STATUS_KIND_FIELD_NUMBER: _ClassVar[int]
    STATUS_DAYS_FIELD_NUMBER: _ClassVar[int]
    STATUS_REASON_FIELD_NUMBER: _ClassVar[int]
    NOT_AFTER_FIELD_NUMBER: _ClassVar[int]
    status_kind: str
    status_days: int
    status_reason: str
    not_after: str
    def __init__(self, status_kind: _Optional[str] = ..., status_days: _Optional[int] = ..., status_reason: _Optional[str] = ..., not_after: _Optional[str] = ...) -> None: ...

class LicenseSummary(_message.Message):
    __slots__ = ("status_kind", "status_days", "expires_at", "grace_end", "mode")
    STATUS_KIND_FIELD_NUMBER: _ClassVar[int]
    STATUS_DAYS_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    GRACE_END_FIELD_NUMBER: _ClassVar[int]
    MODE_FIELD_NUMBER: _ClassVar[int]
    status_kind: str
    status_days: int
    expires_at: str
    grace_end: str
    mode: str
    def __init__(self, status_kind: _Optional[str] = ..., status_days: _Optional[int] = ..., expires_at: _Optional[str] = ..., grace_end: _Optional[str] = ..., mode: _Optional[str] = ...) -> None: ...

class AccountView(_message.Message):
    __slots__ = ("is_house", "short_id", "name", "position_limit", "effective_position_limit", "eur_consumed_cents", "eur_limit_cents", "eur_remaining_cents", "gbp_consumed_cents", "gbp_limit_cents", "gbp_remaining_cents", "slot_limit", "slot_mode")
    IS_HOUSE_FIELD_NUMBER: _ClassVar[int]
    SHORT_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    POSITION_LIMIT_FIELD_NUMBER: _ClassVar[int]
    EFFECTIVE_POSITION_LIMIT_FIELD_NUMBER: _ClassVar[int]
    EUR_CONSUMED_CENTS_FIELD_NUMBER: _ClassVar[int]
    EUR_LIMIT_CENTS_FIELD_NUMBER: _ClassVar[int]
    EUR_REMAINING_CENTS_FIELD_NUMBER: _ClassVar[int]
    GBP_CONSUMED_CENTS_FIELD_NUMBER: _ClassVar[int]
    GBP_LIMIT_CENTS_FIELD_NUMBER: _ClassVar[int]
    GBP_REMAINING_CENTS_FIELD_NUMBER: _ClassVar[int]
    SLOT_LIMIT_FIELD_NUMBER: _ClassVar[int]
    SLOT_MODE_FIELD_NUMBER: _ClassVar[int]
    is_house: bool
    short_id: str
    name: str
    position_limit: int
    effective_position_limit: int
    eur_consumed_cents: int
    eur_limit_cents: int
    eur_remaining_cents: int
    gbp_consumed_cents: int
    gbp_limit_cents: int
    gbp_remaining_cents: int
    slot_limit: int
    slot_mode: SlotLimitMode
    def __init__(self, is_house: bool = ..., short_id: _Optional[str] = ..., name: _Optional[str] = ..., position_limit: _Optional[int] = ..., effective_position_limit: _Optional[int] = ..., eur_consumed_cents: _Optional[int] = ..., eur_limit_cents: _Optional[int] = ..., eur_remaining_cents: _Optional[int] = ..., gbp_consumed_cents: _Optional[int] = ..., gbp_limit_cents: _Optional[int] = ..., gbp_remaining_cents: _Optional[int] = ..., slot_limit: _Optional[int] = ..., slot_mode: _Optional[_Union[SlotLimitMode, str]] = ...) -> None: ...

class CashLimitStatus(_message.Message):
    __slots__ = ("eur_limit_cents", "eur_consumed_cents", "eur_remaining_cents", "gbp_limit_cents", "gbp_consumed_cents", "gbp_remaining_cents", "eur_pool", "gbp_pool", "delivery_risk_applied", "delivery_risk_source")
    EUR_LIMIT_CENTS_FIELD_NUMBER: _ClassVar[int]
    EUR_CONSUMED_CENTS_FIELD_NUMBER: _ClassVar[int]
    EUR_REMAINING_CENTS_FIELD_NUMBER: _ClassVar[int]
    GBP_LIMIT_CENTS_FIELD_NUMBER: _ClassVar[int]
    GBP_CONSUMED_CENTS_FIELD_NUMBER: _ClassVar[int]
    GBP_REMAINING_CENTS_FIELD_NUMBER: _ClassVar[int]
    EUR_POOL_FIELD_NUMBER: _ClassVar[int]
    GBP_POOL_FIELD_NUMBER: _ClassVar[int]
    DELIVERY_RISK_APPLIED_FIELD_NUMBER: _ClassVar[int]
    DELIVERY_RISK_SOURCE_FIELD_NUMBER: _ClassVar[int]
    eur_limit_cents: int
    eur_consumed_cents: int
    eur_remaining_cents: int
    gbp_limit_cents: int
    gbp_consumed_cents: int
    gbp_remaining_cents: int
    eur_pool: CashPool
    gbp_pool: CashPool
    delivery_risk_applied: bool
    delivery_risk_source: DeliveryRiskSource
    def __init__(self, eur_limit_cents: _Optional[int] = ..., eur_consumed_cents: _Optional[int] = ..., eur_remaining_cents: _Optional[int] = ..., gbp_limit_cents: _Optional[int] = ..., gbp_consumed_cents: _Optional[int] = ..., gbp_remaining_cents: _Optional[int] = ..., eur_pool: _Optional[_Union[CashPool, _Mapping]] = ..., gbp_pool: _Optional[_Union[CashPool, _Mapping]] = ..., delivery_risk_applied: bool = ..., delivery_risk_source: _Optional[_Union[DeliveryRiskSource, str]] = ...) -> None: ...

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

class OmtRuleLoad(_message.Message):
    __slots__ = ("observation_period_sec", "l1", "local_omts", "estimated_load", "headroom")
    OBSERVATION_PERIOD_SEC_FIELD_NUMBER: _ClassVar[int]
    L1_FIELD_NUMBER: _ClassVar[int]
    LOCAL_OMTS_FIELD_NUMBER: _ClassVar[int]
    ESTIMATED_LOAD_FIELD_NUMBER: _ClassVar[int]
    HEADROOM_FIELD_NUMBER: _ClassVar[int]
    observation_period_sec: int
    l1: int
    local_omts: int
    estimated_load: int
    headroom: int
    def __init__(self, observation_period_sec: _Optional[int] = ..., l1: _Optional[int] = ..., local_omts: _Optional[int] = ..., estimated_load: _Optional[int] = ..., headroom: _Optional[int] = ...) -> None: ...

class OmtGuard(_message.Message):
    __slots__ = ("enabled", "reported", "report_age_sec", "stale", "short", "long", "headroom", "blocked_reason")
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    REPORTED_FIELD_NUMBER: _ClassVar[int]
    REPORT_AGE_SEC_FIELD_NUMBER: _ClassVar[int]
    STALE_FIELD_NUMBER: _ClassVar[int]
    SHORT_FIELD_NUMBER: _ClassVar[int]
    LONG_FIELD_NUMBER: _ClassVar[int]
    HEADROOM_FIELD_NUMBER: _ClassVar[int]
    BLOCKED_REASON_FIELD_NUMBER: _ClassVar[int]
    enabled: bool
    reported: bool
    report_age_sec: int
    stale: bool
    short: OmtRuleLoad
    long: OmtRuleLoad
    headroom: int
    blocked_reason: str
    def __init__(self, enabled: bool = ..., reported: bool = ..., report_age_sec: _Optional[int] = ..., stale: bool = ..., short: _Optional[_Union[OmtRuleLoad, _Mapping]] = ..., long: _Optional[_Union[OmtRuleLoad, _Mapping]] = ..., headroom: _Optional[int] = ..., blocked_reason: _Optional[str] = ...) -> None: ...

class ThrottlingStatus(_message.Message):
    __slots__ = ("mbr_id", "timestamp", "status", "short_observation_period", "short_tolerance_period", "short_reconnection_cool_down", "short_omt_limit_l1", "short_omt_limit_l2", "short_status", "short_current_omt_count", "short_release_timestamp", "long_observation_period", "long_tolerance_period", "long_reconnection_cool_down", "long_omt_limit_l1", "long_omt_limit_l2", "long_status", "long_current_omt_count", "long_release_timestamp", "guard", "throttling_member_action", "throttling_user_action")
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
    SHORT_RELEASE_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    LONG_OBSERVATION_PERIOD_FIELD_NUMBER: _ClassVar[int]
    LONG_TOLERANCE_PERIOD_FIELD_NUMBER: _ClassVar[int]
    LONG_RECONNECTION_COOL_DOWN_FIELD_NUMBER: _ClassVar[int]
    LONG_OMT_LIMIT_L1_FIELD_NUMBER: _ClassVar[int]
    LONG_OMT_LIMIT_L2_FIELD_NUMBER: _ClassVar[int]
    LONG_STATUS_FIELD_NUMBER: _ClassVar[int]
    LONG_CURRENT_OMT_COUNT_FIELD_NUMBER: _ClassVar[int]
    LONG_RELEASE_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    GUARD_FIELD_NUMBER: _ClassVar[int]
    THROTTLING_MEMBER_ACTION_FIELD_NUMBER: _ClassVar[int]
    THROTTLING_USER_ACTION_FIELD_NUMBER: _ClassVar[int]
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
    short_release_timestamp: str
    long_observation_period: int
    long_tolerance_period: int
    long_reconnection_cool_down: int
    long_omt_limit_l1: int
    long_omt_limit_l2: int
    long_status: str
    long_current_omt_count: int
    long_release_timestamp: str
    guard: OmtGuard
    throttling_member_action: str
    throttling_user_action: str
    def __init__(self, mbr_id: _Optional[str] = ..., timestamp: _Optional[str] = ..., status: _Optional[str] = ..., short_observation_period: _Optional[int] = ..., short_tolerance_period: _Optional[int] = ..., short_reconnection_cool_down: _Optional[int] = ..., short_omt_limit_l1: _Optional[int] = ..., short_omt_limit_l2: _Optional[int] = ..., short_status: _Optional[str] = ..., short_current_omt_count: _Optional[int] = ..., short_release_timestamp: _Optional[str] = ..., long_observation_period: _Optional[int] = ..., long_tolerance_period: _Optional[int] = ..., long_reconnection_cool_down: _Optional[int] = ..., long_omt_limit_l1: _Optional[int] = ..., long_omt_limit_l2: _Optional[int] = ..., long_status: _Optional[str] = ..., long_current_omt_count: _Optional[int] = ..., long_release_timestamp: _Optional[str] = ..., guard: _Optional[_Union[OmtGuard, _Mapping]] = ..., throttling_member_action: _Optional[str] = ..., throttling_user_action: _Optional[str] = ...) -> None: ...

class GetSystemInfoRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetAreaTableRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class AreaInfo(_message.Message):
    __slots__ = ("eic", "short_name", "long_name", "parent_ma_eic", "fill_country", "area_class", "epex_da", "h2h_only", "assigned_products", "name_source")
    EIC_FIELD_NUMBER: _ClassVar[int]
    SHORT_NAME_FIELD_NUMBER: _ClassVar[int]
    LONG_NAME_FIELD_NUMBER: _ClassVar[int]
    PARENT_MA_EIC_FIELD_NUMBER: _ClassVar[int]
    FILL_COUNTRY_FIELD_NUMBER: _ClassVar[int]
    AREA_CLASS_FIELD_NUMBER: _ClassVar[int]
    EPEX_DA_FIELD_NUMBER: _ClassVar[int]
    H2H_ONLY_FIELD_NUMBER: _ClassVar[int]
    ASSIGNED_PRODUCTS_FIELD_NUMBER: _ClassVar[int]
    NAME_SOURCE_FIELD_NUMBER: _ClassVar[int]
    eic: str
    short_name: str
    long_name: str
    parent_ma_eic: str
    fill_country: str
    area_class: AreaClass
    epex_da: bool
    h2h_only: bool
    assigned_products: _containers.RepeatedScalarFieldContainer[str]
    name_source: AreaNameSource
    def __init__(self, eic: _Optional[str] = ..., short_name: _Optional[str] = ..., long_name: _Optional[str] = ..., parent_ma_eic: _Optional[str] = ..., fill_country: _Optional[str] = ..., area_class: _Optional[_Union[AreaClass, str]] = ..., epex_da: bool = ..., h2h_only: bool = ..., assigned_products: _Optional[_Iterable[str]] = ..., name_source: _Optional[_Union[AreaNameSource, str]] = ...) -> None: ...

class MarketAreaInfo(_message.Message):
    __slots__ = ("eic", "name", "long_name", "name_source")
    EIC_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    LONG_NAME_FIELD_NUMBER: _ClassVar[int]
    NAME_SOURCE_FIELD_NUMBER: _ClassVar[int]
    eic: str
    name: str
    long_name: str
    name_source: AreaNameSource
    def __init__(self, eic: _Optional[str] = ..., name: _Optional[str] = ..., long_name: _Optional[str] = ..., name_source: _Optional[_Union[AreaNameSource, str]] = ...) -> None: ...

class AreaTable(_message.Message):
    __slots__ = ("areas", "market_areas")
    AREAS_FIELD_NUMBER: _ClassVar[int]
    MARKET_AREAS_FIELD_NUMBER: _ClassVar[int]
    areas: _containers.RepeatedCompositeFieldContainer[AreaInfo]
    market_areas: _containers.RepeatedCompositeFieldContainer[MarketAreaInfo]
    def __init__(self, areas: _Optional[_Iterable[_Union[AreaInfo, _Mapping]]] = ..., market_areas: _Optional[_Iterable[_Union[MarketAreaInfo, _Mapping]]] = ...) -> None: ...

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
    __slots__ = ("market_id", "backend_version", "backend_time_zone", "backend_market_time_zone", "contract_store_time_in_days", "trade_pool_store_time_in_hours", "max_orders", "capabilities", "allowed_clearing_acct_types", "request_limits", "voltnir_version", "products", "risk_sets")
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
    PRODUCTS_FIELD_NUMBER: _ClassVar[int]
    RISK_SETS_FIELD_NUMBER: _ClassVar[int]
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
    products: _containers.RepeatedCompositeFieldContainer[Product]
    risk_sets: _containers.RepeatedCompositeFieldContainer[RiskSet]
    def __init__(self, market_id: _Optional[str] = ..., backend_version: _Optional[str] = ..., backend_time_zone: _Optional[str] = ..., backend_market_time_zone: _Optional[str] = ..., contract_store_time_in_days: _Optional[int] = ..., trade_pool_store_time_in_hours: _Optional[int] = ..., max_orders: _Optional[int] = ..., capabilities: _Optional[str] = ..., allowed_clearing_acct_types: _Optional[str] = ..., request_limits: _Optional[_Iterable[_Union[RequestLimit, _Mapping]]] = ..., voltnir_version: _Optional[str] = ..., products: _Optional[_Iterable[_Union[Product, _Mapping]]] = ..., risk_sets: _Optional[_Iterable[_Union[RiskSet, _Mapping]]] = ...) -> None: ...

class ProductDeliveryArea(_message.Message):
    __slots__ = ("delivery_area_id", "risk_set_id")
    DELIVERY_AREA_ID_FIELD_NUMBER: _ClassVar[int]
    RISK_SET_ID_FIELD_NUMBER: _ClassVar[int]
    delivery_area_id: str
    risk_set_id: int
    def __init__(self, delivery_area_id: _Optional[str] = ..., risk_set_id: _Optional[int] = ...) -> None: ...

class Product(_message.Message):
    __slots__ = ("name", "currency", "state", "revision_no", "cash_limit_enabled", "default_risk_set_id", "delivery_areas", "tick_cents", "min_price_cents", "max_price_cents", "lot_sub_mw", "min_qty_sub_mw", "max_qty_sub_mw", "iceberg_min_peak_sub_mw", "dec_shft_px", "dec_shft_qty", "qty_unit", "scale", "block_order_product", "block_maximum_hours", "dst_block_product", "linked_order_product")
    NAME_FIELD_NUMBER: _ClassVar[int]
    CURRENCY_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    REVISION_NO_FIELD_NUMBER: _ClassVar[int]
    CASH_LIMIT_ENABLED_FIELD_NUMBER: _ClassVar[int]
    DEFAULT_RISK_SET_ID_FIELD_NUMBER: _ClassVar[int]
    DELIVERY_AREAS_FIELD_NUMBER: _ClassVar[int]
    TICK_CENTS_FIELD_NUMBER: _ClassVar[int]
    MIN_PRICE_CENTS_FIELD_NUMBER: _ClassVar[int]
    MAX_PRICE_CENTS_FIELD_NUMBER: _ClassVar[int]
    LOT_SUB_MW_FIELD_NUMBER: _ClassVar[int]
    MIN_QTY_SUB_MW_FIELD_NUMBER: _ClassVar[int]
    MAX_QTY_SUB_MW_FIELD_NUMBER: _ClassVar[int]
    ICEBERG_MIN_PEAK_SUB_MW_FIELD_NUMBER: _ClassVar[int]
    DEC_SHFT_PX_FIELD_NUMBER: _ClassVar[int]
    DEC_SHFT_QTY_FIELD_NUMBER: _ClassVar[int]
    QTY_UNIT_FIELD_NUMBER: _ClassVar[int]
    SCALE_FIELD_NUMBER: _ClassVar[int]
    BLOCK_ORDER_PRODUCT_FIELD_NUMBER: _ClassVar[int]
    BLOCK_MAXIMUM_HOURS_FIELD_NUMBER: _ClassVar[int]
    DST_BLOCK_PRODUCT_FIELD_NUMBER: _ClassVar[int]
    LINKED_ORDER_PRODUCT_FIELD_NUMBER: _ClassVar[int]
    name: str
    currency: str
    state: str
    revision_no: int
    cash_limit_enabled: bool
    default_risk_set_id: int
    delivery_areas: _containers.RepeatedCompositeFieldContainer[ProductDeliveryArea]
    tick_cents: int
    min_price_cents: int
    max_price_cents: int
    lot_sub_mw: int
    min_qty_sub_mw: int
    max_qty_sub_mw: int
    iceberg_min_peak_sub_mw: int
    dec_shft_px: int
    dec_shft_qty: int
    qty_unit: str
    scale: ProductScaleClass
    block_order_product: bool
    block_maximum_hours: int
    dst_block_product: bool
    linked_order_product: bool
    def __init__(self, name: _Optional[str] = ..., currency: _Optional[str] = ..., state: _Optional[str] = ..., revision_no: _Optional[int] = ..., cash_limit_enabled: bool = ..., default_risk_set_id: _Optional[int] = ..., delivery_areas: _Optional[_Iterable[_Union[ProductDeliveryArea, _Mapping]]] = ..., tick_cents: _Optional[int] = ..., min_price_cents: _Optional[int] = ..., max_price_cents: _Optional[int] = ..., lot_sub_mw: _Optional[int] = ..., min_qty_sub_mw: _Optional[int] = ..., max_qty_sub_mw: _Optional[int] = ..., iceberg_min_peak_sub_mw: _Optional[int] = ..., dec_shft_px: _Optional[int] = ..., dec_shft_qty: _Optional[int] = ..., qty_unit: _Optional[str] = ..., scale: _Optional[_Union[ProductScaleClass, str]] = ..., block_order_product: bool = ..., block_maximum_hours: _Optional[int] = ..., dst_block_product: bool = ..., linked_order_product: bool = ...) -> None: ...

class RiskSetA(_message.Message):
    __slots__ = ("pos_buy_ordr", "pos_sell_ordr", "pos_buy_trade", "pos_sell_trade", "neg_buy_ordr", "neg_sell_ordr", "neg_buy_trade", "neg_sell_trade")
    POS_BUY_ORDR_FIELD_NUMBER: _ClassVar[int]
    POS_SELL_ORDR_FIELD_NUMBER: _ClassVar[int]
    POS_BUY_TRADE_FIELD_NUMBER: _ClassVar[int]
    POS_SELL_TRADE_FIELD_NUMBER: _ClassVar[int]
    NEG_BUY_ORDR_FIELD_NUMBER: _ClassVar[int]
    NEG_SELL_ORDR_FIELD_NUMBER: _ClassVar[int]
    NEG_BUY_TRADE_FIELD_NUMBER: _ClassVar[int]
    NEG_SELL_TRADE_FIELD_NUMBER: _ClassVar[int]
    pos_buy_ordr: float
    pos_sell_ordr: float
    pos_buy_trade: float
    pos_sell_trade: float
    neg_buy_ordr: float
    neg_sell_ordr: float
    neg_buy_trade: float
    neg_sell_trade: float
    def __init__(self, pos_buy_ordr: _Optional[float] = ..., pos_sell_ordr: _Optional[float] = ..., pos_buy_trade: _Optional[float] = ..., pos_sell_trade: _Optional[float] = ..., neg_buy_ordr: _Optional[float] = ..., neg_sell_ordr: _Optional[float] = ..., neg_buy_trade: _Optional[float] = ..., neg_sell_trade: _Optional[float] = ...) -> None: ...

class RiskSetAlpha(_message.Message):
    __slots__ = ("buy_ordr", "sell_ordr", "buy_trade", "sell_trade")
    BUY_ORDR_FIELD_NUMBER: _ClassVar[int]
    SELL_ORDR_FIELD_NUMBER: _ClassVar[int]
    BUY_TRADE_FIELD_NUMBER: _ClassVar[int]
    SELL_TRADE_FIELD_NUMBER: _ClassVar[int]
    buy_ordr: float
    sell_ordr: float
    buy_trade: float
    sell_trade: float
    def __init__(self, buy_ordr: _Optional[float] = ..., sell_ordr: _Optional[float] = ..., buy_trade: _Optional[float] = ..., sell_trade: _Optional[float] = ...) -> None: ...

class RiskSet(_message.Message):
    __slots__ = ("risk_set_id", "name", "revision_no", "a", "alpha")
    RISK_SET_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    REVISION_NO_FIELD_NUMBER: _ClassVar[int]
    A_FIELD_NUMBER: _ClassVar[int]
    ALPHA_FIELD_NUMBER: _ClassVar[int]
    risk_set_id: int
    name: str
    revision_no: int
    a: RiskSetA
    alpha: RiskSetAlpha
    def __init__(self, risk_set_id: _Optional[int] = ..., name: _Optional[str] = ..., revision_no: _Optional[int] = ..., a: _Optional[_Union[RiskSetA, _Mapping]] = ..., alpha: _Optional[_Union[RiskSetAlpha, _Mapping]] = ...) -> None: ...

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

class GetSlotLimitRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class SetSlotLimitRequest(_message.Message):
    __slots__ = ("mode", "house_limit")
    MODE_FIELD_NUMBER: _ClassVar[int]
    HOUSE_LIMIT_FIELD_NUMBER: _ClassVar[int]
    mode: SlotLimitMode
    house_limit: int
    def __init__(self, mode: _Optional[_Union[SlotLimitMode, str]] = ..., house_limit: _Optional[int] = ...) -> None: ...

class SlotLimitResponse(_message.Message):
    __slots__ = ("mode", "house_limit")
    MODE_FIELD_NUMBER: _ClassVar[int]
    HOUSE_LIMIT_FIELD_NUMBER: _ClassVar[int]
    mode: SlotLimitMode
    house_limit: int
    def __init__(self, mode: _Optional[_Union[SlotLimitMode, str]] = ..., house_limit: _Optional[int] = ...) -> None: ...

class GetSlotPositionsRequest(_message.Message):
    __slots__ = ("delivery_area", "from_ms", "to_ms", "v_member_short_id")
    DELIVERY_AREA_FIELD_NUMBER: _ClassVar[int]
    FROM_MS_FIELD_NUMBER: _ClassVar[int]
    TO_MS_FIELD_NUMBER: _ClassVar[int]
    V_MEMBER_SHORT_ID_FIELD_NUMBER: _ClassVar[int]
    delivery_area: str
    from_ms: int
    to_ms: int
    v_member_short_id: str
    def __init__(self, delivery_area: _Optional[str] = ..., from_ms: _Optional[int] = ..., to_ms: _Optional[int] = ..., v_member_short_id: _Optional[str] = ...) -> None: ...

class SlotScopePosition(_message.Message):
    __slots__ = ("scope", "net", "max_long", "max_short", "limit", "buy_headroom", "sell_headroom")
    SCOPE_FIELD_NUMBER: _ClassVar[int]
    NET_FIELD_NUMBER: _ClassVar[int]
    MAX_LONG_FIELD_NUMBER: _ClassVar[int]
    MAX_SHORT_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    BUY_HEADROOM_FIELD_NUMBER: _ClassVar[int]
    SELL_HEADROOM_FIELD_NUMBER: _ClassVar[int]
    scope: str
    net: int
    max_long: int
    max_short: int
    limit: int
    buy_headroom: int
    sell_headroom: int
    def __init__(self, scope: _Optional[str] = ..., net: _Optional[int] = ..., max_long: _Optional[int] = ..., max_short: _Optional[int] = ..., limit: _Optional[int] = ..., buy_headroom: _Optional[int] = ..., sell_headroom: _Optional[int] = ...) -> None: ...

class SlotPosition(_message.Message):
    __slots__ = ("slot_start_ms", "slot_end_ms", "scopes")
    SLOT_START_MS_FIELD_NUMBER: _ClassVar[int]
    SLOT_END_MS_FIELD_NUMBER: _ClassVar[int]
    SCOPES_FIELD_NUMBER: _ClassVar[int]
    slot_start_ms: int
    slot_end_ms: int
    scopes: _containers.RepeatedCompositeFieldContainer[SlotScopePosition]
    def __init__(self, slot_start_ms: _Optional[int] = ..., slot_end_ms: _Optional[int] = ..., scopes: _Optional[_Iterable[_Union[SlotScopePosition, _Mapping]]] = ...) -> None: ...

class SlotPositionsResponse(_message.Message):
    __slots__ = ("delivery_area", "from_ms", "to_ms", "mode", "house_limit", "locked", "slots", "seq")
    DELIVERY_AREA_FIELD_NUMBER: _ClassVar[int]
    FROM_MS_FIELD_NUMBER: _ClassVar[int]
    TO_MS_FIELD_NUMBER: _ClassVar[int]
    MODE_FIELD_NUMBER: _ClassVar[int]
    HOUSE_LIMIT_FIELD_NUMBER: _ClassVar[int]
    LOCKED_FIELD_NUMBER: _ClassVar[int]
    SLOTS_FIELD_NUMBER: _ClassVar[int]
    SEQ_FIELD_NUMBER: _ClassVar[int]
    delivery_area: str
    from_ms: int
    to_ms: int
    mode: SlotLimitMode
    house_limit: int
    locked: bool
    slots: _containers.RepeatedCompositeFieldContainer[SlotPosition]
    seq: int
    def __init__(self, delivery_area: _Optional[str] = ..., from_ms: _Optional[int] = ..., to_ms: _Optional[int] = ..., mode: _Optional[_Union[SlotLimitMode, str]] = ..., house_limit: _Optional[int] = ..., locked: bool = ..., slots: _Optional[_Iterable[_Union[SlotPosition, _Mapping]]] = ..., seq: _Optional[int] = ...) -> None: ...

class GetCashLimitRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class SetCashLimitRequest(_message.Message):
    __slots__ = ("currency", "cap_cents")
    CURRENCY_FIELD_NUMBER: _ClassVar[int]
    CAP_CENTS_FIELD_NUMBER: _ClassVar[int]
    currency: str
    cap_cents: _wrappers_pb2.Int64Value
    def __init__(self, currency: _Optional[str] = ..., cap_cents: _Optional[_Union[_wrappers_pb2.Int64Value, _Mapping]] = ...) -> None: ...

class CashLimitResponse(_message.Message):
    __slots__ = ("eur", "gbp")
    EUR_FIELD_NUMBER: _ClassVar[int]
    GBP_FIELD_NUMBER: _ClassVar[int]
    eur: CashPool
    gbp: CashPool
    def __init__(self, eur: _Optional[_Union[CashPool, _Mapping]] = ..., gbp: _Optional[_Union[CashPool, _Mapping]] = ...) -> None: ...

class CashPool(_message.Message):
    __slots__ = ("ecc_limit_cents", "ecc_revision", "ecc_effective_from", "m7_remaining_cents", "cap_cents", "house_cents", "cap_above_ecc", "breached", "allocated_cents", "unallocated_cents", "over_allocated", "reported_at_ms", "stale")
    ECC_LIMIT_CENTS_FIELD_NUMBER: _ClassVar[int]
    ECC_REVISION_FIELD_NUMBER: _ClassVar[int]
    ECC_EFFECTIVE_FROM_FIELD_NUMBER: _ClassVar[int]
    M7_REMAINING_CENTS_FIELD_NUMBER: _ClassVar[int]
    CAP_CENTS_FIELD_NUMBER: _ClassVar[int]
    HOUSE_CENTS_FIELD_NUMBER: _ClassVar[int]
    CAP_ABOVE_ECC_FIELD_NUMBER: _ClassVar[int]
    BREACHED_FIELD_NUMBER: _ClassVar[int]
    ALLOCATED_CENTS_FIELD_NUMBER: _ClassVar[int]
    UNALLOCATED_CENTS_FIELD_NUMBER: _ClassVar[int]
    OVER_ALLOCATED_FIELD_NUMBER: _ClassVar[int]
    REPORTED_AT_MS_FIELD_NUMBER: _ClassVar[int]
    STALE_FIELD_NUMBER: _ClassVar[int]
    ecc_limit_cents: _wrappers_pb2.Int64Value
    ecc_revision: _wrappers_pb2.Int64Value
    ecc_effective_from: str
    m7_remaining_cents: _wrappers_pb2.Int64Value
    cap_cents: _wrappers_pb2.Int64Value
    house_cents: int
    cap_above_ecc: bool
    breached: bool
    allocated_cents: int
    unallocated_cents: int
    over_allocated: bool
    reported_at_ms: _wrappers_pb2.Int64Value
    stale: bool
    def __init__(self, ecc_limit_cents: _Optional[_Union[_wrappers_pb2.Int64Value, _Mapping]] = ..., ecc_revision: _Optional[_Union[_wrappers_pb2.Int64Value, _Mapping]] = ..., ecc_effective_from: _Optional[str] = ..., m7_remaining_cents: _Optional[_Union[_wrappers_pb2.Int64Value, _Mapping]] = ..., cap_cents: _Optional[_Union[_wrappers_pb2.Int64Value, _Mapping]] = ..., house_cents: _Optional[int] = ..., cap_above_ecc: bool = ..., breached: bool = ..., allocated_cents: _Optional[int] = ..., unallocated_cents: _Optional[int] = ..., over_allocated: bool = ..., reported_at_ms: _Optional[_Union[_wrappers_pb2.Int64Value, _Mapping]] = ..., stale: bool = ...) -> None: ...

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

class FlattenOutcome(_message.Message):
    __slots__ = ("ok", "error")
    OK_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    ok: bool
    error: str
    def __init__(self, ok: bool = ..., error: _Optional[str] = ...) -> None: ...

class TradingAllowedResponse(_message.Message):
    __slots__ = ("allowed", "flatten")
    ALLOWED_FIELD_NUMBER: _ClassVar[int]
    FLATTEN_FIELD_NUMBER: _ClassVar[int]
    allowed: bool
    flatten: FlattenOutcome
    def __init__(self, allowed: bool = ..., flatten: _Optional[_Union[FlattenOutcome, _Mapping]] = ...) -> None: ...

class AckTradeIngestFaultRequest(_message.Message):
    __slots__ = ("reason",)
    REASON_FIELD_NUMBER: _ClassVar[int]
    reason: str
    def __init__(self, reason: _Optional[str] = ...) -> None: ...

class AckTradeIngestFaultResponse(_message.Message):
    __slots__ = ("ttl_sec", "expires_at_ms", "renewed")
    TTL_SEC_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_AT_MS_FIELD_NUMBER: _ClassVar[int]
    RENEWED_FIELD_NUMBER: _ClassVar[int]
    ttl_sec: int
    expires_at_ms: int
    renewed: bool
    def __init__(self, ttl_sec: _Optional[int] = ..., expires_at_ms: _Optional[int] = ..., renewed: bool = ...) -> None: ...

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

class RestoreTradeHistoryRequest(_message.Message):
    __slots__ = ("days",)
    DAYS_FIELD_NUMBER: _ClassVar[int]
    days: int
    def __init__(self, days: _Optional[int] = ...) -> None: ...

class RestoreTradeHistoryResponse(_message.Message):
    __slots__ = ("chunk_count", "effective_from_ms", "effective_days")
    CHUNK_COUNT_FIELD_NUMBER: _ClassVar[int]
    EFFECTIVE_FROM_MS_FIELD_NUMBER: _ClassVar[int]
    EFFECTIVE_DAYS_FIELD_NUMBER: _ClassVar[int]
    chunk_count: int
    effective_from_ms: int
    effective_days: int
    def __init__(self, chunk_count: _Optional[int] = ..., effective_from_ms: _Optional[int] = ..., effective_days: _Optional[int] = ...) -> None: ...

class GetCashLimitsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class CashLimit(_message.Message):
    __slots__ = ("currency", "current_limit", "current_revision", "configured_limit", "dec_shft", "lmt_id", "state", "start_date", "revision_no", "end_date")
    CURRENCY_FIELD_NUMBER: _ClassVar[int]
    CURRENT_LIMIT_FIELD_NUMBER: _ClassVar[int]
    CURRENT_REVISION_FIELD_NUMBER: _ClassVar[int]
    CONFIGURED_LIMIT_FIELD_NUMBER: _ClassVar[int]
    DEC_SHFT_FIELD_NUMBER: _ClassVar[int]
    LMT_ID_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    START_DATE_FIELD_NUMBER: _ClassVar[int]
    REVISION_NO_FIELD_NUMBER: _ClassVar[int]
    END_DATE_FIELD_NUMBER: _ClassVar[int]
    currency: str
    current_limit: int
    current_revision: int
    configured_limit: int
    dec_shft: int
    lmt_id: str
    state: str
    start_date: str
    revision_no: int
    end_date: str
    def __init__(self, currency: _Optional[str] = ..., current_limit: _Optional[int] = ..., current_revision: _Optional[int] = ..., configured_limit: _Optional[int] = ..., dec_shft: _Optional[int] = ..., lmt_id: _Optional[str] = ..., state: _Optional[str] = ..., start_date: _Optional[str] = ..., revision_no: _Optional[int] = ..., end_date: _Optional[str] = ...) -> None: ...

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
    __slots__ = ("per_contract", "per_area_prod", "per_vm", "per_vm_area_prod", "computed_at_ms", "compute_us", "totals", "unpriced_trades")
    PER_CONTRACT_FIELD_NUMBER: _ClassVar[int]
    PER_AREA_PROD_FIELD_NUMBER: _ClassVar[int]
    PER_VM_FIELD_NUMBER: _ClassVar[int]
    PER_VM_AREA_PROD_FIELD_NUMBER: _ClassVar[int]
    COMPUTED_AT_MS_FIELD_NUMBER: _ClassVar[int]
    COMPUTE_US_FIELD_NUMBER: _ClassVar[int]
    TOTALS_FIELD_NUMBER: _ClassVar[int]
    UNPRICED_TRADES_FIELD_NUMBER: _ClassVar[int]
    per_contract: _containers.RepeatedCompositeFieldContainer[ContractPnl]
    per_area_prod: _containers.RepeatedCompositeFieldContainer[AreaProductPnl]
    per_vm: _containers.RepeatedCompositeFieldContainer[VmContractPnl]
    per_vm_area_prod: _containers.RepeatedCompositeFieldContainer[VmAreaProductPnl]
    computed_at_ms: int
    compute_us: int
    totals: _containers.RepeatedCompositeFieldContainer[CurrencyTotal]
    unpriced_trades: int
    def __init__(self, per_contract: _Optional[_Iterable[_Union[ContractPnl, _Mapping]]] = ..., per_area_prod: _Optional[_Iterable[_Union[AreaProductPnl, _Mapping]]] = ..., per_vm: _Optional[_Iterable[_Union[VmContractPnl, _Mapping]]] = ..., per_vm_area_prod: _Optional[_Iterable[_Union[VmAreaProductPnl, _Mapping]]] = ..., computed_at_ms: _Optional[int] = ..., compute_us: _Optional[int] = ..., totals: _Optional[_Iterable[_Union[CurrencyTotal, _Mapping]]] = ..., unpriced_trades: _Optional[int] = ...) -> None: ...

class CurrencyTotal(_message.Message):
    __slots__ = ("currency", "realized_pnl", "unrealized_pnl")
    CURRENCY_FIELD_NUMBER: _ClassVar[int]
    REALIZED_PNL_FIELD_NUMBER: _ClassVar[int]
    UNREALIZED_PNL_FIELD_NUMBER: _ClassVar[int]
    currency: str
    realized_pnl: int
    unrealized_pnl: int
    def __init__(self, currency: _Optional[str] = ..., realized_pnl: _Optional[int] = ..., unrealized_pnl: _Optional[int] = ...) -> None: ...

class ContractPnl(_message.Message):
    __slots__ = ("area_id", "contract_id", "product", "signed_position", "avg_open_px", "mark_px", "mark_source", "realized_pnl", "unrealized_pnl", "currency", "delivery_day")
    AREA_ID_FIELD_NUMBER: _ClassVar[int]
    CONTRACT_ID_FIELD_NUMBER: _ClassVar[int]
    PRODUCT_FIELD_NUMBER: _ClassVar[int]
    SIGNED_POSITION_FIELD_NUMBER: _ClassVar[int]
    AVG_OPEN_PX_FIELD_NUMBER: _ClassVar[int]
    MARK_PX_FIELD_NUMBER: _ClassVar[int]
    MARK_SOURCE_FIELD_NUMBER: _ClassVar[int]
    REALIZED_PNL_FIELD_NUMBER: _ClassVar[int]
    UNREALIZED_PNL_FIELD_NUMBER: _ClassVar[int]
    CURRENCY_FIELD_NUMBER: _ClassVar[int]
    DELIVERY_DAY_FIELD_NUMBER: _ClassVar[int]
    area_id: str
    contract_id: int
    product: str
    signed_position: int
    avg_open_px: int
    mark_px: int
    mark_source: MarkSource
    realized_pnl: int
    unrealized_pnl: int
    currency: str
    delivery_day: str
    def __init__(self, area_id: _Optional[str] = ..., contract_id: _Optional[int] = ..., product: _Optional[str] = ..., signed_position: _Optional[int] = ..., avg_open_px: _Optional[int] = ..., mark_px: _Optional[int] = ..., mark_source: _Optional[_Union[MarkSource, str]] = ..., realized_pnl: _Optional[int] = ..., unrealized_pnl: _Optional[int] = ..., currency: _Optional[str] = ..., delivery_day: _Optional[str] = ...) -> None: ...

class AreaProductPnl(_message.Message):
    __slots__ = ("area_id", "product", "realized_pnl", "unrealized_pnl", "currency")
    AREA_ID_FIELD_NUMBER: _ClassVar[int]
    PRODUCT_FIELD_NUMBER: _ClassVar[int]
    REALIZED_PNL_FIELD_NUMBER: _ClassVar[int]
    UNREALIZED_PNL_FIELD_NUMBER: _ClassVar[int]
    CURRENCY_FIELD_NUMBER: _ClassVar[int]
    area_id: str
    product: str
    realized_pnl: int
    unrealized_pnl: int
    currency: str
    def __init__(self, area_id: _Optional[str] = ..., product: _Optional[str] = ..., realized_pnl: _Optional[int] = ..., unrealized_pnl: _Optional[int] = ..., currency: _Optional[str] = ...) -> None: ...

class VmContractPnl(_message.Message):
    __slots__ = ("v_member_short_id", "area_id", "contract_id", "product", "signed_position", "avg_open_px", "mark_px", "mark_source", "realized_pnl", "unrealized_pnl", "currency", "delivery_day")
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
    CURRENCY_FIELD_NUMBER: _ClassVar[int]
    DELIVERY_DAY_FIELD_NUMBER: _ClassVar[int]
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
    currency: str
    delivery_day: str
    def __init__(self, v_member_short_id: _Optional[str] = ..., area_id: _Optional[str] = ..., contract_id: _Optional[int] = ..., product: _Optional[str] = ..., signed_position: _Optional[int] = ..., avg_open_px: _Optional[int] = ..., mark_px: _Optional[int] = ..., mark_source: _Optional[_Union[MarkSource, str]] = ..., realized_pnl: _Optional[int] = ..., unrealized_pnl: _Optional[int] = ..., currency: _Optional[str] = ..., delivery_day: _Optional[str] = ...) -> None: ...

class VmAreaProductPnl(_message.Message):
    __slots__ = ("v_member_short_id", "area_id", "product", "realized_pnl", "unrealized_pnl", "currency")
    V_MEMBER_SHORT_ID_FIELD_NUMBER: _ClassVar[int]
    AREA_ID_FIELD_NUMBER: _ClassVar[int]
    PRODUCT_FIELD_NUMBER: _ClassVar[int]
    REALIZED_PNL_FIELD_NUMBER: _ClassVar[int]
    UNREALIZED_PNL_FIELD_NUMBER: _ClassVar[int]
    CURRENCY_FIELD_NUMBER: _ClassVar[int]
    v_member_short_id: str
    area_id: str
    product: str
    realized_pnl: int
    unrealized_pnl: int
    currency: str
    def __init__(self, v_member_short_id: _Optional[str] = ..., area_id: _Optional[str] = ..., product: _Optional[str] = ..., realized_pnl: _Optional[int] = ..., unrealized_pnl: _Optional[int] = ..., currency: _Optional[str] = ...) -> None: ...

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
    __slots__ = ("trade_id", "contract_id", "qty", "px", "exec_time", "exec_time_ms", "revision_no", "state", "buy_dlvry_area", "sell_dlvry_area", "self_trade", "remote_trade_id")
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
    REMOTE_TRADE_ID_FIELD_NUMBER: _ClassVar[int]
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
    remote_trade_id: str
    def __init__(self, trade_id: _Optional[str] = ..., contract_id: _Optional[int] = ..., qty: _Optional[int] = ..., px: _Optional[int] = ..., exec_time: _Optional[str] = ..., exec_time_ms: _Optional[int] = ..., revision_no: _Optional[int] = ..., state: _Optional[str] = ..., buy_dlvry_area: _Optional[str] = ..., sell_dlvry_area: _Optional[str] = ..., self_trade: bool = ..., remote_trade_id: _Optional[str] = ...) -> None: ...

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
    __slots__ = ("name", "max_position", "cash_limit", "cash_limit_gbp", "max_slot_position", "delivery_areas")
    NAME_FIELD_NUMBER: _ClassVar[int]
    MAX_POSITION_FIELD_NUMBER: _ClassVar[int]
    CASH_LIMIT_FIELD_NUMBER: _ClassVar[int]
    CASH_LIMIT_GBP_FIELD_NUMBER: _ClassVar[int]
    MAX_SLOT_POSITION_FIELD_NUMBER: _ClassVar[int]
    DELIVERY_AREAS_FIELD_NUMBER: _ClassVar[int]
    name: str
    max_position: int
    cash_limit: int
    cash_limit_gbp: int
    max_slot_position: int
    delivery_areas: DeliveryAreaScope
    def __init__(self, name: _Optional[str] = ..., max_position: _Optional[int] = ..., cash_limit: _Optional[int] = ..., cash_limit_gbp: _Optional[int] = ..., max_slot_position: _Optional[int] = ..., delivery_areas: _Optional[_Union[DeliveryAreaScope, _Mapping]] = ...) -> None: ...

class PatchMemberRequest(_message.Message):
    __slots__ = ("id", "name", "max_position", "active", "cash_limit", "cash_limit_gbp", "max_slot_position", "clear_max_slot_position", "delivery_areas")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    MAX_POSITION_FIELD_NUMBER: _ClassVar[int]
    ACTIVE_FIELD_NUMBER: _ClassVar[int]
    CASH_LIMIT_FIELD_NUMBER: _ClassVar[int]
    CASH_LIMIT_GBP_FIELD_NUMBER: _ClassVar[int]
    MAX_SLOT_POSITION_FIELD_NUMBER: _ClassVar[int]
    CLEAR_MAX_SLOT_POSITION_FIELD_NUMBER: _ClassVar[int]
    DELIVERY_AREAS_FIELD_NUMBER: _ClassVar[int]
    id: str
    name: _wrappers_pb2.StringValue
    max_position: _wrappers_pb2.Int64Value
    active: _wrappers_pb2.BoolValue
    cash_limit: _wrappers_pb2.Int64Value
    cash_limit_gbp: _wrappers_pb2.Int64Value
    max_slot_position: int
    clear_max_slot_position: bool
    delivery_areas: DeliveryAreaScope
    def __init__(self, id: _Optional[str] = ..., name: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., max_position: _Optional[_Union[_wrappers_pb2.Int64Value, _Mapping]] = ..., active: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ..., cash_limit: _Optional[_Union[_wrappers_pb2.Int64Value, _Mapping]] = ..., cash_limit_gbp: _Optional[_Union[_wrappers_pb2.Int64Value, _Mapping]] = ..., max_slot_position: _Optional[int] = ..., clear_max_slot_position: bool = ..., delivery_areas: _Optional[_Union[DeliveryAreaScope, _Mapping]] = ...) -> None: ...

class DeleteMemberRequest(_message.Message):
    __slots__ = ("member_id",)
    MEMBER_ID_FIELD_NUMBER: _ClassVar[int]
    member_id: str
    def __init__(self, member_id: _Optional[str] = ...) -> None: ...

class AuditOrdersRequest(_message.Message):
    __slots__ = ("cursor", "limit", "date_from", "date_to", "area", "product", "status", "user_code", "v_member_short_id", "voltnir_user_short_id", "voltnir_username", "sort_order")
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
    SORT_ORDER_FIELD_NUMBER: _ClassVar[int]
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
    sort_order: str
    def __init__(self, cursor: _Optional[str] = ..., limit: _Optional[int] = ..., date_from: _Optional[str] = ..., date_to: _Optional[str] = ..., area: _Optional[str] = ..., product: _Optional[str] = ..., status: _Optional[str] = ..., user_code: _Optional[str] = ..., v_member_short_id: _Optional[str] = ..., voltnir_user_short_id: _Optional[str] = ..., voltnir_username: _Optional[str] = ..., sort_order: _Optional[str] = ...) -> None: ...

class AuditOrderItem(_message.Message):
    __slots__ = ("json",)
    JSON_FIELD_NUMBER: _ClassVar[int]
    json: str
    def __init__(self, json: _Optional[str] = ...) -> None: ...

class AuditOrdersResponse(_message.Message):
    __slots__ = ("items", "next_cursor")
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    NEXT_CURSOR_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[AuditOrderItem]
    next_cursor: str
    def __init__(self, items: _Optional[_Iterable[_Union[AuditOrderItem, _Mapping]]] = ..., next_cursor: _Optional[str] = ...) -> None: ...

class AuditTradesRequest(_message.Message):
    __slots__ = ("cursor", "limit", "date_from", "date_to", "area", "product", "user_code", "v_member_short_id", "time_basis", "voltnir_user_short_id", "voltnir_username", "sort_order", "contract_id")
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
    SORT_ORDER_FIELD_NUMBER: _ClassVar[int]
    CONTRACT_ID_FIELD_NUMBER: _ClassVar[int]
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
    sort_order: str
    contract_id: str
    def __init__(self, cursor: _Optional[str] = ..., limit: _Optional[int] = ..., date_from: _Optional[str] = ..., date_to: _Optional[str] = ..., area: _Optional[str] = ..., product: _Optional[str] = ..., user_code: _Optional[str] = ..., v_member_short_id: _Optional[str] = ..., time_basis: _Optional[str] = ..., voltnir_user_short_id: _Optional[str] = ..., voltnir_username: _Optional[str] = ..., sort_order: _Optional[str] = ..., contract_id: _Optional[str] = ...) -> None: ...

class AuditTradeItem(_message.Message):
    __slots__ = ("json",)
    JSON_FIELD_NUMBER: _ClassVar[int]
    json: str
    def __init__(self, json: _Optional[str] = ...) -> None: ...

class AuditTradesResponse(_message.Message):
    __slots__ = ("items", "next_cursor")
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    NEXT_CURSOR_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[AuditTradeItem]
    next_cursor: str
    def __init__(self, items: _Optional[_Iterable[_Union[AuditTradeItem, _Mapping]]] = ..., next_cursor: _Optional[str] = ...) -> None: ...

class AuditPublicTradesRequest(_message.Message):
    __slots__ = ("cursor", "limit", "date_from", "date_to", "area", "product", "state", "sort_order")
    CURSOR_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    DATE_FROM_FIELD_NUMBER: _ClassVar[int]
    DATE_TO_FIELD_NUMBER: _ClassVar[int]
    AREA_FIELD_NUMBER: _ClassVar[int]
    PRODUCT_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    SORT_ORDER_FIELD_NUMBER: _ClassVar[int]
    cursor: str
    limit: int
    date_from: str
    date_to: str
    area: str
    product: str
    state: str
    sort_order: str
    def __init__(self, cursor: _Optional[str] = ..., limit: _Optional[int] = ..., date_from: _Optional[str] = ..., date_to: _Optional[str] = ..., area: _Optional[str] = ..., product: _Optional[str] = ..., state: _Optional[str] = ..., sort_order: _Optional[str] = ...) -> None: ...

class AuditPublicTradeItem(_message.Message):
    __slots__ = ("json",)
    JSON_FIELD_NUMBER: _ClassVar[int]
    json: str
    def __init__(self, json: _Optional[str] = ...) -> None: ...

class AuditPublicTradesResponse(_message.Message):
    __slots__ = ("items", "next_cursor")
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    NEXT_CURSOR_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[AuditPublicTradeItem]
    next_cursor: str
    def __init__(self, items: _Optional[_Iterable[_Union[AuditPublicTradeItem, _Mapping]]] = ..., next_cursor: _Optional[str] = ...) -> None: ...

class AuditEventsRequest(_message.Message):
    __slots__ = ("cursor", "limit", "date_from", "date_to", "action", "target_type", "actor_short_id", "outcome", "sort_order", "v_member_short_id")
    CURSOR_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    DATE_FROM_FIELD_NUMBER: _ClassVar[int]
    DATE_TO_FIELD_NUMBER: _ClassVar[int]
    ACTION_FIELD_NUMBER: _ClassVar[int]
    TARGET_TYPE_FIELD_NUMBER: _ClassVar[int]
    ACTOR_SHORT_ID_FIELD_NUMBER: _ClassVar[int]
    OUTCOME_FIELD_NUMBER: _ClassVar[int]
    SORT_ORDER_FIELD_NUMBER: _ClassVar[int]
    V_MEMBER_SHORT_ID_FIELD_NUMBER: _ClassVar[int]
    cursor: str
    limit: int
    date_from: str
    date_to: str
    action: str
    target_type: str
    actor_short_id: str
    outcome: str
    sort_order: str
    v_member_short_id: str
    def __init__(self, cursor: _Optional[str] = ..., limit: _Optional[int] = ..., date_from: _Optional[str] = ..., date_to: _Optional[str] = ..., action: _Optional[str] = ..., target_type: _Optional[str] = ..., actor_short_id: _Optional[str] = ..., outcome: _Optional[str] = ..., sort_order: _Optional[str] = ..., v_member_short_id: _Optional[str] = ...) -> None: ...

class AuditEventItem(_message.Message):
    __slots__ = ("json",)
    JSON_FIELD_NUMBER: _ClassVar[int]
    json: str
    def __init__(self, json: _Optional[str] = ...) -> None: ...

class AuditEventsResponse(_message.Message):
    __slots__ = ("items", "next_cursor")
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    NEXT_CURSOR_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[AuditEventItem]
    next_cursor: str
    def __init__(self, items: _Optional[_Iterable[_Union[AuditEventItem, _Mapping]]] = ..., next_cursor: _Optional[str] = ...) -> None: ...

class M7ErrorsRequest(_message.Message):
    __slots__ = ("cursor", "limit", "date_from", "date_to", "kind", "category", "err_code", "sort_order")
    CURSOR_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    DATE_FROM_FIELD_NUMBER: _ClassVar[int]
    DATE_TO_FIELD_NUMBER: _ClassVar[int]
    KIND_FIELD_NUMBER: _ClassVar[int]
    CATEGORY_FIELD_NUMBER: _ClassVar[int]
    ERR_CODE_FIELD_NUMBER: _ClassVar[int]
    SORT_ORDER_FIELD_NUMBER: _ClassVar[int]
    cursor: str
    limit: int
    date_from: str
    date_to: str
    kind: str
    category: str
    err_code: int
    sort_order: str
    def __init__(self, cursor: _Optional[str] = ..., limit: _Optional[int] = ..., date_from: _Optional[str] = ..., date_to: _Optional[str] = ..., kind: _Optional[str] = ..., category: _Optional[str] = ..., err_code: _Optional[int] = ..., sort_order: _Optional[str] = ...) -> None: ...

class M7ErrorItem(_message.Message):
    __slots__ = ("json",)
    JSON_FIELD_NUMBER: _ClassVar[int]
    json: str
    def __init__(self, json: _Optional[str] = ...) -> None: ...

class M7ErrorsResponse(_message.Message):
    __slots__ = ("items", "next_cursor")
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    NEXT_CURSOR_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[M7ErrorItem]
    next_cursor: str
    def __init__(self, items: _Optional[_Iterable[_Union[M7ErrorItem, _Mapping]]] = ..., next_cursor: _Optional[str] = ...) -> None: ...

class ListExchangeMessagesRequest(_message.Message):
    __slots__ = ("cursor", "limit", "date_from", "date_to", "severity", "scope", "code", "sort_order")
    CURSOR_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    DATE_FROM_FIELD_NUMBER: _ClassVar[int]
    DATE_TO_FIELD_NUMBER: _ClassVar[int]
    SEVERITY_FIELD_NUMBER: _ClassVar[int]
    SCOPE_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    SORT_ORDER_FIELD_NUMBER: _ClassVar[int]
    cursor: str
    limit: int
    date_from: str
    date_to: str
    severity: str
    scope: str
    code: int
    sort_order: str
    def __init__(self, cursor: _Optional[str] = ..., limit: _Optional[int] = ..., date_from: _Optional[str] = ..., date_to: _Optional[str] = ..., severity: _Optional[str] = ..., scope: _Optional[str] = ..., code: _Optional[int] = ..., sort_order: _Optional[str] = ...) -> None: ...

class ExchangeMessageItem(_message.Message):
    __slots__ = ("json",)
    JSON_FIELD_NUMBER: _ClassVar[int]
    json: str
    def __init__(self, json: _Optional[str] = ...) -> None: ...

class ListExchangeMessagesResponse(_message.Message):
    __slots__ = ("items", "next_cursor")
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    NEXT_CURSOR_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[ExchangeMessageItem]
    next_cursor: str
    def __init__(self, items: _Optional[_Iterable[_Union[ExchangeMessageItem, _Mapping]]] = ..., next_cursor: _Optional[str] = ...) -> None: ...

class ListSystemLogRequest(_message.Message):
    __slots__ = ("cursor", "limit", "min_level", "date_from", "date_to")
    CURSOR_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    MIN_LEVEL_FIELD_NUMBER: _ClassVar[int]
    DATE_FROM_FIELD_NUMBER: _ClassVar[int]
    DATE_TO_FIELD_NUMBER: _ClassVar[int]
    cursor: int
    limit: int
    min_level: str
    date_from: str
    date_to: str
    def __init__(self, cursor: _Optional[int] = ..., limit: _Optional[int] = ..., min_level: _Optional[str] = ..., date_from: _Optional[str] = ..., date_to: _Optional[str] = ...) -> None: ...

class SystemLogItem(_message.Message):
    __slots__ = ("json",)
    JSON_FIELD_NUMBER: _ClassVar[int]
    json: str
    def __init__(self, json: _Optional[str] = ...) -> None: ...

class SystemLogBuffer(_message.Message):
    __slots__ = ("enabled", "level", "capacity", "len", "oldest_seq", "oldest_ts_ms", "newest_seq", "started_at_ms", "dropped", "has_entries")
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    LEVEL_FIELD_NUMBER: _ClassVar[int]
    CAPACITY_FIELD_NUMBER: _ClassVar[int]
    LEN_FIELD_NUMBER: _ClassVar[int]
    OLDEST_SEQ_FIELD_NUMBER: _ClassVar[int]
    OLDEST_TS_MS_FIELD_NUMBER: _ClassVar[int]
    NEWEST_SEQ_FIELD_NUMBER: _ClassVar[int]
    STARTED_AT_MS_FIELD_NUMBER: _ClassVar[int]
    DROPPED_FIELD_NUMBER: _ClassVar[int]
    HAS_ENTRIES_FIELD_NUMBER: _ClassVar[int]
    enabled: bool
    level: str
    capacity: int
    len: int
    oldest_seq: int
    oldest_ts_ms: int
    newest_seq: int
    started_at_ms: int
    dropped: int
    has_entries: bool
    def __init__(self, enabled: bool = ..., level: _Optional[str] = ..., capacity: _Optional[int] = ..., len: _Optional[int] = ..., oldest_seq: _Optional[int] = ..., oldest_ts_ms: _Optional[int] = ..., newest_seq: _Optional[int] = ..., started_at_ms: _Optional[int] = ..., dropped: _Optional[int] = ..., has_entries: bool = ...) -> None: ...

class ListSystemLogResponse(_message.Message):
    __slots__ = ("items", "next_cursor", "truncated", "buffer")
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    NEXT_CURSOR_FIELD_NUMBER: _ClassVar[int]
    TRUNCATED_FIELD_NUMBER: _ClassVar[int]
    BUFFER_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[SystemLogItem]
    next_cursor: int
    truncated: bool
    buffer: SystemLogBuffer
    def __init__(self, items: _Optional[_Iterable[_Union[SystemLogItem, _Mapping]]] = ..., next_cursor: _Optional[int] = ..., truncated: bool = ..., buffer: _Optional[_Union[SystemLogBuffer, _Mapping]] = ...) -> None: ...

class WatchContractsRequest(_message.Message):
    __slots__ = ("areas", "products", "contract_ids")
    AREAS_FIELD_NUMBER: _ClassVar[int]
    PRODUCTS_FIELD_NUMBER: _ClassVar[int]
    CONTRACT_IDS_FIELD_NUMBER: _ClassVar[int]
    areas: _containers.RepeatedScalarFieldContainer[str]
    products: _containers.RepeatedScalarFieldContainer[str]
    contract_ids: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, areas: _Optional[_Iterable[str]] = ..., products: _Optional[_Iterable[str]] = ..., contract_ids: _Optional[_Iterable[int]] = ...) -> None: ...

class ContractsEvent(_message.Message):
    __slots__ = ("type", "contracts", "area_id", "contract_id")
    class EventType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        SNAPSHOT: _ClassVar[ContractsEvent.EventType]
        UPSERT: _ClassVar[ContractsEvent.EventType]
        DELETE: _ClassVar[ContractsEvent.EventType]
    SNAPSHOT: ContractsEvent.EventType
    UPSERT: ContractsEvent.EventType
    DELETE: ContractsEvent.EventType
    TYPE_FIELD_NUMBER: _ClassVar[int]
    CONTRACTS_FIELD_NUMBER: _ClassVar[int]
    AREA_ID_FIELD_NUMBER: _ClassVar[int]
    CONTRACT_ID_FIELD_NUMBER: _ClassVar[int]
    type: ContractsEvent.EventType
    contracts: _containers.RepeatedCompositeFieldContainer[Contract]
    area_id: str
    contract_id: str
    def __init__(self, type: _Optional[_Union[ContractsEvent.EventType, str]] = ..., contracts: _Optional[_Iterable[_Union[Contract, _Mapping]]] = ..., area_id: _Optional[str] = ..., contract_id: _Optional[str] = ...) -> None: ...

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
    __slots__ = ("type", "orders", "reason", "rejected_action", "err_code")
    class EventType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        SNAPSHOT: _ClassVar[OrdersEvent.EventType]
        ADDED: _ClassVar[OrdersEvent.EventType]
        MODIFIED: _ClassVar[OrdersEvent.EventType]
        CANCELLED: _ClassVar[OrdersEvent.EventType]
        FILLED: _ClassVar[OrdersEvent.EventType]
        REJECTED: _ClassVar[OrdersEvent.EventType]
    SNAPSHOT: OrdersEvent.EventType
    ADDED: OrdersEvent.EventType
    MODIFIED: OrdersEvent.EventType
    CANCELLED: OrdersEvent.EventType
    FILLED: OrdersEvent.EventType
    REJECTED: OrdersEvent.EventType
    TYPE_FIELD_NUMBER: _ClassVar[int]
    ORDERS_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    REJECTED_ACTION_FIELD_NUMBER: _ClassVar[int]
    ERR_CODE_FIELD_NUMBER: _ClassVar[int]
    type: OrdersEvent.EventType
    orders: _containers.RepeatedCompositeFieldContainer[OwnOrder]
    reason: str
    rejected_action: str
    err_code: int
    def __init__(self, type: _Optional[_Union[OrdersEvent.EventType, str]] = ..., orders: _Optional[_Iterable[_Union[OwnOrder, _Mapping]]] = ..., reason: _Optional[str] = ..., rejected_action: _Optional[str] = ..., err_code: _Optional[int] = ...) -> None: ...

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
    __slots__ = ("contract_ids",)
    CONTRACT_IDS_FIELD_NUMBER: _ClassVar[int]
    contract_ids: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, contract_ids: _Optional[_Iterable[int]] = ...) -> None: ...

class WatchPnlRequest(_message.Message):
    __slots__ = ("v_member_short_id",)
    V_MEMBER_SHORT_ID_FIELD_NUMBER: _ClassVar[int]
    v_member_short_id: str
    def __init__(self, v_member_short_id: _Optional[str] = ...) -> None: ...

class WatchSlotPositionsRequest(_message.Message):
    __slots__ = ("delivery_area", "from_ms", "to_ms", "v_member_short_id")
    DELIVERY_AREA_FIELD_NUMBER: _ClassVar[int]
    FROM_MS_FIELD_NUMBER: _ClassVar[int]
    TO_MS_FIELD_NUMBER: _ClassVar[int]
    V_MEMBER_SHORT_ID_FIELD_NUMBER: _ClassVar[int]
    delivery_area: str
    from_ms: int
    to_ms: int
    v_member_short_id: str
    def __init__(self, delivery_area: _Optional[str] = ..., from_ms: _Optional[int] = ..., to_ms: _Optional[int] = ..., v_member_short_id: _Optional[str] = ...) -> None: ...

class WatchTradeTapeRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class TradeTapeEvent(_message.Message):
    __slots__ = ("type", "rows", "sent_at_ms")
    class EventType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        SNAPSHOT: _ClassVar[TradeTapeEvent.EventType]
        UPSERTED: _ClassVar[TradeTapeEvent.EventType]
    SNAPSHOT: TradeTapeEvent.EventType
    UPSERTED: TradeTapeEvent.EventType
    TYPE_FIELD_NUMBER: _ClassVar[int]
    ROWS_FIELD_NUMBER: _ClassVar[int]
    SENT_AT_MS_FIELD_NUMBER: _ClassVar[int]
    type: TradeTapeEvent.EventType
    rows: _containers.RepeatedCompositeFieldContainer[TradeTapeRow]
    sent_at_ms: int
    def __init__(self, type: _Optional[_Union[TradeTapeEvent.EventType, str]] = ..., rows: _Optional[_Iterable[_Union[TradeTapeRow, _Mapping]]] = ..., sent_at_ms: _Optional[int] = ...) -> None: ...

class TradeTapeRow(_message.Message):
    __slots__ = ("trade_id", "contract_id", "area_id", "prod", "name", "delivery_start", "px", "qty", "exec_time", "exec_time_ms", "state")
    TRADE_ID_FIELD_NUMBER: _ClassVar[int]
    CONTRACT_ID_FIELD_NUMBER: _ClassVar[int]
    AREA_ID_FIELD_NUMBER: _ClassVar[int]
    PROD_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    DELIVERY_START_FIELD_NUMBER: _ClassVar[int]
    PX_FIELD_NUMBER: _ClassVar[int]
    QTY_FIELD_NUMBER: _ClassVar[int]
    EXEC_TIME_FIELD_NUMBER: _ClassVar[int]
    EXEC_TIME_MS_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    trade_id: str
    contract_id: int
    area_id: _wrappers_pb2.StringValue
    prod: _wrappers_pb2.StringValue
    name: _wrappers_pb2.StringValue
    delivery_start: _wrappers_pb2.StringValue
    px: int
    qty: int
    exec_time: str
    exec_time_ms: int
    state: str
    def __init__(self, trade_id: _Optional[str] = ..., contract_id: _Optional[int] = ..., area_id: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., prod: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., name: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., delivery_start: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., px: _Optional[int] = ..., qty: _Optional[int] = ..., exec_time: _Optional[str] = ..., exec_time_ms: _Optional[int] = ..., state: _Optional[str] = ...) -> None: ...

class WatchHub2HubRequest(_message.Message):
    __slots__ = ("delivery_area_from", "delivery_from", "delivery_to")
    DELIVERY_AREA_FROM_FIELD_NUMBER: _ClassVar[int]
    DELIVERY_FROM_FIELD_NUMBER: _ClassVar[int]
    DELIVERY_TO_FIELD_NUMBER: _ClassVar[int]
    delivery_area_from: str
    delivery_from: str
    delivery_to: str
    def __init__(self, delivery_area_from: _Optional[str] = ..., delivery_from: _Optional[str] = ..., delivery_to: _Optional[str] = ...) -> None: ...

class Hub2HubEvent(_message.Message):
    __slots__ = ("snapshot", "update", "heartbeat")
    SNAPSHOT_FIELD_NUMBER: _ClassVar[int]
    UPDATE_FIELD_NUMBER: _ClassVar[int]
    HEARTBEAT_FIELD_NUMBER: _ClassVar[int]
    snapshot: Hub2HubSnapshot
    update: Hub2HubUpdate
    heartbeat: Hub2HubHeartbeat
    def __init__(self, snapshot: _Optional[_Union[Hub2HubSnapshot, _Mapping]] = ..., update: _Optional[_Union[Hub2HubUpdate, _Mapping]] = ..., heartbeat: _Optional[_Union[Hub2HubHeartbeat, _Mapping]] = ...) -> None: ...

class Hub2HubSnapshot(_message.Message):
    __slots__ = ("enabled", "capacity_connected", "data")
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    CAPACITY_CONNECTED_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    enabled: bool
    capacity_connected: bool
    data: _containers.RepeatedCompositeFieldContainer[AtcEntry]
    def __init__(self, enabled: bool = ..., capacity_connected: bool = ..., data: _Optional[_Iterable[_Union[AtcEntry, _Mapping]]] = ...) -> None: ...

class Hub2HubUpdate(_message.Message):
    __slots__ = ("rows", "source_area", "dlvry_start", "dlvry_end")
    ROWS_FIELD_NUMBER: _ClassVar[int]
    SOURCE_AREA_FIELD_NUMBER: _ClassVar[int]
    DLVRY_START_FIELD_NUMBER: _ClassVar[int]
    DLVRY_END_FIELD_NUMBER: _ClassVar[int]
    rows: _containers.RepeatedCompositeFieldContainer[AtcEntry]
    source_area: str
    dlvry_start: str
    dlvry_end: str
    def __init__(self, rows: _Optional[_Iterable[_Union[AtcEntry, _Mapping]]] = ..., source_area: _Optional[str] = ..., dlvry_start: _Optional[str] = ..., dlvry_end: _Optional[str] = ...) -> None: ...

class Hub2HubHeartbeat(_message.Message):
    __slots__ = ("connected", "ts_ms")
    CONNECTED_FIELD_NUMBER: _ClassVar[int]
    TS_MS_FIELD_NUMBER: _ClassVar[int]
    connected: bool
    ts_ms: int
    def __init__(self, connected: bool = ..., ts_ms: _Optional[int] = ...) -> None: ...

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

class WatchExchangeMessagesRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class WatchSystemLogRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...
