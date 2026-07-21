# Voltnir WebSocket API v1: Reference

> Auto-generated from the Voltnir API reference.

Voltnir WebSocket API v1

The WebSocket API is a public, first-class transport for building your own trading desk on a single connection. It is the same transport the Voltnir trading terminal itself uses, so anything the terminal does, your client can do too.

## How it works & why

Voltnir exposes the same capabilities over three transports, each suited to a different kind of client:

| Transport | Best for | Why |
| --- | --- | --- |
| **REST** | simple desks, signal bots, ops scripts | stateless, one request per call, trivial to script with curl |
| **gRPC** | latency-sensitive automated trading | binary Protocol Buffers over HTTP/2, generated typed clients, streaming watches |
| **WebSocket** | building a trading terminal / desk | one long-lived session carrying both live push data and your commands, with execution acks correlated to the same ordered stream |

A WebSocket connection does **two** things at once, and that duality is the whole point:

- **Streaming subscriptions**: the server *pushes* live data to you: the order book, your orders and trades, P&L, system status, the public trade tape. This is WebSocket's native strength and why a desk uses it: you don't poll, you subscribe once and receive deltas.
- **Request/response commands**: you *send* an action (place an order, query a contract, manage users) and get one correlated reply. These mirror the entire REST/gRPC unary surface, so a desk never needs a second transport to act on what it sees streaming in.

Because a single socket multiplexes many frames (stream deltas arriving continuously, several commands in flight), each command carries a client-generated `req_id` and the server echoes it on the reply. That correlation id is what lets you match a response to the request that produced it without serialising your calls. It is the WebSocket analogue of an HTTP request/response pair or a gRPC unary call.

Order submission is the case where the single session pays off most: you send `new_order`, the server validates and acknowledges it, and the fill (when it happens) arrives on the same `orders`/`trades` stream in the same order as the book update that caused it, with no racing two transports to reconstruct what happened.

## Parity with REST & gRPC

Voltnir treats the three transports as one surface exposed three ways. The rule the gateway enforces:

- **Every unary operation is at strict parity.** A WebSocket command, its REST endpoint, and its gRPC RPC take the same fields in the same units, enforce the same permissions, and return the same body and the same error semantics, so they cannot drift. That's why this reference can point you at the REST reference for full field-level detail: the data is identical.
- **Streaming is the per-transport-native exception.** Live push is expressed in each transport's idiom and is *not* required to be shape-identical, only semantically equivalent. WebSocket streams broadcast whole working sets (e.g. all your orders); gRPC offers `Watch*` RPCs over single entities or filtered sets; REST has no streaming at all. They carry the same underlying data with the same units and permissions.

What this means for you: pick the transport that fits your client, and you lose no capability. A unary call behaves identically whichever you choose; for live data, WebSocket and gRPC each have a streaming model and REST does not. The [transport mapping table](#parity-table) lists the correspondence command by command.

## Connection & versioning

Connect to the path-versioned endpoint:

```
ws://<host>:9001/ws/v1        (wss:// behind a TLS reverse proxy)
```

The version lives in the path, mirroring REST's `/api/v1` and gRPC's `voltnir.api.v1`. The bare root (`/`) and `/v1` are accepted as transition aliases; an unknown version such as `/ws/v2` is rejected at the upgrade handshake. **Why path versioning:** a future breaking change ships as a new `/ws/v2` endpoint while `/ws/v1` keeps running unchanged, so an existing client is never silently broken; it keeps speaking the version it connected to until you choose to migrate.

## Authentication

The first message on a new connection **must** be an auth frame carrying your API key. Any other first message closes the connection (10 s window).

```
// client → server (text)
{"action": "auth", "token": "<your-api-key>"}
```

On success the server replies with a `ConfigPayload` text frame carrying the delivery areas and products this instance trades, operational/trading flags, the current M7 throttling counters, current limits, the installed license, the negotiated `protocol_version` (assert it equals `"v1"`), and a `public_trades` hint describing the saved-tape backend:

```
// server → client (text)
{"protocol_version": "v1", "areas": ["DE","FR"], "products": ["H","Q"],
 "operational": true, "throttling": {…}, "trading_enabled": true,
 "cash_limits": {…}, "order_pos_limit": 50000, "cash_limit": {…},
 "license": {…}, "public_trades": {"persist": "postgresql", "queryable": true}}
```

`public_trades.persist` is `"off"`, `"postgresql"`, or `"parquet"`, and `public_trades.queryable` is `true` only for `"postgresql"`, the one backend whose saved tape is returned by the [`audit/public_trades`](rest_api_v1.md) endpoints. A `"parquet"` tape is written to rotating files for offline tools (export-only; the audit query returns an empty page), and `"off"` persists nothing. The live `public_trades` subscription stream is unaffected by this setting.

Any handshake failure (a bad token, the 10 s timeout, or a first message that is not an auth frame) yields `{"msg_type": "auth_error", "error": "<reason>"}` followed by a close. The same API key, permissions, and license tier apply on every transport: WebSocket grants no more and no less than REST or gRPC.

Credentials stay **live** for the whole connection: permission and member-assignment changes apply to an open session immediately, and deleting a user or rotating their API key closes that user's open sessions. After rotating your own key, reconnect and re-authenticate with the new one.

## Frame types

Server→client frames come in two styles:

| Style | Transport | Routed by | Carries |
| --- | --- | --- | --- |
| Stream frame | binary (zstd-compressed JSON) | `"stream"` | subscription snapshots, deltas, heartbeats |
| Response / one-shot | text (uncompressed JSON) | `"type"` / `"msg_type"` | command response envelopes, ConfigPayload, auth_error, watch_hub2hub frames |

**Why two styles:** stream frames are high-frequency and compress well, so they ride a compact binary channel; replies are low-frequency and must be trivial for any-language clients to parse and correlate, so they stay plain text. Decompress binary frames with zstd then parse JSON, routing on `"stream"`; parse text frames directly, routing on `"type"` (the request/response envelope, see below, and the `watch_hub2hub` subscription frames) or `"msg_type"` (the `auth_error` handshake failure).

## Request/response envelope

Every unary command carries a client-generated `req_id`; the server replies with exactly one correlated `response` text frame. `op` echoes the action so you can route without tracking `req_id` state if you prefer. `req_id` is technically optional (a command sent without one gets a response without one), but always sending it is strongly recommended.

> [!CAUTION]
> A message that is not valid JSON, or whose `action` is not a recognized command, receives **no** response frame; it is dropped (and logged server-side). Don't wait indefinitely on a reply to a malformed command; send well-formed text frames with a known `action`.

```
// request
{"action": "<op>", "req_id": "<uuid>", …params}

// success
{"type": "response", "req_id": "…", "op": "new_order", "ok": true,
 "result": { …same body the REST/gRPC equivalent returns… }}

// failure
{"type": "response", "req_id": "…", "op": "new_order", "ok": false,
 "error": {"code": "POSITION_LIMIT_EXCEEDED", "http_status": 422,
           "grpc_status": "FailedPrecondition", "message": "position limit exceeded"}}
```

The `result` body is byte-for-byte what the REST endpoint and gRPC RPC return. That is the parity guarantee in practice.

## Errors

A failed command returns `ok: false` with an `error` object carrying the canonical `code` plus its REST and gRPC equivalents. **Why all three:** the same failure then reads identically no matter which transport you use, and a client bridging transports can map cleanly in either direction.

| code | http_status | grpc_status | meaning |
| --- | --- | --- | --- |
| `PERMISSION_DENIED` | 403 | PermissionDenied | missing permission, or a desk-gated op on a trader license (`LICENSE_DESK_REQUIRED`) |
| `UNAUTHENTICATED` | 401 | Unauthenticated | missing / invalid credentials |
| `BAD_REQUEST` | 400 | InvalidArgument | malformed or invalid input |
| `NOT_FOUND` | 404 | NotFound | order / contract / user / member does not exist |
| `CONFLICT` | 409 | Aborted | state conflict (not active, modify already in progress) |
| `POSITION_LIMIT_EXCEEDED` | 422 | FailedPrecondition | order would breach the position limit |
| `CASH_LIMIT_EXCEEDED` | 422 | FailedPrecondition | order would breach the Voltnir order cash limit (global or per-member pool) |
| `SELF_CROSS_BLOCKED` | 422 | FailedPrecondition | order would cross your own resting order under reject policy |
| `TRADING_DISABLED` | 422 | FailedPrecondition | operator kill-switch is engaged (`trading_allowed = false`); `new_order` and `modify_order` are rejected before reaching M7. Cancels (`delete_order` / `cancel_all_orders`) are not gated; they only reduce exposure |
| `TIMEOUT` | 504 | DeadlineExceeded | exchange did not acknowledge in time |
| `NOT_OPERATIONAL` | 503 | Unavailable | gateway prerequisites not met / database unavailable |
| `INTERNAL` | 500 | Internal | unexpected server-side failure |

## Units & conventions

- **Price**: integer *cents* (EUR/MWh × 100). `5000` = 50.00 EUR/MWh. May be negative on power markets.
- **Quantity / display_qty / position limit**: integer *sub-MW* (MW × 1000). `1000` = 1.0 MW.
- **Orders are keyed by `client_order_id`** (a UUID), never the numeric M7 `order_id`; the same handle survives M7's delete-plus-recreate on modify.
- Timestamps are RFC 3339 strings; `*_ms` fields are UNIX epoch milliseconds.
- Enum values are lower snake_case, except `side` which is `"BUY"` / `"SELL"`.

These are the same units REST and gRPC use; there is no WebSocket-specific encoding.

## Execution semantics

`new_order` and `modify_order` are request/response with an immediate ack/reject. Synchronous failures (permission, validation, not-found, modify-in-progress) return an error envelope at once. `new_order` then awaits the M7 round-trip and resolves with `{client_order_id, state, reason}`, identical to REST/gRPC. A *rejected* order is a **successful** response carrying `state: "REJECTED"` (only a gateway error becomes an error envelope), matching gRPC `SubmitOrder`. The receive loop is never blocked while awaiting the exchange, so other commands and stream frames keep flowing. The full lifecycle afterward (fills, cancels, state changes) arrives on the `orders` and `trades` subscriptions.

## Reconnect & recovery

Keep the `client_order_id` from each `new_order` ack. After a disconnect: reconnect, re-auth, and resubscribe to `orders` and `trades`. The server sends a full snapshot on subscribe, each order carrying its `client_order_id`, so you can reconcile any in-flight orders against the authoritative state. A lagged subscriber is automatically re-snapshotted. For true idempotency across a disconnect that happens *before* the ack, supply your own `client_order_id` on `new_order` (it must be a valid UUID); re-sending the same key for a still-live order is rejected, so you can safely retry without risking a duplicate.

## Streaming: subscribing

Subscribe and unsubscribe with control messages. A successful subscribe gets no response envelope: the data arrives as stream frames; only a *denied* subscribe on a permission-gated stream is answered with an error envelope (`op: "subscribe"`):

```json
{"action": "subscribe", "stream": "<name>"}     // contracts also takes
                                                //   "areas": [...], "products": [...]
{"action": "unsubscribe", "stream": "<name>"}
```

Every stream is opt-in: nothing is pushed until you subscribe to it. Streams marked *no permission* are open to any authenticated caller; streams carrying a permission tag are additionally gated server-side at subscribe.

Stream frames are zstd-compressed binary, tagged by `"stream"`. Most send a `snapshot` (full current state) on first subscribe, then `deltas` thereafter; both fields are omitted when empty to save bytes (a frame with neither is a heartbeat; only the `contracts` stream emits these, every tick). Every frame carries `sent_at_ms` for latency measurement. Field-level semantics of the payload objects (`OwnOrder`, `OwnTrade`, `AreaContract`, `PnlSnapshot`, …) match the REST responses of the same name; see the REST reference for full field tables.

### `Stream` `orders`

_no permission_

Your orders, split by lifecycle. Re-sent in full whenever any order changes.

#### Frame

```json
{"stream": "orders", "orders_acknowledged": [OwnOrder…],
 "orders_pending": [PendingOrder…], "sent_at_ms": 1718…}
```

**Scoping.** Every `orders` frame is narrowed to what the connection's caller may see, exactly like the [`list_orders`](#cmd-list_orders) command (no member filter). A caller holding `read_orders` (or `bypass_member_check`) receives the firm-wide order book; everyone else receives only the orders tagged with a virtual member assigned to them, with untagged house orders withheld.

### `Stream` `trades`

_no permission_

Your fills. Snapshot on subscribe, then per-`trade_id` deltas.

#### Frame

```json
{"stream": "trades", "snapshot": [OwnTrade…] | absent,
 "deltas": [OwnTrade…], "sent_at_ms": 1718…}
```

### `Stream` `messages`

_no permission_

System and order-rejection messages. Snapshot then new-message deltas.

#### Frame

```json
{"stream": "messages", "snapshot": [SystemMessage…] | absent,
 "deltas": [SystemMessage…], "sent_at_ms": 1718…}
```

### `Stream` `status`

_1 Hz_

The trading-posture aggregate, streamed. The streaming companion of the unary [`get_status`](#cmd-get_status) command / REST `GET /status` / gRPC `GetStatus`; the gRPC `WatchStatus` RPC is its streaming twin.

> [!NOTE]
> Permission-gated server-side (`read_status`): a subscribe without it is answered with a `{"type":"response","op":"subscribe","ok":false,"error":{…}}` envelope and no stream.

#### Frame

```json
{"stream": "status", "throttling": {…}, "trading_enabled": true,
 "operational": true, "cash_limits": {…}, "order_pos_limit": 50000,
 "cash_limit": {
   "eur_limit_cents": 10000000, "eur_consumed_cents": 3500000, "eur_remaining_cents": 6500000,
   "gbp_limit_cents": 0,        "gbp_consumed_cents": 0,       "gbp_remaining_cents": 0
 },
 "license": {…}, "sent_at_ms": 1718…}
```

`cash_limit` is the **Voltnir order cash limit**: the configured limit, current consumption, and remaining headroom per currency pool, in cents (`remaining = limit − consumed`; `*_limit_cents == 0` means that pool is not enforced). Distinct from `cash_limits`, the M7-reported margin feed. The *configured* limits alone are also queryable / settable one-shot via [`get_cash_limit`](#cmd-get_cash_limit) / [`set_cash_limit`](#cmd-set_cash_limit); this status frame additionally streams live consumption + remaining. Cash-limit order bounces arrive on the [`messages`](#stream-messages) stream as order-rejection entries.

### `Stream` `pnl`

_1 Hz_

Per-contract, per-(area,product), and per-virtual-member P&L. Recomputed only when positions move.

#### Frame

```json
{"stream": "pnl", "pnl": PnlSnapshot, "sent_at_ms": 1718…}
```

**Scoping.** Every `pnl` frame is narrowed to what the connection's caller may see, exactly like the [`get_pnl`](#cmd-get_pnl) command (no member filter). A caller holding `read_pnl` (or `bypass_member_check`) receives the firm-wide snapshot; everyone else receives only their assigned members' `per_vm`/`per_vm_area_prod` rows, with the firm-wide `per_contract`/`per_area_prod` rollups empty.

### `Stream` `state`

_1 Hz_

Full runtime-health snapshot, same shape as [`get_state`](#cmd-get_state) / REST `GET /state`, under `state`.

> [!NOTE]
> Permission-gated server-side (`read_state`): a subscribe without it is answered with a `{"type":"response","op":"subscribe","ok":false,"error":{…}}` envelope and no stream.

#### Frame

```json
{"stream": "state", "state": SystemState, "sent_at_ms": 1718…}
```

### `Stream` `contracts`

_10 Hz_

Order book + contract metadata for the subscribed `{areas, products}`. Snapshot on subscribe (and on lag recovery), then upsert/delete deltas; emits a heartbeat every tick for latency diagnostics. `build_us` / `encode_us` report server-side frame cost.

#### Example

```
// subscribe with a filter
{"action": "subscribe", "stream": "contracts", "areas": ["DE"], "products": ["H"]}

// frame
{"stream": "contracts",
 "snapshot": [AreaContract…] | absent,
 "deltas": [{"type": "Upsert", "contract": AreaContract}
          | {"type": "Delete", "area_id": "DE", "contract_id": "12345"}] | absent,
 "sent_at_ms": 1718…, "build_us": 120, "encode_us": 45}
```

**Filters are required in practice.** A contract is included only when its area is in `areas` *and* its product is in `products`. An empty set matches nothing, so subscribing without both filters yields an empty snapshot and no data. A second `subscribe` on `contracts` replaces the active filter (and re-sends a snapshot).

The *subscribe* snapshot includes each contract's `last_history` trend-chip prefill. *Lag-recovery* snapshots omit it (kept small so a slow client can catch up), so treat `last_history` as optional and retain any prefill you already hold when it is absent.

> [!CAUTION]
> Each `AreaContract` carries `predefined`: `false` marks a **user-defined block** contract, where the exchange rejects regular limit orders (M7 error 1051, `"Can't enter OPEN order for user-defined blocks"`); only block orders are accepted. Do not offer regular order entry on a contract with `predefined: false`. `null` means metadata not yet received (not a block).

### `Stream` `public_trades`

_no permission_

Market-wide public trade tape (raw). There is no snapshot: the first frame after subscribe is an empty confirmation; seed per-contract history via [`public_trades_for_contract`](#cmd-public_trades_for_contract), then live deltas follow. Filter by `contract_id` client-side.

#### Frame

```json
{"stream": "public_trades", "deltas": [PublicTrade…], "sent_at_ms": 1718…}
```

### `Stream` `trade_tape`

_no permission_

Same source as [`public_trades`](#stream-public_trades), pre-enriched with each trade's `area_id`, `prod`, `name`, and `delivery_start` so you can render a cross-product tape without your own contract lookup. Snapshot is the ~200 most recent, oldest-first.

#### Frame

```json
{"stream": "trade_tape", "snapshot": [TradeTapeRow…] | absent,
 "deltas": [TradeTapeRow…], "sent_at_ms": 1718…}
```

### `Stream` `watch_hub2hub`

_no permission_

Live cross-border ATC (hub-to-hub capacity) for an area + delivery window. Unlike the other streams this is text-framed: an initial `hub2hub_response` snapshot, then per-entry `hub2hub_update` deltas and `hub2hub_heartbeat` connection-state frames. Updates are filtered server-side to entries whose hub matches `delivery_area` and whose delivery start falls in `[delivery_from, delivery_to)`. A second `watch_hub2hub` on the same connection replaces the prior subscription. (For a one-shot fetch without a subscription, use [`hub2hub_query`](#cmd-hub2hub_query).)

#### Example

```json
{"action": "watch_hub2hub", "delivery_area": "DE",
 "delivery_from": "2026-06-16T06:00:00Z", "delivery_to": "2026-06-16T22:00:00Z"}
{"action": "unwatch_hub2hub"}

// snapshot: {"type": "hub2hub_response", "delivery_area": "DE", …, "data": [AtcEntry…]}
// delta:    {"type": "hub2hub_update", "delivery_area": "DE", "entry": AtcEntry}
// liveness: {"type": "hub2hub_heartbeat", "connected": true, "ts_ms": 1718…}
```

### `Stream` `audit`

_Permission: read_audit_

Live tail of the compliance audit log. There is **no snapshot**: seed page 0 with the [`audit_query`](#cmd-audit_query) `events` entity, then subscribe. The feed is **event-driven, not polled**. The server pushes each audit row as it is committed, batched into at most one frame per tick (rows that existed before you subscribed are not replayed; that's what the seed query is for), so there is no per-client database polling. Each row is the same JSON the `audit_query` `events` entity returns, keyed by a stable per-row `id` (use it to dedup against the seeded page). Apply your panel's filters to the tail client-side.

> [!NOTE]
> Permission-gated server-side (`read_audit`): a subscribe without it is answered with a `{"type":"response","op":"subscribe","ok":false,"error":{…}}` envelope and no stream.

#### Example

```json
{"action": "subscribe", "stream": "audit"}
{"action": "unsubscribe", "stream": "audit"}

// delta: {"stream": "audit", "deltas": [AuditEvent…], "sent_at_ms": 1718…}
```

### `Stream` `m7_errors`

_Permission: read_m7_errors_

Live tail of the M7 exchange-error log. Same tail semantics as [`audit`](#stream-audit) but gated by `read_m7_errors`; seed via the [`audit_query`](#cmd-audit_query) `m7_errors` entity. Rows carry the stable `id` key.

#### Example

```json
{"action": "subscribe", "stream": "m7_errors"}
{"action": "unsubscribe", "stream": "m7_errors"}

// delta: {"stream": "m7_errors", "deltas": [M7Error…], "sent_at_ms": 1718…}
```

## Commands: Orders

All order fields and validation match REST `POST/PUT/DELETE /order` exactly (cents / sub-MW; see the REST reference for full field semantics).

### `Command` `new_order`

_Permission: create_order_

Submit a new order. Mirrors REST `POST /order` and gRPC `SubmitOrder`.

#### Parameters

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `side` | `string` | Yes | `"BUY"` or `"SELL"`. |
| `price` | `i64` | Yes | Cents (CCY/MWh × 100); may be negative. |
| `quantity` | `u32` | Yes | Sub-MW (MW × 1000). |
| `delivery_area_id` | `string` | Yes | EIC delivery area (e.g. `"DE"`). |
| `contract_id` | `i64` | One of | Direct contract id, or omit and supply `product` + `delivery_start`. |
| `product` + `delivery_start` | `string` | One of | Resolve the contract by delivery window (RFC 3339 start) against `delivery_area_id`. |
| `order_type` | `string` | No | Default `"regular"`. |
| `exe_restriction` | `string` | No | `"non"` (default), `"fok"`, `"ioc"`, `"aon"`. |
| `validity_res` | `string` | No | `"gfs"` (default), `"gtd"`, `"validity_non"`. |
| `entry_state` | `string` | No | Default `"active"`; `"hibernated"` submits the order inactive. |
| `display_qty` | `u32` | No | Sub-MW. Required for iceberg orders, and rejected on any other order type. |
| `validity_date` | `string` | No | RFC 3339; used with `validity_res: "gtd"`. |
| `pre_arranged_acct` | `string` | No | Pre-arranged counterparty account. |
| `v_member_short_id` | `string` | No | Virtual member to book the order to. |
| `client_order_id` | `string` | No | Client-supplied idempotency key (valid UUID); generated when omitted. |

#### Example

```json
{"action": "new_order", "req_id": "…", "side": "BUY", "price": 5000,
 "quantity": 1000, "delivery_area_id": "DE", "contract_id": 12345}
// or identify the contract by delivery window instead of contract_id:
{"action": "new_order", "req_id": "…", "side": "BUY", "price": 5000,
 "quantity": 1000, "delivery_area_id": "DE",
 "product": "H", "delivery_start": "2026-06-16T06:00:00Z"}
// → result: {"client_order_id": "…", "state": "ACTIVE", "reason": null}
```

**Contract identification.** Supply `contract_id`, or omit it and supply both `product` and `delivery_start` (resolved against `delivery_area_id`), identical to REST `POST /order` and gRPC `SubmitOrder`. Supplying neither is a `BAD_REQUEST`; a delivery window that matches no live contract is `NOT_FOUND`.

`client_order_id` is optional: omit it (or send `null`) and the gateway generates one, returned in the result. To make submission idempotent across a disconnect, supply your own; it must be a valid UUID, and reusing one still attached to a live order is rejected (`BAD_REQUEST`). Available identically on REST `POST /order` and gRPC `SubmitOrder`.

A *rejected* order is a **successful** response carrying `state: "REJECTED"` and a `reason`; only a gateway error becomes an error envelope. See [Execution semantics](#execution).

### `Command` `modify_order`

_Permission: modify_order_

Amend price, quantity, or validity of an existing order, or activate/deactivate it. Mirrors REST `PUT /order` and gRPC `ModifyOrder`.

#### Parameters

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `client_order_id` | `string` | Yes | The order's stable handle. |
| `modify_action` | `string` | No | `"modify"` (default), `"activate"`, `"deactivate"`. |
| `price` | `i64` | When modifying | Cents. Required when `modify_action` is `"modify"`. |
| `quantity` | `u32` | When modifying | Sub-MW. Required when `modify_action` is `"modify"`, and must be greater than zero. |
| `display_qty` | `u32` | No | Sub-MW, for iceberg orders. Must be < the new quantity. |
| `validity_res` / `validity_date` | `string` | No | New validity restriction / date. |
| `v_member_short_id` | `string` | No | Re-tag to another member (subject to member isolation). |

#### Example

```json
{"action": "modify_order", "req_id": "…", "client_order_id": "…",
 "modify_action": "modify", "price": 5500, "quantity": 500}
// modify_action "activate" / "deactivate" carry no price/quantity
// → result: {"status": "accepted"}  (only after M7 acknowledges receipt)
```

### `Command` `delete_order`

_Permission: delete_order_

Cancel one order by `client_order_id`. Mirrors REST `DELETE /order` and gRPC `CancelOrder`. Not gated by the kill-switch; cancels only reduce exposure.

#### Example

```json
{"action": "delete_order", "req_id": "…", "client_order_id": "…"}
// → result: {"status": "cancelled"}  (only after M7 acknowledges receipt)
```

**Acknowledgement** (also applies to `modify_order`). The response is returned only once M7 acknowledges receipt. If M7 rejects the request (e.g. the order was concurrently filled or deleted) the envelope is `ok:false` with a `CONFLICT` error; if no acknowledgement arrives within `system.order_ack_timeout_ms` the error is `TIMEOUT`. The resulting order state is delivered on the [`orders`](#stream-orders) stream.

**Member isolation** (also applies to `modify_order`). Beyond the `modify_order` / `delete_order` capability, the caller must be authorized to act on the order's member: assigned, or `bypass_member_check`; an untagged house order needs `trade_global`. `read_orders` grants visibility, not the right to act. An order outside that scope returns `NOT_FOUND`, identical to a missing one, so a desk cannot cancel, modify, or re-tag another member's order.

### `Command` `cancel_all_orders`

_Permission: delete_order_

Cancel every order the caller is authorized to act on, atomically. Mirrors REST `DELETE /orders` and gRPC `CancelAllOrders`.

#### Example

```json
{"action": "cancel_all_orders", "req_id": "…"}
// → result: {"deleted": <count>}  (only after M7 acknowledges the cancel)
// not gated by the kill-switch; works even when trading is disabled
// ok:false CONFLICT if M7 rejects; TIMEOUT if no ack within order_ack_timeout_ms
```

**Member isolation.** A full-authority caller (`bypass_member_check` + `trade_global`) cancels the whole account in one atomic command; a member-scoped caller cancels only their members' orders (other desks' and, without `trade_global`, house orders are left untouched). `deleted` counts only the orders this caller targeted.

### `Command` `get_order`

Look up one order (pending or acknowledged) by `client_order_id`. Mirrors REST `GET /order` and gRPC `GetOrder`. Authenticated-only; member-scoped.

#### Example

```json
{"action": "get_order", "req_id": "…", "client_order_id": "…"}
// → result: the order (pending or acknowledged), or NOT_FOUND
```

`get_order` is member-scoped like [`list_orders`](#cmd-list_orders): an order tagged with a member the caller may not see (or an untagged house order, for a caller without broad read) returns `NOT_FOUND`, identical to an unknown `client_order_id`, so it is not an existence oracle. A caller with `read_orders`/`bypass_member_check` can look up any order.

### `Command` `list_orders`

List the caller-visible resting orders, optionally filtered. Mirrors REST `GET /orders` and gRPC `ListOrders`. Authenticated-only; member-scoped.

#### Parameters

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `delivery_area` | `string` | No | Filter to one delivery area. |
| `contract_id` | `u64` | No | Filter to one contract; requires `delivery_area`. |
| `product` | `string` | No | Filter to one product; requires `delivery_area`. |
| `delivery_start` | `string` | No | With `product`: narrow to the contract at this RFC 3339 delivery start. Ignored without `product`. |
| `v_member_short_id` | `string` | No | Narrow to one member (authorization required, see below). |

#### Example

```json
{"action": "list_orders", "req_id": "…", "delivery_area": "DE",
 "contract_id": 12345, "product": "H",
 "v_member_short_id": "VM001"}
// all filters optional; contract_id/product require delivery_area
// → result: caller-scoped array of resting orders
```

`list_orders` is member-scoped like REST `GET /orders`: a caller with `read_orders` (or `bypass_member_check`) sees the firm-wide order book, everyone else only their assigned members' orders (untagged house orders withheld). The optional `v_member_short_id` narrows to one member and returns a `PermissionDenied` error envelope unless the caller is assigned to it or holds broad read.

## Commands: Contracts

Contract metadata and per-contract working sets. Authenticated-only. Shapes match REST `GET /contract/…`; see the REST reference for full field tables.

### `Command` `list_contracts`

All contracts for a delivery area. Mirrors REST `GET /contract/{area_id}` and gRPC `ListContracts`.

#### Example

```json
{"action": "list_contracts", "req_id": "…", "area_id": "DE"}
// → result: array of contracts for the area
```

### `Command` `get_contract`

One contract's detail: metadata plus the caller's working set on it. Mirrors REST `GET /contract/{area_id}/{contract_id}` and gRPC `GetContract`.

#### Example

```json
{"action": "get_contract", "req_id": "…", "area_id": "DE", "contract_id": "12345"}
// → result: {contract, orders_acknowledged, orders_pending, trades, net_pos}
```

### `Command` `get_contract_by_delivery`

Same result as [`get_contract`](#cmd-get_contract), resolved by product + delivery start instead of contract id. Mirrors REST `GET /contract/{area}/by-delivery/…` and gRPC `GetContractByDelivery`.

#### Example

```json
{"action": "get_contract_by_delivery", "req_id": "…", "area_id": "DE",
 "prod": "H", "dlvry_start": "2026-06-16T06:00:00Z"}
// → result: same shape as get_contract
```

## Commands: System

Most read-only queries need no permission; setters require the noted permission. `get_state` is gated by `read_state` and `get_status` by `read_status`. Result bodies match the REST endpoint of the same name; see the REST reference for full field tables.

### `Command` `get_state`

_Permission: read_state_

Runtime-health snapshot: uptime, AMQP/upstream connectivity and latency telemetry, license. Mirrors REST `GET /state` and gRPC `GetState`; the [`state`](#stream-state) stream is its streaming form.

#### Example

```json
{"action": "get_state", "req_id": "…"}
// → result: SystemState, same shape as REST GET /state
```

### `Command` `get_status`

_Permission: read_status_

The trading-posture aggregate in one call: the one-shot form of the [`status`](#stream-status) stream, same flat shape as REST `GET /status` and gRPC `GetStatus`.

#### Example

```json
{"action": "get_status", "req_id": "…"}
// result: {"throttling": {…}, "trading_enabled": true, "operational": true,
//          "cash_limits": {…}, "order_pos_limit": 50000,
//          "cash_limit": {"eur_limit_cents": …, "eur_consumed_cents": …, "eur_remaining_cents": …,
//                         "gbp_limit_cents": …, "gbp_consumed_cents": …, "gbp_remaining_cents": …},
//          "license": {…}}
```

`cash_limit` values are in cents (`i64`); `order_pos_limit` is sub-MW. See the [`status`](#stream-status) stream card for the field semantics.

### `Command` `get_throttling`

Current M7 request-throttling counters (per-window request budget and usage). Mirrors REST `GET /throttling` and gRPC `GetThrottling`. Authenticated-only.

#### Example

```json
{"action": "get_throttling", "req_id": "…"}
// → result: M7 throttling counters, same shape as REST GET /throttling
```

### `Command` `get_system_info`

Gateway + exchange system parameters: `voltnir_version` (this gateway's build, always set even before M7 responds) plus the M7 system params (`backend_version`, rate limits, `max_orders`, retention). Mirrors REST `GET /system_info` and gRPC `GetSystemInfo`. Authenticated-only.

#### Example

```json
{"action": "get_system_info", "req_id": "…"}
// → result: same shape as REST GET /system_info; M7-sourced fields are null
//   until the exchange has responded, voltnir_version is always set
```

### `Command` `get_cash_limits`

The M7-reported cash/margin limit feed, keyed by ISO currency. Distinct from the Voltnir order cash limit ([`get_cash_limit`](#cmd-get_cash_limit)). Mirrors REST `GET /cash_limits` and gRPC `GetCashLimits`. Authenticated-only.

#### Example

```json
{"action": "get_cash_limits", "req_id": "…"}
// → result: {"limits": {"EUR": {…}, …}}, same shape as REST GET /cash_limits
```

### `Command` `list_permissions`

_Permission: manage_users_

The catalog of assignable permissions with human-readable descriptions. Render it; don't hardcode your own copy. Mirrors REST `GET /permissions` and gRPC `ListPermissions`.

#### Example

```json
{"action": "list_permissions", "req_id": "…"}
// → result: {"permissions": [{"code": "create_order", "description": "…"}, …]}
```

### `Command` `get_pnl`

Caller-scoped P&L snapshot: per-contract, per-(area,product), and per-virtual-member. Mirrors REST `GET /pnl` and gRPC `GetPnl`; the [`pnl`](#stream-pnl) stream is its streaming form. Authenticated-only; member-scoped.

#### Parameters

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `v_member_short_id` | `string` | No | Narrow to one member (authorization required, see below). |

#### Example

```json
{"action": "get_pnl", "req_id": "…", "v_member_short_id": "VM001"}
// → result: caller-scoped PnL snapshot; member filter optional
```

`get_pnl` is member-scoped like REST `GET /pnl`: a caller with `read_pnl` (or `bypass_member_check`) sees the firm-wide snapshot, everyone else only their assigned members (firm-wide `per_contract`/`per_area_prod` empty). The optional `v_member_short_id` narrows to one member and returns a `PermissionDenied` error envelope unless the caller is assigned to it or holds broad read.

### `Command` `list_public_trades`

Recent market-wide public trades, optionally filtered. Mirrors REST `GET /public_trades` and gRPC `ListPublicTrades`. Authenticated-only.

#### Parameters

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `limit` | `u32` | No | Default 100, capped at 1000; must be > 0. |
| `contract_id` | `u64` | No | Filter to one contract. |
| `area_id` | `string` | No | Filter to one delivery area. |

#### Example

```json
{"action": "list_public_trades", "req_id": "…", "limit": 100,
 "contract_id": 12345, "area_id": "DE"}   // filters optional
// → result: {"trades": […]}
```

### `Command` `get_contract_limit`

The global per-contract net position limit, in sub-MW. Mirrors REST `GET /contract_limit` and gRPC `GetContractLimit`. Authenticated-only.

#### Example

```json
{"action": "get_contract_limit", "req_id": "…"}
// → result: {"limit": <sub-MW>}
```

### `Command` `set_order_pos_limit`

_Permission: set_position_limit_

Set the global per-contract net position limit. Mirrors REST `PUT /contract_limit` and gRPC `SetContractLimit`.

#### Parameters

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `limit` | `i32` | Yes | New limit in sub-MW. Must be non-negative; `0` is the operator kill-switch (blocks all new position-taking). |

#### Example

```json
{"action": "set_order_pos_limit", "req_id": "…", "limit": 5000}  // sub-MW
// → result: {"order_pos_limit": 5000}
// limit < 0 is rejected with BAD_REQUEST ("limit must be non-negative")
```

### `Command` `get_trading_allowed`

Read the trading kill-switch. Mirrors REST `GET /trading_allowed` and gRPC `GetTradingAllowed`. Authenticated-only.

#### Example

```json
{"action": "get_trading_allowed", "req_id": "…"}
// → result: {"enabled": true}
```

### `Command` `toggle_trade_enabled`

_Permission: toggle_trading_

Explicit, idempotent SET of the trading kill-switch (despite the name, it never toggles blindly). Mirrors REST `PUT /trading_allowed` and gRPC `SetTradingAllowed`.

#### Parameters

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `enabled` | `bool` | Yes | Required. A missing field is rejected as a malformed command (it never defaults, so it can't silently disable trading). |

#### Example

```json
{"action": "toggle_trade_enabled", "req_id": "…", "enabled": false}
// → result: {"enabled": false}
```

> [!WARNING]
> Disabling flattens the book AND rejects `new_order`/`modify_order` with `TRADING_DISABLED`; cancels stay allowed. Rejected with `CONFLICT` when the `system.disable_trading` config flag is set (config is the absolute authority).

### `Command` `get_self_trade_policy`

Read the self-trade prevention policy. Mirrors REST `GET /self_trade_policy` and gRPC `GetSelfTradePolicy`. Authenticated-only.

#### Example

```json
{"action": "get_self_trade_policy", "req_id": "…"}
// → result: {"policy": "observe"}
```

### `Command` `set_self_trade_policy`

_Permission: set_self_trade_policy_

Set the self-trade prevention policy. Under `reject`, an order that would cross your own resting order is refused with `SELF_CROSS_BLOCKED`. Mirrors REST `PUT /self_trade_policy` and gRPC `SetSelfTradePolicy`.

#### Parameters

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `policy` | `string` | Yes | `"observe"` or `"reject"`. |

#### Example

```json
{"action": "set_self_trade_policy", "req_id": "…", "policy": "reject"}
// → result: {"policy": "reject"}
```

### `Command` `get_cash_limit`

Read both configured global cash pools (EUR + GBP, in cents). The global (overarching-member) limit; distinct from [`get_cash_limits`](#cmd-get_cash_limits) (the M7 feed). Mirrors REST `GET /cash_limit` and gRPC `GetCashLimit`. Authenticated-only.

#### Example

```json
{"action": "get_cash_limit", "req_id": "…"}
// → result: {"cents": <EUR cents>, "gbp_cents": <GBP cents>}
```

### `Command` `set_cash_limit`

_Permission: set_cash_limit_

Update one global cash pool. Takes effect immediately; every per-member cash limit is capped at the global value. Mirrors REST `PUT /cash_limit` and gRPC `SetCashLimit`.

#### Parameters

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `cents` | `i64` | Yes | New limit in cents of the target currency. Must be ≥ 0; `0` disables that pool's check. |
| `currency` | `string` | No | `"eur"` (default) or `"gbp"`. Unknown values are `BAD_REQUEST`. |

#### Example

```json
{"action": "set_cash_limit", "req_id": "…", "cents": 10000000}            // EUR pool
{"action": "set_cash_limit", "req_id": "…", "cents": 5000000, "currency": "gbp"}  // GBP pool
// → result: {"cents": …, "gbp_cents": …}
```

### `Command` `get_cash_fail_closed`

Read the cash fail-closed flag. Mirrors REST `GET /cash_fail_closed` and gRPC `GetCashFailClosed`. Authenticated-only.

#### Example

```json
{"action": "get_cash_fail_closed", "req_id": "…"}
// → result: {"enabled": true}
```

### `Command` `set_cash_fail_closed`

_Permission: set_cash_limit_

Set the cash fail-closed flag, ECC parity (§3.11/§3.12), **enabled by default**: when enabled, a 0/unset cash limit means **no trading** in that pool; disable to opt into fail-open. Gated by `set_cash_limit` (part of the cash-limit control). Mirrors REST `PUT /cash_fail_closed` and gRPC `SetCashFailClosed`.

#### Parameters

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `enabled` | `bool` | Yes | `true` = fail-closed (default posture), `false` = fail-open. |

#### Example

```json
{"action": "set_cash_fail_closed", "req_id": "…", "enabled": false}
// → result: {"enabled": false}
```

### `Command` `get_holidays`

Read both ECC bank-holiday calendars (EUR + GBP), used by the cash-limit exposure window (the 16:00 reset rolls over them). EUR and GBP are **independent** calendars (GB bank holidays close CHAPS). Mirrors REST `GET /holidays` and gRPC `GetHolidays`. Authenticated-only.

#### Example

```json
{"action": "get_holidays", "req_id": "…"}
// → result: {"eur": [{"date": "2026-12-25", "label": "Christmas Day"}], "gbp": [...]}
```

### `Command` `set_holidays`

_Permission: set_cash_limit_

Replace one currency's whole holiday calendar. Mirrors REST `PUT /holidays` and gRPC `SetHolidays`.

#### Parameters

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `currency` | `string` | Yes | `"eur"` or `"gbp"`. |
| `holidays` | `array` | Yes | `{date, label?}` objects; `date` is `YYYY-MM-DD`. |

#### Example

```json
{"action": "set_holidays", "req_id": "…", "currency": "gbp",
 "holidays": [{"date": "2026-08-31", "label": "Summer Bank Holiday"}, {"date": "2026-12-25"}]}
// → result: {"eur": […], "gbp": […]}  (both calendars after the change)
```

**Errors** (all holiday mutations): `BAD_REQUEST` (unknown currency / malformed `YYYY-MM-DD` / duplicate), `NOT_FOUND` (remove of an absent date).

### `Command` `add_holiday`

_Permission: set_cash_limit_

Add one date to a currency's calendar. Mirrors REST `POST /holidays` and gRPC `AddHoliday`.

#### Example

```json
{"action": "add_holiday", "req_id": "…", "currency": "eur",
 "date": "2026-01-01", "label": "New Year's Day"}
// → result: {"eur": […], "gbp": […]}  (both calendars after the change)
```

### `Command` `remove_holiday`

_Permission: set_cash_limit_

Remove one date from a currency's calendar. Mirrors REST `DELETE /holidays` and gRPC `RemoveHoliday`.

#### Example

```json
{"action": "remove_holiday", "req_id": "…", "currency": "eur", "date": "2026-01-01"}
// → result: {"eur": […], "gbp": […]}  (both calendars after the change)
// removing an absent date → NOT_FOUND
```

### `Command` `restart`

_Permission: restart_system_

Initiate a gateway restart. Mirrors REST `POST /restart` and gRPC `Restart`. Expect the socket to close shortly after the response.

#### Example

```json
{"action": "restart", "req_id": "…"}
// → result: {"status": "restart initiated"}
```

## Commands: Users & Members

Self queries are open to any authenticated caller. Management commands require the **desk** license (a `trader` license returns `PERMISSION_DENIED` / `LICENSE_DESK_REQUIRED`) plus the noted permission. Bodies match REST `/users` and `/members` exactly.

### `Command` `get_me`

Your own user record: id, username, short id, permission set. Mirrors REST `GET /users/me` and gRPC `GetMe`. Authenticated-only.

#### Example

```json
{"action": "get_me", "req_id": "…"}
// → result: {"id": "…", "username": "…", "short_id": "U002", "permissions": […]}
```

### `Command` `get_my_members`

The virtual members assigned to you: the only member short ids you may set on orders (unless you hold `bypass_member_check`). Returns the same per-member objects as [`get_members`](#cmd-get_members), live cash-usage fields included. Mirrors REST `GET /users/me/members` and gRPC `GetMyMembers`. Authenticated-only.

#### Example

```json
{"action": "get_my_members", "req_id": "…"}
// → result: [Member…], same shape as get_members
```

### `Command` `get_users`

_Permission: manage_users_

List all users with their ids, usernames, short ids, and permission sets. Mirrors REST `GET /users` and gRPC `ListUsers`.

#### Example

```json
{"action": "get_users", "req_id": "…"}
// → result: [{"id": "…", "username": "…", "short_id": "U001", "permissions": […]}, …]
```

### `Command` `create_user`

_Permission: manage_users_

Create a user, optionally granting permissions in the same call (validated *before* any write, so a bad request never leaves a half-created user). Mirrors REST `POST /users` and gRPC `CreateUser`.

#### Parameters

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `username` | `string` | Yes | Non-empty, unique. |
| `permissions` | `string[]` | No | Permission codes to grant on creation (see [`list_permissions`](#cmd-list_permissions)). |

#### Example

```json
{"action": "create_user", "req_id": "…", "username": "alice", "permissions": ["create_order"]}
// → result: {id, username, short_id, permissions, api_key}
```

> [!CAUTION]
> `api_key` is the raw plaintext key, shown **only in this response**. It cannot be retrieved again, only rotated.

### `Command` `delete_user`

_Permission: manage_users_

Delete a user. Mirrors REST `DELETE /users/{id}` and gRPC `DeleteUser`.

#### Example

```json
{"action": "delete_user", "req_id": "…", "user_id": "…"}
// → result: {} on success
```

### `Command` `set_permissions`

_Permission: manage_users_

Replace a user's permission set. Mirrors REST `PUT /users/{id}/permissions` and gRPC `SetPermissions`.

#### Example

```json
{"action": "set_permissions", "req_id": "…", "user_id": "…", "permissions": [...]}
// → result: {} on success
// the admin account's permissions are immutable → PERMISSION_DENIED if targeted
```

### `Command` `rotate_api_key`

_Permission: manage_users_

Rotate a user's API key; the old key stops working immediately. Mirrors REST `POST /users/{id}/rotate-api-key` and gRPC `RotateApiKey`. **Not desk-gated**, unlike the other user-management commands.

#### Example

```json
{"action": "rotate_api_key", "req_id": "…", "user_id": "…"}
// → result: {"api_key": "…"}  (shown once)
// trader tier: self-only, user_id must be the caller; any other target → NOT_FOUND
// desk tier: manage_users may rotate any user
```

Rotating your **own** key invalidates this connection's credential, so the server closes your open WebSocket sessions. Reconnect and re-authenticate with the new key.

### `Command` `get_user_members`

_Permission: manage_users_

The member assignments of any user, as an array of member ids. Mirrors REST `GET /users/{id}/members` and gRPC `GetUserMembers`.

#### Example

```json
{"action": "get_user_members", "req_id": "…", "user_id": "…"}
// → result: ["<member-id>", …]  (the user's assigned member ids)
```

### `Command` `set_user_members`

_Permission: manage_users_

Replace a user's member assignments. Mirrors REST `PUT /users/{id}/members` and gRPC `SetUserMembers`.

#### Example

```json
{"action": "set_user_members", "req_id": "…", "user_id": "…", "member_ids": [...]}
// → result: {} on success
```

### `Command` `get_members`

_Permission: manage_members_

List all virtual members with their configured limits and live cash usage. Mirrors REST `GET /members` and gRPC `ListMembers`.

#### Example

```json
{"action": "get_members", "req_id": "…"}
// → result:
// [{"id":"…","short_id":"VM001","name":"Desk A","max_position":5000,
//   "cash_limit":10000000,"cash_limit_gbp":0,"active":true,
//   "eur_consumed_cents":4200000,"eur_limit_cents":10000000,"eur_remaining_cents":5800000,
//   "gbp_consumed_cents":0,"gbp_limit_cents":0,"gbp_remaining_cents":0}, …]
```

`cash_limit` / `cash_limit_gbp` are the configured per-member **overrides** in EUR / GBP cents; `0` = no override (the global limit applies). The `*_consumed` / `*_limit` / `*_remaining` trio is live cash usage per pool: `consumed` = this member's open-order + executed-trade exposure; `*_limit_cents` = the **effective** cap (override capped at the global, or the inherited global; need not equal `cash_limit`); `remaining = limit − consumed` (negative when over; `0` limit = pool not enforced). Same shape and semantics as REST `GET /api/v1/members` and the gRPC `Member` message. [`get_my_members`](#cmd-get_my_members) returns the same per-member objects for the caller's assigned members.

### `Command` `create_member`

_Permission: manage_members_

Create a virtual member (auto-generated sequential `short_id`). Mirrors REST `POST /members` and gRPC `CreateMember`.

#### Parameters

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `name` | `string` | Yes | Display name. |
| `max_position` | `i64` | No | Per-member position limit, sub-MW. |
| `cash_limit` / `cash_limit_gbp` | `i64` | No | Per-member cash overrides in cents; `0`/omitted = no override. |

#### Example

```json
{"action": "create_member", "req_id": "…", "name": "Desk A", "max_position": 5000,
 "cash_limit": 10000000, "cash_limit_gbp": 0}
// → result: the created Member object, same shape as get_members; a fresh member has
//   *_consumed_cents 0 and *_remaining_cents == the effective *_limit_cents
```

### `Command` `patch_member`

_Permission: manage_members_

Update a member; all update fields optional. Mirrors REST `PATCH /members/{id}` and gRPC `PatchMember`.

#### Example

```json
{"action": "patch_member", "req_id": "…", "member_id": "…", "name": "…",
 "max_position": 6000, "cash_limit": 10000000, "cash_limit_gbp": 0,
 "active": false}
// cash_limit in cents; 0 clears the override
// → result: {} on success
```

## Queries & Reports

These one-shot queries use the standard request/response [envelope](#envelope): send with a `req_id`, receive a correlated `{"type":"response", …, "ok":true, "result":{…}}`. The shapes below show the `result` body; on failure you get an error envelope instead (e.g. `read_audit`/`export_reports` missing → `PERMISSION_DENIED`, a bad date filter → `BAD_REQUEST`). The data matches the equivalent REST endpoint and gRPC RPC.

### `Command` `audit_query`

_m7_errors: read_m7_errors_

Cursor-paginated audit history from the store. `entity` is `orders`, `trades`, `public_trades`, `events`, or `m7_errors` (mirroring REST `GET /audit/{orders,trades,public_trades,events,m7_errors}`); for `public_trades` the `status` filter is the M7 trade state (e.g. `ACTI`, `CNCL`). Most entities require `read_audit`; **`m7_errors` requires the dedicated `read_m7_errors`** permission instead.

#### Parameters

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `entity` | `string` | Yes | `orders` · `trades` · `public_trades` · `events` · `m7_errors`. |
| `cursor` | `string` | No | `null` on the first page; pass back the previous response's `next_cursor`. |
| `limit` | `u32` | No | Default 50, max 200; an explicit `limit=0` is rejected (`BAD_REQUEST`), same rule as REST `GET /audit/{…}`. |
| `filters` | `object` | No | Entity-specific filter set; see the examples below. |

#### Example: orders / trades / public_trades

```json
{"action": "audit_query", "req_id": "…", "entity": "orders", "cursor": null,
 "limit": 100, "filters": {"date_from": "…", "date_to": "…", "area": "DE",
 "product": "H", "status": "ACTIVE", "user_code": "TRADER1", "v_member_short_id": "VM001",
 "voltnir_user_short_id": "U001", "voltnir_username": "j.doe",
 "sort_order": "DESC"}}
// → result: {"entity": "orders", "items": [...],
//            "next_cursor": "…" | null, "total_hint": 1234 | null}
```

`user_code` = EPEX trader/user code (renamed from the former, mislabelled `user_id`); `voltnir_user_short_id` / `voltnir_username` attribute the submitting Voltnir user. Audit rows carry `voltnir_user_id` + `voltnir_user_short_id` + `voltnir_username`. A `contract_id` filter (string) is accepted for `entity: "trades"` only; it is ignored for orders, and `public_trades` uses only the date/`area`/`product`/`status` filters.

#### Example: events

**`entity: "events"`** queries the compliance audit-event log, the append-only who-did-what record of actor-driven mutations (user/permission/member/limit changes, kill-switch and self-trade toggles, order rejections, report exports, system/license lifecycle). It uses the events-only filters `action` / `target_type` / `actor_short_id` / `outcome` (`ok` · `error`; plus the shared date/ cursor/limit). Each item carries the actor, transport, source IP, `before`/`after` snapshots, outcome, and reason.

```json
{"action": "audit_query", "req_id": "…", "entity": "events", "cursor": null,
 "limit": 100, "filters": {"action": "permissions_set", "target_type": "user",
 "actor_short_id": "U001", "outcome": "ok", "date_from": "…", "date_to": "…"}}
// → result: {"entity": "events", "items": [{"ts": "…", "actor_short_id": "U001",
//            "transport": "ws", "action": "permissions_set", "target_type": "user",
//            "before": [...], "after": [...], "outcome": "ok",
//            "source_ip": "203.0.113.7", ...}],
//            "next_cursor": "…" | null, "total_hint": 1042 | null}
```

#### Example: m7_errors

**`entity: "m7_errors"`** queries the M7 exchange-error log, the append-only record of M7-side faults off the AMQP line. **Gated by `read_m7_errors`** (not `read_audit`). Uses the m7-errors-only filters `kind` / `category` / `err_code` (plus the shared date/cursor/ limit). `err_resp` rows are enriched from the DFS200 §4 catalog with a human `err_identifier` + `category`; the other kinds (`parse_error`, `unknown_type`, `ack_uncorrelated`, `seq_gap`) carry no code/category.

```json
{"action": "audit_query", "req_id": "…", "entity": "m7_errors", "cursor": null,
 "limit": 100, "filters": {"kind": "err_resp", "category": "limits",
 "err_code": 1149, "date_from": "…", "date_to": "…"}}
// → result: {"entity": "m7_errors", "items": [{"received_at": "…", "kind": "err_resp",
//            "category": "order_entry", "err_code": 1149,
//            "err_identifier": "order_rejected_self_trade_protection",
//            "err_text": "…", "cl_ordr_id": "…", "var_list": [...],
//            "severity": "error", ...}],
//            "next_cursor": "…" | null, "total_hint": 37 | null}
```

### `Command` `generate_report`

_Permission: export_reports_

Enqueue a background order/trade export, then poll the returned token with [`report_poll`](#cmd-report_poll). Matches REST `POST /audit/export/…`.

#### Parameters

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `kind` | `string` | Yes | `"orders"` or `"trades"`. |
| `format` | `string` | Yes | `"json"` or `"csv"`. |
| `from` / `to` | `string` | Yes | RFC 3339 window (`from < to`). |
| `area` / `product` | `string` | No | Optional filters. |

#### Example

```json
{"action": "generate_report", "req_id": "…", "kind": "orders", "from": "…",
 "to": "…", "format": "json", "area": "DE", "product": "H"}
// → result: {"token": "<uuid>"}
```

### `Command` `report_poll`

_Permission: export_reports_

Poll an export by token until ready. The result carries a `status` discriminant; when `"ready"` the file is base64-encoded inline.

#### Example

```json
{"action": "report_poll", "req_id": "…", "token": "<uuid>"}
// → result: {"token": "…", "status": "pending"}            (or "not_found")
//         | {"token": "…", "status": "failed", "error": "…"}
//         | {"token": "…", "status": "ready", "filename": "…",
//            "content_type": "application/json", "data": "<base64>"}
```

### `Command` `hub2hub_query`

One-shot cross-border ATC capacity for an area + window (no subscription). For live updates use [`watch_hub2hub`](#stream-watch_hub2hub). Mirrors REST `GET /hub2hub` and gRPC `GetHub2Hub`. Authenticated-only.

#### Example

```json
{"action": "hub2hub_query", "req_id": "…", "delivery_area": "DE",
 "delivery_from": "2026-06-16T06:00:00Z", "delivery_to": "2026-06-16T22:00:00Z"}
// → result: {"delivery_area": "DE", "delivery_from": "…", "delivery_to": "…",
//            "enabled": true, "capacity_connected": true, "data": [AtcEntry…]}
```

### `Command` `public_trades_for_contract`

The retained public-trade history for one contract, typically fired on chart mount, then kept live via the [`public_trades`](#stream-public_trades) stream (dedup by `trade_id`). Authenticated-only.

#### Example

```json
{"action": "public_trades_for_contract", "req_id": "…", "contract_id": 12345}
// → result: {"contract_id": 12345, "trades": [PublicTrade…]}
```

## Transport mapping

The unary surface, command by command. Each row is the same operation on all three transports, with the same fields, units, permissions, and errors.

| WebSocket command | REST | gRPC RPC |
| --- | --- | --- |
| `new_order` | POST /order | SubmitOrder |
| `modify_order` | PUT /order | ModifyOrder |
| `delete_order` | DELETE /order | CancelOrder |
| `cancel_all_orders` | DELETE /orders | CancelAllOrders |
| `get_order` | GET /order | GetOrder |
| `list_orders` | GET /orders | ListOrders |
| `list_contracts` | GET /contract/{area} | ListContracts |
| `get_contract` | GET /contract/{area}/{id} | GetContract |
| `get_contract_by_delivery` | GET /contract/{area}/by-delivery/… | GetContractByDelivery |
| `get_state` | GET /state | GetState |
| `get_status` | GET /status | GetStatus |
| `get_throttling` | GET /throttling | GetThrottling |
| `get_system_info` | GET /system_info | GetSystemInfo |
| `get_cash_limits` | GET /cash_limits | GetCashLimits |
| `list_permissions` | GET /permissions | ListPermissions |
| `get_pnl` | GET /pnl | GetPnl |
| `list_public_trades` | GET /public_trades | ListPublicTrades |
| `get_contract_limit` · `set_order_pos_limit` | GET/PUT /contract_limit | GetContractLimit · SetContractLimit |
| `get_cash_limit` · `set_cash_limit` | GET/PUT /cash_limit | GetCashLimit · SetCashLimit |
| `get_holidays` · `set_holidays` · `add_holiday` · `remove_holiday` | GET/PUT/POST/DELETE /holidays | GetHolidays · SetHolidays · AddHoliday · RemoveHoliday |
| `get_trading_allowed` · `toggle_trade_enabled` | GET/PUT /trading_allowed | GetTradingAllowed · SetTradingAllowed |
| `get_self_trade_policy` · `set_self_trade_policy` | GET/PUT /self_trade_policy | GetSelfTradePolicy · SetSelfTradePolicy |
| `restart` | POST /restart | Restart |
| `get_me` · `get_my_members` | GET /users/me · /users/me/members | GetMe · GetMyMembers |
| user/member management | /users · /members | ListUsers, CreateUser, … CreateMember, PatchMember |
| `audit_query` | GET /audit/{orders,trades,public_trades,events,m7_errors} | QueryAuditOrders · QueryAuditTrades · QueryAuditPublicTrades · QueryAuditEvents · QueryM7Errors |
| `generate_report` · `report_poll` | POST /audit/export/… · GET /audit/export/{token} | ExportOrders · ExportTrades (server-streaming) |
| `hub2hub_query` | GET /hub2hub | GetHub2Hub |

**Streaming has no REST column.** WebSocket streams correspond to the gRPC `Watch*` RPCs by data, not shape: `contracts` ≈ `WatchContract`, `orders` ≈ `WatchOrder` / `WatchOrders`, `trades` ≈ `WatchTrades`, `messages` ≈ `WatchMessages`, `pnl` ≈ `WatchPnl`, `status` ≈ `WatchStatus`, `state` ≈ `WatchState`, `public_trades` ≈ `WatchPublicTrades`, `audit` ≈ `WatchAuditEvents`, `m7_errors` ≈ `WatchM7Errors`. Only `trade_tape` (a filtered view of the same data `WatchPublicTrades` carries) and `watch_hub2hub` remain WebSocket-native live feeds with no dedicated gRPC twin.
