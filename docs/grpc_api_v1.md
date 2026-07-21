# Voltnir gRPC API v1: Reference

> Auto-generated from the Voltnir API reference.

SDKs [Python](#python-sdk) JavaScriptsoon Gosoon

## What is gRPC?

gRPC is a high-performance RPC framework that runs on top of HTTP/2. A client calls a method on a remote service as if it were a local function; the framework takes care of serialisation (Protocol Buffers), transport, multiplexing, streaming, and authentication metadata. Voltnir's gRPC surface is defined by a single `.proto` file ([proto_volt/voltnir_api_v1.proto](https://github.com/Voltnir/voltnir-sdk/blob/master/proto_volt/voltnir_api_v1.proto)) which is the canonical contract; every SDK on this page is a convenience wrapper around stubs generated from that file.

Compared with Voltnir's REST API the differences relevant to integrators are:

- **Schema-first.** Field names, types, and enums are declared in the `.proto` and generated into client code, so there is no hand-rolled JSON parsing.
- **Streaming.** Long-lived server-streaming RPCs replace the REST *poll-token-fetch* dance for exports and add live push feeds (`WatchContract`, `WatchOrders`, `WatchTrades`, `WatchPnl`, and more: 11 in total) that REST has no equivalent for.
- **Status codes are an enum, not HTTP.** Failures use `grpc.StatusCode` (e.g. `UNAUTHENTICATED`, `NOT_FOUND`); see [Errors](#errors) for the mapping.
- **Functional parity with REST.** Every unary RPC mirrors a REST endpoint exactly: same fields, same units, same permission gates, same validation rules. The streaming RPCs are the only gRPC-only surface.

> [!NOTE]
> New to gRPC? Start with the [Python SDK](#python-sdk) section below. It hides the protocol details behind idiomatic sync / async clients. The [Errors](#errors) and [Streaming](#streaming) sections cover everything you need to know about wire behaviour.

## Connection

Standard gRPC over HTTP/2. Any conformant client (tonic, grpcio, grpc-go, @grpc/grpc-js, …) can talk to it.

| Setting | Default | Notes |
| --- | --- | --- |
| Port | `3443` | Configured via `grpc_server.port`. Independent of the REST port (`3000`); both transports run side by side. |
| TLS | Off | Plaintext HTTP/2 by default. Set `grpc_server.tls.cert_path` and `key_path` in YAML to enable. Cert rotation requires a server restart. |
| Protocol | HTTP/2 | Standard gRPC framing. No gRPC-Web or HTTP/2 transcoding in v1. |
| Streaming | Server-only | 13 server-streaming RPCs (2 export + 11 watch); no client-streaming or bidi streams in v1. |

#### Bare-bones smoke test (grpcurl)

```
grpcurl -plaintext \
  -H 'authorization: Bearer <your_api_key>' \
  localhost:3443 \
  voltnir.api.v1.VoltAPI/GetState
```

If you see `UNAUTHENTICATED: missing bearer token` the metadata header is malformed; the key name is lowercase `authorization` and the scheme is the literal string `Bearer` (capital B, single space).

## Authentication

Every RPC requires an `authorization: Bearer <api-key>` entry in the request **metadata**. The server SHA-256-hashes the token and validates it against your account. Tokens cannot be retrieved after creation; if a key is lost, rotate it via `RotateApiKey`.

> [!NOTE]
> **Required on every call:**
>  metadata key `authorization` (lowercase) → value `Bearer <your_api_key>` (capital `B`).

#### Auth failures

| Cause | gRPC `StatusCode` |
| --- | --- |
| Missing `authorization` metadata | `UNAUTHENTICATED` |
| Header present but not in `Bearer <token>` form | `UNAUTHENTICATED` |
| Hashed token doesn't match any user | `UNAUTHENTICATED` |
| Caller lacks the required `Permission` | `PERMISSION_DENIED` |

#### Permission set

Permission gates are enforced per-RPC. The variants are identical to REST:

| Permission | Grants |
| --- | --- |
| `create_order` | Submit new orders |
| `modify_order` | Modify existing orders (price/qty/activate/deactivate) |
| `delete_order` | Cancel one or all orders |
| `toggle_trading` | Set the *trading allowed* kill-switch |
| `set_position_limit` | Update the per-contract net-position cap |
| `set_cash_limit` | Update the global (overarching-member) cash limit |
| `set_self_trade_policy` | Set the self-trade (cross-trade) prevention policy |
| `manage_users` | List / create / delete users, set permissions, rotate keys, set member assignments |
| `manage_members` | List / create / patch virtual members |
| `read_audit` | Query the audit log |
| `read_m7_errors` | Query the M7 exchange-error log |
| `read_pnl` | Read firm-wide P&L (every member + house book); without it a caller sees only their assigned members' P&L |
| `read_orders` | Read the firm-wide order book (every member + untagged house orders); without it a caller sees only their assigned members' orders |
| `read_state` | Read the runtime-health state (`GetState` / `WatchState`) |
| `read_status` | Read the trading-posture aggregate: throttling, kill-switch, cash limits, license (`GetStatus` / `WatchStatus`) |
| `export_reports` | Export orders / trades |
| `restart_system` | Trigger graceful shutdown |
| `bypass_member_check` | Act on any virtual member without an explicit assignment, skip the per-member position-limit check, and see firm-wide orders and P&L |
| `trade_global` | Submit orders on the global (house) account; without it a caller must trade under a member |

## Errors

gRPC uses a status enum instead of HTTP codes. Voltnir's mapping is exhaustive and matches REST 1:1, which is useful when porting clients between transports.

| REST status | gRPC `StatusCode` | Trigger |
| --- | --- | --- |
| 400 | `INVALID_ARGUMENT` | Malformed input, unknown enum value, parse error |
| 401 | `UNAUTHENTICATED` | Missing / invalid bearer token |
| 403 | `PERMISSION_DENIED` | Caller lacks the required permission |
| 404 | `NOT_FOUND` | Unknown contract / order / user / member |
| 409 | `ABORTED` | State conflict, e.g. modify already in progress |
| 422 | `FAILED_PRECONDITION` | Position limit / cash limit / self-cross exceeded, or trading disabled (operator kill-switch) |
| 500 | `INTERNAL` | Unexpected error |
| 503 | `UNAVAILABLE` | DB unavailable, system not operational |
| 504 | `DEADLINE_EXCEEDED` | M7 did not acknowledge within `system.order_ack_timeout_ms` (default 2s) |

Error details are carried in `Status::message` as a plain string. No structured `google.rpc.Status.details` payload is emitted in v1.

## Streaming semantics

All 13 streaming RPCs are **server-streaming**: the client sends one request and reads many responses until the server closes the stream or the client cancels. Cancellation is observed at the next safe boundary, checked at every database page and every chunk send, so cancelling a long export or a slow watch is cheap and immediate.

### Export streams (`ExportOrders` / `ExportTrades`)

Replaces REST's two-step (POST → token → GET) export with a single long-lived call. The response is a stream of `ExportChunk` messages each carrying a `bytes data` field; concatenate them in order to reconstruct the file. Chunk size is currently 64 KiB. `ExportRequest.format` must be `JSON` or `CSV`; `from` and `to` are **required** RFC 3339 timestamps (`from` < `to`), matching the REST + WS export contract. An unset format, empty/out-of-order dates, or a malformed timestamp returns `INVALID_ARGUMENT`.

If the client cancels, the stream stops promptly; no wasted work on a result nobody will read.

### Watch streams (`WatchContract` / `WatchOrder` / `WatchOrders`)

- **Snapshot first.** The first event after subscribe is always `SNAPSHOT`, carrying the current full state (one `Contract`, one `OwnOrder`, or the full filtered list).
- **Lag recovery.** If the server falls behind, the stream recovers with a `SNAPSHOT` and continues; it doesn't tear down. Treat any post-initial `SNAPSHOT` as a "start over" signal. Recovery is coalesced: a burst of lag yields at most one recovery `SNAPSHOT`, and `WatchContract` skips it entirely when the contract hasn't changed since the last event you received (you're already current), so don't rely on a snapshot per lagged event.
- **Terminal events close the stream.** `WatchOrder` closes cleanly on `FILLED` / `CANCELLED` / `REJECTED`, so clients don't have to track lifecycle state. `FILLED` carries the final order body (real price/side/ids, `quantity == 0`, state `INACTIVE`) captured before the store removed it. Note that M7's `INACTIVE` state does not distinguish cancellation from expiry, and a full fill reported through an execution-report upsert (rather than the trade path) also lands as `CANCELLED`, so treat `CANCELLED` as "left the book without a trade-path fill".
- **Pending orders are watchable.** `WatchOrder` on a locally-submitted order that hasn't been acknowledged by M7 yet opens with a `SNAPSHOT` whose body has `state == PENDING` and `order_id == 0` (side/price/quantity/contract are the real submitted values). The M7 ack arrives as the next event with the real `order_id`, so `submit_order → watch_order` is race-free.
- **WatchContract closes with a final `STATE_CHANGE`.** When the watched contract is deleted, tombstoned, or deactivated, the stream emits one last `STATE_CHANGE` carrying the final contract body, then ends.
- **Filter semantics.** `WatchOrders` accepts `delivery_area` alone; `contract_id` requires `delivery_area`, and `contract_id` alone returns `INVALID_ARGUMENT` (same rule as `list_orders`).

**Cancel a stream** by exiting the iterator (`break`) or, in Python, calling `stream.cancel()` on the call object. Both unwind cleanly on the server side. Every watch method also accepts an optional `timeout` (overall gRPC deadline in seconds; the iterator raises `DeadlineExceeded` when it fires) for bounded consumption.

## Units & sentinels

Identical to REST: integer fixed-point on the wire, no floating-point. The full table lives on the REST page; below is the short version every gRPC integrator hits.

| Field | Wire type | Unit | Sentinel for "absent" |
| --- | --- | --- | --- |
| `price` | `sint64` | Cents (CCY/MWh × 100); may be negative | N/A, required where used |
| `quantity` | `uint32` | Sub-MW (MW × 1000) | N/A, required > 0 on submit |
| `display_qty` / `hidden_quantity` | `uint32` | Sub-MW | `0` |
| `contract_id` (orders / trades) | `int64` | M7 numeric ID | `0` |
| `contract_id` (contract / watch) | `string` | M7 string ID | `""` |
| RFC 3339 timestamps | `string` | — | `""` |
| Unix-ms timestamps | `int64` | UTC | `0` |

> [!NOTE]
> Proto3 has no null scalars. A handful of fields use `google.protobuf.Int64Value` / `UInt32Value` / `StringValue` / `BoolValue` wrappers when "absent" must be distinguished from "zero"; see `ModifyOrderRequest` and `PatchMemberRequest`. The full unit table is on the [REST page](rest_api_v1.md#units).

## Python SDK

`voltnir_sdk` wraps the generated gRPC stubs with sync (`VoltnirClient`) and async (`AsyncVoltnirClient`) facades. Both surfaces are identical method-for-method; pick one based on your runtime. Located at `clients/python/`.

#### Install

```bash
# Install from the public repo (GitHub):
pip install "git+https://github.com/Voltnir/voltnir-sdk.git#subdirectory=clients/python"
# …or the Codeberg mirror:
pip install "git+https://codeberg.org/Voltnir/voltnir-sdk.git#subdirectory=clients/python"

# …or from a local checkout:
cd clients/python
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

Generated stubs are vendored under `src/voltnir_sdk/_generated/`, so no `protoc` is required at install time. Add `'.[dev]'` if you also want the codegen toolchain.

License holders can also download a versioned tarball of this SDK (and the raw `.proto` schema bundle for building a client in any other language) from the Voltnir customer portal (see [voltnir.io](https://voltnir.io)). After extracting: `pip install ./voltnir-python-sdk-<version>`. Each artifact ships with a `.sha256` companion (`sha256sum -c`).

#### Quickstart: sync

```
from voltnir_sdk import VoltnirClient, Side, OrderType

with VoltnirClient(host="localhost", port=3443, api_key="…") as client:
    me = client.get_me()
    print(me.username, list(me.permissions))

    contracts = client.list_contracts(area_id="10YBE----------2")
    first = contracts.contracts[0]

    for event in client.watch_contract(area_id=first.area_id, contract_id=first.contract_id):
        print(event.type, event.contract.last_price)
        break
```

#### Quickstart: async

```
import asyncio
from voltnir_sdk import AsyncVoltnirClient

async def main():
    async with AsyncVoltnirClient(host="localhost", port=3443, api_key="…") as c:
        me = await c.get_me()
        print(me.username)
        async for event in c.watch_contract(area_id="10YBE----------2", contract_id="12345"):
            print(event.type)
            break

asyncio.run(main())
```

#### TLS & connection options

```
VoltnirClient(
    host="voltnir.example.com",
    port=3443,
    api_key="…",
    tls=True,
    ca_cert_path="cert.pem",   # trust this PEM (handy for self-signed dev certs)
    timeout=10.0,              # default per-RPC deadline (seconds)
)
```

TLS is opt-in; plaintext is the default. Streams have no per-call timeout; they live until the server closes or the client cancels.

#### Error handling

Every RPC raises a typed subclass of `VoltnirError` on failure. Catch the specific class you care about; everything inherits from the base.

| gRPC status | Exception |
| --- | --- |
| `UNAUTHENTICATED` | `Unauthenticated` |
| `PERMISSION_DENIED` | `PermissionDenied` |
| `NOT_FOUND` | `NotFound` |
| `INVALID_ARGUMENT` | `InvalidArgument` |
| `FAILED_PRECONDITION` | `FailedPrecondition` |
| `ABORTED` | `Aborted` |
| `UNAVAILABLE` | `Unavailable` |
| `DEADLINE_EXCEEDED` | `DeadlineExceeded` |
| `INTERNAL` | `Internal` |
| Anything else | `VoltnirError` (base) |

```
from voltnir_sdk import VoltnirClient, NotFound, PermissionDenied

try:
    client.set_trading_allowed(allowed=False)
except PermissionDenied as e:
    print("missing toggle_trading:", e.message)
except NotFound as e:
    print("missing prerequisite:", e.message)
```

Each instance carries `e.code` (the `grpc.StatusCode`), `e.message` (server detail), and `e.rpc` (which RPC raised it).

## SDK reference: Orders

Submit, modify, cancel, and look up your orders. Mirrors the REST `/api/v1/order(s)` endpoints 1:1; same fields, same units, same permission gates.

### `Unary` `client.submit_order(**kwargs)`

_Permission: create_order_

Submit a new order to the exchange. Specify the contract either by `contract_id` (numeric, int64) or by `product` + `delivery_start`. Returns the post-ack state. Rejected with `FAILED_PRECONDITION` when the operator kill-switch is engaged (`set_trading_allowed(allowed=False)`).

#### Arguments

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `side` | `Side` enum | Yes | `Side.BUY` or `Side.SELL`. |
| `price` | `sint64` | Yes | Cents/MWh (may be negative). |
| `quantity` | `uint32` | Yes | Sub-MW. Must be > 0. |
| `delivery_area_id` | `string` | Yes | EIC area code, ≤ 64 chars. |
| `contract_id` | `int64` | Cond* | M7 contract id. Either this OR `product`+`delivery_start`. |
| `product` | `string` | Cond* | Product code (e.g. `"H"`), used with `delivery_start`. |
| `delivery_start` | `string` | Cond* | RFC 3339: used with `product` to look up the contract. |
| `order_type` | `OrderType` | No | Default `REGULAR`. |
| `exe_restriction` | `ExeRestriction` | No | Default `NON`. Options: `NON`, `FOK`, `IOC`, `AON`. **`FOK`/`IOC` require `validity_res` = `VALIDITY_NON`**; leaving the `GFS` default returns `INVALID_ARGUMENT`. |
| `validity_res` | `ValidityRes` | No | Default `GFS`. Options: `GFS`, `GTD`, `VALIDITY_NON`. Must be `VALIDITY_NON` when `exe_restriction` is `FOK` or `IOC`. |
| `entry_state` | `string` | No | Default `"ACTI"`. Use `"HIBE"` to submit hibernated. |
| `display_qty` | `uint32` | Cond | Required for iceberg orders, and rejected on any other order type. Must be < `quantity`. |
| `validity_date` | `string` | Cond | RFC 3339. Required when `validity_res` = `GTD`. |
| `pre_arranged_acct` | `string` | Cond | Required when `order_type` = `PRE_ARRANGED`. |
| `v_member_short_id` | `string` | No | Virtual member tag. |
| `client_order_id` | `string` | No | Optional idempotency key (must be a UUID); `""` → the gateway generates one. Reusing one still attached to a live order is rejected (`INVALID_ARGUMENT`). |

> [!NOTE]
> `order_type` accepts `REGULAR`, `BLOCK`, `ICEBERG`, `BALANCE`, `PRE_ARRANGED`, `EXCHANGE_PRE_ARRANGED` on submit. `STOP`, `PRIVATE`, and `UNKNOWN_TYPE` are read-only values and are rejected with `INVALID_ARGUMENT`.

> [!CAUTION]
> A submitted `PRE_ARRANGED` order reads back as `EXCHANGE_PRE_ARRANGED`; the domain stores a single pre-arranged kind. Don't compare submitted vs returned `order_type` for equality.

#### Returns

`SubmitOrderResponse { client_order_id, state, reason }`: `state` is one of `PENDING`, `ACTIVE`, `INACTIVE`, `HIBERNATED`, `REJECTED`; `REJECTED` always carries a `reason` string. Note an **exchange-side rejection is a successful RPC** (OK with `state = REJECTED`), unlike REST which returns HTTP 422 for the same case; the status-code mapping table above covers gateway-side errors only.

#### Example

```
from voltnir_sdk import Side, OrderType, ValidityRes

resp = client.submit_order(
    side=Side.BUY,
    price=5000,                  # 50.00 EUR/MWh
    quantity=1000,               # 1.0 MW
    delivery_area_id="10YNL----------L",
    product="H",
    delivery_start="2026-04-20T22:00:00Z",
    order_type=OrderType.REGULAR,
    validity_res=ValidityRes.GFS,
)
print(resp.client_order_id, resp.state)
```

### `Unary` `client.modify_order(**kwargs)`

_Permission: modify_order_

Modify, activate, or deactivate (hibernate) an existing order. `price` / `quantity` use proto wrapper types: pass the value to change them, omit them otherwise. Rejected with `FAILED_PRECONDITION` when the operator kill-switch is engaged (`set_trading_allowed(allowed=False)`).

**Member isolation.** Beyond the `modify_order` capability, the caller must be authorized to act on the existing order's member (assigned / `bypass_member_check`; house orders need `trade_global`). `read_orders` grants visibility, not the right to act. An order outside that scope returns `NotFound` (identical to a missing one), so a desk cannot modify or re-tag another member's order.

#### Arguments

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `client_order_id` | `string` | Yes | UUID of the order to modify. |
| `action` | `ModifyAction` | No | Default `MODIFY`. Options: `MODIFY`, `ACTIVATE`, `DEACTIVATE`. |
| `price` | `Int64Value` | Cond | Required when `action` = `MODIFY`. Cents. |
| `quantity` | `UInt32Value` | Cond | Required when `action` = `MODIFY`, and must be greater than zero. Sub-MW. |
| `display_qty` | `uint32` | No | Iceberg display quantity. Sub-MW. |
| `validity_res` | `ValidityRes` | No | Optional change to validity restriction. |
| `validity_date` | `string` | Cond | RFC 3339. Required when `validity_res` = `GTD`. |
| `v_member_short_id` | `string` | No | Virtual member tag. |

> [!CAUTION]
> An unset `action` field is `MODIFY_UNSPECIFIED` (the proto3 zero value), which the server treats as `MODIFY`. Always set `action` explicitly.

#### Returns

`ModifyOrderResponse`: returned once M7 **acknowledges receipt** of the modify. `ABORTED` if M7 rejects it (e.g. the order was concurrently filled or deleted), `DEADLINE_EXCEEDED` if no acknowledgement arrives within `system.order_ack_timeout_ms`. The resulting order state is delivered via `WatchOrder` / `WatchOrders`.

#### Example

```
from google.protobuf.wrappers_pb2 import Int64Value, UInt32Value
from voltnir_sdk import ModifyAction

# Adjust price + quantity
client.modify_order(
    client_order_id="550e8400-e29b-41d4-a716-446655440000",
    action=ModifyAction.MODIFY,
    price=Int64Value(value=5200),
    quantity=UInt32Value(value=2000),
)

# Hibernate
client.modify_order(
    client_order_id="550e8400-e29b-41d4-a716-446655440000",
    action=ModifyAction.DEACTIVATE,
)
```

### `Unary` `client.cancel_order(client_order_id="…")`

_Permission: delete_order_

Cancel a single resting order. The order must be in `ACTIVE` or `HIBERNATED` state with no concurrent modify in flight. Not gated by the kill-switch: a cancel only reduces exposure, so it works even when trading is disabled.

**Member isolation.** Beyond the `delete_order` capability, the caller must be authorized to act on the order's member (assigned / `bypass_member_check`; house orders need `trade_global`). An order outside that scope returns `NotFound`, identical to a missing one.

#### Arguments

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `client_order_id` | `string` | Yes | UUID of the order to cancel. |

#### Returns

`CancelOrderResponse`: returned once M7 **acknowledges receipt** of the cancel. `ABORTED` if M7 rejects it (e.g. the order was concurrently filled or deleted), `DEADLINE_EXCEEDED` if no acknowledgement arrives within `system.order_ack_timeout_ms`.

#### Example

```
client.cancel_order(client_order_id="550e8400-e29b-41d4-a716-446655440000")
```

### `Unary` `client.cancel_all_orders()`

_Permission: delete_order_

Cancel every resting order the caller is authorized to act on.

**Member isolation.** A full-authority caller (`bypass_member_check` + `trade_global`) cancels the whole account in one atomic exchange command. A member-scoped caller cancels only their members' orders, one per order; other desks' and (without `trade_global`) house orders are untouched. `read_orders` does not grant cancellation. `deleted` counts only the orders this caller targeted.

> [!CAUTION]
> Also triggered automatically when `set_trading_allowed(allowed=False)` is invoked. Use deliberately. Not gated by the kill-switch: cancel-all only reduces exposure, so it works even when trading is disabled.

#### Arguments

None.

#### Returns

`CancelAllOrdersResponse` with a `deleted` count = number of active orders this caller targeted at dispatch time. Returned once M7 **acknowledges** the cancel (the atomic account-wide cancel is one request → one ack; a member-scoped cancel awaits each per-order ack). `ABORTED` on rejection, `DEADLINE_EXCEEDED` on timeout.

#### Example

```
resp = client.cancel_all_orders()
print(resp.deleted, "orders dispatched for cancellation")
```

### `Unary` `client.get_order(client_order_id="…")`

_Permission: (authenticated, member-scoped)_

Look up a single order by `client_order_id`. Checks the pending store first; if not there, checks the confirmed store. Exactly one of the two response fields is populated.

**Scoping.** Member-isolated, like `list_orders`. An order tagged with a member the caller may not see (or an untagged house order, for a caller without broad read) returns `NotFound` (identical to an unknown `client_order_id`), so the lookup is not an existence oracle. A caller holding `read_orders`/`bypass_member_check` can look up any order.

#### Arguments

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `client_order_id` | `string` | Yes | UUID of the order to retrieve. |

#### Returns

`GetOrderResponse` with two message fields: `confirmed` (an `OwnOrder`) and `pending` (a `PendingOrder`, submitted but not yet acked by M7). Exactly one of them is populated. Use `resp.HasField("confirmed")` to branch.

#### Example

```
resp = client.get_order(client_order_id="550e8400-e29b-41d4-a716-446655440000")
if resp.HasField("confirmed"):
    print("order_id:", resp.confirmed.order_id, "state:", resp.confirmed.state)
else:
    print("still pending; entry_ts_ms:", resp.pending.entry_ts_ms)
```

### `Unary` `client.list_orders(delivery_area="", contract_id=0, product="", delivery_start="", v_member_short_id="")`

_Permission: (authenticated, member-scoped)_

List the caller's confirmed orders, optionally filtered. Pending orders (not yet acked) are excluded; query `get_order` for those. Filter priority mirrors REST `GET /orders` exactly: `delivery_area` + `contract_id` (exact contract) wins over `delivery_area` + `product` (+ optional `delivery_start`), which wins over `delivery_area` alone (all orders in that area); no filter returns everything. A negative `contract_id` is rejected with `INVALID_ARGUMENT`.

**Scoping.** A caller holding `read_orders` (or `bypass_member_check`) gets the firm-wide order book: every member's orders plus the untagged house orders. Everyone else gets only the orders tagged with a virtual member assigned to them; untagged house orders are withheld.

#### Arguments

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `delivery_area` | `string` | No | `""` = no filter. |
| `contract_id` | `int64` | Cond | `0` = no filter. Requires `delivery_area` if set; `contract_id` alone returns `INVALID_ARGUMENT`. |
| `product` | `string` | Cond | `""` = no filter. Product code (e.g. `"H"`). Requires `delivery_area`; ignored when `contract_id` is set. |
| `delivery_start` | `string` | No | RFC 3339. Narrows the `product` filter to the single contract with this delivery start. Only meaningful with `product`. |
| `v_member_short_id` | `string` | No | Empty = caller's default scope. Non-empty narrows to one member's orders; `PermissionDenied` unless the caller is assigned to it or holds `read_orders`/`bypass_member_check`. |

#### Returns

`ListOrdersResponse { repeated OwnOrder orders }`.

#### Example

```
resp = client.list_orders(delivery_area="10YBE----------2", contract_id=2958876)
for order in resp.orders:
    print(order.client_order_id, order.state, order.quantity)
```

## SDK reference: Contracts

Look up tradeable contracts and their order books.

### `Unary` `client.list_contracts(area_id="…")`

_Permission: (authenticated)_

List every known contract for an area, ordered by `dlvry_start` ascending. Returns full `Contract` messages including state and the order book; call `get_contract` when you also need the caller's own orders, trades, and net position (`ContractDetail`). The `buy`/`sell` arrays are per-order book rows (`ObEntry`: `price`, `quantity`, `order_id`, `order_entry_time`, `order_execution_restriction`, `order_type`, the same row shape as REST; multiple rows can share a price). The `state` enum maps the three known M7 codes (`ACTI`/`SUSP`/`CLOS`) and degrades anything else to `CONTRACT_STATE_UNSPECIFIED`; the companion `state_raw` field always carries the verbatim M7 4-char code (parity with the REST `state` string). `predefined` is `false` for a **user-defined block** contract, on which the exchange rejects regular limit orders (M7 error 1051): only block orders are accepted; do not offer regular order entry there. Note: proto3 cannot represent an unset bool, so a contract whose metadata has not yet arrived also serializes as `predefined=false`. Treat `predefined=false` as block-only only for contracts that otherwise carry full metadata (or read REST/WS, where the field is `null` until known).

#### Arguments

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `area_id` | `string` | Yes | EIC code of the delivery area (e.g. `"10YBE----------2"`). |

#### Returns

`ListContractsResponse { repeated Contract contracts }`.

#### Example

```
resp = client.list_contracts(area_id="10YBE----------2")
print(len(resp.contracts), "contracts")
for c in resp.contracts[:5]:
    print(c.contract_id, c.name, c.state)
```

### `Unary` `client.get_contract(area_id="…", contract_id="…")`

_Permission: (authenticated)_

Fetch full detail for one contract: the `Contract` shape (with order book), the caller's orders against it, the caller's trades, and the caller's net position.

> [!NOTE]
> `contract_id` is a **string** here (the M7 wire-level identifier). It's distinct from `SubmitOrderRequest.contract_id`, which is an `int64`.

#### Arguments

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `area_id` | `string` | Yes | EIC code of the delivery area. |
| `contract_id` | `string` | Yes | M7 contract id (string form). |

#### Returns

`ContractDetail { Contract contract, repeated OwnOrder orders_acknowledged, repeated OwnTrade trades, sint32 net_pos, repeated PendingOrder orders_pending }`. `net_pos` is sub-MW and reflects **executed (ACTI) trades only**; open and pending orders are excluded (mirrors REST). Positive = net long, negative = net short.

**orders_acknowledged vs orders_pending.** `orders_acknowledged` holds orders **M7 has acknowledged**; each carries an `order_id` and an order `state`. `orders_pending` (a `repeated PendingOrder`) holds orders **submitted but not yet acknowledged** by M7: no `order_id`, no `state` (implicitly pending). A pending order is **never** in `orders_acknowledged`; it moves there only once acked. To know whether you already have an order working on this contract, check **both**. (Mirrors the REST `orders_acknowledged` + `orders_pending` split and the WS `orders_acknowledged` + `orders_pending` frame.) Both `OwnOrder` and `PendingOrder` carry `v_member_short_id` (the virtual-member tag; `""` for the default member). On an acknowledged `OwnOrder` it is recovered from the M7 `Txt` field, so an order stays attributable to its member across the submit→ack transition.

#### Example

```
detail = client.get_contract(area_id="10YBE----------2", contract_id="2958876")
print("best bid:", detail.contract.best_bid, "x", detail.contract.best_bid_qty)
print("best ask:", detail.contract.best_ask, "x", detail.contract.best_ask_qty)
print("acknowledged orders:", len(detail.orders_acknowledged))
print("pending (un-acked) orders:", len(detail.orders_pending))
print("my net position:", detail.net_pos, "sub-MW")
```

### `Unary` `client.get_contract_by_delivery(area_id="…", prod="…", dlvry_start="…")`

_Permission: (authenticated)_

Resolve a contract by `(area, product, delivery_start)` and return the same `ContractDetail` shape as `get_contract`.

#### Arguments

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `area_id` | `string` | Yes | EIC code of the delivery area. |
| `prod` | `string` | Yes | Product code (e.g. `"H"`, `"Q"`). |
| `dlvry_start` | `string` | Yes | RFC 3339 delivery start. |

#### Returns

`ContractDetail`. `NOT_FOUND` if no contract matches.

#### Example

```
detail = client.get_contract_by_delivery(
    area_id="10YBE----------2",
    prod="H",
    dlvry_start="2026-04-30T13:00:00Z",
)
print(detail.contract.contract_id, detail.contract.state)
```

### `Unary` `client.get_hub2hub(delivery_area_from="…", delivery_from="…", delivery_to="…", delivery_area_to="")`

_Permission: (authenticated)_

Get the ATC (available transfer capacity) grid for a source delivery area between two timestamps, one row per (source, destination) border edge. Mirrors REST `GET /hub2hub`, including the optional destination filter.

#### Arguments

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `delivery_area_from` | `string` | Yes | EIC code of the source area. |
| `delivery_from` | `string` | Yes | RFC 3339: window start (inclusive on `dlvry_start`). |
| `delivery_to` | `string` | Yes | RFC 3339: window end (exclusive on `dlvry_start`). |
| `delivery_area_to` | `string` | No | `""` = all destinations. EIC code to keep only one destination's rows. |

#### Returns

`GetHub2HubResponse { bool enabled, bool capacity_connected, repeated AtcEntry data }`: `enabled` reflects the gateway's `enable_hub_2_hub` config (when `false`, `data` is always empty), `capacity_connected` is the upstream capacity-feed heartbeat. REST returns the same two flags.

#### Row fields (`AtcEntry`)

| Field | Type | Description |
| --- | --- | --- |
| `source_area` | `string` | Source delivery area EIC. |
| `target_area` | `string` | Destination delivery area EIC. |
| `dlvry_start` | `string` | RFC 3339: start of the delivery window. |
| `dlvry_end` | `string` | RFC 3339: end of the delivery window. |
| `atc_out` | `sint64 (sub-MW)` | ATC out of `source_area` toward `target_area`. Raw signed M7 value in **sub-MW (MW × 1000)**. Divide by 1000 for MW, the same scale as order/trade quantity; identical to the REST `atc_out` field. May be negative (M7 publishes negative ATC). *The M7 XSD does not formally annotate the ATC unit, but the feed encodes it in sub-MW like every other M7 power quantity, confirmed against the live feed.* |
| `atc_in` | `sint64 (sub-MW)` | ATC in the inbound direction (into `source_area`), raw signed M7 value in sub-MW (MW × 1000); divide by 1000 for MW. May be negative. |
| `revision_no` | `int64` | M7 revision number of the ATC publication this row came from. |
| `timestmp` | `string` | RFC 3339: timestamp of the M7 ATC publication. |
| `source_best_bid` | `Int64Value (CCY/MWh × 100)`, nullable | Best resting bid in `source_area` for the same delivery window. `None` when no resting quote is available. |
| `source_best_ask` | `Int64Value (CCY/MWh × 100)`, nullable | Best resting ask in `source_area`. `None` when no resting quote is available. |
| `dest_best_bid` | `Int64Value (CCY/MWh × 100)`, nullable | Best resting bid in `target_area`. `None` when no resting quote is available. |
| `dest_best_ask` | `Int64Value (CCY/MWh × 100)`, nullable | Best resting ask in `target_area`. `None` when no resting quote is available. |

The four `*_best_bid`/`*_best_ask` fields are populated by joining the hub-to-hub feed with the live order-book best-quote state at frame-emit time. They let clients derive a per-border *implicit-spread* (e.g. `dest_best_bid − source_best_ask` for an export-direction order) without taking a separate per-area contracts subscription. A value of `0` in the order book is treated as "no quote" and surfaced as a missing wrapper on the wire (negative power prices are legitimate, so 0 cannot double as the absent sentinel).

#### Example

```
resp = client.get_hub2hub(
    delivery_area_from="10YBE----------2",
    delivery_from="2026-04-30T00:00:00Z",
    delivery_to="2026-05-01T00:00:00Z",
)
for row in resp.data:
    spread = None
    if row.HasField("dest_best_bid") and row.HasField("source_best_ask"):
        spread = (row.dest_best_bid.value - row.source_best_ask.value) / 100.0
    print(row.source_area, "→", row.target_area, row.atc_out, "ATC out",
          f"spread €{spread:+.2f}" if spread is not None else "(no spread)")
```

## SDK reference: System

Health, throttling, and operator controls (kill-switch, position limit, restart).

### `Unary` `client.get_state()`

_Permission: read_state_

Snapshot of overall system health: uptime, AMQP / WS connectivity, operational flag, and a list of any active issues. Gated by `read_state` (`PERMISSION_DENIED` without it). The trading-posture fields (kill-switch, position limit, throttling, cash limits, license) moved to [`GetStatus`](#sdk-get_status).

#### Arguments

None.

#### Returns

`SystemState`: the same shape as REST `GET /api/v1/state` (including the four rolling-average display strings `ws_order_book_avg_processing_time`, `ws_order_book_avg_latency`, `ws_private_data_avg_processing_time`, `ws_private_data_avg_latency`), with one documented parity divergence: the `amqp_authenticated_with` block is omitted entirely on gRPC (REST returns it with only the `v7_token` secret stripped). The former `trading_enabled` + `order_pos_limit` convenience fields have moved off `SystemState` onto [`SystemStatus` (`GetStatus`)](#sdk-get_status); read them there. The nested `license` message (`LicenseView`) carries `status_kind` (`active` / `expiring_soon` / `expired` / `in_grace`), `status_days` (days remaining or elapsed; `0` for `active`), `license_id`, `mode` (`trader` / `desk` capability tier), `environment`, `issued_at`, `expires_at`, the provenance fields `schema_version` / `issuer` / `signing_key_id`, the `holder` sub-message (`LicenseHolder` with `legal_entity` + `portal_user_id`; unset for a free `sim` license), and the authorized EPEX identities: `epex_any` (`true` = any identity, for sim) plus a repeated `epex_identities` (`EpexIdentityView` with `account_id` + `user_id`) when scoped. License expiry does not gate individual RPCs or drop a stream mid-grace, but once the licence is past its grace window the whole gateway shuts down (it also refuses to start). Note: gRPC is served on **every** license tier (`trader` and `desk`); it's a transport, not a desk-only surface. The only desk-only operations are the user/permission/member management RPCs (see [Users & Members](#sdk-list_users)).

#### Example

```
state = client.get_state()
print(state.uptime, "operational:", state.operational)
print("license:", state.license.status_kind, state.license.expires_at)
```

### `Unary` `client.get_status()`

_Permission: read_status_

The trading-posture aggregate in one call: M7 throttling, the trading kill-switch and operational flags, the M7-reported cash/margin limits, the per-contract position limit, the Voltnir order cash limit, and the installed license. Same data as REST `GET /api/v1/status` and the WS `status` stream. Gated by `read_status` (`PERMISSION_DENIED` without it).

#### Arguments

None.

#### Returns

`SystemStatus`: `throttling` (`ThrottlingStatus`, same message as [`GetThrottling`](#sdk-get_throttling)), `trading_enabled` (`bool`; the kill-switch state, same as `GetTradingAllowed`), `operational` (`bool`), `cash_limits` (repeated `CashLimit`, same as [`GetCashLimits`](#sdk-get_cash_limits)), `order_pos_limit` (`sint32`, sub-MW; same as `GetContractLimit`), `cash_limit` (`CashLimitStatus` with the six `int64` cents fields `eur_limit_cents` / `eur_consumed_cents` / `eur_remaining_cents` / `gbp_limit_cents` / `gbp_consumed_cents` / `gbp_remaining_cents`; `remaining = limit − consumed`, a `*_limit_cents` of `0` means that pool is not enforced), and `license` (`LicenseView`, identical to the [`GetState`](#sdk-get_state) license projection).

#### Example

```
status = client.get_status()
print("trading:", status.trading_enabled, "pos_limit:", status.order_pos_limit)
print("eur remaining:", status.cash_limit.eur_remaining_cents / 100)
```

### `Unary` `client.get_throttling()`

_Permission: (authenticated)_

M7 throttling counters as last reported by the exchange. Every field is `optional`; until M7 has sent its first response, all are `None`.

#### Arguments

None.

#### Returns

`ThrottlingStatus`: operations-per-period limits and current counters.

#### Example

```
th = client.get_throttling()
# Fields are proto3 `optional` scalars, so HasField() works directly.
if th.HasField("short_omt_limit_l1"):
    print("short OMT L1 limit:", th.short_omt_limit_l1)
if th.HasField("long_omt_limit_l1"):
    print("long OMT L1 limit:", th.long_omt_limit_l1)
```

### `Unary` `client.get_system_info()`

_Permission: (authenticated)_

M7 system parameters captured on connection: backend version, time zones, data-retention windows, the per-session order cap, capabilities, and the per-message-type request rate limits. The M7-sourced scalars are `optional` and `request_limits` is empty until M7 has sent its first `SystemInfoResp`. `voltnir_version` is this gateway's own software version (not from M7): a plain `string` that is always set, even before the first `SystemInfoResp`.

#### Arguments

None.

#### Returns

`SystemInfo`: `voltnir_version` (this gateway's build, always set) plus the M7 backend metadata and a repeated `RequestLimit` (`message`, `duration_ms`, `rate`) list.

#### Example

```
info = client.get_system_info()
if info.HasField("max_orders"):
    print("max resting orders:", info.max_orders)
for rl in info.request_limits:
    print(rl.message, "→", rl.rate, "per", rl.duration_ms, "ms")
```

### `Unary` `client.get_cash_limits()`

_Permission: (authenticated)_

Snapshot of every currency's M7 cash/margin limit. Mirrors REST `GET /api/v1/cash_limits`. Raw integer fields pair with `dec_shft`: human amount = raw / 10dec_shft. Every field past `currency` is `optional`; partial reports leave them unset.

#### Arguments

None.

#### Returns

`GetCashLimitsResponse { repeated CashLimit limits }`.

#### Example

```
resp = client.get_cash_limits()
for lim in resp.limits:
    if lim.HasField("current_limit") and lim.HasField("dec_shft"):
        print(lim.currency, lim.current_limit / (10 ** lim.dec_shft))
```

### `Unary` `client.list_permissions()`

_Permission: manage_users_

The catalog of assignable permissions: every permission `code` that can be granted via `set_permissions`, paired with a human-readable `description`. Mirrors REST `GET /api/v1/permissions`. Render this rather than hardcoding the list, so a new permission appears automatically. Server-defined and stable within an API version.

#### Arguments

None.

#### Returns

`ListPermissionsResponse { repeated PermissionInfo permissions }`, where `PermissionInfo { string code; string description; }`.

#### Example

```
resp = client.list_permissions()
for p in resp.permissions:
    print(p.code, "-", p.description)
```

### `Unary` `client.get_pnl(v_member_short_id=…)`

_Permission: (authenticated, member-scoped)_

Recompute the caller-scoped PnL snapshot from the live trade store + order book. Mirrors REST `GET /api/v1/pnl` and the WebSocket `pnl` stream. Money is q8 units = M7-px × sub-MW = **EUR × 100,000**; divide by 100,000 to render EUR. Open / pending orders do not contribute.

**Scoping.** A caller holding `read_pnl` (or `bypass_member_check`) gets the firm-wide snapshot: every member plus the house-account `per_contract`/`per_area_prod` rollups. Everyone else gets only the `per_vm`/`per_vm_area_prod` rows for their assigned members, with the firm-wide rollups empty.

#### Arguments

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `v_member_short_id` | `string` | No | Empty = caller's default scope. Non-empty narrows to one member's rows; `PermissionDenied` unless the caller is assigned to it or holds `read_pnl`/`bypass_member_check`. |

#### Returns

`PnlSnapshot` with four scopes: `per_contract`, `per_area_prod`, `per_vm`, `per_vm_area_prod`, plus `computed_at_ms` / `compute_us`.

#### Example

```
snap = client.get_pnl()
total_eur = sum(c.realized_pnl + c.unrealized_pnl for c in snap.per_contract) / 100_000
print(f"PnL: {total_eur:+.2f} EUR across {len(snap.per_contract)} contracts")
```

### `Unary` `client.list_public_trades(limit=…, contract_id=…, area_id=…)`

_Permission: (authenticated)_

Up to `limit` most-recent public trades from the market-wide tape, oldest first. Mirrors REST `GET /api/v1/public_trades`. Optional in-memory filters for `contract_id` and `area_id`.

#### Arguments

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `limit` | `uint32` | No | 0 = default (100); hard-capped at 1000. |
| `contract_id` | `uint64` | No | 0 = all contracts. |
| `area_id` | `string` | No | "" = all areas; matches buy- or sell-side. Max 64 chars (over-length → INVALID_ARGUMENT). |

#### Returns

`ListPublicTradesResponse { repeated PublicTrade trades }`. `buy_dlvry_area` / `sell_dlvry_area` use `""` as the absent sentinel.

#### Example

```
resp = client.list_public_trades(limit=50, contract_id=100001)
for t in resp.trades:
    print(t.exec_time, t.px, t.qty)
```

### `Unary` `client.get_contract_limit()`

_Permission: (authenticated)_

Read the current per-contract net-position cap (sub-MW).

#### Returns

`ContractLimitResponse { sint32 quantity }`.

#### Example

```
resp = client.get_contract_limit()
print("limit:", resp.quantity, "sub-MW")
```

### `Unary` `client.set_contract_limit(quantity=…)`

_Permission: set_position_limit_

Update the per-contract net-position cap. Applies immediately to subsequent `submit_order` validation.

#### Arguments

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `quantity` | `sint32` | Yes | New limit in sub-MW. Negative values are rejected. **`0` is fully supported and blocks all new position-taking** (every order that would move \|net position\| above 0 is rejected), the operator kill-switch. `0` does *not* disable the check. |

#### Returns

`ContractLimitResponse` echoing the new value.

#### Example

```
client.set_contract_limit(quantity=50000)   # 50 MW
```

### `Unary` `client.get_cash_limit()`

_Permission: (authenticated)_

Read the **global** (overarching-member) cash limit for both currency pools. Mirrors REST `GET /api/v1/cash_limit`. Distinct from `get_cash_limits()` (plural), the read-only M7-supplied per-currency feed.

#### Returns

`CashLimitResponse { sint64 cents, sint64 gbp_cents }`: EUR + GBP pools in cents (`0` = not enforced). The two are independent (ECC settles them separately).

#### Example

```
resp = client.get_cash_limit()
print("cash limit:", resp.cents, "EUR cents")
```

### `Unary` `client.set_cash_limit(cents=…)`

_Permission: set_cash_limit_

Update a global cash pool (caps the monetary value of executed trades + open orders). Applies immediately to subsequent `submit_order` / `modify_order` validation. Every per-member cash limit is capped at the global value. `currency` selects the pool (EUR and GBP are independent).

#### Arguments

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `cents` | `sint64` | Yes | New cash limit in cents of the target currency. Negative values are rejected. `0` disables that pool. |
| `currency` | `string` | No | `"eur"` (default) or `"gbp"`. Unknown values return `INVALID_ARGUMENT`. |

#### Returns

`CashLimitResponse` with both pools after the update.

#### Example

```
client.set_cash_limit(cents=10000000)                  # €100,000 (EUR pool)
client.set_cash_limit(cents=5000000, currency="gbp")  # £50,000 (GBP pool)
```

### `Unary` `client.get_cash_fail_closed()`

_Permission: (authenticated)_

Read the cash-limit **fail-closed** switch. Mirrors REST `GET /api/v1/cash_fail_closed`. Enabled by default (ECC parity, §3.11/§3.12): a `0`/unset cash limit means *no trading* in that pool rather than "disabled". Disable it to opt into Voltnir's historical fail-open semantics.

#### Returns

`CashFailClosedResponse { bool enabled }`.

#### Example

```
print("fail-closed:", client.get_cash_fail_closed().enabled)
```

### `Unary` `client.set_cash_fail_closed(enabled=…)`

_Permission: set_cash_limit_

Set the cash-limit fail-closed switch (part of the cash-limit control, so gated by `set_cash_limit`). Applies immediately to subsequent `submit_order` / `modify_order` validation. With `enabled=True`, a `0`/unset limit in a pool rejects all exposure-adding orders in that pool; with `enabled=False` a `0` limit disables the pool's check (unbounded).

#### Arguments

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `enabled` | `bool` | Yes | `true` = ECC fail-closed; `false` = disabled-on-zero. |

#### Returns

`CashFailClosedResponse` with the new state.

#### Example

```
client.set_cash_fail_closed(enabled=True)   # ECC parity: 0 limit = no trading
```

### `Unary` `client.get_holidays()`

_Permission: (authenticated)_

Read both ECC **bank-holiday calendars** (EUR + GBP) for the cash-limit exposure window. Mirrors REST `GET /api/v1/holidays`. The cash limit re-bases exposure at 16:00 (ECC tz) each working day; configured holidays extend the window across public holidays. EUR and GBP keep independent calendars (GB bank holidays close CHAPS); both share the 16:00 reset, only the dates differ. Runtime-managed and persisted to the database.

#### Returns

`HolidaysResponse { repeated Holiday eur; repeated Holiday gbp }`, where `Holiday { string date; string label }` (`label` empty when unset).

#### Example

```
for h in client.get_holidays().gbp:
    print(h.date, h.label)
```

### `Unary` `client.set_holidays(currency=…, holidays=…)`

_Permission: set_cash_limit_

Replace one currency's whole calendar (holidays are part of the cash-limit methodology, so gated by `set_cash_limit`). Applies immediately on the next cash check. Mirrors REST `PUT /api/v1/holidays`.

#### Arguments

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `currency` | `string` | Yes | `"eur"` or `"gbp"`. |
| `holidays` | `repeated Holiday` | No | Full replacement list; empty clears the currency. Duplicate dates are rejected (`INVALID_ARGUMENT`). |

#### Returns

`HolidaysResponse` with both calendars after the change.

#### Example

```
from voltnir_sdk._generated import voltnir_api_v1_pb2 as pb
client.set_holidays(currency="gbp", holidays=[
    pb.Holiday(date="2026-08-31", label="Summer Bank Holiday"),
    pb.Holiday(date="2026-12-25"),
])
```

### `Unary` `client.add_holiday(currency=…, date=…, label=…)`

_Permission: set_cash_limit_

Add a single date to a currency's calendar. Mirrors REST `POST /api/v1/holidays`. A duplicate date or malformed `YYYY-MM-DD` is `INVALID_ARGUMENT`.

#### Arguments

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `currency` | `string` | Yes | `"eur"` or `"gbp"`. |
| `date` | `string` | Yes | `YYYY-MM-DD`. |
| `label` | `string` | No | Optional display label. |

#### Returns

`HolidaysResponse` with both calendars after the change.

#### Example

```
client.add_holiday(currency="eur", date="2026-01-01", label="New Year's Day")
```

### `Unary` `client.remove_holiday(currency=…, date=…)`

_Permission: set_cash_limit_

Remove a single date from a currency's calendar. Mirrors REST `DELETE /api/v1/holidays`. A date that is not configured is `NOT_FOUND`.

#### Arguments

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `currency` | `string` | Yes | `"eur"` or `"gbp"`. |
| `date` | `string` | Yes | `YYYY-MM-DD`. |

#### Returns

`HolidaysResponse` with both calendars after the change.

#### Example

```
client.remove_holiday(currency="eur", date="2026-01-01")
```

### `Unary` `client.get_trading_allowed()`

_Permission: (authenticated)_

Read the operator kill-switch.

#### Returns

`TradingAllowedResponse { bool allowed }`.

#### Example

```
print("trading allowed:", client.get_trading_allowed().allowed)
```

### `Unary` `client.set_trading_allowed(allowed=…)`

_Permission: toggle_trading_

Operator kill-switch. Setting `allowed=False` rejects exposure-adding traffic (`submit_order` and `modify_order` fail with `FAILED_PRECONDITION`) **and** immediately dispatches a cancel-all to the exchange. Cancels (`cancel_order` / `cancel_all_orders`) stay available, since pulling an order only reduces exposure.

> [!WARNING]
> `set_trading_allowed(allowed=False)` cancels every resting order. There is no undo.

> [!CAUTION]
> When the `system.disable_trading` debug flag is set in `config.yml`, this RPC is rejected with `ABORTED`: the config flag is the absolute authority and the runtime toggle cannot override it.

#### Arguments

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `allowed` | `bool` | Yes | `True` = trading on; `False` = kill-switch. |

#### Returns

`TradingAllowedResponse` echoing the new state.

#### Example

```
client.set_trading_allowed(allowed=False)   # kill-switch on
```

### `Unary` `client.get_self_trade_policy()`

_Permission: (authenticated)_

Returns the active self-trade (cross-trade) prevention policy. EPEX M7 does not prevent self-trades server-side; this is a Voltnir-side pre-trade check.

#### Returns

`SelfTradePolicyResponse { SelfTradePolicy policy }`: `SELF_TRADE_POLICY_OBSERVE` or `SELF_TRADE_POLICY_REJECT`.

#### Example

```
print(client.get_self_trade_policy().policy)
```

### `Unary` `client.set_self_trade_policy(policy=…)`

_Permission: set_self_trade_policy_

Set the self-trade prevention policy. Takes effect immediately and is persisted. With `reject`, an order that would cross one of your own resting orders fails `submit_order` with `FAILED_PRECONDITION` and a `SELF_CROSS_BLOCKED` message. The `config.yml` `self_trade.policy` only seeds the default on a fresh database.

#### Arguments

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `policy` | `str` | Yes | `"observe"` or `"reject"`. |

#### Returns

`SelfTradePolicyResponse` echoing the new policy. An unspecified/unknown value returns `INVALID_ARGUMENT`.

#### Example

```
client.set_self_trade_policy(policy="reject")
```

### `Unary` `client.restart()`

_Permission: restart_system_

Trigger a graceful shutdown. The process exits and relies on the host supervisor (systemd, Docker, …) to bring it back.

> [!WARNING]
> Real shutdown, not a soft reset. Active streams, in-flight orders, and websocket subscribers are torn down.

#### Arguments

None.

#### Returns

`RestartResponse`: sent before the process exits.

#### Example

```
client.restart()
```

## SDK reference: Users & Members

User accounts, API keys, permissions, and virtual member assignments.

**Desk-tier gate.** Every management RPC below *except* `get_me`, `get_my_members`, and `rotate_api_key` requires the desk-tier license capability in addition to the per-call permission. This is the same gate REST applies via `require_desk` and WS via its `require_desk` helper. On a `trader` license these RPCs return `PermissionDenied` with message `LICENSE_DESK_REQUIRED`. (gRPC is served on all license tiers, so a `trader` license does reach these RPCs and is blocked here by the desk gate; this is the active protection, not a redundant one.)

### `Unary` `client.get_me()`

_Permission: (authenticated)_

Return the caller's own profile, derived from the bearer token.

#### Returns

`UserProfile { string id, string username, repeated string permissions, string short_id }`: `short_id` (e.g. `"U001"`) is the compact handle used to attribute the user on the audit trail.

#### Example

```
me = client.get_me()
print(me.username, list(me.permissions))
```

### `Unary` `client.get_my_members()`

_Permission: (authenticated)_

List the virtual members assigned to the caller.

#### Returns

`MemberListResponse { repeated Member members }`. Each `Member` carries `id` / `short_id` / `name` / `max_position` (`sint64`, sub-MW) / `active` (`bool`), the configured overrides `cash_limit` / `cash_limit_gbp` (`sint64` cents; `0` = none), and the live cash-usage trio per pool: `eur_consumed_cents` / `eur_limit_cents` / `eur_remaining_cents` and the `gbp_*` equivalents (all `sint64` cents). `consumed` is the member's open-order + executed-trade exposure; `*_limit_cents` is the **effective** cap (the override capped at the global limit, or the inherited global when there is no override, so it need not equal `cash_limit`); `remaining = limit − consumed` (negative when over, a `*_limit_cents` of `0` means that pool is not enforced). Same shape and semantics as REST `GET /api/v1/members` and the WS `get_members` response.

#### Example

```
for m in client.get_my_members().members:
    print(m.short_id, m.name, m.eur_consumed_cents, m.eur_remaining_cents)
```

### `Unary` `client.list_users()`

_Permission: manage_users_

List every user in the system.

#### Returns

`ListUsersResponse { repeated UserProfile users }`.

#### Example

```
for u in client.list_users().users:
    print(u.id, u.username, list(u.permissions))
```

### `Unary` `client.create_user(username="…", permissions=[…])`

_Permission: manage_users_

Create a new user with a fresh API key. Permissions are applied in the same call; no separate `SetPermissions` follow-up needed (REST `POST /users` accepts the same optional `permissions` array). Permission strings are validated *before* any database write: an unknown permission returns `INVALID_ARGUMENT` and leaves no user behind.

> [!WARNING]
> The plaintext API key is returned **once** and stored only as a SHA-256 hash thereafter. If the caller loses it, rotate via `rotate_api_key`.

#### Arguments

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `username` | `string` | Yes | Unique username. |
| `permissions` | `repeated string` | No | Permission names from the table in [Authentication](#authentication). Empty = no permissions. |

#### Returns

`CreateUserResponse { UserProfile user, string api_key }`: the profile (`resp.user.id`, `resp.user.username`, `resp.user.permissions`) is nested; `api_key` is the one-time plaintext value.

#### Example

```
resp = client.create_user(
    username="ops_oncall",
    permissions=["create_order", "modify_order", "delete_order", "toggle_trading"],
)
print("save this key now:", resp.api_key)
```

### `Unary` `client.delete_user(user_id="…")`

_Permission: manage_users_

Delete a user. Their API key is invalidated and any active sessions are dropped.

#### Arguments

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `user_id` | `string` | Yes | User id to delete. |

#### Returns

`google.protobuf.Empty`.

#### Example

```
client.delete_user(user_id="42")
```

### `Unary` `client.set_permissions(user_id="…", permissions=[…])`

_Permission: manage_users_

Replace the user's permission set with the given list. Replace-all semantics: pass an empty list to revoke everything. The built-in `admin` account's permissions are **immutable** (it always holds every permission); targeting it returns `PERMISSION_DENIED`.

#### Arguments

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `user_id` | `string` | Yes | Target user. |
| `permissions` | `repeated string` | Yes | New permission set; empty = revoke all. |

#### Returns

`google.protobuf.Empty`.

#### Example

```
client.set_permissions(user_id="42", permissions=["read_audit"])
```

### `Unary` `client.rotate_api_key(user_id="…")`

_Permission: manage_users_

Issue a fresh API key for the user; the previous key is invalidated immediately. Not desk-gated, so a `trader`-tier license can rotate its own key. On the trader tier it is **self-only**: `user_id` must be the caller's own id; any other target (including a non-existent one) returns `NOT_FOUND` so it cannot probe for other accounts. A desk-tier `manage_users` holder may rotate any user.

#### Arguments

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `user_id` | `string` | Yes | Target user. On the trader tier this must be the caller's own id. |

#### Returns

`RotateApiKeyResponse { string api_key }`: shown once, then hashed.

`NOT_FOUND`: user id not found, *or* (trader tier) a target that is not the caller.

#### Example

```
resp = client.rotate_api_key(user_id="42")
print("new key:", resp.api_key)
```

### `Unary` `client.get_user_members(user_id="…")`

_Permission: manage_users_

List the virtual members assigned to a specific user. The returned values are member **UUIDs** (the `Member.id` field), not `VM…`-style short ids; resolve display names via `list_members`.

#### Arguments

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `user_id` | `string` | Yes | Target user. |

#### Returns

`UserMembersResponse { repeated string member_ids }`: member UUIDs.

#### Example

```
print(client.get_user_members(user_id="42").member_ids)
```

### `Unary` `client.set_user_members(user_id="…", member_ids=[…])`

_Permission: manage_users_

Replace the user's set of virtual-member assignments. Replace-all semantics. The list values are member **UUIDs** (`Member.id`), not `VM…`-style short ids; passing short ids silently assigns nothing.

#### Arguments

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `user_id` | `string` | Yes | Target user. |
| `member_ids` | `repeated string` | Yes | Replacement list of member UUIDs. |

#### Returns

`google.protobuf.Empty`.

#### Example

```
desk_a = next(m for m in client.list_members().members if m.short_id == "VM001")
client.set_user_members(user_id="42", member_ids=[desk_a.id])
```

### `Unary` `client.list_members()`

_Permission: manage_members_

List every virtual member in the system.

#### Returns

`MemberListResponse { repeated Member members }`: see [`get_my_members`](#sdk-get_my_members) for the full `Member` field set (configured limits + live cash usage per pool).

#### Example

```
for m in client.list_members().members:
    print(m.short_id, m.name, m.eur_consumed_cents, m.eur_limit_cents, m.eur_remaining_cents)
```

### `Unary` `client.create_member(name="…", max_position=…)`

_Permission: manage_members_

Create a new virtual member. The `short_id` is generated server-side (`VM001`, `VM002`, …) and returned in the `Member` response; it cannot be chosen by the caller.

#### Arguments

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `name` | `string` | Yes | Display name. |
| `max_position` | `sint64` | Yes | Position cap in sub-MW. |
| `cash_limit` | `sint64` | No | Per-member cash limit in EUR cents. Default `0` (no override → global applies); always capped at the global limit. |
| `cash_limit_gbp` | `sint64` | No | Per-member GBP cash limit in GBP cents. Default `0` (no override → global GBP limit applies). |

#### Returns

`Member`: the newly-created record (full field set per [`get_my_members`](#sdk-get_my_members)). A fresh member has no orders/trades yet, so its `*_consumed_cents` are `0` and `*_remaining_cents` equal the effective `*_limit_cents`.

#### Example

```
m = client.create_member(name="Trading Desk Alpha", max_position=10000)
print(m.id)
```

### `Unary` `client.patch_member(**kwargs)`

_Permission: manage_members_

Partial update: only fields that are explicitly set on the wire are applied. Uses `google.protobuf` wrapper types so unset fields skip cleanly.

#### Arguments

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Target member **UUID** (`Member.id`), not the `VM…` short_id. |
| `name` | `StringValue` | No | New display name. |
| `max_position` | `Int64Value` | No | New position cap (sub-MW). |
| `cash_limit` | `Int64Value` | No | New per-member cash limit in EUR cents (`0` clears the override). The field the overarching member lowers when next-window collateral is insufficient. |
| `cash_limit_gbp` | `Int64Value` | No | New per-member GBP cash limit in GBP cents (`0` clears the override). |
| `active` | `BoolValue` | No | Activate / deactivate the member. |

#### Returns

`google.protobuf.Empty`.

#### Example

```
from google.protobuf.wrappers_pb2 import BoolValue, Int64Value

desk = next(m for m in client.list_members().members if m.short_id == "VM042")
client.patch_member(id=desk.id, active=BoolValue(value=False))
client.patch_member(id=desk.id, max_position=Int64Value(value=20000))
```

## SDK reference: Audit

Cursor-paginated read access to the audit log of orders and trades. Items are returned as opaque JSON strings; the schema matches the REST audit response 1:1.

### `Unary` `client.query_audit_orders(**kwargs)`

_Permission: read_audit_

Page through the audit log of order events. Optional filters narrow the result; the returned `next_cursor` drives pagination.

#### Arguments

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `cursor` | `string` | No | `""` on the first page; pass back the previous response's `next_cursor` for subsequent pages. |
| `limit` | `uint32` | No | Page size. `0` (or unset) == default `50`; capped at `200`. (REST rejects an explicit `limit=0` with 400 instead, since proto3 cannot distinguish unset from 0.) |
| `date_from` / `date_to` | `string` | No | RFC 3339: inclusive window. `""` = unbounded. |
| `area` | `string` | No | EIC area filter. |
| `product` | `string` | No | Product filter. |
| `status` | `string` | No | Order state filter. |
| `user_code` | `string` | No | EPEX trader/user code filter (e.g. `"TRADER1"`). Renamed from the former, mislabelled `user_id` field. |
| `v_member_short_id` | `string` | No | Virtual-member filter. |
| `voltnir_user_short_id` | `string` | No | Submitting Voltnir user short-id filter (e.g. `"U001"`). |
| `voltnir_username` | `string` | No | Submitting Voltnir username-snapshot filter (e.g. `"j.doe"`). |

#### Returns

`AuditOrdersResponse { repeated AuditOrderItem items, string next_cursor, uint64 total_hint }`; each `item.json` is the audit row serialised as JSON. `total_hint` of `0` means not available on this page.

#### Example

```
cursor = ""
while True:
    page = client.query_audit_orders(limit=100, cursor=cursor, area="10YBE----------2")
    for item in page.items:
        print(item.json)
    if not page.next_cursor:
        break
    cursor = page.next_cursor
```

### `Unary` `client.query_audit_trades(**kwargs)`

_Permission: read_audit_

Page through the audit log of trade events. Same shape and semantics as `query_audit_orders` minus the `status` filter. Each item's JSON carries both the execution time (`exec_time` / `executed_at`) and the contract delivery window (`delivery_start` / `delivery_end`); `time_basis` selects which axis `date_from`/`date_to` filter on. Mirrors REST `GET /api/v1/audit/trades`.

#### Arguments

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `cursor` | `string` | No | `""` for the first page. |
| `limit` | `uint32` | No | Page size. `0` (or unset) == default `50`; capped at `200`. (REST rejects an explicit `limit=0` with 400 instead, since proto3 cannot distinguish unset from 0.) |
| `date_from` / `date_to` | `string` | No | RFC 3339 window, applied to the axis chosen by `time_basis`. |
| `time_basis` | `string` | No | Which timestamp the window filters on: `""`/`delivery` (**default**, contract delivery window, **overlap** semantics: `delivery_end ≥ date_from` and `delivery_start ≤ date_to`) or `execution` (execution time). Any other value → `INVALID_ARGUMENT`. |
| `area` | `string` | No | EIC area filter. |
| `product` | `string` | No | Product filter. |
| `user_code` | `string` | No | EPEX trader/user code filter (e.g. `"TRADER1"`). Renamed from the former, mislabelled `user_id` field. |
| `v_member_short_id` | `string` | No | Virtual-member filter. |
| `voltnir_user_short_id` | `string` | No | Submitting Voltnir user short-id filter (e.g. `"U001"`). |
| `voltnir_username` | `string` | No | Submitting Voltnir username-snapshot filter (e.g. `"j.doe"`). |

> [!NOTE]
> **Delivery (default) vs. execution.** `delivery` (the default) filters on the contract delivery period using overlap, so block / multi-period products spanning the window are still returned (settlement / exposure / REMIT view); `execution` filters on when the trade matched (transaction view). Trades recorded before delivery capture was added have `null` `delivery_start`/`delivery_end` and never match the default delivery filter; use `time_basis=execution` for those.

#### Returns

`AuditTradesResponse { repeated AuditTradeItem items, string next_cursor, uint64 total_hint }`. Each `AuditTradeItem.json` is the same row shape as REST (now including `delivery_start` / `delivery_end`). `total_hint` of `0` means not available on this page.

#### Example

```
import json
# All trades delivering on 2026-04-20 (delivery-window overlap), not by trade time:
page = client.query_audit_trades(
    date_from="2026-04-20T00:00:00Z",
    date_to="2026-04-21T00:00:00Z",
    time_basis="delivery",
)
for item in page.items:
    t = json.loads(item.json)
    print(t["trade_id"], t["delivery_start"], "->", t["delivery_end"])
```

### `Unary` `client.query_audit_public_trades(**kwargs)`

_Permission: read_audit_

Page through the persisted market-wide public trade tape (M7 `PblcTradeConfRprt`). Populated only when the gateway runs with `market_data.public_trades.persist: postgresql` (`false` or the export-only `parquet` backend leave the table empty). Data is scoped to assigned products; pre-arranged trades are excluded; prices (`px`) are Eurocents. Mirrors the REST `GET /audit/public_trades` endpoint 1:1.

#### Arguments

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `cursor` | `string` | No | `""` for the first page. |
| `limit` | `uint32` | No | Page size. `0` (or unset) == default `50`; capped at `200`. (REST rejects an explicit `limit=0` with 400 instead, since proto3 cannot distinguish unset from 0.) |
| `date_from` / `date_to` | `string` | No | RFC 3339 window on execution time. |
| `area` | `string` | No | EIC area; matches buy **or** sell delivery area. |
| `product` | `string` | No | Product filter. |
| `state` | `string` | No | Trade state (`ACTI`, `CNCL`, …). |

#### Returns

`AuditPublicTradesResponse { repeated AuditPublicTradeItem items, string next_cursor, uint64 total_hint }`; each `item.json` is one public trade serialised as JSON.

#### Example

```
page = client.query_audit_public_trades(limit=100, area="10YDE-EON------1", state="ACTI")
print(len(page.items), "public trades; next_cursor:", page.next_cursor)
```

### `Unary` `client.query_audit_events(**kwargs)`

_Permission: read_audit_

Page through the **compliance audit-event log**: the append-only who-did-what record of actor-driven mutations (user/permission/member/limit changes, kill-switch and self-trade toggles, order rejections, report exports, system/license lifecycle). Each `item.json` carries the actor, transport, source IP, `before`/`after` snapshots, outcome, and reason. Mirrors REST `GET /api/v1/audit/events`.

#### Arguments

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `cursor` | `string` | No | `""` on the first page; pass back the previous response's `next_cursor`. |
| `limit` | `uint32` | No | Page size. `0` (or unset) == default `50`; capped at `200`. |
| `date_from` / `date_to` | `string` | No | RFC 3339: inclusive window. `""` = unbounded. |
| `action` | `string` | No | Action token filter, e.g. `permissions_set`, `order_rejected`, `trading_toggled`. |
| `target_type` | `string` | No | Target-kind filter: `user`, `member`, `profile`, `order`, `trading`, `report`, `license`, `system`. |
| `actor_short_id` | `string` | No | Acting user's short-id filter (e.g. `"U001"`). |
| `outcome` | `string` | No | Outcome filter: `ok` or `error`. |

#### Returns

`AuditEventsResponse { repeated AuditEventItem items, string next_cursor, uint64 total_hint }`; each `item.json` is the audit event serialised as JSON. `total_hint` of `0` means not available on this page.

#### Example

```
page = client.query_audit_events(limit=100, action="permissions_set", outcome="ok")
for item in page.items:
    print(item.json)
```

### `Unary` `client.query_m7_errors(**kwargs)`

_Permission: read_m7_errors_

Page through the **M7 exchange-error log**: the append-only record of M7-side faults off the AMQP line. Gated by the **dedicated `read_m7_errors`** permission (not `read_audit`). `err_resp` rows are enriched from the vendor DFS200 §4 catalog with a human `err_identifier` + `category`; other kinds (`unknown_type`, `ack_uncorrelated`, `seq_gap`) carry no code/category. Mirrors REST `GET /api/v1/audit/m7_errors`.

#### Arguments

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `cursor` | `string` | No | `""` on the first page; pass back the previous response's `next_cursor`. |
| `limit` | `uint32` | No | Page size. `0` (or unset) == default `50`; capped at `200`. |
| `date_from` / `date_to` | `string` | No | RFC 3339: inclusive window on receive time. `""` = unbounded. |
| `kind` | `string` | No | Fault-class filter: `err_resp`, `unknown_type`, `ack_uncorrelated`, `seq_gap`. |
| `category` | `string` | No | DFS200 §4 section filter: `order_entry`, `general`, `trade`, `user_right`, `limits`, `wrong_reference`, `unknown`. |
| `err_code` | `int64` | No | Raw numeric M7 code filter, e.g. `1149`. `0` (or unset) == no filter. |

#### Returns

`M7ErrorsResponse { repeated M7ErrorItem items, string next_cursor, uint64 total_hint }`; each `item.json` is the m7_errors row serialised as JSON. `total_hint` of `0` means not available on this page.

#### Example

```
page = client.query_m7_errors(limit=100, kind="err_resp", category="limits")
for item in page.items:
    print(item.json)
```

## SDK reference: Streaming

13 server-streaming RPCs. Sync versions return a regular iterator; async versions return an `AsyncIterator`. Cancel by exiting the loop or calling `stream.cancel()`. See [Streaming semantics](#streaming) for the protocol-level rules (snapshot-first, lag recovery, terminal closure).

### `Server Stream` `client.export_orders(**kwargs)`

_Permission: export_reports_

Stream an export of audit-log orders in JSON / CSV. Concatenate the chunk `data` bytes in order to reconstruct the file.

> [!NOTE]
> **Reserved-word note:** the proto field `from` conflicts with Python's keyword. Pass `from_` instead; the SDK rewrites it on the wire.

#### Arguments

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `format` | `ExportFormat` | Yes | `JSON` or `CSV`. `FORMAT_UNSPECIFIED` is rejected. |
| `from_` | `string` | Yes | RFC 3339: window start. Maps to proto `from`. |
| `to` | `string` | Yes | RFC 3339: window end. `from >= to` rejected before any DB work. |
| `area` | `string` | No | EIC area filter. |
| `product` | `string` | No | Product filter. |

#### Returns

`Iterator[ExportChunk]`: each chunk carries a `bytes data` field; chunk size is currently 64 KiB.

#### Example

```
from voltnir_sdk import ExportFormat

with open("orders_april.json", "wb") as fh:
    for chunk in client.export_orders(
        format=ExportFormat.JSON,
        from_="2026-04-01T00:00:00Z",
        to="2026-05-01T00:00:00Z",
        area="10YBE----------2",
    ):
        fh.write(chunk.data)
```

### `Server Stream` `client.export_trades(**kwargs)`

_Permission: export_reports_

Stream an export of audit-log trades. Same shape, args, and semantics as `export_orders`.

#### Arguments

See [export_orders](#sdk-export_orders), which is identical (`format`, `from_`, `to`, `area`, `product`).

#### Returns

`Iterator[ExportChunk]`.

#### Example

```
from voltnir_sdk import ExportFormat

buf = bytearray()
for chunk in client.export_trades(format=ExportFormat.CSV):
    buf.extend(chunk.data)
print(len(buf), "bytes received")
```

### `Server Stream` `client.watch_contract(area_id="…", contract_id="…", timeout=None)`

_Permission: (authenticated)_

Live push stream for one specific contract. First event after subscribe is always `SNAPSHOT`; subsequent events carry the full post-mutation `Contract` on every tick.

Treat any `SNAPSHOT` after the initial one as a **start-over** signal: the server has fallen behind and is re-syncing you.

#### Arguments

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `area_id` | `string` | Yes | EIC code of the delivery area. |
| `contract_id` | `string` | Yes | M7 contract id (string form). |

#### Returns

`Iterator[ContractEvent]`: each event has `type` ∈ {`SNAPSHOT`, `ORDER_BOOK_UPDATE`, `STATE_CHANGE`, `TRADE`} and a full `Contract` body. `ORDER_BOOK_UPDATE` fires on order-book mutations, `STATE_CHANGE` on contract metadata / lifecycle mutations (`ContractInfoRprt` path), and `TRADE` whenever a trade touches the contract; own executions and public-tape trades both fire, deduplicated on `(trade_id, revision_no)` since an own execution is usually mirrored on the public tape. When the contract is deleted, tombstoned, or deactivated the stream emits a final `STATE_CHANGE` and closes.

#### Example

```
for event in client.watch_contract(area_id="10YBE----------2", contract_id="2958876"):
    print(event.type, event.contract.last_price, event.contract.best_bid, event.contract.best_ask)
```

### `Server Stream` `client.watch_order(client_order_id="…", timeout=None)`

_Permission: (authenticated, member-scoped)_

Live push stream for one specific order. Closes automatically on terminal events (`FILLED` / `CANCELLED` / `REJECTED`).

**Scoping.** Member-isolated like `get_order`: an order the caller may not see returns `NotFound` at the snapshot (identical to an unknown `client_order_id`), never the body or a stream. A caller holding `read_orders`/`bypass_member_check` can watch any order.

Pending orders (locally submitted, not yet acked by M7) are watchable: the stream opens with a `SNAPSHOT` whose body has `state == PENDING` and `order_id == 0` (side/price/quantity/contract are the real submitted values). The M7 ack arrives as the next event with the real `order_id`, so `submit_order → watch_order` is race-free.

#### Arguments

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `client_order_id` | `string` | Yes | UUID of the order to watch. |

#### Returns

`Iterator[OrderEvent]`: `type` ∈ {`SNAPSHOT`, `UPDATE`, `FILLED`, `CANCELLED`, `REJECTED`}. `FILLED` carries the final order body (`quantity == 0`, state `INACTIVE`, real price/side/ids). `CANCELLED` covers every non-trade-path exit from the book; M7's `INACTIVE` does not distinguish cancellation from expiry or an OER-reported fill.

#### Example

```
for event in client.watch_order(client_order_id="550e8400-e29b-41d4-a716-446655440000"):
    print(event.type, event.order.state, event.order.quantity)
```

### `Server Stream` `client.watch_orders(delivery_area="", contract_id="", v_member_short_id="", timeout=None)`

_Permission: (authenticated, member-scoped)_

Live push stream over the caller's order list, optionally scoped. First event is `SNAPSHOT` with the full filtered list; subsequent events carry one order at a time.

> [!NOTE]
> **Filter semantics:** `delivery_area` alone is a valid filter; `contract_id` requires `delivery_area`, and `contract_id` alone returns `INVALID_ARGUMENT`. Same rule as `list_orders` and REST `GET /orders`.

**Scoping.** The snapshot and every event are narrowed to what the caller may see, exactly like `list_orders`: a caller holding `read_orders` (or `bypass_member_check`) sees the firm-wide order book; everyone else sees only their assigned members' orders, with untagged house orders withheld.

#### Arguments

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `delivery_area` | `string` | Cond | `""` = no filter. Required if `contract_id` is set. |
| `contract_id` | `string` | Cond | `""` = no filter. Requires `delivery_area`. |
| `v_member_short_id` | `string` | No | Empty = caller's default scope. Non-empty narrows the stream to one member; `PermissionDenied` unless the caller is assigned to it or holds `read_orders`/`bypass_member_check`. |

#### Returns

`Iterator[OrdersEvent]`: `type` ∈ {`SNAPSHOT`, `ADDED`, `MODIFIED`, `CANCELLED`, `FILLED`}. `ADDED` fires on an order's first confirmed appearance (a modify-as-delete+re-create successor stays `MODIFIED`); `orders` carries exactly one order on every non-SNAPSHOT event. `FILLED` carries the final order body (`quantity == 0`, state `INACTIVE`, real price/side/ids). `CANCELLED` covers every non-trade-path exit from the book (cancel, expiry, OER-reported fill; M7 does not distinguish them).

#### Example

```
for event in client.watch_orders(delivery_area="10YBE----------2", contract_id="2958876"):
    if event.type == 0:   # SNAPSHOT
        print("snapshot:", len(event.orders), "orders")
    else:
        print(event.type, event.orders[0].client_order_id)
```

### `Server Stream` `client.watch_trades()`

_Permission: (authenticated)_

Live push stream of the caller's filled trades, the gRPC mirror of the WS `trades` subscription. First event is `SNAPSHOT` (full current list); each execution arrives as `UPSERTED` carrying one trade. A lagged broadcast re-emits a fresh `SNAPSHOT`.

#### Returns

`Iterator[TradeEvent]`: `type` ∈ {`SNAPSHOT`, `UPSERTED`}; `trades` carries the full list on `SNAPSHOT`, exactly one on `UPSERTED`.

### `Server Stream` `client.watch_public_trades()`

_Permission: (authenticated)_

Live market-wide public trade tape, mirror of the WS `public_trades` stream. No snapshot (seed history via `list_public_trades`); each message is one live `PublicTrade`. Filter by `contract_id`/`area_id` client-side. A lagged broadcast skips missed prints (re-request per-contract history to recover).

#### Returns

`Iterator[PublicTrade]`

### `Server Stream` `client.watch_pnl(v_member_short_id="")`

_Permission: (authenticated, member-scoped)_

Live P&L, mirror of the WS `pnl` stream. P&L is a computed view, not an event, so this polls: an immediate `PnlSnapshot` on subscribe then a fresh one each second, scoped exactly like `get_pnl`.

#### Arguments

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `v_member_short_id` | `string` | No | Empty = caller's default scope. Non-empty narrows to one member; `PermissionDenied` unless the caller may see it (same as `get_pnl`). |

#### Returns

`Iterator[PnlSnapshot]`: one per second.

### `Server Stream` `client.watch_state()`

_Permission: read_state_

Live runtime-health snapshot, mirror of the WS `state` stream and the streaming form of `get_state`. Emits an immediate `SystemState` then a fresh one each second. Gated by `read_state` (`PERMISSION_DENIED` at open without it). The trading-posture aggregate is its own stream now; see [`WatchStatus`](#sdk-watch_status).

#### Returns

`Iterator[SystemState]`: one per second.

### `Server Stream` `client.watch_status()`

_Permission: read_status_

Live trading-posture aggregate, mirror of the WS `status` stream and the streaming form of `get_status`. Emits an immediate `SystemStatus` then a fresh one each second (1 Hz poll). Gated by `read_status` (`PERMISSION_DENIED` at open without it). Carries throttling, the trading/operational flags, M7 cash limits, position limit, the Voltnir order cash limit (cents), and the license.

#### Returns

`Iterator[SystemStatus]`: one per second.

### `Server Stream` `client.watch_messages()`

_Permission: (authenticated)_

Live system / order-rejection log, mirror of the WS `messages` stream. Polls at 1 Hz: the current log on subscribe, then rows appended since (deduped on `ts_ms`). Each row is JSON (`MessageItem.json`) with the same shape as the REST `/state` `messages` array.

#### Returns

`Iterator[MessageItem]`: each `.json` is one message row.

### `Server Stream` `client.watch_audit_events()`

_Permission: read_audit_

Live tail of the compliance audit log, the streaming companion to `query_audit_events`. Gated by `read_audit` (denied at open, server-side). Event-driven: each row is pushed the moment it commits (no per-stream polling). No snapshot: seed history via `query_audit_events`, then this tails rows appended after subscribe. Each `AuditEventItem.json` carries a stable per-row `id`; dedup on it against the seeded page. Filter client-side.

#### Returns

`Iterator[AuditEventItem]`

### `Server Stream` `client.watch_m7_errors()`

_Permission: read_m7_errors_

Live tail of the M7 exchange-error log, the streaming companion to `query_m7_errors`. Same event-driven semantics as `watch_audit_events` (pushed on commit, no polling) but gated by `read_m7_errors`; seed via `query_m7_errors`. Each `M7ErrorItem.json` carries the stable `id` key.

#### Returns

`Iterator[M7ErrorItem]`

## verify.py runner

A linear smoke runner ships with the SDK at `clients/python/verify.py`. It walks every read-only RPC and (optionally) a hibernated-order lifecycle, printing `[PASS]` / `[FAIL]` / `[SKIP]` per step. Use it after starting or upgrading Voltnir to confirm the gRPC surface is healthy.

```
cd clients/python
.venv/bin/python verify.py \
    --host localhost --port 3443 \
    --api-key "$VOLTNIR_KEY" \
    --area 10YBE----------2 \
    [--mutate] [--tls --ca cert.pem]
```

Read-only by default. `--area` is required and deployment-specific; `--mutate` opts into placing + cancelling a hibernated test order on a freshly-found `ACTI` contract.

## JavaScript SDK (coming soon)

A TypeScript / Node SDK is planned. It will sit alongside the Python one under `clients/javascript/` and wrap the same generated stubs (via `@grpc/grpc-js` + `ts-proto`). Until then, generate stubs directly from `proto_volt/voltnir_api_v1.proto` with `protoc-gen-ts_proto`.

> [!NOTE]
> Want it sooner? Contact us at [contact@voltnir.io](mailto:contact@voltnir.io).

## Go SDK (coming soon)

Same plan: a Go SDK using `google.golang.org/grpc` will land under `clients/go/` in a future release. For now generate stubs from `proto_volt/voltnir_api_v1.proto` with `protoc-gen-go` + `protoc-gen-go-grpc`.
