# Voltnir WebSocket API v1: Reference

> Auto-generated from the Voltnir API reference.

<a id="overview" name="overview"></a>

## Overview

The Voltnir WebSocket API is the session transport onto the EPEX SPOT M7 intraday gateway: one long-lived connection at `/ws/v1` carries your commands and the live push data on the same ordered socket. It is the transport the Voltnir trading terminal itself uses, so anything the terminal does, your client can do too.

- **Parity with REST and gRPC.** Every command mirrors a REST endpoint and a gRPC RPC exactly: same fields, same units, same permission gates, same validation, and the `result` body is the body the REST endpoint returns. The permission table is identical across the three references.
- **Streaming.** Subscribe once and the server pushes a snapshot, then deltas: your orders and trades, the order book, P&L, status, the public trade tape. Each stream is the semantic peer of a gRPC `Watch*` RPC; REST has no equivalent.
- **Correlated replies.** Every command carries a client-generated `req_id` that the server echoes on its one reply, so several commands can be in flight beside the stream frames. Replies can arrive in a different order from their commands, so match them by `req_id`; a client that needs one command to take effect before the next waits for its reply. A failure is an error envelope carrying the canonical `code` with its HTTP and gRPC status; the [Error reference](#errors) maps each one.
- **One ordered session.** You send `new_order`, the server acknowledges it, and the fill, when it happens, arrives on the same `orders` / `trades` streams in the same order as the book update that caused it, with no second transport to reconcile.

Read [Connecting and authentication](#connecting) first, then [Permissions](#permissions) and [Conventions](#conventions). The commands follow, grouped by domain, then [Streaming](#streaming) and the [Error reference](#errors).

<a id="connecting" name="connecting"></a>

## Connecting and authentication

#### Connection and versioning

Connect to the path-versioned endpoint:

```
ws://<host>:9001/ws/v1        (wss:// behind a TLS reverse proxy)
```

The version lives in the path, mirroring REST's `/api/v1` and gRPC's `voltnir.api.v1`. The bare root (`/`) and `/v1` are accepted as transition aliases; an unknown version such as `/ws/v2` is rejected at the upgrade handshake. **Why path versioning:** a future breaking change ships as a new `/ws/v2` endpoint while `/ws/v1` keeps running unchanged, so an existing client is never silently broken; it keeps speaking the version it connected to until you choose to migrate.

#### Authentication

The first message on a new connection **must** be an auth frame carrying your API key. Any other first message closes the connection (10 s window).

The `token` may also be a **session token** (it starts with `vs_`), accepted exactly like a key and acting as its user with that user's live permissions. The trading terminal signs in this way so the browser never keeps the API key. Sessions are minted and ended over REST only, with [`POST /sessions`](rest_api_v1.md#post-sessions) and [`DELETE /sessions/current`](rest_api_v1.md#delete-sessions-current); a program connecting here authenticates with its API key. An expired or ended session gets the same `auth_error` as a wrong key, and a connection open on a session closes when that session ends or expires.

```
// client → server (text)
{"action": "auth", "token": "<your-api-key>"}
```

On success the server replies with a `ConfigPayload` text frame carrying the **connection facts**, the delivery areas and the products this instance subscribes market data for (every assigned product can be traded; see the product reference op), the negotiated `protocol_version` (assert it equals `"v1"`) and a `public_trades` hint describing the saved-tape backend, flattened together with the **caller-scoped trading posture**, the same layered field set the [`get_status`](#cmd-get_status) command returns. Every connection gets the base posture (`operational`, `throttling`, `trading_enabled`, `license_summary`) and its own `accounts`; the desk-wide money and full licence are carried only for a connection holding `read_status`.

```
// server → client (text)
{"protocol_version": "v1", "areas": ["DE","FR"], "products": ["H","Q"],
 "public_trades": {"persist": "postgresql", "queryable": true},
 // base posture + own accounts, always present
 "operational": true, "throttling": {…}, "trading_enabled": true,
 "license_summary": {"status": {"kind": "active"}, "expires_at": "2027-01-01T00:00:00Z", "mode": "desk"},
 "accounts": [{"is_house": true, "position_limit": 50000, "effective_position_limit": 50000,
               "eur_limit_cents": 10000000, "eur_consumed_cents": 3500000, "eur_remaining_cents": 6500000,
               "gbp_limit_cents": 0, "gbp_consumed_cents": 0, "gbp_remaining_cents": 0}],
 // the block below is present only with `read_status`
 "cash_limits": {…}, "order_pos_limit": 50000, "cash_limit": {…},
 "license": {…}, "stranded_pending_count": 0, "stranded_pending_qty": 0,
 "claims_count": 0, "claims_qty": 0, "claims_held_count": 0, "claims_held_qty": 0,
 "m7_client_cert": {"status": {"kind": "valid"}, "not_after": "2027-03-01T12:00:00Z"}}
```

**The desk-money and full-licence keys are omitted, not null, without `read_status`.** They are the same fields the [`get_status`](#cmd-get_status) aggregate withholds from a caller lacking the permission, the withholding is inside the per-caller projection, not at a subscribe gate. A client must therefore treat each of them as optional and render from its own defaults when they are absent, the same handling it already needs for a field it did not ask for.

`public_trades.persist` is `"off"`, `"postgresql"`, or `"parquet"`, and `public_trades.queryable` is `true` only for `"postgresql"`, the one backend whose saved tape is returned by the [`audit/public_trades`](rest_api_v1.md#get-audit-public-trades) endpoints. A `"parquet"` tape is written to rotating files for offline tools (export-only; the audit query returns an empty page), and `"off"` persists nothing. The live `public_trades` subscription stream is unaffected by this setting.

Any handshake failure (a bad token, the 10 s timeout, or a first message that is not an auth frame) yields `{"msg_type": "auth_error", "error": "<reason>"}` followed by a close. The same API key, permissions, and license tier apply on every transport: WebSocket grants no more and no less than REST or gRPC.

Credentials stay **live** for the whole connection: permission and member-assignment changes apply to an open connection immediately, and deleting a user or rotating their API key closes that user's open connections, as does ending or expiring the session token a connection authenticated with. After rotating your own key, reconnect and re-authenticate with the new one.

#### Frame types

Server→client frames come in two styles:

| Style | Transport | Routed by | Carries |
| --- | --- | --- | --- |
| Stream frame | binary (zstd-compressed JSON) | `"stream"` | subscription snapshots, deltas, heartbeats |
| Response / one-shot | text (uncompressed JSON) | `"type"` / `"msg_type"` | command response envelopes, ConfigPayload, auth_error, watch_hub2hub frames |

**Why two styles:** stream frames are high-frequency and compress well, so they ride a compact binary channel; replies are low-frequency and must be trivial for any-language clients to parse and correlate, so they stay plain text. Decompress binary frames with zstd then parse JSON, routing on `"stream"`; parse text frames directly, routing on `"type"` (the request/response envelope, see below, and the `watch_hub2hub` subscription frames) or `"msg_type"` (the `auth_error` handshake failure).

#### <a id="envelope" name="envelope"></a>Request/response envelope

Every unary command carries a client-generated `req_id`; the server replies with exactly one correlated `response` text frame. `op` echoes the action so you can route without tracking `req_id` state if you prefer. `req_id` is technically optional (a command sent without one gets a response without one), but always sending it is strongly recommended.

Replies can arrive in a different order from their commands. A command that waits for the exchange (`new_order`, `modify_order`, `delete_order`, `cancel_all_orders`, `recall_trade` and a `toggle_trade_enabled` that disables trading) is answered when the exchange answers, and while it waits the connection keeps sending stream frames and answering your other commands. Two commands sent without waiting for the first reply may reach the exchange in either order. A client that needs one command to take effect before the next sends the next one after the first reply. Disabling trading is the exception: the switch is set before the server reads your next command, so a `new_order` sent right behind it is refused with `TRADING_DISABLED`.

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

#### <a id="reconnect" name="reconnect"></a>Reconnect and recovery

Keep the `client_order_id` from each `new_order` ack. After a disconnect: reconnect, re-auth, and resubscribe to `orders` and `trades`. The server sends a full snapshot on subscribe, each order carrying its `client_order_id`, so you can reconcile any in-flight orders against the authoritative state. A lagged subscriber is automatically re-snapshotted. For true idempotency across a disconnect that happens *before* the ack, supply your own `client_order_id` on `new_order` (it must be a valid UUID); re-sending a key the gateway still holds is rejected, so a retry cannot create a duplicate. See *Reusing a `client_order_id`* under [`new_order`](#cmd-new_order) for which keys are held and for how long.

<a id="permissions" name="permissions"></a>

## Permissions

Every operation is authorised by the permissions held by the API key that calls it. The same permissions apply on REST, gRPC and WebSocket: a key grants no more and no less on one transport than on another.

#### What each permission grants

| Permission | Grants |
| --- | --- |
| `create_order` | Submit new orders. |
| `modify_order` | Change the price or quantity of an open order, or activate and deactivate it. |
| `delete_order` | Cancel one open order, or cancel all open orders at once. |
| `recall_trade` | Ask the exchange to recall a trade this gateway placed, for a member the caller may act on. |
| `toggle_trading` | Set the trading kill switch: enable or disable all trading, and flatten the resting book when disabling. Acknowledge a `trade_report refused` fault to keep trading through it. |
| `set_position_limit` | Set the per-contract net-position limit. |
| `set_cash_limit` | Set the desk cash limit, and edit the TARGET2 holiday calendar that drives its settlement window. |
| `set_self_trade_policy` | Set the self-trade (cross-trade) prevention policy. |
| `manage_users` | Create, update and delete users and their API keys, set permissions, rotate keys, and set member assignments. |
| `manage_members` | Create, update and delete virtual sub-accounts (members). |
| `read_audit` | Read the compliance audit events and the public-trade history. Order and trade history need no permission: they are member-scoped. |
| `read_m7_errors` | Read the exchange-error log and the exchange-message log. |
| `read_logs` | Read the gateway's own diagnostic log. |
| `read_pnl` | Read firm-wide P&L, every member plus the house book. Without it a caller sees only the P&L of its assigned members. |
| `read_orders` | Read the firm-wide order book, every member plus untagged house orders. Without it a caller sees only its assigned members' orders. |
| `read_state` | Read the runtime-health snapshot: uptime, connectivity and latency telemetry. |
| `read_status` | Read the desk-wide money and full licence inside the trading-posture aggregate, plus the cash and limit component reads. |
| `read_metrics` | Scrape the Prometheus metrics exposition. It grants nothing else, and it is REST-only. |
| `export_reports` | Generate and download order, trade and audit-trail report exports (REST only). The audit-trail export also needs `read_audit`. |
| `restart_system` | Trigger a graceful restart of the gateway. |
| `restore_trade_history` | Restore the trade history the exchange still serves into the persistent store. |
| `bypass_member_check` | Act on any member without an explicit assignment, skip the per-member position-limit check, and see firm-wide orders and P&L. |
| `trade_global` | Submit orders on the global (house) account without a member. Without it a caller must always trade under a member. |

#### How a key receives permissions

A holder of `manage_users` sets a user's full permission set with `set_permissions`; passing an empty set revokes everything. The built-in `admin` account always holds every permission and its set cannot be changed. A permission change applies to an open session at once, with no reconnect.

#### What a missing permission looks like here

The command's response frame carries a `PermissionDenied` error, and the denial is recorded as a `permission_denied` audit event.

#### Operation to permission

This table is identical in the REST, gRPC and WebSocket references. "Base permission" is what a caller must hold to use the operation at all. "Scope-widening" is a permission that broadens the result or authorises a variant but is not required to call: a caller without it receives the caller-scoped view instead of a refusal.

| Operation | REST | gRPC | WebSocket | Base permission | Scope-widening |
| --- | --- | --- | --- | --- | --- |
| `create_order` | `POST /order` | `SubmitOrder` | `new_order` | `create_order` | `bypass_member_check`, `trade_global` |
| `modify_order` | `PUT /order` | `ModifyOrder` | `modify_order` | `modify_order` | none |
| `cancel_order` | `DELETE /order` | `CancelOrder` | `delete_order` | `delete_order` | none |
| `cancel_all_orders` | `DELETE /orders` | `CancelAllOrders` | `cancel_all_orders` | `delete_order` | none |
| `submit_basket` | `POST /basket` | `SubmitBasket` | `submit_basket` | `create_order` | `bypass_member_check`, `trade_global` |
| `cancel_basket` | `DELETE /basket` | `CancelBasket` | `cancel_basket` | `delete_order` | none |
| `recall_trade` | `POST /trade/recall` | `RecallTrade` | `recall_trade` | `recall_trade` | `bypass_member_check`, `trade_global` |
| `get_order` | `GET /order` | `GetOrder` | `get_order` | none (authenticated) | `read_orders` |
| `list_orders` | `GET /orders` | `ListOrders` | `list_orders` | none (authenticated) | `read_orders` |
| `get_area_contracts` | `GET /contract/{area_id}` | `ListContracts` | `list_contracts` | none (authenticated) | none |
| `get_contract` | `GET /contract/{area_id}/{contract_id}` | `GetContract` | `get_contract` | none (authenticated) | `read_orders` |
| `get_contract_by_delivery` | `GET /contract/{area_id}/by-delivery/{prod}/{dlvry_start}` | `GetContractByDelivery` | `get_contract_by_delivery` | none (authenticated) | `read_orders` |
| `get_hub2hub` | `GET /hub2hub` | `GetHub2Hub` | `hub2hub_query` | none (authenticated) | none |
| `get_state` | `GET /state` | `GetState` | `get_state` | `read_state` | none |
| `metrics` | `GET /metrics` | `none (REST-only)` | `none (REST-only)` | `read_metrics` | none |
| `get_status` | `GET /status` | `GetStatus` | `get_status` | none (authenticated) | `read_status` (desk money and licence) |
| `get_throttling` | `GET /throttling` | `GetThrottling` | `get_throttling` | none (authenticated) | none |
| `get_cash_limits` | `GET /cash_limits` | `GetCashLimits` | `get_cash_limits` | `read_status` | none |
| `get_cash_limit` | `GET /cash_limit` | `GetCashLimit` | `get_cash_limit` | `read_status` | none |
| `get_contract_limit` | `GET /contract_limit` | `GetContractLimit` | `get_contract_limit` | `read_status` | none |
| `get_slot_limit` | `GET /slot_limit` | `GetSlotLimit` | `get_slot_limit` | `read_status` | none |
| `get_slot_positions` | `GET /slot_positions` | `GetSlotPositions` | `get_slot_positions` | none (member-scoped) | `read_status` (House scope) |
| `get_trading_allowed` | `GET /trading_allowed` | `GetTradingAllowed` | `get_trading_allowed` | none (authenticated) | none |
| `get_system_info` | `GET /system_info` | `GetSystemInfo` | `get_system_info` | none (authenticated) | none |
| `get_area_table` | `GET /area_table` | `GetAreaTable` | `get_area_table` | none (authenticated) | none |
| `get_pnl` | `GET /pnl` | `GetPnl` | `get_pnl` | none (authenticated) | `read_pnl` |
| `get_self_trade_policy` | `GET /self_trade_policy` | `GetSelfTradePolicy` | `get_self_trade_policy` | none (authenticated) | none |
| `get_holidays` | `GET /holidays` | `GetHolidays` | `get_holidays` | none (authenticated) | none |
| `get_public_trades` | `GET /public_trades` | `ListPublicTrades` | `list_public_trades` | none (authenticated) | none |
| `toggle_trading` | `PUT /trading_allowed` | `SetTradingAllowed` | `toggle_trade_enabled` | `toggle_trading` | none |
| `ack_trade_ingest_fault` | `POST /trade_ingest_fault/ack` | `AckTradeIngestFault` | `ack_trade_ingest_fault` | `toggle_trading` | none |
| `set_contract_limit` | `PUT /contract_limit` | `SetContractLimit` | `set_order_pos_limit` | `set_position_limit` | none |
| `set_cash_limit` | `PUT /cash_limit` | `SetCashLimit` | `set_cash_limit` | `set_cash_limit` | none |
| `set_self_trade_policy` | `PUT /self_trade_policy` | `SetSelfTradePolicy` | `set_self_trade_policy` | `set_self_trade_policy` | none |
| `set_slot_limit` | `PUT /slot_limit` | `SetSlotLimit` | `set_slot_limit` | `set_position_limit` | none |
| `restart` | `POST /restart` | `Restart` | `restart` | `restart_system` | none |
| `restore_trade_history` | `POST /restore-trade-history` | `RestoreTradeHistory` | `restore_trade_history` | `restore_trade_history` | none |
| `put_holidays` | `PUT /holidays` | `SetHolidays` | `set_holidays` | `set_cash_limit` | none |
| `post_holiday` | `POST /holidays` | `AddHoliday` | `add_holiday` | `set_cash_limit` | none |
| `delete_holiday` | `DELETE /holidays` | `RemoveHoliday` | `remove_holiday` | `set_cash_limit` | none |
| `list_users` | `GET /users` | `ListUsers` | `get_users` | `manage_users` (desk) | none |
| `create_user` | `POST /users` | `CreateUser` | `create_user` | `manage_users` (desk) | none |
| `delete_user` | `DELETE /users/{id}` | `DeleteUser` | `delete_user` | `manage_users` (desk) | none |
| `set_permissions` | `PUT /users/{id}/permissions` | `SetPermissions` | `set_permissions` | `manage_users` (desk) | none |
| `get_user_members` | `GET /users/{user_id}/members` | `GetUserMembers` | `get_user_members` | `manage_users` (desk) | none |
| `set_user_members` | `PUT /users/{user_id}/members` | `SetUserMembers` | `set_user_members` | `manage_users` (desk) | none |
| `rotate_api_key` | `POST /users/{id}/rotate-api-key` | `RotateApiKey` | `rotate_api_key` | `manage_users` | none |
| `list_permissions` | `GET /permissions` | `ListPermissions` | `list_permissions` | `manage_users` | none |
| `list_members` | `GET /members` | `ListMembers` | `get_members` | `manage_members` (desk) | none |
| `create_member` | `POST /members` | `CreateMember` | `create_member` | `manage_members` (desk) | none |
| `patch_member` | `PATCH /members/{id}` | `PatchMember` | `patch_member` | `manage_members` (desk) | none |
| `delete_member` | `DELETE /members/{id}` | `DeleteMember` | `delete_member` | `manage_members` (desk) | none |
| `audit_orders` | `GET /audit/orders` | `QueryAuditOrders` | `audit_query (entity=orders)` | none (member-scoped) | `read_orders` |
| `audit_trades` | `GET /audit/trades` | `QueryAuditTrades` | `audit_query (entity=trades)` | none (member-scoped) | `read_orders` |
| `audit_public_trades` | `GET /audit/public_trades` | `QueryAuditPublicTrades` | `audit_query (entity=public_trades)` | `read_audit` | none |
| `audit_events` | `GET /audit/events` | `QueryAuditEvents` | `audit_query (entity=events)` | `read_audit` | `read_orders` |
| `audit_m7_errors` | `GET /audit/m7_errors` | `QueryM7Errors` | `audit_query (entity=m7_errors)` | `read_m7_errors` | none |
| `audit_exchange_messages` | `GET /audit/exchange_messages` | `ListExchangeMessages` | `list_exchange_messages` | `read_m7_errors` | none |
| `list_system_log` | `GET /system/logs` | `ListSystemLog` | `list_system_log` | `read_logs` | none |
| `export_orders` | `POST /audit/export/orders` | `none (REST-only)` | `none (REST-only)` | `export_reports` | `read_orders` |
| `export_trades` | `POST /audit/export/trades` | `none (REST-only)` | `none (REST-only)` | `export_reports` | `read_orders` |
| `export_audit_events` | `POST /audit/export/events` | `none (REST-only)` | `none (REST-only)` | `export_reports` and `read_audit` | `read_orders` |
| `download_report` | `GET /audit/export/{token}` | `none (REST-only)` | `none (REST-only)` | `export_reports` | none |
| `get_me` | `GET /users/me` | `GetMe` | `get_me` | none (authenticated) | none |
| `get_my_members` | `GET /users/me/members` | `GetMyMembers` | `get_my_members` | none (authenticated) | none |
| `create_session` | `POST /sessions` | `none (REST-only)` | `none (REST-only)` | none (authenticated, API key only) | none |
| `revoke_session` | `DELETE /sessions/current` | `none (REST-only)` | `none (REST-only)` | none (authenticated, session token only) | none |

Notes: "(desk)" marks an operation additionally behind the desk-management licence gate; `rotate_api_key` and `list_permissions` use `manage_users` but are not desk-gated. `metrics` is REST-only by representation. `create_session` and `revoke_session` are REST-only by design: they mint and end the session the trading terminal signs in with, and every transport accepts the resulting token, so a gRPC or WebSocket client loses nothing. `export_orders`, `export_trades`, `export_audit_events` and `download_report` are the report file exports, REST-only by design: the rows in a file are the ones the audit reads page through on every transport. On WebSocket the five paged audit reads share the one `audit_query` command, keyed by `entity`.

<a id="conventions" name="conventions"></a>

## Conventions

Integer fixed-point on the wire, no floating-point, identical to REST and gRPC. There is no WebSocket-specific encoding: the field-level semantics of every result body match the REST response of the same name.

#### <a id="units" name="units"></a>Units and sentinels

| Field | Type | Unit | Notes |
| --- | --- | --- | --- |
| `price` | `i64` | cents (CCY/MWh × 100) | `5000` = 50.00 EUR/MWh. May be negative on power markets. |
| `quantity` / `display_qty` / position limit | `i64` | sub-MW (MW × 1000) | `1000` = 1.0 MW. |
| cash amounts (`*_cents`, `cap_cents`) | `i64` | cents (currency × 100) | Per currency pool; EUR and GBP are never summed. |
| RFC 3339 timestamps | `string` | none | e.g. `"2026-04-16T22:00:00Z"`. |
| `*_ms` timestamps | `i64` | Unix epoch ms (UTC) | Milliseconds since the epoch. |

#### Timestamps, IDs and enums

Orders are keyed by `client_order_id`, a UUID you supply or the gateway generates, never the numeric M7 `order_id`; the same handle survives M7's delete-plus-recreate on modify. Timestamps are RFC 3339 strings, and `*_ms` fields are Unix epoch milliseconds. Enum values are lower snake_case, except `side`, which is `"BUY"` or `"SELL"`.

#### Pagination

The audit and report reads are cursor-paged. Pass `limit` (default 50, capped at 200; an explicit `limit=0` is rejected) and read `next_cursor` from the result; a `null` `next_cursor` is the last page. Feed it back as `cursor` on the next call. There is no total count: iterate by following `next_cursor` until it is `null`. A date window filters on the delivery basis and orders the page accordingly, so a just-executed row can fall outside page one of a windowed query. An empty string in `filters` is the same as leaving the field out: `"area": ""` filters nothing and `"date_from": ""` sets no bound, as on REST and gRPC.

#### <a id="execution" name="execution"></a>Execution semantics

`new_order` and `modify_order` are request/response with an immediate ack/reject. Synchronous failures (permission, validation, not-found, modify-in-progress) return an error envelope at once. `new_order` then awaits the M7 round-trip and resolves with `{client_order_id, state, reason}`, identical to REST/gRPC. A *rejected* order is a **successful** response carrying `state: "REJECTED"` (only a gateway error becomes an error envelope), matching gRPC `SubmitOrder`. The receive loop is never blocked while awaiting the exchange, so other commands and stream frames keep flowing. The full lifecycle afterward (fills, cancels, state changes) arrives on the `orders` and `trades` subscriptions.

#### Error frame shape

A failed command returns `ok: false` with an `error` object carrying the canonical `code`, its `http_status` and `grpc_status` equivalents, and a human `message`. The same failure then reads identically on any transport. The full code table is the [Error reference](#errors).

<a id="ops-orders" name="ops-orders"></a>

## Orders

### <a id="cmd-new_order" name="cmd-new_order"></a>`Command` `action "new_order"`

Submit a new order. Identify the contract by `contract_id`, or omit it and supply `product` + `delivery_start`, or create a user-defined block with `product` + `delivery_start` + `delivery_end`. Mirrors REST `POST /order` and gRPC `SubmitOrder`.

**Required permission:** `create_order`. `bypass_member_check` and `trade_global` widen where the order may be booked. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `side` | `string` | none | Yes | `"BUY"` or `"SELL"`. |
| `price` | `i64` | cents (CCY/MWh × 100) | Yes | May be negative. |
| `quantity` | `u32` | sub-MW (MW × 1000) | Yes | Must be greater than zero. |
| `delivery_area_id` | `string` | none | Yes | EIC delivery area code, exactly 16 characters (e.g. `"10YNL----------L"`). Any other length is refused with `BAD_REQUEST` before anything is sent. Only the length is checked: whether a 16-character code names an area you trade is the exchange’s call. |
| `contract_id` | `i64` | none | One of | Direct contract id, or omit and supply `product` + `delivery_start`. |
| `product` + `delivery_start` | `string` | RFC 3339 | One of | Resolve the contract by product and delivery start against `delivery_area_id`. Any RFC 3339 instant: `2026-10-25T00:00:00Z`, `2026-10-25T00:00:00.000Z` and `2026-10-25T02:00:00+02:00` name the same contract. The doubled hour of a clock change is two instants: on 2026-10-25, 02:00 CEST is `00:00Z` (hour `02A`) and 02:00 CET is `01:00Z` (hour `02B`). |
| `delivery_end` | `string` | RFC 3339 | No | Creates a user-defined block over `[delivery_start, delivery_end)`. Only with `order_type: "block"`, `product` and `delivery_start`, and no `contract_id`; anywhere else it is `BLOCK_DELIVERY_END_INVALID`. The rules are those of REST [POST /order](rest_api_v1.md#post-order), *User-defined blocks*: the window is covered end to end by at least two consecutive contracts of the product in the area and no more than its `blockMaximumHours`, and the order takes `aon` or `fok`. Until the exchange names the block’s contract the pending order carries a gateway placeholder `contract_id` (250 and above). |
| `order_type` | `string` | none | No | Default `"regular"`. |
| `exe_restriction` | `string` | none | No | `"non"` (default), `"fok"`, `"ioc"`, `"aon"`. `"fok"`/`"ioc"` require `validity_res` = `"non"`. |
| `validity_res` | `string` | none | No | `"gfs"` (default), `"gtd"`, `"non"`. |
| `entry_state` | `string` | none | No | Default `"active"`; `"hibernated"` submits the order inactive. Refused on a `pre_arranged` order. |
| `display_qty` | `u32` | sub-MW (MW × 1000) | No | Required for iceberg orders, rejected on any other order type. Must be less than `quantity`. |
| `validity_date` | `string` | RFC 3339 | Cond | An RFC 3339 instant, e.g. `2026-10-25T01:30:00Z`, in the form the exchange’s schema takes: an uppercase `T` and `Z`, seconds up to 59, and an offset within ±14:00, which is forwarded unchanged; a space for the `T`, a lowercase `t` or `z` and a leap second are refused; the exchange works in UTC, so send `Z`; the exchange GUI’s `02:30A` form is refused. Required when `validity_res: "gtd"`. |
| `pre_arranged_acct` | `string` | none | Cond | Pre-arranged counterparty account. Required when `order_type: "pre_arranged"`. 1-32 printable ASCII characters without spaces, quotes, angle brackets or `&`; anything else is refused. |
| `v_member_short_id` | `string` | none | No | Virtual member to book the order to. |
| `client_order_id` | `string` | none | No | Client-supplied idempotency key (valid UUID); generated when omitted. Reusing one the gateway still holds is rejected (`BAD_REQUEST`); see *Reusing a `client_order_id`* below. |
| `ack_only` | `bool` | none | No | Default `false` waits for the exchange's outcome. `true` returns as soon as the exchange acknowledges receipt (`state: "PENDING"`). A non-bool value is rejected as a malformed command. See *Receipt vs. outcome* below. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `client_order_id` | `string` | none | always | The order's stable handle, the one you supplied or the one the gateway generated. |
| `state` | `string` | none | always | One of `PENDING`, `ACTIVE`, `INACTIVE`, `HIBERNATED`, `REJECTED`. |
| `reason` | `string\|null` | none | always | The exchange's words when `state` is `REJECTED`; `null` otherwise. |
| `err_code` | `i64\|null` | none | always | The exchange's numeric error code when `state` is `REJECTED` and the refusal carried one code (e.g. `1051`); `null` otherwise. A refusal that names no order is answered at once too: the exchange answers the request the order was sent under. |

#### Errors

| Error code | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `create_order`. |
| `BAD_REQUEST` | An unknown or output-only enum value, an empty `delivery_area_id` (`delivery_area_id is required`) or one that is not 16 characters (`delivery_area_id must be a 16-character EIC code`), an iceberg without a valid `display_qty`, `fok`/`ioc` without `validity_res: "non"`, a `validity_date` not in the form the exchange’s schema takes (`validity_date must be an RFC 3339 timestamp written as 2026-09-22T16:00:00Z or 2026-09-22T18:00:00+02:00`), a `pre_arranged_acct` outside the printable-ASCII class (or with spaces, quotes, angle brackets or `&`), a `pre_arranged` order entered hibernated (`a pre-arranged order cannot be entered hibernated`), neither `contract_id` nor `product`+`delivery_start`, a `delivery_start` that is not an RFC 3339 timestamp (`delivery_start must be an RFC 3339 timestamp, e.g. 2026-10-25T00:00:00Z`), a price or size off the product grid, or a `client_order_id` already in use. |
| `NOT_FOUND` | The contract named by `product` and `delivery_start` does not exist. |
| `TRADING_DISABLED` · `POSITION_LIMIT_EXCEEDED` · `SLOT_POSITION_LIMIT_EXCEEDED` · `SLOT_WINDOW_UNKNOWN` · `CASH_LIMIT_EXCEEDED` · `SELF_CROSS_BLOCKED` · `LOAD_THROTTLED` | The pre-trade gate refused the order: trading is disabled, a position or cash-pool bound would be exceeded, a self-cross is blocked, or the exchange load guard refuses. |
| `CONTRACT_IN_DELIVERY` | The contract has reached its delivery start on the gateway’s clock. Refused before anything reaches M7, whatever state the exchange still lists the contract in; on the production markets the exchange’s published gate-closure parameters close trading at or before the delivery start, so there this refuses nothing the exchange would still take. The refusal does not depend on the exchange refusing such an order, and applies as well in a test environment that still accepts one after the delivery start. Not transient. Orders already resting on it stay listed by [`list_orders`](#cmd-list_orders) and are cancelled with [`delete_order`](#cmd-delete_order). |
| `MEMBER_AREA_NOT_ALLOWED` | The order is tagged with a member whose [delivery areas](#cmd-get_members) do not include `delivery_area_id`, for every caller, `bypass_member_check` included; a block and a pre-arranged order alike. Refused before anything reaches M7. 422 / `FailedPrecondition`. |
| `BLOCK_DELIVERY_END_INVALID` | `delivery_end` without `order_type: "block"`, with a `contract_id`, or without `product` and `delivery_start`. 400 / `InvalidArgument`. |
| `BLOCK_RESTRICTION_NON` | A block order, created or joined, with `exe_restriction: "non"`; a block takes `aon` or `fok`. 400 / `InvalidArgument`. |
| `BLOCK_WINDOW_TOO_SHORT` | The block window covers fewer than two contracts of its product. 400 / `InvalidArgument`. |
| `BLOCK_SWEEP_UNSUPPORTED` | A block order with `exe_restriction: "ioc"`: a market sweep, not supported. 422 / `FailedPrecondition`. |
| `BLOCK_NOT_SUPPORTED` | The product’s settings take no user-defined blocks. 422 / `FailedPrecondition`. |
| `BLOCK_WINDOW_NOT_CONTIGUOUS` | The window is not covered end to end by consecutive contracts of the product in the area’s catalogue. 422 / `FailedPrecondition`. |
| `BLOCK_WINDOW_TOO_LONG` | The window exceeds the product’s `blockMaximumHours`. 422 / `FailedPrecondition`. |
| `TIMEOUT` | The exchange did not acknowledge in time; the outcome is unknown, not failed. |
| `NOT_PROCESSED` | The exchange handed the request back undelivered; it definitely was not processed and may be resubmitted with the same `client_order_id`. |

The transport-wide codes (`UNAUTHENTICATED`, `RATE_LIMITED`, `NOT_OPERATIONAL`, `INTERNAL`) may also occur; see the [Error reference](#errors).

#### Example

```json
{"action": "new_order", "req_id": "…", "side": "BUY", "price": 5000,
 "quantity": 1000, "delivery_area_id": "10YNL----------L", "contract_id": 12345}
// or identify the contract by delivery window instead of contract_id:
{"action": "new_order", "req_id": "…", "side": "BUY", "price": 5000,
 "quantity": 1000, "delivery_area_id": "10YNL----------L",
 "product": "H", "delivery_start": "2026-06-16T06:00:00Z"}
// → result: {"client_order_id": "…", "state": "ACTIVE", "reason": null}
```

**Contract identification.** Supply `contract_id`, or omit it and supply both `product` and `delivery_start` (resolved against `delivery_area_id`), identical to REST `POST /order` and gRPC `SubmitOrder`. Supplying neither is a `BAD_REQUEST`; a delivery window that matches no live contract is `NOT_FOUND`.

A *rejected* order is a **successful** response carrying `state: "REJECTED"` and a `reason`; only a gateway error becomes an error envelope. See [Execution semantics](#execution).

**Receipt vs. outcome (`ack_only`).** By default a new order waits for the exchange's outcome: the confirming execution report (*confirmed*, a settled `state`) or the exchange's refusal (*rejected*, `state: "REJECTED"`). Setting `ack_only: true` returns as soon as the exchange acknowledges receipt (*acknowledged*, `state: "PENDING"`, received, outcome not yet known); the same `PENDING` is returned when a waited call's outcome does not arrive inside the order outcome timeout. An `ack_only` caller manages the order lifecycle itself and follows the [`orders`](#stream-orders) stream for the resulting state or a later refusal. Identical on REST `POST /order` and gRPC `SubmitOrder`.

**Product parameters and gate closure.** Price and size are measured against the parameters the exchange publishes for the contract’s product, the minimum price increment, the price bounds, the quantity increment, the quantity bounds and the minimum iceberg peak, and against the contract’s own trading state in the delivery area, before anything is sent. An order that breaks one is refused with `BAD_REQUEST` naming the bound (`"price must be a multiple of the product tick size of …"`, `"quantity is above the product maximum of … MW"`, `"the contract’s trading session has closed in this delivery area"` and the rest), rather than costing a round trip and returning as an exchange rejection that still counts a full order-management transaction. The bounds are the exchange’s own, read off its product reference data rather than transcribed, so a market’s tick, increment and closing rule are always the current ones. Nothing is enforced that the exchange has not published: a contract or a product no report has named yet is left to the exchange to judge, so a late report never costs a legitimate order. Gate closure is read from the contract’s published trading-phase end, which is where a market’s “60 minutes before delivery in XBID, 30 nationally, 5 in a local TSO area” already lives, with a two-second tolerance for clock differences, so the last seconds before closure are never refused early. The same check applies your member’s own order limit, the largest single-order quantity the exchange sets for your member on the product: an order above it, an iceberg measured on its full size, is refused with `"quantity is above the member order limit of … MW"`, after the product bounds. A product with no member limit reported is left to the exchange. Identical on REST `POST /order` and gRPC `SubmitOrder`.

**Request expiry.** Every request that adds exposure, a new order, an amendment and an activation, is sent to the exchange with an expiry of `system.order_request_expiration_ms` (10 seconds by default). The exchange drops such a request when it has not taken it off its queue within the expiry, and drops one it took off the queue but had not processed within the expiry again, so a request is executed within twice the expiry of reaching the exchange, or never: a request the exchange cannot process in time is dropped, not executed late. A cancel (`delete_order`), cancel-all and a deactivation carry no expiry of their own and keep the exchange’s 45-second default: they only remove exposure, and a dropped cancel would leave an order live exactly when the exchange is backlogged.

**After a `TIMEOUT`.** The order keeps counting against your position and cash limits until the exchange answers it with its execution report or its refusal. Without an answer it is released at its **expiry bound**, measured from when the gateway sent it: twice the request expiry plus 5 seconds (25 seconds by default), or, for an order in a delivery area coupled to XBID, twice the expiry plus 25 seconds (45 seconds by default), because the exchange may wait another 20 seconds for XBID’s answer. `system.pending_order_reap_age_ms` can only lengthen that wait. The release needs one more certainty, that no answer can have been missed: the exchange’s order feed has been continuously connected since the order was sent. An acknowledgement of receipt changes nothing either way: the exchange may omit it for an order it processed, and may lose an order it acknowledged. That release is recorded on [`messages`](#stream-messages) stream and in the audit log as an `order_rejected` event from the `order_reaper` component.

**If that certainty is not available**, because the order feed dropped or gapped since the order was sent, the order is **held, not released**. It goes on consuming both limits and is reported once on the [`messages`](#stream-messages) stream, because the gateway cannot rule out that it is resting at the exchange. It is settled by the first order snapshot taken after its bound, which arrives when the gateway next resubscribes to the exchange’s order feed: if the snapshot carries it, it becomes a normal live order; if not, it is released then, because it can no longer land. A snapshot taken before the bound settles only the orders it carries. An order in an XBID-coupled area is held until its own execution report or refusal, or a restart, when the exchange warned that XBID has not answered it (error 1142), or when the gateway’s connection to the exchange’s message feed reset since it was sent, so such a warning may have been lost: the exchange documents no bound on XBID’s answer. Any held order is released at the latest about an hour after its contract’s delivery ends, when no market still trades the contract; the release is reported on the [`messages`](#stream-messages) stream, and an exchange report that still arrives for it counts the order again. The number and size of held orders are on the status aggregate (`stranded_pending_count`, `stranded_pending_qty`). The `restart` command restarts the process, which releases every held order and rebuilds the order book from the exchange’s own snapshot.

**Reusing a `client_order_id`.** A key is refused for as long as the gateway holds a record of the order it named, whatever that order’s state. A key held by a pending order (including one a `TIMEOUT` left counting), by a resting, hibernated, filled or deleted order, or by an order the exchange rejected is refused with `BAD_REQUEST` (`"client_order_id '…' is already in use"`). A key whose submission was written off after a `TIMEOUT`, released as described above, or released by a snapshot that did not carry a held order, is **retired** and refused with `BAD_REQUEST` (`"client_order_id '…' was reclaimed after no exchange acknowledgement; use a new id"`): the written-off order may still be resting at the exchange, and a late report carrying that id must not attach to a different order. If such a report does arrive, the order is confirmed under its own id, its exposure counts again, the event is recorded on the [`messages`](#stream-messages) stream, and from then on the key is `already in use`. Retry a timed-out submission with a **new** id. Two keys are free at once: one whose request the gateway refused before sending it to the exchange, and one whose only record is a `NOT_PROCESSED` rejection, which the resubmission replaces.

**How long a key is held.** The record lives in the gateway’s memory, not in the database, so a held key becomes free again when the record goes: when the order has finished and its contract has been swept from the gateway, about an hour after its delivery end (an order still live at the exchange then keeps its record until it finishes, and goes on the next sweep after that), or when the gateway resubscribes to the exchange’s order feed (a restart does too), because the records are then rebuilt from the exchange’s snapshot, which carries only the orders still on the market, the keys of filled and deleted orders are free from that point. An order the exchange rejected was never on its book, so the snapshot does not drop it: its key stays held, and the lookup still answers it `REJECTED` with the exchange’s reason, until the sweep, or until a restart for an order on a contract the gateway never listed, such as a refused new block order, which the sweep does not reach. A pending order’s key and a retired key survive a resubscription and are dropped by a restart; a retired key also survives the sweep, and the 10,000 most recent are remembered. The refusal guards against two orders under one key; it is not a history of every key ever used, so do not reuse a key on purpose except after `NOT_PROCESSED`.

### <a id="cmd-modify_order" name="cmd-modify_order"></a>`Command` `action "modify_order"`

Amend price, quantity, or validity of an existing order, or activate/deactivate it. Mirrors REST `PUT /order` and gRPC `ModifyOrder`.

**Required permission:** `modify_order`, plus the right to act on the order's member (assigned, or `bypass_member_check`; a house order needs `trade_global`). (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `client_order_id` | `string` | none | Yes | The order's stable handle. |
| `modify_action` | `string` | none | No | `"modify"` (default), `"activate"`, `"deactivate"`. |
| `price` | `i64` | cents (CCY/MWh × 100) | When modifying | Required when `modify_action` is `"modify"`. |
| `quantity` | `u32` | sub-MW (MW × 1000) | When modifying | Required when `modify_action` is `"modify"`, and must be greater than zero. |
| `display_qty` | `u32` | sub-MW (MW × 1000) | No | For iceberg orders. Must be less than the new quantity. |
| `validity_res` / `validity_date` | `string` | RFC 3339 | No | New validity restriction / date. The date is an RFC 3339 instant, e.g. `2026-10-25T01:30:00Z`, in the form the exchange’s schema takes: an uppercase `T` and `Z`, seconds up to 59, and an offset within ±14:00, which is forwarded unchanged; a space for the `T`, a lowercase `t` or `z` and a leap second are refused; the exchange works in UTC, so send `Z`; the exchange GUI’s `02:30A` form is refused. Required when `validity_res` is `"gtd"`. |
| `v_member_short_id` | `string` | none | No | May only restate the order's own member; a different one returns `NOT_FOUND`. Omit it and the order keeps the member it has. |
| `ack_only` | `bool` | none | No | Default `false` waits for the exchange's outcome. `true` returns as soon as the exchange acknowledges receipt (`status: "acknowledged"`). A non-bool value is rejected as a malformed command. See *Receipt vs. outcome* below. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `status` | `string` | none | always | `"modified"` when the exchange's execution report confirmed the amendment, or `"acknowledged"` when only the receipt landed (`ack_only`, or the outcome window lapsed). |

#### Errors

| Error code | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `modify_order`. |
| `BAD_REQUEST` | `modify_action: "modify"` without a price or quantity, a quantity not greater than zero, or a `validity_date` not in the form the exchange’s schema takes (`validity_date must be an RFC 3339 timestamp written as 2026-09-22T16:00:00Z or 2026-09-22T18:00:00+02:00`). |
| `NOT_FOUND` | No open order with that `client_order_id` in the caller scope, or `v_member_short_id` names a different member. |
| `CONFLICT` | A modify is already in progress, or the exchange refused the amendment. |
| `ORDER_CHANGED` | The order's revision moved under the command; nothing was applied and the same command may be retried. |
| `ORDER_PENDING` | The order was sent and the exchange has not yet acknowledged it, so there is no exchange order to modify; nothing was sent. Retry once it is acknowledged, or wait for it on the [`orders`](#stream-orders) stream. A caller who may not act on the order’s member gets `NOT_FOUND` instead, as for an unknown order. |
| `TRADING_DISABLED` · `POSITION_LIMIT_EXCEEDED` · `SLOT_POSITION_LIMIT_EXCEEDED` · `SLOT_WINDOW_UNKNOWN` · `CASH_LIMIT_EXCEEDED` · `SELF_CROSS_BLOCKED` · `LOAD_THROTTLED` | The pre-trade gate refused the new price or size. |
| `CONTRACT_IN_DELIVERY` | The contract has reached its delivery start on the gateway’s clock and the command adds exposure: `activate` (a re-entry at the exchange), or `modify` with a larger `quantity` or any new `price` (a delete and re-entry at M7). A shrink at the same price is not refused with this code, though like any `modify` it is refused `BAD_REQUEST` (for example `the contract has expired`) once the exchange shows the contract closed. `deactivate` and a cancel are refused by neither. |
| `MEMBER_AREA_NOT_ALLOWED` | The order belongs to a member whose [delivery areas](#cmd-get_members) no longer include the order’s area. Refused on every `modify_action`, for every caller. 422 / `FailedPrecondition`. |
| `TIMEOUT` | The exchange did not acknowledge in time; the outcome is unknown. |
| `NOT_PROCESSED` | The exchange handed the request back undelivered; it definitely was not applied. |

The transport-wide codes (`UNAUTHENTICATED`, `RATE_LIMITED`, `NOT_OPERATIONAL`, `INTERNAL`) may also occur; see the [Error reference](#errors).

#### Example

```json
{"action": "modify_order", "req_id": "…", "client_order_id": "…",
 "modify_action": "modify", "price": 5500, "quantity": 500}
// modify_action "activate" / "deactivate" carry no price/quantity
// → result: {"status": "modified"}      (outcome confirmed by the exchange's report)
// → result: {"status": "acknowledged"}  (received; ack_only, or the outcome window lapsed)
```

**Receipt vs. outcome (`ack_only`).** By default a modify waits for the exchange's outcome: the confirming execution report (*confirmed* → `{"status":"modified"}`) or the exchange's refusal (*rejected* → a `CONFLICT` error frame carrying M7's words, or `ORDER_CHANGED` when the order's revision moved under the command). A waited call is confirmed only on its own command's report: when two commands on the order are at the exchange at once and one report could be either's (a modify retried at the same revision), neither is confirmed on it. The one the exchange refuses is answered with that refusal, the other is then confirmed, and with no refusal on either command's correlation id inside the order outcome timeout both are answered *acknowledged*. Setting `ack_only: true` returns as soon as the exchange acknowledges receipt (*acknowledged* → `{"status":"acknowledged"}`, received, outcome not yet known); the same *acknowledged* answer is returned when a waited call's outcome does not arrive inside the order outcome timeout. An `ack_only` caller manages the order lifecycle itself and follows the [`orders`](#stream-orders) stream for the resulting state or a later refusal. Identical on REST `PUT /order` (200/202) and gRPC `ModifyOrder`. A modify on an order the exchange has not yet acknowledged, which a new order answered *acknowledged* may still be, is refused `ORDER_PENDING`: retry once the order is acknowledged, or wait for it on the [`orders`](#stream-orders) stream.

**Expiry and held headroom.** An amendment and an activation carry the request expiry described under `new_order`, and the exposure they add is released the same way as a pending order’s: at any time on the exchange’s answer (the command’s own execution report or refusal, a later revision of the order, or the order leaving the book), and without one only at the command’s expiry bound with the order feed continuously connected; otherwise it is held and reported once. An XBID timeout warning (error 1142) is not a refusal: the added exposure stays held until the command’s own report or a restart, and a caller still waiting is answered `{"status":"acknowledged"}`, never a refusal. The number and size of these claims, and of the held ones, are on the status aggregate (`claims_count`, `claims_qty`, `claims_held_count`, `claims_held_qty`).

**An order keeps its execution restriction.** The exchange re-creates an order on every amendment and reads an amendment that names no restriction as `non`, which it refuses on a block. So every action, a re-price, a resize, an activation and a hibernation, restates the order’s own type and execution restriction as the exchange last reported it, or all-or-none for a block whose report names none: a block goes out as a block with its `aon` or `fok`, and an order without a restriction is sent exactly as before. A modify cannot change the restriction; to change it, cancel and re-enter.

**One modify at a time, and the conflict clears itself** (gates `delete_order` too). While a modify is in flight, a second `modify_order` on the same `client_order_id` returns `CONFLICT` "modify already in progress" and a `delete_order` returns `CONFLICT` "modify in progress, retry after confirmation": the exchange replaces an order on modify, so a second command dispatched in that window would target an order id that no longer exists. The lock is released by the exchange's execution report, and it expires on its own after the receipt wait and the outcome wait together (5s by default, floored at 1s) after it was taken, a moment before the command reaches the exchange, so it lapses a moment before the modify's own waits do, by design. An execution report that never arrives therefore costs one such window, not the order, retry after it and the next modify takes the lock.

**A modify is a full pre-trade entry.** The exchange re-creates an order on every amendment, so `modify` and `activate` both run the whole gate, position limits (House and member), slot position limits, cash limits, and self-trade prevention, with the same rejections as [`new_order`](#cmd-new_order), and can be refused. For a live order the gate measures the *change*: it is checked on the price and quantity the order will carry, against sums that already contain the order being amended, so a reprice or resize that lowers exposure always passes. The exposure an admitted amendment adds, a larger size or a costlier price, and the whole returning size of an activation, count against your limits from the moment it is sent until the exchange's answer settles it, so two amendments sent at once cannot both spend the same room. An amendment that lowers exposure frees nothing until the exchange confirms it. Self-trade prevention is checked at the new price, and an order is never treated as crossing itself. It also sees where your other orders are *going*: an amendment to an order *on the book*, already sent to the exchange but not yet confirmed, is measured at both the price it rests at and the price it is moving to, so two amendments in flight at once cannot cross each other, and neither can slip through on a price the other has not committed to yet. That second reading is dropped as soon as the exchange settles the amendment, or after the same window as the modify lock if no answer arrives. Only orders that can actually fill are counted, and the check never refuses an amendment that can only shrink a cross: an amendment that takes no more size and does not move the price toward the other side is admitted even when the order is already crossing, so a desk is never trapped in a self-cross it is reducing. A hibernated order holds no exposure, the exchange releases its cash allocation and Voltnir excludes it from both sums, so it is off the book, is not a self-cross counterparty, and `activate` is gated for the order's whole returning size (and is visible to other orders from the moment the activation is sent), while a `modify` on an order that is already hibernated changes no live exposure, is not measured against the limits, is not made a self-cross counterparty by the amendment either, and is checked when it is activated instead. `deactivate` only removes exposure: it is never refused on a limit, and, like [`delete_order`](#cmd-delete_order), it is not gated on the gateway being operational either, so the way out of the market stays open through an outage. It still awaits the exchange's receipt, so it never reports a hibernation the exchange did not take. The product’s own bounds apply too: a `modify` restates a price and a size, so both face the product’s tick, increment, price and quantity bounds exactly as a [`new_order`](#cmd-new_order) does, including on a hibernated order, because the amendment itself is what the exchange would refuse, and both `modify` and `activate` are refused on a contract the exchange has closed in that delivery area. Your member’s own order limit applies to a `modify` the same way; an `activate` brings back the size the exchange already accepted and is measured against neither.

**An order's member is fixed for its life.** The exchange re-creates an order on every amendment, so the member tag the command publishes is what the new revision comes back on. Every action does it, a re-price, an activation and a hibernation all re-send the order's own text, because the exchange re-creates an order on an amendment and does not define what an omitted text field leaves behind. The text an amendment sends is never poorer than the one the order already holds: the delivery duration, delivery start and product it was entered with ride along even when the contract is no longer in the platform's own book, so a quarter-hour leg cannot come back looking like an hour. That tag is always the order's existing one, never a value in the request: naming a different member, or naming any member on an untagged house order, is refused with the `NOT_FOUND` an out-of-scope order gets, so the command is not a way to learn which member an order belongs to. To move exposure between members, cancel and re-enter.

### <a id="cmd-delete_order" name="cmd-delete_order"></a>`Command` `action "delete_order"`

Cancel one order by `client_order_id`. Mirrors REST `DELETE /order` and gRPC `CancelOrder`. Not gated by the kill-switch; cancels only reduce exposure, so they work even when trading is disabled.

**Required permission:** `delete_order`, plus the right to act on the order's member (assigned, or `bypass_member_check`; a house order needs `trade_global`). (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `client_order_id` | `string` | none | Yes | The order's stable handle. |
| `ack_only` | `bool` | none | No | Default `false` waits for the exchange's outcome. `true` returns as soon as the exchange acknowledges receipt (`status: "acknowledged"`). A non-bool value is rejected as a malformed command. See *Receipt vs. outcome* below. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `status` | `string` | none | always | `"cancelled"` when the deletion's execution report confirmed it, or `"acknowledged"` when only the receipt landed (`ack_only`, or the outcome window lapsed). |

#### Errors

| Error code | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `delete_order`. |
| `NOT_FOUND` | No open order with that `client_order_id` in the caller scope. |
| `CONFLICT` | A modify is in progress on the order, or the exchange refused the cancel (e.g. the order was concurrently filled or deleted). |
| `ORDER_CHANGED` | The order's revision moved under the cancel; it may already be gone. Retry. |
| `ORDER_PENDING` | The order was sent and the exchange has not yet acknowledged it, so there is no exchange order to cancel; nothing was sent, and the order may rest once it is acknowledged. Retry the cancel then, or wait for the order on the [`orders`](#stream-orders) stream. A caller who may not act on the order’s member gets `NOT_FOUND` instead, as for an unknown order. |
| `MEMBER_AREA_NOT_ALLOWED` | The order belongs to a member whose [delivery areas](#cmd-get_members) no longer include the order’s area. Refused for every caller; nothing was sent. `cancel_all_orders` skips such an order. 422 / `FailedPrecondition`. |
| `TIMEOUT` | The exchange did not acknowledge in time; the outcome is unknown. |
| `NOT_PROCESSED` | The exchange handed the cancel back undelivered; it definitely was not applied. |

The transport-wide codes (`UNAUTHENTICATED`, `NOT_OPERATIONAL`, `INTERNAL`) may also occur; see the [Error reference](#errors). A cancel is never refused with `RATE_LIMITED`.

#### Example

```json
{"action": "delete_order", "req_id": "…", "client_order_id": "…"}
// → result: {"status": "cancelled"}     (outcome confirmed by the deletion's report)
// → result: {"status": "acknowledged"}  (received; ack_only, or the outcome window lapsed)
```

**Receipt vs. outcome (`ack_only`).** By default a cancel waits for the exchange's outcome: the deletion's execution report (*confirmed* → `{"status":"cancelled"}`) or the exchange's refusal (*rejected* → a `CONFLICT` error frame carrying M7's words, or `ORDER_CHANGED` when the order's revision moved under the command). A waited call is confirmed only on its own command's report: when two cancels of the order are at the exchange at once, the deletion's report could be either's, so neither is confirmed on it. The exchange deletes the order for one and refuses the other (M7 error 2014, order not found); the losing cancel is answered with that refusal, the other is then confirmed, and with no refusal on either command's correlation id inside the order outcome timeout both are answered *acknowledged*. Setting `ack_only: true` returns as soon as the exchange acknowledges receipt (*acknowledged* → `{"status":"acknowledged"}`, received, outcome not yet known); the same *acknowledged* answer is returned when a waited call's outcome does not arrive inside the order outcome timeout. An `ack_only` caller manages the order lifecycle itself and follows the [`orders`](#stream-orders) stream for the resulting state or a later refusal. Identical on REST `DELETE /order` (200/202) and gRPC `CancelOrder`. A cancel of an order the exchange has not yet acknowledged, which a new order answered *acknowledged* may still be, is refused `ORDER_PENDING`: retry once the order is acknowledged, or wait for it on the [`orders`](#stream-orders) stream. A cancel carries no request expiry: it keeps the exchange’s 45-second default, so a cancel queued behind a backlog is still executed rather than dropped.

**Acknowledgement** (also applies to `modify_order`). The response is never returned before M7 acknowledges receipt, and by default not before the outcome (see *Receipt vs. outcome* above). If M7 rejects the request (e.g. the order was concurrently filled or deleted) the envelope is `ok:false` with a `CONFLICT` error; if it refuses it because the order's revision moved under the command the error is `ORDER_CHANGED`, which means it was not applied and the same command may be retried; if the exchange returns the request undelivered the error is `NOT_PROCESSED`, which means it definitely was not applied; if no acknowledgement arrives within the order acknowledgement timeout the error is `TIMEOUT`, which means unknown rather than failed. The resulting order state is delivered on the [`orders`](#stream-orders) stream.

**Member isolation** (also applies to `modify_order`). Beyond the `modify_order` / `delete_order` capability, the caller must be authorized to act on the order's member: assigned, or `bypass_member_check`; an untagged house order needs `trade_global`. `read_orders` grants visibility, not the right to act. An order outside that scope returns `NOT_FOUND`, identical to a missing one, so a desk cannot cancel, modify, or re-tag another member's order.

### <a id="cmd-cancel_all_orders" name="cmd-cancel_all_orders"></a>`Command` `action "cancel_all_orders"`

Cancel every order the caller is authorized to act on. Mirrors REST `DELETE /orders` and gRPC `CancelAllOrders`. It reports on receipt alone and does not wait for each deletion's execution report: the resulting order states arrive on the [`orders`](#stream-orders) stream.

**Required permission:** `delete_order`. Scope follows the caller's member authority. (see [Permissions](#permissions))

#### Request

This command takes no fields beyond the envelope's `action` and `req_id`.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `deleted` | `u32` | count | always | Orders whose cancel the exchange acknowledged, counted on receipt rather than on each deletion's report. Account-wide: the login user's own active orders, pre-arranged ones included, when the command was sent. Member-scoped: the orders whose own cancel it acknowledged. |

**Member delivery areas.** A member-scoped sweep skips an order whose member may not trade the order’s area: it is neither cancelled nor counted as targeted. The account-wide cancel is one exchange command and pulls it with everything else.

#### Errors

| Error code | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `delete_order`. |
| `CONFLICT` | The exchange refused a cancel in a member-scoped sweep; the message ends with the counts. |
| `ORDER_PENDING` | A member-scoped sweep met one or more of the caller’s orders the exchange has not yet acknowledged; every other order’s cancel went out and the message ends with the counts. Call it again once they are acknowledged. |
| `NOT_PROCESSED` | The exchange handed the cancel back undelivered. |
| `TIMEOUT` | No acknowledgement within the order acknowledgement timeout; the outcome is unknown. |

The transport-wide codes (`UNAUTHENTICATED`, `NOT_OPERATIONAL`, `INTERNAL`) may also occur; see the [Error reference](#errors). Cancel-all is never refused with `RATE_LIMITED`.

#### Example

```json
{"action": "cancel_all_orders", "req_id": "…"}
// → result: {"deleted": <count>}  (only after M7 acknowledges the cancel)
// not gated by the kill-switch; works even when trading is disabled
// ok:false CONFLICT if M7 rejects, ORDER_CHANGED if the order's revision
// moved under the command; NOT_PROCESSED if the exchange returns it
// undelivered; TIMEOUT if no ack within the order acknowledgement timeout;
// a member-scoped cancel the exchange did not acknowledge in full fails with
// that failure's code and the counts at the end of the message
```

**Member isolation.** A full-authority caller (`bypass_member_check` + `trade_global`) cancels the whole account in one atomic command; a member-scoped caller cancels only their members' orders (other desks' and, without `trade_global`, house orders are left untouched). Either arm acts only on orders this gateway's own login user placed, never a colleague's on the same membership, and the atomic arm counts the login user's own orders, pre-arranged ones included, exactly what the exchange's blanket delete removes. `deleted` counts only orders this caller targeted.

**A member-scoped cancel succeeds only when the exchange acknowledges the cancel for every order it targeted.** If the exchange refuses one, or one cannot be sent because its product’s price scale is unknown or unsupported, the cancel still goes out for every other order and the request then fails. If the route to the exchange fails, no receipt in time, the request returned undelivered, the publish failed, or load management refused the cancel because the exchange has the member order-restricted, it stops at that order. Either way the error carries that failure’s own code, so a refusal is `CONFLICT`, and its message ends with the counts, for example `(cancel-all incomplete: the exchange acknowledged the cancel for 2 of 3 targeted orders; 1 may still be resting)`. The account-wide cancel is one exchange command with no partial outcome, so its errors carry no counts.

**An order not yet acknowledged leaves a member-scoped cancel incomplete.** One of the caller’s orders that the exchange has not yet acknowledged has no exchange order id to cancel by. The cancel still goes out for every acknowledged order, and the request then fails `ORDER_PENDING`, with that order counted as targeted and not acknowledged, for example `ORDER_PENDING: … (cancel-all incomplete: the exchange acknowledged the cancel for 1 of 2 targeted orders; 1 may still be resting)`. Call it again once the order is acknowledged. A refusal of one of the acknowledged orders stays the error’s cause, and the counts still include the unacknowledged order. Another desk’s unacknowledged order does not count. The account-wide cancel is unchanged.

### <a id="cmd-submit_basket" name="cmd-submit_basket"></a>`Command` `action "submit_basket"`

Enter 1 to 100 orders as one exchange order entry under one list instruction. Mirrors REST `POST /basket` and gRPC `SubmitBasket`.

**Required permission:** `create_order`. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `basket_ref` | `string` (UUID) | none | optional | Idempotency key; absent has the gateway mint one. |
| `list_exec_inst` | `string` | none | required | `none`, `valid` or `linked`. |
| `orders` | `array` | none | required | 1 to 100 orders, each with the fields of [`new_order`](#cmd-new_order) (without `action` and `req_id`). |

- `none`: the exchange validates and processes each order on its own.
- `valid`: every order must pass the exchange’s entry validation or the whole list is rejected; accepted orders then rest independently.
- `linked`: every order must be `fok` (with validity `non`); the list executes whole or the exchange deletes it whole, and its orders never match each other. All orders must be on local products or all on remote products; different products may be mixed.

**All or none at the gateway.** Every order is checked before anything is sent, with the checks a single order takes: the field rules, member and delivery area, the contract and its product’s bounds, position, slot and cash limits and the self-cross policy. Every order is evaluated, and one failure refuses the whole basket with `BASKET_REFUSED`, whose message lists each failing order as `[<index>] <CODE>: <text>` joined by `"; "`. Nothing reaches the exchange then. A field the single-order validator refuses keeps its own code, with the order’s index leading its message. A `none` or `valid` basket is checked as if its orders were entered one after another, so a later order sees the earlier ones resting and an order crossing an earlier one meets the self-cross policy, because the exchange matches them. A `linked` basket fills whole or not at all, so position and slot limits are checked on its net effect: an hourly buy and the four quarter-hour sells of that hour, of equal size, move no slot. Its cash is the sum of each order’s own requirement, because the exchange checks cash per order, and the self-cross scan passes over its own orders, which cannot match each other, but sees every other order of the desk.

**Load management.** A basket spends one order transaction per order. One that would take the member past the gateway’s throttling threshold is refused whole and spends nothing.

**The basket reference.** `basket_ref` is a UUID idempotency key; leave it out and the gateway mints one. Every order of the basket carries it as `basket_ref` on the order views, read back from the order’s own text, so it survives a gateway restart. Whether the orders do is the exchange's decision: it may delete every order of a basket when the gateway logs out or disconnects, a restart included, although on the exchange's simulator it kept them through a restart. The gateway shows what the exchange reports afterwards. A reference the gateway still holds a basket under is refused `BASKET_REF_IN_USE`. Each order may carry its own `client_order_id`; two orders under one id are refused. A basket always waits for its outcomes, so an order’s `ack_only` is not read. A block create (`delivery_end`) is refused; join an existing block by its `contract_id`.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `basket_ref` | `string` | none | always | The basket reference, as sent or as minted. |
| `list_exec_inst` | `string` | none | always | As sent. |
| `basket_id` | `u64 \| null` | none | always | The exchange’s basket id; `null` when it reported none. |
| `orders` | `array` | none | always | Each order’s `client_order_id`, `state`, `reason` and `err_code`, in request order. |

**The answer** lists each order’s outcome in request order with the fields a single submit answers. It waits for every order’s outcome, within the order acknowledgement window and then the outcome window; an order without one is `PENDING`. The exchange’s rejection of a `valid` list, the kill of a `linked` list and the refusal of single orders are each order’s `state` and `err_code`, never an error. The exchange rejects a `valid` or `linked` list whole, so when it refuses one, every order of the list is answered `REJECTED`, an order the refusal did not name with the refusal’s own `reason` and `err_code`; a refusal naming some orders of a `none` list rejects those alone. `basket_id` is the exchange’s own id, reported only for a basket of two or more orders.

#### Errors

| Error code | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `create_order`. |
| `BAD_REQUEST` | An order the single-order validator refuses, its index leading the message; or an unknown `list_exec_inst`. |
| `BASKET_EMPTY` | The basket carries no order. 400 / `InvalidArgument`. |
| `BASKET_TOO_LARGE` | The basket carries more than 100 orders. 400 / `InvalidArgument`. |
| `BASKET_LINKED_REQUIRES_FOK` | A `linked` basket with an order that is not `fok`; the message names it. 400 / `InvalidArgument`. |
| `BASKET_DUPLICATE_ORDER_ID` | Two orders under one `client_order_id`. 400 / `InvalidArgument`. |
| `BASKET_BLOCK_UNSUPPORTED` | An order would create a user-defined block. 400 / `InvalidArgument`. |
| `BASKET_REF_IN_USE` | The gateway still holds a basket under this `basket_ref`. 400 / `InvalidArgument`. |
| `BASKET_LINKED_NOT_SUPPORTED` | A `linked` basket on a product that publishes `linked_order_product` false. 422 / `FailedPrecondition`. |
| `BASKET_REFUSED` | One or more orders failed an admission check; each is listed with its own code. 422 / `FailedPrecondition`. |
| `NOT_PROCESSED` | The exchange handed the basket back undelivered; safe to resubmit. |

> [!NOTE]
> Answered from its own task, so the connection keeps streaming and answering while the basket waits for the exchange.

#### Example

```json
{"action": "submit_basket", "req_id": "b1", "list_exec_inst": "valid",
 "orders": [{"side": "BUY", "price": 5000, "quantity": 1000, "delivery_area_id": "10YDE-RWENET---I", "contract_id": 111},
            {"side": "BUY", "price": 5000, "quantity": 1000, "delivery_area_id": "10YDE-RWENET---I", "contract_id": 222}]}
// → result: {"basket_ref": "…", "list_exec_inst": "valid", "basket_id": 4711, "orders": [{"client_order_id": "…", "state": "ACTIVE", …}, …]}
```

### <a id="cmd-cancel_basket" name="cmd-cancel_basket"></a>`Command` `action "cancel_basket"`

Cancel every resting order of one basket that the caller may act on: the login user’s own orders in the caller’s member scope. One cancel per order, each awaiting the exchange’s receipt, never a multi-order request. A basket with no order the caller may act on is not found. A cancel only takes exposure off, so load management never refuses it for headroom; while the exchange has the member restricted it is refused, as a single cancel is. Mirrors REST `DELETE /basket` and gRPC `CancelBasket`.

**Required permission:** `delete_order`. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `basket_ref` | `string` (UUID) | none | required | The basket to cancel. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `basket_ref` | `string` | none | always | The basket reference. |
| `cancelled` | `integer` | count | always | Orders whose cancel the exchange acknowledged. |
| `orders` | `array` | none | always | Each order’s `client_order_id`, `cancelled` (bool), and, when not cancelled, the `code` and `error` it was refused with (`null` otherwise). |

An order-level refusal is reported on that order and the next is tried. A failure of the route to the exchange stops the cancel: before any cancel was acknowledged it is the call’s error, as for a single cancel; after one, it is reported on every order not yet cancelled. An order the exchange has not yet acknowledged is reported `ORDER_PENDING`. `cancelled` counts acknowledged cancels, not confirmed deletions.

#### Errors

| Error code | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `delete_order`. |
| `BASKET_NOT_FOUND` | No order of the basket is held for this caller. 404 / `NotFound`. |
| `LOAD_THROTTLED` | The exchange has the member order-restricted, so load management refused the first cancel. |

#### Example

```json
{"action": "cancel_basket", "req_id": "c1", "basket_ref": "…"}
// → result: {"basket_ref": "…", "cancelled": 2, "orders": [{"client_order_id": "…", "cancelled": true, "code": null, "error": null}, …]}
```

### <a id="cmd-recall_trade" name="cmd-recall_trade"></a>`Command` `action "recall_trade"`

Ask the exchange to recall an executed trade (a mistrade), or every recallable trade of one order. Mirrors REST `POST /trade/recall` and gRPC `RecallTrade`, with the same fields, codes and statuses.

**Required permission:** `recall_trade`. (see [Permissions](#permissions))

**Whose trade.** Only a trade this gateway's exchange login placed can be recalled, and only for a member you may act on: a member you are assigned to (or any member with `bypass_member_check`); a House trade needs `trade_global`. A trade placed by another exchange user on your balancing group, which the exchange reports to your login too, is refused as not your own. A trade you cannot see, or one of a member you may not act on, is not found.

**The exchange's rules, not the gateway's.** The exchange accepts a recall only within its windows: a trade can be recalled within 5 minutes of its execution (error 2013 after that), not too close to its delivery (2012, 3007), not below its turnover floor (3008), and never for an auction (3009) or OTC trade (3017); a trade already recalled, rejected, granted or requested is refused too (3001, 3004, 3005, 3006). The gateway applies none of these windows: it forwards the request and reports the exchange's refusal with its code. It refuses only a trade that is not `ACTI` and a `revision_no` it has seen move on. Market operations decide a recall that was accepted; the decision arrives later as the trade's new state, `RGRA` (granted, the trade is reversed) or `RREJ` (rejected, the trade stands).

**Cascade.** A cross-contract trade carries a `parent_trade_id`, and recalling it recalls every trade with the same parent at once. A recall by `client_order_id` therefore sends one request per parent; the other trades of that parent follow it: `cascaded` when the exchange took the request (`requested` or `submitted`), otherwise the request's own outcome, reason and code (`refused`, `unknown`, `not_sent`), so a trade is never shown recalled when its group's request was not; a recall by `trade_id` names them in `cascaded_with`.

**One order, every fill.** An order that filled in several trades needs one recall per trade, each inside the exchange's window. A recall by `client_order_id` recalls every trade of the order you hold (its modifications keep the id, so every fill of the order is found) and sends the requests at once, so the whole order is answered within one wait rather than one per trade.

**Limits.** A recall is not an order management transaction and never counts against the exchange's load-management limits. Each request the gateway sends counts once against your per-key request bound: a recall by `client_order_id` counts each request after the first, and a request the bound refuses is answered `not_sent`.

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `trade_id` | `string` | none | one of | The exchange trade id (numeric) of one trade to recall. |
| `client_order_id` | `string` | none | one of | Recall every own trade of this order you may act on: the `ACTI` ones are sent, the others are answered `not_recallable`. |
| `revision_no` | `i64` | none | No | With `trade_id` only: the revision you saw. If the gateway holds a newer one, nothing is sent and the answer is `TRADE_CHANGED`. Omitted, the gateway's latest revision is used. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `client_order_id` | `string` | none | by `client_order_id` | The order you named. |
| `results` | `array` | none | always | One result per trade, in execution order. |
| `counts` | `object` | count | by `client_order_id` | How many results carry each outcome, every outcome listed. |

Each result:

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `trade_id` | `string` | none | always | The exchange trade id. |
| `outcome` | `string` | none | always | What became of the recall; see *Outcomes* below. |
| `state` | `string` | none | always | The trade's state when the answer was built ([Trade states](#trade-states)). |
| `revision_no` | `i64` | none | always | The trade's revision when the answer was built. |
| `recall_req_time` | `string` | RFC 3339 | when it applies | When the exchange registered the recall request. |
| `latest_recall_process_time` | `string` | RFC 3339 | when it applies | Until when market operations can decide the recall. |
| `m7_err_code` | `i64` | none | when it applies | The exchange's error code, on `refused` only. |
| `m7_error_key` | `string` | none | when it applies | The code's key in the exchange's error catalogue (for example `trade_execution_too_long_ago` for 2013, `recall_already_requested` for 3006, `otc_cannot_be_recalled` for 3017). |
| `reason` | `string` | none | when it applies | The exchange's words on `refused`; the state on `not_recallable`; why on `unknown` and `not_sent`. |
| `cascaded_with` | `string[]` | none | when it applies | For a trade whose recall was sent: the other trades you hold with the same `parent_trade_id`, which the exchange recalls with it. For the other trades of its parent: that trade, whatever its outcome. |

#### Outcomes

| Outcome | Meaning |
| --- | --- |
| `requested` | The exchange acknowledged the request and the trade moved to a recall state (`RREQ`, `RSFA` for a trade with another exchange, or already `RGRA` / `RREJ`) within the wait. |
| `submitted` | The exchange acknowledged the request, which means it forwarded it for processing, and the trade had not moved to a recall state by the end of the wait (`system.recall_outcome_wait_ms`, 5 s by default). The state change follows on the trade streams. A trade that moved to another state in the wait (a cancellation by market operations, `CREQ` or `CNCL`) is answered `submitted` too, its `reason` naming the state. Until the exchange refuses or returns the request, a new recall of this trade, or of a trade the exchange recalls with it, is answered `not_recallable` for 60 seconds after it was sent; after that, a trade still `ACTI` can be asked again, well inside the exchange's 5-minute window. |
| `refused` | The exchange refused the recall, at its receipt or after acknowledging it. `m7_err_code` and `m7_error_key` say why. |
| `unknown` | No acknowledgement arrived in time (`system.order_ack_timeout_ms`). The request may have reached the exchange: read the trade's state before asking again. The gateway never resends it. Until the exchange refuses or returns the request, a new recall of this trade, or of a trade the exchange recalls with it, is answered `not_recallable` for 60 seconds after it was sent; after that, a trade still `ACTI` can be asked again, well inside the exchange's 5-minute window. |
| `not_recallable` | Nothing was sent: the trade is not `ACTI`, and `reason` names the state (already requested, already recalled, already rejected, cancelled), or a recall of the same trade, or of a trade the exchange recalls with it (the same `parent_trade_id`), is still awaiting the exchange. The gateway sends one recall of a trade at a time: a second one sent before the exchange has answered the first would be refused by the exchange as a concurrent update after the first had already moved the trade, so the gateway answers it here instead. |
| `cascaded` | Not sent itself: the trade shares its `parent_trade_id` with the trade in `cascaded_with`, whose request the exchange took, and the exchange recalls every trade with the same parent together. When that request was refused, unknown or not sent, the trade carries that outcome, reason and code instead of `cascaded`. |
| `not_sent` | The exchange never received it: the per-key request bound refused it, the gateway was shutting down, or the message broker handed the request back undelivered (`reason` starts `NOT_PROCESSED`). Safe to ask again. |

#### Status

A recall by `trade_id` answers with its one result's status: `requested` and `submitted` answer `ok: true` with the body, a `submitted` one adding `"code": "RECALL_SUBMITTED"`; `refused` answers the error `RECALL_REFUSED`, `not_recallable` `RECALL_NOT_POSSIBLE`, `unknown` `OUTCOME_UNKNOWN` and `not_sent` `NOT_PROCESSED`. Such an error object carries `results`, `m7_err_code` and `m7_error_key` beside the code, status pair and message. A recall by `client_order_id` answers `ok: true` whenever the order has a trade you may recall, whatever each outcome is.

#### Errors

| Error code | Condition |
| --- | --- |
| `BAD_REQUEST` | Both targets or neither, `revision_no` with `client_order_id`, an empty `client_order_id`, or a `trade_id` that is not numeric. The message names the rule. |
| `PERMISSION_DENIED` | The caller does not hold `recall_trade`, or the trade is one the caller can see but this gateway's exchange login did not place. |
| `TRADE_NOT_FOUND` | No such trade, or no trade of that order, that the caller may recall. |
| `TRADE_CHANGED` | The trade's revision moved past `revision_no`; nothing was sent. |
| `RECALL_NOT_POSSIBLE` | The trade is not `ACTI`; nothing was sent. |
| `RECALL_REFUSED` | The exchange refused the recall. |
| `OUTCOME_UNKNOWN` | No acknowledgement in time; read the trade before asking again. |
| `NOT_PROCESSED` | The exchange never received the request; safe to retry. |
| `NOT_OPERATIONAL` | The gateway's exchange login is not known yet, so no trade can be shown to be its own. |

The transport-wide codes (`UNAUTHENTICATED`, `RATE_LIMITED`, `INTERNAL`) may also occur; see the [Error reference](#errors).

#### Example

```json
{"action": "recall_trade", "req_id": "r1", "trade_id": "1500000001", "revision_no": 1}
// → result: {"results": [{"trade_id": "1500000001", "outcome": "requested", "state": "RREQ", "revision_no": 2, …}]}
{"action": "recall_trade", "req_id": "r2", "client_order_id": "6f0c2a54-…"}
// → result: {"client_order_id": "6f0c2a54-…", "results": […], "counts": {"requested": 2, "cascaded": 1, …}}
```

### <a id="cmd-get_order" name="cmd-get_order"></a>`Command` `action "get_order"`

Look up one order (pending or acknowledged) by `client_order_id`. Mirrors REST `GET /order` and gRPC `GetOrder`.

**Required permission:** none (authenticated caller); member-scoped. `read_orders` or `bypass_member_check` widens the lookup to any order. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `client_order_id` | `string` | none | Yes | The order's stable handle. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `result` | `object` | none | always | The order: an `OwnOrder` if acknowledged, or a `PendingOrder` if submitted but not yet acked by M7. Same field shapes as the [`orders`](#stream-orders) stream entries. |

#### Errors

| Error code | Condition |
| --- | --- |
| `NOT_FOUND` | No pending or confirmed order with that `client_order_id` in the caller scope. Identical to an out-of-scope order, so the lookup is not an existence oracle. |

The transport-wide codes (`UNAUTHENTICATED`, `RATE_LIMITED`, `INTERNAL`) may also occur; see the [Error reference](#errors).

#### Example

```json
{"action": "get_order", "req_id": "…", "client_order_id": "…"}
// → result: the order (pending or acknowledged), or NOT_FOUND
```

`get_order` is member-scoped like [`list_orders`](#cmd-list_orders): an order tagged with a member the caller may not see (or an untagged house order, for a caller without broad read) returns `NOT_FOUND`, identical to an unknown `client_order_id`. A caller with `read_orders`/`bypass_member_check` can look up any order.

### <a id="cmd-list_orders" name="cmd-list_orders"></a>`Command` `action "list_orders"`

List the caller-visible resting orders, optionally filtered. Mirrors REST `GET /orders` and gRPC `ListOrders`.

An order the exchange reports filled or deleted leaves the list as soon as the gateway holds that report. Read it with [`get_order`](#cmd-get_order) while the gateway still holds it, or in the order audit ([`audit_query`](#cmd-audit_query)). A hibernated order stays listed: it is still yours at the exchange and can be activated or cancelled.

**Required permission:** none (authenticated caller); member-scoped. `read_orders` or `bypass_member_check` returns the firm-wide order book. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `delivery_area` | `string` | none | No | Filter to one delivery area. |
| `contract_id` | `u64` | none | No | Filter to one contract; requires `delivery_area`. |
| `product` | `string` | none | No | Filter to one product; requires `delivery_area`; ignored when `contract_id` is set. |
| `delivery_start` | `string` | RFC 3339 | No | With `product`: narrow to the contract at this delivery start. Ignored without `product`. Any RFC 3339 instant: `2026-10-25T00:00:00Z`, `2026-10-25T00:00:00.000Z` and `2026-10-25T02:00:00+02:00` name the same contract. The doubled hour of a clock change is two instants: on 2026-10-25, 02:00 CEST is `00:00Z` (hour `02A`) and 02:00 CET is `01:00Z` (hour `02B`). |
| `v_member_short_id` | `string` | none | No | Narrow to one member (authorization required, see below). |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `result` | `array of OwnOrder` | none | always | Caller-scoped resting orders; pending (not yet acked) orders are excluded, query [`get_order`](#cmd-get_order) for those. |

#### Errors

| Error code | Condition |
| --- | --- |
| `BAD_REQUEST` | `contract_id` or `product` without `delivery_area`, a negative `contract_id`, or a `delivery_start` with `product` that is not an RFC 3339 timestamp (`delivery_start must be an RFC 3339 timestamp, e.g. 2026-10-25T00:00:00Z`). |
| `PERMISSION_DENIED` | `v_member_short_id` names a member the caller is not assigned to and may not read. |

The transport-wide codes (`UNAUTHENTICATED`, `RATE_LIMITED`, `INTERNAL`) may also occur; see the [Error reference](#errors).

#### Example

```json
{"action": "list_orders", "req_id": "…", "delivery_area": "10YNL----------L",
 "contract_id": 12345, "product": "H",
 "v_member_short_id": "VM001"}
// all filters optional; contract_id/product require delivery_area
// → result: caller-scoped array of resting orders
```

`list_orders` is member-scoped like REST `GET /orders`: a caller with `read_orders` (or `bypass_member_check`) sees the firm-wide order book, everyone else only their assigned members' orders (untagged house orders withheld). The optional `v_member_short_id` narrows to one member and returns a `PermissionDenied` error envelope unless the caller is assigned to it or holds broad read. An acknowledged order recovers its `v_member_short_id` from the order's exchange text field only for this gateway's own login user; a colleague's order on the same membership (a different M7 `user_code`) carries its `user_code` and neither a virtual member nor a Voltnir user, and is scoped like an untagged house order.

<a id="ops-market" name="ops-market"></a>

## Contracts & market data

The contract catalogue and per-contract working sets. Result shapes match REST `GET /contract/…`; a contract read by `get_contract` carries the exchange reference price (`ref_px_cents`, `ref_px_type`, `ref_px_date`, `ref_px_updated_ms`).

### <a id="cmd-list_contracts" name="cmd-list_contracts"></a>`Command` `action "list_contracts"`

The contract catalogue of a delivery area, ordered by delivery start ascending: each contract's id, product, delivery period, state and trading phase, with no order book and no prices. Mirrors REST `GET /contract/{area_id}` and gRPC `ListContracts`. The catalogue covers **every product the exchange has assigned your account**, since the gateway inquires contract definitions account-wide, including an assigned product you have not subscribed market data for.

The catalogue is for finding contract ids: call it at startup or when a new delivery day appears, and do not poll it. One contract's order book comes from [`get_contract`](#cmd-get_contract) or [`get_contract_by_delivery`](#cmd-get_contract_by_delivery). Live data comes from the WebSocket `contracts` stream and gRPC `WatchContracts`, one stream with one filter on both: by area and product, or by contract id to follow one contract or a few.

**Contracts not open yet.** The catalogue lists the contracts the exchange has created but not yet opened for trading, in every configured delivery area whose exchange product list includes the contract's product. Such a row has `state` `IACT`, `trading_phase` `CLSD`, and `trading_phase_start` and `trading_phase_end` both `null`. Every row the exchange has opened in an area carries a `trading_phase_start`, so a `CLSD` row with a `null` `trading_phase_start` is a contract that has not opened yet. `act_point` is the exchange's activation point, not the opening time; the exchange publishes no opening time. `new_order` on such a row is refused with `BAD_REQUEST` (400 / `InvalidArgument`) and `"the contract is not open for trading yet"`. When the exchange's opening report reaches the gateway, the same row turns tradable in place, sent on the `contracts` stream as an update (the same `contract_id`, with the area's own state and phase); while the gateway runs that report is the exchange's broadcast, and a new login also lists the opened row. A contract that opens without one of those areas leaves it, removed from it with a delete.

**Required permission:** none (authenticated caller). (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `area_id` | `string` | none | Yes | EIC code of the delivery area (e.g. `"DE"`). |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `result` | `array of object` | none | always | One row per active contract whose delivery period is known, sorted by delivery start ascending, with exactly the fields of a REST [`GET /contract/{area_id}`](rest_api_v1.md#get-contracts) row: `contract_id`, `area_id`, `prod`, `name`, `long_name`, `dlvry_start`, `dlvry_end`, `duration`, `predefined`, `state`, `trading_phase`, `trading_phase_start`, `trading_phase_end`. |

#### Errors

| Error code | Condition |
| --- | --- |
| `NOT_FOUND` | The delivery area is unknown. |

The transport-wide codes (`UNAUTHENTICATED`, `RATE_LIMITED`, `INTERNAL`) may also occur; see the [Error reference](#errors).

#### Example

```json
{"action": "list_contracts", "req_id": "…", "area_id": "DE"}
// → result: [{"contract_id": "100001", "area_id": "DE", "prod": "H", "dlvry_start": "2026-04-20T22:00:00Z", "state": "ACTI", "trading_phase": "CONT", …}]
```

### <a id="cmd-get_contract" name="cmd-get_contract"></a>`Command` `action "get_contract"`

One contract's detail: metadata plus the caller's working set on it. Mirrors REST `GET /contract/{area_id}/{contract_id}` and gRPC `GetContract`.

**Required permission:** none (authenticated caller); member-scoped. `read_orders` or `bypass_member_check` widens the working set to firm-wide. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `area_id` | `string` | none | Yes | EIC delivery area. |
| `contract_id` | `string` | none | Yes | M7 contract id. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `contract` | `Contract` | none | always | Contract metadata, order book and reference price (the REST [contract object](rest_api_v1.md#contract-object)). |
| `orders_acknowledged` | `array of OwnOrder` | none | always | Caller-scoped acknowledged orders on the contract. |
| `orders_pending` | `array of PendingOrder` | none | always | Caller-scoped pending orders on the contract. |
| `trades` | `array of OwnTrade` | none | always | Caller-scoped fills on the contract. It holds what the live trade stream holds: the trades of the current cash-exposure window (since the most recent 16:00 booking cut on an ECC business day) and every trade on a contract whose delivery day, in its market's local time, is today or later. A trade recorded without its delivery window is kept for up to seven days after it executed. Earlier trades come from the trade history: [`audit_query`](#cmd-audit_query) with `entity: "trades"`. Each trade carries its `state` ([Trade states](#trade-states)) and the [recall fields](#recall-fields). |
| `net_pos` | `i32` | sub-MW (MW × 1000) | always | Executed net position (+ long, − short); firm-wide with broad read, otherwise the assigned members' sum. |

#### Errors

| Error code | Condition |
| --- | --- |
| `NOT_FOUND` | No contract with that id in the area, or its delivery end has passed on the gateway’s clock. Orders still resting on a finished contract are read through [`list_orders`](#cmd-list_orders) (with `delivery_area` and `contract_id`) and cancelled with `delete_order`. |

The transport-wide codes (`UNAUTHENTICATED`, `RATE_LIMITED`, `INTERNAL`) may also occur; see the [Error reference](#errors).

#### Example

```json
{"action": "get_contract", "req_id": "…", "area_id": "DE", "contract_id": "12345"}
// → result: {contract, orders_acknowledged, orders_pending, trades, net_pos}
```

**Scoping.** `orders_acknowledged`, `orders_pending`, `trades` and `net_pos` are member-isolated exactly like [`list_orders`](#cmd-list_orders). A caller holding `read_orders` (or `bypass_member_check`) sees every member's rows plus the untagged house-account rows, and `net_pos` is the firm-wide executed position (sub-MW, executed trades only). Everyone else sees only the rows tagged with a virtual member assigned to them, house rows withheld, and `net_pos` is the sum of those members' executed positions; with no assigned members the lists are empty and `net_pos` is 0. A trade between two virtual members of the desk reaches a member-scoped caller as the ordinary fill of its own leg: only the leg its members placed, carrying that leg's own member, member name, Voltnir user and user name exactly as a fill against an outside counterparty would, with the other leg, its member and its Voltnir user withheld; a caller holding `read_orders` (or `bypass_member_check`) sees both legs.

### <a id="cmd-get_contract_by_delivery" name="cmd-get_contract_by_delivery"></a>`Command` `action "get_contract_by_delivery"`

Same result, member-scoped the same way, as [`get_contract`](#cmd-get_contract), resolved by product + delivery start instead of contract id. Mirrors REST `GET /contract/{area}/by-delivery/…` and gRPC `GetContractByDelivery`.

**Required permission:** none (authenticated caller); member-scoped. `read_orders` or `bypass_member_check` widens the working set to firm-wide. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `area_id` | `string` | none | Yes | EIC delivery area. |
| `prod` | `string` | none | Yes | Product code (e.g. `"H"`). |
| `dlvry_start` | `string` | RFC 3339 | Yes | Delivery start of the contract. Any RFC 3339 instant: `2026-10-25T00:00:00Z`, `2026-10-25T00:00:00.000Z` and `2026-10-25T02:00:00+02:00` name the same contract. The doubled hour of a clock change is two instants: on 2026-10-25, 02:00 CEST is `00:00Z` (hour `02A`) and 02:00 CET is `01:00Z` (hour `02B`). |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `result` | `object` | none | always | Same shape as [`get_contract`](#cmd-get_contract): `{contract, orders_acknowledged, orders_pending, trades, net_pos}`. |

#### Errors

| Error code | Condition |
| --- | --- |
| `BAD_REQUEST` | `dlvry_start` is not an RFC 3339 timestamp (`dlvry_start must be an RFC 3339 timestamp, e.g. 2026-10-25T00:00:00Z`). |
| `NOT_FOUND` | No contract for that area, product and delivery start, or its delivery end has passed on the gateway’s clock. |

The transport-wide codes (`UNAUTHENTICATED`, `RATE_LIMITED`, `INTERNAL`) may also occur; see the [Error reference](#errors).

#### Example

```json
{"action": "get_contract_by_delivery", "req_id": "…", "area_id": "DE",
 "prod": "H", "dlvry_start": "2026-06-16T06:00:00Z"}
// → result: same shape as get_contract
```

### <a id="cmd-hub2hub_query" name="cmd-hub2hub_query"></a>`Command` `action "hub2hub_query"`

One-shot hub-to-hub ATC capacity for a source area + window, optionally narrowed to one destination (no subscription). For live updates use [`watch_hub2hub`](#stream-watch_hub2hub). Mirrors REST `GET /hub2hub` and gRPC `GetHub2Hub`.

**Required permission:** none (authenticated caller). (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `delivery_area_from` | `string` | none | Yes | Source delivery area EIC code. `delivery_area` is accepted as the same field. |
| `delivery_area_to` | `string` | none | No | Destination delivery area EIC code; keeps only that destination's connections, and leaves out an interval with no connection to it. Absent or empty = all destinations. |
| `delivery_from` | `string` | RFC 3339 | Yes | Window start (inclusive on `dlvry_start`). |
| `delivery_to` | `string` | RFC 3339 | Yes | Window end (exclusive on `dlvry_start`). The server does not check that `delivery_from` is before `delivery_to`. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `delivery_area_from` / `delivery_area` | `string` | none | always | Both echo the requested source area. |
| `delivery_area_to` | `string` | none | always | Echoes the requested destination; `null` when none was sent. |
| `delivery_from` / `delivery_to` | `string` | RFC 3339 | always | Echoes the request window. |
| `enabled` | `bool` | none | always | Whether hub-to-hub capacity is enabled for the area. |
| `capacity_connected` | `bool` | none | always | Whether the capacity feed is currently connected. |
| `data` | `array of AtcEntry` | none | always | ATC capacity rows in the window. A row whose delivery period ended more than an hour ago is left out. |

#### Errors

| Error code | Condition |
| --- | --- |
| `BAD_REQUEST` | `delivery_from` or `delivery_to` is not valid RFC 3339; the message names the field (`invalid delivery_from: …`). Refused whether or not hub-to-hub is enabled. |

The transport-wide codes (`UNAUTHENTICATED`, `RATE_LIMITED`, `INTERNAL`) may also occur; see the [Error reference](#errors).

#### Example

```json
{"action": "hub2hub_query", "req_id": "…", "delivery_area_from": "10YNL----------L",
 "delivery_area_to": "10YDE-VE-------2",
 "delivery_from": "2026-06-16T06:00:00Z", "delivery_to": "2026-06-16T22:00:00Z"}
// → result: {"delivery_area_from": "10YNL----------L", "delivery_area": "10YNL----------L",
//            "delivery_area_to": "10YDE-VE-------2", "delivery_from": "…", "delivery_to": "…",
//            "enabled": true, "capacity_connected": true, "data": [AtcEntry…]}
```

### <a id="cmd-list_public_trades" name="cmd-list_public_trades"></a>`Command` `action "list_public_trades"`

Recent market-wide public trades, optionally filtered. Mirrors REST `GET /public_trades` and gRPC `ListPublicTrades`.

**Required permission:** none (authenticated caller). (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `limit` | `u32` | count | No | Default 100, capped at 1000; must be greater than zero. |
| `contract_id` | `u64` | none | No | Filter to one contract. |
| `area_id` | `string` | none | No | Filter to one delivery area. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `trades` | `array of PublicTrade` | none | always | The matching public trades. |

#### Errors

| Error code | Condition |
| --- | --- |
| `BAD_REQUEST` | A `limit` of zero or an out-of-range filter value. |

The transport-wide codes (`UNAUTHENTICATED`, `RATE_LIMITED`, `INTERNAL`) may also occur; see the [Error reference](#errors).

#### Example

```json
{"action": "list_public_trades", "req_id": "…", "limit": 100,
 "contract_id": 12345, "area_id": "DE"}   // filters optional
// → result: {"trades": […]}
```

### <a id="cmd-public_trades_for_contract" name="cmd-public_trades_for_contract"></a>`Command` `action "public_trades_for_contract"`

The retained public-trade history for one contract, typically fired on chart mount, then kept live via the [`public_trades`](#stream-public_trades) stream (dedup by `trade_id`).

**Required permission:** none (authenticated caller). (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `contract_id` | `u64` | none | Yes | The contract to seed history for. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `contract_id` | `u64` | none | always | Echoes the request. |
| `trades` | `array of PublicTrade` | none | always | The retained public-trade history for the contract. |

#### Errors

| Error code | Condition |
| --- | --- |
| `BAD_REQUEST` | A missing or malformed `contract_id`. |

The transport-wide codes (`UNAUTHENTICATED`, `RATE_LIMITED`, `INTERNAL`) may also occur; see the [Error reference](#errors).

#### Example

```json
{"action": "public_trades_for_contract", "req_id": "…", "contract_id": 12345}
// → result: {"contract_id": 12345, "trades": [PublicTrade…]}
```

<a id="ops-sysreads" name="ops-sysreads"></a>

## System reads

`get_state` is gated by `read_state`. `get_status` and its base component reads (`get_throttling`, `get_trading_allowed`) are open to every authenticated caller; the desk-money component reads (`get_cash_limits`, `get_cash_limit`, `get_contract_limit`) stay gated by `read_status`. Result bodies match the REST endpoint of the same name.

### <a id="cmd-get_state" name="cmd-get_state"></a>`Command` `action "get_state"`

Runtime-health snapshot: uptime, AMQP/upstream connectivity and latency telemetry, license. Mirrors REST `GET /state` and gRPC `GetState`; the [`state`](#stream-state) stream is its streaming form.

**Required permission:** `read_state`. (see [Permissions](#permissions))

#### Request

This command takes no fields beyond the envelope's `action` and `req_id`.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `result` | `SystemState` | none | always | The runtime-health snapshot: uptime, `operational`, the `issues` list, the AMQP and WebSocket feed health flags, the license, and the trade-persistence and product-scale and contract-catalogue counters described below. Same shape as REST `GET /state`. |

#### Errors

| Error code | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `read_state`. |

The transport-wide codes (`UNAUTHENTICATED`, `RATE_LIMITED`, `INTERNAL`) may also occur; see the [Error reference](#errors).

#### Example

```json
{"action": "get_state", "req_id": "…"}
// → result: SystemState, same shape as REST GET /state
```

`operational` is `false` whenever any order-critical subsystem is degraded: the exchange session, the three AMQP channels, or either M7 WebSocket feed, the order book *and* the private-data stream, each connected, synchronized and sequence-healthy. `issues` then carries one string per failing condition; the strings are identical on all three transports and enumerated on the [REST `GET /state`](rest_api_v1.md#get-state) page. The private-data feed carries your own orders and execution reports, so while it is degraded the exposure the order gate measures against has stopped advancing: `new_order` and `modify_order` are refused with `NOT_OPERATIONAL` until it recovers. `delete_order`, `cancel_all_orders` and `toggle_trade_enabled` are never gated on `operational`, pulling an order only reduces exposure. The snapshot also carries four cumulative-since-start trade-persistence counters, `trades_received`, `trades_persisted`, `trades_persist_failed` and `writes_dropped`, identical to REST `GET /state`; a non-zero `trades_persist_failed` or `writes_dropped` signals a persistence loss. A fifth counter, `trade_reports_refused`, counts exchange trade reports refused for an unreadable financial core; while it is non-zero and the `trade_report refused` condition above is present, order entry is closed until the re-asked window brings the missed trade in, unless the desk trades on through it (`admission` then reads `degraded`). Beside `operational` the snapshot carries `admission`: `open`, `closed` or `degraded`: whether new orders and modifies are admitted. `closed` while any order-critical issue is present, except as follows. `degraded` while the only issues are `trade_report refused` and the `cash_exposure_window not covered` it opens, and admission is open anyway because `system.trade_ingest_fault` is `continue` or an operator acknowledged the fault. Cancels are never gated. It also carries the product decimal-scale fields, `product_parameters_loaded` and the counters `product_scale_unrepresentable`, `product_scale_frames_dropped`, `product_scale_orders_refused`, `product_scale_changes`, again the same as REST; on a gateway whose products publish the (2, 3, MW) scale the API is denominated in they read `true` and `0`. It also carries the two contract-catalogue fields `contracts_awaiting_definition` (book-born contracts withheld from the `contracts` stream until their delivery report lands) and `contract_reports_broadcast` (contract reports received as broadcasts this session). Beside `issues` it carries `last_update_pass_refused`, `true` when the exchange refused this login's inquiry for the trades it updated while Voltnir was not connected (`dateMeaning=LAST_UPDATE`). Voltnir then trades on the match-time inquiry alone, so a recall or cancellation resolved during that time, on a trade matched before the cash-exposure window, can still count in position, slot sums and P&L until the exchange reports the trade again. It does not close order entry. The refused question is not asked again: the next login asks only about what changed after this session last heard the exchange, so a trade reversed during the outage before this login keeps counting until the exchange reports it again or a trade-history restore brings it back. The flag clears when the gateway next connects to the exchange.

### <a id="cmd-get_status" name="cmd-get_status"></a>`Command` `action "get_status"`

The caller-scoped trading-posture aggregate in one call: the one-shot form of the [`status`](#stream-status) stream, same flat shape as REST `GET /status` and gRPC `GetStatus`.

**Required permission:** none (authenticated caller). `read_status` adds the desk-wide money and full licence keys. (see [Permissions](#permissions))

#### Request

This command takes no fields beyond the envelope's `action` and `req_id`.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `throttling` | `object` | none | always | M7's load-management report plus this gateway's own guard (base layer). |
| `trading_enabled` | `bool` | none | always | The kill switch (base layer). |
| `operational` | `bool` | none | always | `true` when every required subsystem is healthy (base layer). |
| `admission` | `string` | none | always | `open`, `closed` or `degraded`: whether new orders and modifies are admitted. `closed` while any order-critical issue is present, except as follows. `degraded` while the only issues are `trade_report refused` and the `cash_exposure_window not covered` it opens, and admission is open anyway because `system.trade_ingest_fault` is `continue` or an operator acknowledged the fault. Cancels are never gated. Base layer; the same value as the `state` snapshot. |
| `license_summary` | `object` | none | always | Base-layer license projection: status kind, expiry, grace-window end while in grace, and `mode`, the licence tier (`"trader"` or `"desk"`; on `"trader"` the user, member and permission management commands are refused with `LICENSE_DESK_REQUIRED`). |
| `accounts` | `array of AccountView` | none | always | The accounts the caller may trade for, each with its own position limits and cash usage (empty when none). |
| `cash_limits` | `object` | none | read_status | M7-reported per-currency cash/margin feed. Absent without `read_status`. |
| `order_pos_limit` | `i64` | sub-MW (MW × 1000) | read_status | The global per-contract net position limit. Absent without `read_status`. |
| `cash_limit` | `object` | none | read_status | The desk-wide cash-limit state per currency pool, with `delivery_risk_applied` and `delivery_risk_source` as the [`status`](#stream-status) stream describes them. Absent without `read_status`. |
| `license` | `object` | none | read_status | The full installed license. Absent without `read_status`. |
| `stranded_pending_count` | `i64` | count | read_status | New orders held past their expiry bound: no answer from the exchange, and the gateway cannot rule out a missed report or a late XBID answer, so they go on consuming position and cash headroom until their report or refusal, the first order snapshot after the bound, a restart, or about an hour after their contract’s delivery ends. 0 on a healthy gateway. Absent without `read_status`. |
| `stranded_pending_qty` | `i64` | sub-MW (MW × 1000) | read_status | Their total quantity. Absent without `read_status`. |
| `claims_count` | `i64` | count | read_status | Amendments and activations whose added exposure counts against the position and cash limits until the exchange answers them or their expiry bound passes. Held claims included. Absent without `read_status`. |
| `claims_qty` | `i64` | sub-MW (MW × 1000) | read_status | What those claims add. Absent without `read_status`. |
| `claims_held_count` | `i64` | count | read_status | Of those, the claims held past their expiry bound, for the same reasons and until the same events as a held new order. 0 on a healthy gateway. Absent without `read_status`. |
| `claims_held_qty` | `i64` | sub-MW (MW × 1000) | read_status | What the held claims add: headroom lost to commands the exchange has not answered. Absent without `read_status`. |
| `m7_client_cert` | `object` | none | read_status | The M7 client certificate, the first certificate in the file the gateway's `epex_connection.cert` setting names: `status`, the tagged `{kind, days?, reason?}`, where `kind` is `valid`, `expiring_soon` (from 30 days before expiry, `days` left), `expired` (`days` since expiry), `not_yet_valid` (`days` until it starts) or `unreadable` (`reason`: a missing file, no PEM block, no certificate, or one that does not parse); and `not_after`, RFC 3339 UTC, absent when unreadable. The gateway reads the file at startup and every hour. The exchange refuses the connection under an expired certificate, with no grace period; a replacement file at the same path is used on the next connection attempt, with no restart. Absent without `read_status`. |

#### Errors

| Error code | Condition |
| --- | --- |
| `UNAUTHENTICATED` | Missing or invalid credentials. No permission is required to call this op. |

The transport-wide codes (`RATE_LIMITED`, `INTERNAL`) may also occur; see the [Error reference](#errors).

#### Example

```json
{"action": "get_status", "req_id": "…"}
// result (read_status caller):
//   {"throttling": {…}, "trading_enabled": true, "operational": true,
//    "license_summary": {"status": {"kind": "active"}, "expires_at": "…", "mode": "desk"},
//    "accounts": [{"is_house": true, "position_limit": 50000, "effective_position_limit": 50000,
//                  "eur_limit_cents": …, "eur_consumed_cents": …, "eur_remaining_cents": …,
//                  "gbp_limit_cents": …, "gbp_consumed_cents": …, "gbp_remaining_cents": …}],
//    // the keys below are present only with read_status
//    "cash_limits": {…}, "order_pos_limit": 50000, "cash_limit": {…}, "license": {…},
//    "stranded_pending_count": 0, "stranded_pending_qty": 0,
//    "claims_count": 0, "claims_qty": 0, "claims_held_count": 0, "claims_held_qty": 0,
//    "m7_client_cert": {"status": {"kind": "valid"}, "not_after": "2027-03-01T12:00:00Z"}}
```

A caller without `read_status` receives the same object with the `cash_limits`, `order_pos_limit`, `cash_limit`, `license`, `stranded_pending_*`, `claims_*` and `m7_client_cert` keys absent. See the [`status`](#stream-status) stream card for the field semantics.

### <a id="cmd-get_throttling" name="cmd-get_throttling"></a>`Command` `action "get_throttling"`

M7's order load-management status for the member, plus this gateway's own client-side guard. Mirrors REST `GET /throttling` and gRPC `GetThrottling`. A base slice of [`get_status`](#cmd-get_status): the budget is shared by the desk's single M7 login, and it carries counts only, no money or positions.

**Required permission:** none (authenticated caller). (see [Permissions](#permissions))

#### Request

This command takes no fields beyond the envelope's `action` and `req_id`.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| M7 status fields | various | seconds / counts | always | M7's own statement of the member's status (thresholds, counts, release times); every period is in seconds, `timestamp`, `short_release_timestamp` and `long_release_timestamp` are UTC, RFC 3339 with `Z`, and every status is `"NO_RESTRICTION"`, `"WARNING"` or `"RESTRICTED"`. All `null` until the exchange first states one. |
| `guard` | `object` | none | always | This gateway's own client-side guard, current to the millisecond: `guard.headroom` is how many further exposure-adding order actions will be admitted before order entry is refused with `LOAD_THROTTLED`; `guard.blocked_reason` says why; `guard.stale` is `true` when the exchange's last report has aged out. |
| `throttling_member_action` | `string` | none | always | What this gateway asks the exchange, at every login, to do with every order of the member when it restricts the member: `"HIBE_MBR_ORDERS"` (the default) hibernates them all, whichever client entered them, overriding every user-level action; `"NONE_MBR_ORDERS"` leaves it to each user's own action. The exchange keeps the value of the last login that stated one. |
| `throttling_user_action` | `string` | none | always | The same for the orders of this gateway's own exchange user: `"HIBE_USER_ORDERS"` (the default), `"HIBE_BG_ORDERS"` (the user's whole balancing group) or `"NONE_USER_ORDERS"`. |

#### Errors

| Error code | Condition |
| --- | --- |
| `UNAUTHENTICATED` | Missing or invalid credentials. No permission is required to call this op. |

The transport-wide codes (`RATE_LIMITED`, `INTERNAL`) may also occur; see the [Error reference](#errors). Field-by-field detail is on [`GET /throttling`](rest_api_v1.md#get-throttling).

#### Example

```json
{"action": "get_throttling", "req_id": "…"}
// → result: M7's throttling report + the local guard, same shape as REST GET /throttling
//   {"status": "NO_RESTRICTION", "short_omt_limit_l1": 1000, …,
//    "guard": {"enabled": true, "reported": true, "headroom": 996,
//              "short": {"observation_period_sec": 10, "l1": 1000,
//                        "local_omts": 3, "estimated_load": 3, "headroom": 996},
//              "long":  {…}, "blocked_reason": null},
//    "throttling_member_action": "HIBE_MBR_ORDERS",
//    "throttling_user_action": "HIBE_USER_ORDERS"}
```

### <a id="cmd-get_system_info" name="cmd-get_system_info"></a>`Command` `action "get_system_info"`

The exchange reference data this session runs against: `voltnir_version` (this gateway's build, always set even before M7 responds), the M7 system params, and two reference tables, `products` (the bounds every order is measured against) and `risk_sets` (the parameters the exchange prices cash-limit exposure with). Mirrors REST `GET /system_info` and gRPC `GetSystemInfo`.

**Required permission:** none (authenticated caller). (see [Permissions](#permissions))

#### Request

This command takes no fields beyond the envelope's `action` and `req_id`.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `voltnir_version` | `string` | none | always | This gateway's own build. Distinct from the M7 backend version. Always set, even before M7 responds. |
| M7 system params | `object` | various | after M7 responds | `backend_version`, rate limits, `max_orders`, retention. `null` until the exchange has answered. |
| `products` | `array of Product` | none | always | The product reference table: one entry for every product the exchange has assigned your account. |
| `risk_sets` | `array of RiskSet` | none | always | The risk-set reference table: what an order costs against the cash limit. |

#### Errors

| Error code | Condition |
| --- | --- |
| `UNAUTHENTICATED` | Missing or invalid credentials. No permission is required to call this op. |

The transport-wide codes (`RATE_LIMITED`, `INTERNAL`) may also occur; see the [Error reference](#errors).

#### Example

```json
{"action": "get_system_info", "req_id": "…"}
// → result: same shape as REST GET /system_info (including the
//   `products` and `risk_sets` tables); M7-sourced fields are null
//   until the exchange has responded, voltnir_version is always set
```

**The bounds are the ones actually enforced.** They come from the exchange’s own product reference data, not from a table inside the gateway, and they are in the wire units an order carries, price in cents, quantity in sub-MW, so they compare directly against [`new_order`](#cmd-new_order) fields. A `null` bound is *not* enforced: the exchange published nothing usable for that rule and judges it itself. Each product also carries its M7 decimal scale, `dec_shft_px`, `dec_shft_qty`, `qty_unit` and `scale` (`representable` / `unrepresentable` / `unknown`), describing the M7 boundary the gateway converts across; the bounds and order fields stay on the gateway's own cents and sub-MW regardless. It also carries its user-defined block settings, `block_order_product` (bool), `block_maximum_hours` (integer, read both as a count of the product's contracts and as hours) and `dst_block_product` (bool, the product's treatment of contracts on the 25-hour clock-change day, which no local check reads), `linked_order_product` (bool, whether the product takes orders in a `linked` basket; `false` refuses one locally with `BASKET_LINKED_NOT_SUPPORTED`), each `null` when the product publishes no reading of it (a `block_maximum_hours` of 0 reads as none), which restricts nothing. Field-by-field meanings are tabulated on the [REST `GET /system_info`](rest_api_v1.md#get-system-info) page.

### <a id="cmd-get_area_table" name="cmd-get_area_table"></a>`Command` `action "get_area_table"`

The M7 EIC area reference table: every delivery / hub-to-hub area (`areas`) and market area (`market_areas`), with each area’s `short_name` / `long_name` overlaid from the live M7 area reports when the exchange named it. Mirrors REST `GET /area_table` and gRPC `GetAreaTable`.

**Required permission:** none (authenticated caller). (see [Permissions](#permissions))

#### Request

This command takes no fields beyond the envelope's `action` and `req_id`.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `areas` | `array of AreaInfo` | none | always | Every delivery and hub-to-hub area; each carries a `name_source` of `static` until a live name lifts it to `exchange`. |
| `market_areas` | `array of MarketAreaInfo` | none | always | The market areas. |

#### Errors

| Error code | Condition |
| --- | --- |
| `UNAUTHENTICATED` | Missing or invalid credentials. No permission is required to call this op. |

The transport-wide codes (`RATE_LIMITED`, `INTERNAL`) may also occur; see the [Error reference](#errors).

#### Example

```json
{"action": "get_area_table", "req_id": "…"}
// → result: same shape as REST GET /area_table
//   ({"areas": [...], "market_areas": [...]}); every area's
//   name_source is "static" until the exchange names it
```

**`fill_country` is the whole country an area colours on a country-fill map**, already folded so a virtual or control sub-zone carries its parent country. It is *absent* for a `border_coupling` area, which is a border and fills no country, treat an absent `fill_country` as “no country”, never a blank one. Field-by-field meanings are tabulated on the [REST `GET /area_table`](rest_api_v1.md#get-area-table) page.

### <a id="cmd-get_pnl" name="cmd-get_pnl"></a>`Command` `action "get_pnl"`

Caller-scoped P&L snapshot: per-contract, per-(area,product), and per-virtual-member. Mirrors REST `GET /pnl` and gRPC `GetPnl`; the [`pnl`](#stream-pnl) stream is its streaming form.

**Required permission:** none (authenticated caller); member-scoped. `read_pnl` or `bypass_member_check` returns the firm-wide snapshot. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `v_member_short_id` | `string` | none | No | Narrow to one member (authorization required, see below). |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `result` | `PnlSnapshot` | q8 money, sub-MW energy | always | The caller-scoped P&L: `per_contract`, `per_area_prod`, `per_vm`, `per_vm_area_prod`, `totals` (one realized/unrealized total per currency), `computed_at_ms` and `unpriced_trades`. Money is q8 (currency × 100,000). Same shape as REST `GET /pnl`. |

#### Errors

| Error code | Condition |
| --- | --- |
| `PERMISSION_DENIED` | `v_member_short_id` names a member the caller is not assigned to and may not read. |

The transport-wide codes (`UNAUTHENTICATED`, `RATE_LIMITED`, `INTERNAL`) may also occur; see the [Error reference](#errors).

#### Example

```json
{"action": "get_pnl", "req_id": "…", "v_member_short_id": "VM001"}
// → result: caller-scoped PnL snapshot; member filter optional
```

`get_pnl` is member-scoped like REST `GET /pnl`: a caller with `read_pnl` (or `bypass_member_check`) sees the firm-wide snapshot, everyone else only their assigned members (firm-wide `per_contract`/`per_area_prod` empty). The optional `v_member_short_id` narrows to one member and returns a `PermissionDenied` error envelope unless the caller is assigned to it or holds broad read.

### <a id="cmd-get_trading_allowed" name="cmd-get_trading_allowed"></a>`Command` `action "get_trading_allowed"`

Read the trading kill-switch. Mirrors REST `GET /trading_allowed` and gRPC `GetTradingAllowed`. The `trading_enabled` base slice of [`get_status`](#cmd-get_status), which a trader needs to know whether it may submit at all.

**Required permission:** none (authenticated caller). (see [Permissions](#permissions))

#### Request

This command takes no fields beyond the envelope's `action` and `req_id`.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `enabled` | `bool` | none | always | Whether trading is currently enabled. |

#### Errors

| Error code | Condition |
| --- | --- |
| `UNAUTHENTICATED` | Missing or invalid credentials. No permission is required to call this op. |

The transport-wide codes (`RATE_LIMITED`, `INTERNAL`) may also occur; see the [Error reference](#errors).

#### Example

```json
{"action": "get_trading_allowed", "req_id": "…"}
// → result: {"enabled": true}
```

### <a id="cmd-get_self_trade_policy" name="cmd-get_self_trade_policy"></a>`Command` `action "get_self_trade_policy"`

Read the self-trade prevention policy. Mirrors REST `GET /self_trade_policy` and gRPC `GetSelfTradePolicy`.

**Required permission:** none (authenticated caller). (see [Permissions](#permissions))

#### Request

This command takes no fields beyond the envelope's `action` and `req_id`.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `policy` | `string` | none | always | `"observe"` or `"reject"`. |

#### Errors

| Error code | Condition |
| --- | --- |
| `UNAUTHENTICATED` | Missing or invalid credentials. No permission is required to call this op. |

The transport-wide codes (`RATE_LIMITED`, `INTERNAL`) may also occur; see the [Error reference](#errors).

#### Example

```json
{"action": "get_self_trade_policy", "req_id": "…"}
// → result: {"policy": "observe"}
```

### <a id="cmd-get_cash_limits" name="cmd-get_cash_limits"></a>`Command` `action "get_cash_limits"`

The M7-reported cash/margin limit feed, keyed by ISO currency. Distinct from the Voltnir order cash limit ([`get_cash_limit`](#cmd-get_cash_limit)). Mirrors REST `GET /cash_limits` and gRPC `GetCashLimits`.

**Required permission:** `read_status`: it exposes the desk-wide money that [`get_status`](#cmd-get_status) carries only under `read_status`. (see [Permissions](#permissions))

#### Request

This command takes no fields beyond the envelope's `action` and `req_id`.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `limits` | `object` | cents (currency × 100) | always | The M7-reported cash/margin feed, keyed by ISO currency (e.g. `{"EUR": {…}}`). |

#### Errors

| Error code | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `read_status`. |

The transport-wide codes (`UNAUTHENTICATED`, `RATE_LIMITED`, `INTERNAL`) may also occur; see the [Error reference](#errors).

#### Example

```json
{"action": "get_cash_limits", "req_id": "…"}
// → result: {"limits": {"EUR": {…}, …}}, same shape as REST GET /cash_limits
```

### <a id="cmd-get_cash_limit" name="cmd-get_cash_limit"></a>`Command` `action "get_cash_limit"`

Read both cash pools (EUR + GBP, in cents). **The desk's cash limit is the exchange's**, the maximum financial exposure it may build between two ECC Booking Cuts, received from M7. An operator cap can only tighten it, and `house_cents` = `min(ecc_limit_cents, cap_cents)` is the number every check uses. That limit is then **partitioned**: `allocated_cents` is what the virtual members hold between them and `unallocated_cents` is what is left for orders placed on the House account itself. An ECC limit the exchange has not reported counts as **zero**, so no order may add exposure in that pool. Distinct from [`get_cash_limits`](#cmd-get_cash_limits) (the raw M7 feed). Mirrors REST `GET /cash_limit` and gRPC `GetCashLimit`.

**Required permission:** `read_status`: it exposes the desk-wide money that [`get_status`](#cmd-get_status) carries only under `read_status`. (see [Permissions](#permissions))

#### Request

This command takes no fields beyond the envelope's `action` and `req_id`.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `eur` / `gbp` | `object` | cents (currency × 100) | always | One cash pool each; every field is described in the table below. |

| Pool field | Type | Description |
| --- | --- | --- |
| `ecc_limit_cents` | `i64?` | The ECC limit in force for the pool. `null` when the exchange has reported none. |
| `ecc_revision` | `i64?` | Revision of the ECC record the limit came from. |
| `ecc_effective_from` | `string?` | The date that record takes effect, `YYYY-MM-DD` in the exposure timezone. The exchange sends it as an instant, a record starting at midnight CEST arrives as `22:00:00Z` the previous day, so the calendar day it names depends on that zone. `null` when not reported or unreadable; the raw exchange value is on [`get_cash_limits`](#cmd-get_cash_limits). |
| `m7_remaining_cents` | `i64?` | What the exchange still has available before the next booking cut, already net of the desk's own open orders and trades. |
| `cap_cents` | `i64?` | The operator cap. `null` = no cap; `0` = a deliberate cap of zero. |
| `house_cents` | `i64` | The limit every check uses: `min(ecc_limit_cents, cap_cents)`. |
| `allocated_cents` | `i64` | Sum of every virtual member's allocation in the pool, active and inactive alike. |
| `unallocated_cents` | `i64` | What is left for the House (untagged) account: `house_cents − allocated_cents`. **Can be negative**; untagged orders are rejected once it reaches zero. |
| `over_allocated` | `bool` | The allocations sum to more than `house_cents`, the exchange lowered its limit under allocations already granted. They are never shrunk on their own; the House remainder absorbs it. |
| `cap_above_ecc` | `bool` | A standing cap now sits above the ECC limit; the cap is left untouched and the ECC limit binds. |
| `breached` | `bool` | The exchange reports the pool's current limit below zero and has deactivated every order in that currency. |
| `reported_at_ms` | `i64?` | When the exchange last reported this pool, Unix ms UTC. `null` when it never has. The gateway re-asks at login, on every reconnect and on a timer, so a value that stops advancing means the reports have stopped arriving. |
| `stale` | `bool` | The pool's figures can no longer be vouched for: the broadcast channel carrying its reports broke since they arrived, or the optional report-age ceiling is armed and has been passed. They are left as reported; the pool refuses every order that adds exposure, with scope `stale_cash_limit`, until it is reported again. |

#### Errors

| Error code | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `read_status`. |

The transport-wide codes (`UNAUTHENTICATED`, `RATE_LIMITED`, `INTERNAL`) may also occur; see the [Error reference](#errors).

#### Example

```json
{"action": "get_cash_limit", "req_id": "…"}
// → result: {
//     "eur": {"ecc_limit_cents": 10000000, "ecc_revision": 7,
//             "ecc_effective_from": "2026-09-03", "m7_remaining_cents": 8412300,
//             "cap_cents": null, "house_cents": 10000000,
//             "allocated_cents": 7500000, "unallocated_cents": 2500000,
//             "over_allocated": false,
//             "cap_above_ecc": false, "breached": false,
//             "reported_at_ms": 1788336000000, "stale": false},
//     "gbp": {…}
//   }
```

**How much an order or trade consumes.** The exchange publishes a *risk set* per product and delivery area: eight price-dependent `a` parameters and four price-independent `alpha` parameters. One leg consumes `a[case] × signed price × MWh + alpha[case] × MWh`, where `case` is chosen by side, price sign, and whether the exposure comes from a resting order or an executed trade. Voltnir reads those parameters from the exchange and prices with them, so its arithmetic is the exchange's arithmetic. A resting order never contributes a credit, its exposure is floored at zero, and every figure scales with the contract's delivery duration, so a 15-minute leg counts a quarter of the hourly amount.

On the exchange's default risk set this reproduces the exchange's own cash-limit rules exactly: a buy at a positive price consumes its value, a trade moves the limit by its full signed value, and the risk-free order cases (sell at a positive price, buy at a negative price) cost nothing. The one exception is a trade whose delivery duration Voltnir does not yet know: it is counted as one hour long when it consumes, and credits nothing until its duration is known. A GB delivery area is assigned a risk set carrying the exchange's GB price-independent delivery risk parameter as its `alpha` sell value, which is why GB sells also decrease the limit for a member the add-on applies to (`status.cash_limit.delivery_risk_applied`; with it `false` a GB leg is priced with its product's default risk set instead, the set the exchange prices such a member's GB legs with), and a GB risk set may charge the price term on a negative-price sell on top of that add-on, and decline to credit a negative-price buy trade.

Until the exchange has published a risk set for a contract's product and area, Voltnir prices the leg with a stand-in rather than at zero: the exchange's EUR rules for a non-GBP area, and the operator-configured GBP delivery-risk rate for a GBP one (charged only with `delivery_risk_applied` on), logged once per delivery area.

### <a id="cmd-get_contract_limit" name="cmd-get_contract_limit"></a>`Command` `action "get_contract_limit"`

The global per-contract net position limit, in sub-MW. Mirrors REST `GET /contract_limit` and gRPC `GetContractLimit`.

**Required permission:** `read_status`: it exposes desk-wide risk configuration that [`get_status`](#cmd-get_status) carries only under `read_status`. (see [Permissions](#permissions))

#### Request

This command takes no fields beyond the envelope's `action` and `req_id`.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `limit` | `i32` | sub-MW (MW × 1000) | always | The global per-contract net position limit. |

#### Errors

| Error code | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `read_status`. |

The transport-wide codes (`UNAUTHENTICATED`, `RATE_LIMITED`, `INTERNAL`) may also occur; see the [Error reference](#errors).

#### Example

```json
{"action": "get_contract_limit", "req_id": "…"}
// → result: {"limit": <sub-MW>}
```

### <a id="cmd-get_holidays" name="cmd-get_holidays"></a>`Command` `action "get_holidays"`

Read both ECC bank-holiday calendars (EUR + GBP), used by the cash-limit exposure window (the 16:00 reset rolls over them). Both pools reset on **ECC Business Days**, weekdays minus the TARGET2 closing days, so the same six dates belong in both calendars every year; they are separate lists only so an ad-hoc closure or a non-ECC deployment can be expressed. Mirrors REST `GET /holidays` and gRPC `GetHolidays`.

**Required permission:** none (authenticated caller). (see [Permissions](#permissions))

#### Request

This command takes no fields beyond the envelope's `action` and `req_id`.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `eur` / `gbp` | `array of Holiday` | none | always | Each entry is `{date, label}`; `date` is `YYYY-MM-DD`. Derived TARGET2 dates carry an `(auto)` suffix on their `label`. |

#### Errors

| Error code | Condition |
| --- | --- |
| `UNAUTHENTICATED` | Missing or invalid credentials. No permission is required to call this op. |

The transport-wide codes (`RATE_LIMITED`, `INTERNAL`) may also occur; see the [Error reference](#errors).

#### Example

```json
{"action": "get_holidays", "req_id": "…"}
// → result: {"eur": [{"date": "2026-12-25", "label": "Christmas Day"}], "gbp": [...]}
```

**The gateway fills in the TARGET2 dates itself:** it derives the six closing days (four fixed dates, two computed from Easter) and adds them to both calendars at startup and on an hourly check, for the current year and, from December, the next one too, so the turn of the year needs no action. A date already in a calendar is never overwritten, so an operator's entry for the same day always wins. **Deleting one of the six derived dates sticks:** the remove operation remembers it for that currency, whoever entered the date, and the check does not add it back; the deletion is persisted with the calendar and survives a restart, and adding the date again, by add or replace, lifts it. A replace is not a deletion: a date it leaves out is restocked at the next check. **An empty calendar is a missing input, not a permissive one:** without it the exposure window can only skip weekends and rolls a day early through every TARGET2 closing day, so that currency's pool refuses every order which adds exposure (`no_holiday_calendar`) until a date is entered. **A calendar is only current for the year it covers:** one holding no date in the current or the next calendar year refuses the same orders under its own `stale_holiday_calendar`; with the derived dates in place this normally never fires. Orders that reduce or do not change exposure keep working, as does the other currency's pool, and entering a date for the current year lifts the refusal immediately, no restart.

<a id="ops-controls" name="ops-controls"></a>

## Limits & controls

Operator writes: the kill switch, position and cash limits, the self-trade policy, the holiday calendars, and the restart and trade-history controls. Each requires the noted permission.

### <a id="cmd-toggle_trade_enabled" name="cmd-toggle_trade_enabled"></a>`Command` `action "toggle_trade_enabled"`

Explicit, idempotent SET of the trading kill-switch (despite the name, it never toggles blindly). Mirrors REST `PUT /trading_allowed` and gRPC `SetTradingAllowed`.

Disabling sets the switch before the server reads your next command, so a `new_order` sent right behind it is refused with `TRADING_DISABLED`. The reply waits for the flatten; while it is pending the stream frames keep flowing and your other commands are answered.

**Required permission:** `toggle_trading`. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `enabled` | `bool` | none | Yes | A missing field is rejected as a malformed command (it never defaults, so it can't silently disable trading). |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `enabled` | `bool` | none | always | The trading flag as it now stands. Always the value you sent, the flip is applied before the flatten and is never rolled back by it. |
| `flatten` | `object\|null` | none | on disable | The outcome of the account-wide cancel. `null` when `enabled: true`, because enabling publishes nothing. |
| `flatten.ok` | `bool` | none | on disable | `true` only when M7 acknowledged the cancel, so it was accepted for processing; the resulting order state converges on the order stream. `false` means the publisher queue would not take the command inside the ack window (the exchange connection is most likely down), the exchange rejected it, or no receipt arrived inside the order acknowledgement timeout (2000 ms by default), in every one of those cases resting orders may still be live and the desk should verify the book directly. |
| `flatten.error` | `string\|null` | none | on disable | The reason when `ok` is `false`; `null` otherwise. Every kill-switch flatten is written to the audit log as `order_cancel_all`, outcome `ok` when confirmed, outcome `error` carrying this reason when not. |

#### Errors

| Error code | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `toggle_trading`. |
| `BAD_REQUEST` | A missing or non-bool `enabled` field. |
| `CONFLICT` | Trading has been disabled in configuration, which the runtime toggle cannot override. |

The transport-wide codes (`UNAUTHENTICATED`, `INTERNAL`) may also occur; see the [Error reference](#errors). A `toggle_trade_enabled` carrying `enabled: false` is never refused with `RATE_LIMITED`.

#### Example

```json
{"action": "toggle_trade_enabled", "req_id": "…", "enabled": false}
// → result: {"enabled": false, "flatten": {"ok": true, "error": null}}

{"action": "toggle_trade_enabled", "req_id": "…", "enabled": true}
// → result: {"enabled": true, "flatten": null}
```

> [!WARNING]
> Disabling flattens the book AND rejects `new_order`/`modify_order` with `TRADING_DISABLED`; cancels stay allowed. **The flag is off whether or not the cancel reached the exchange**, so the envelope is `ok: true` even on an unconfirmed flatten, read `flatten.ok` before assuming M7 took the cancel. Rejected with `CONFLICT` when trading has been disabled in configuration (configuration is the absolute authority).

> [!NOTE]
> This command is handled inline on the connection, so while the flatten is awaited the socket emits nothing else and accepts no further command, bounded by the order acknowledgement timeout (2000 ms by default) for the enqueue and the same again for the receipt. `delete_order` and `cancel_all_orders` behave the same way, since they await an exchange receipt too. The flag itself is already set and persisted before that wait begins, so the halt never waits on the exchange; only the report does.

### <a id="cmd-ack_trade_ingest_fault" name="cmd-ack_trade_ingest_fault"></a>`Command` `action "ack_trade_ingest_fault"`

Acknowledge a raised `trade_report refused` fault, reopening order admission on incomplete figures. While the gateway holds a trade report it could not read, a trade the exchange executed is missing from its count, so position, cash and P&L are understated and, under the default `system.trade_ingest_fault: close`, new orders and modifies are refused. An acknowledgement admits them for `system.trade_ingest_fault_ack_ttl_sec` (1800 s by default) while no other issue is present; `admission` on state and status reads `degraded` meanwhile. Meanwhile the gateway does not reconnect its exchange session over the fault; another order-critical issue closes admission as usual, and the TTL keeps running while it does. It ends early when the fault clears, a repeat restarts the TTL, and it lives in the gateway's memory, so a restart drops it (the login backfill raises the fault again if the report is still unreadable). Each acknowledgement writes a `trade_ingest_fault_acknowledged` audit row carrying the reason and the TTL; one that runs out writes `trade_ingest_fault_ack_expired`. The exchange still checks the member's cash limit on every order. The trading terminal has no control for this: it is an API call. Mirrors REST `POST /trade_ingest_fault/ack` and gRPC `AckTradeIngestFault`.

**Required permission:** `toggle_trading`. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `reason` | `string` | none | Yes | Why the desk trades on. Recorded in the audit row. Missing, empty or blank is refused. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `ttl_sec` | `u64` | s | always | How long admission is reopened for. |
| `expires_at_ms` | `i64` | Unix ms | always | When the acknowledgement expires. It ends earlier when the fault clears. |
| `renewed` | `bool` | none | always | `true` when it replaced a live acknowledgement, restarting the TTL. |

#### Errors

| Error code | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `toggle_trading`. |
| `BAD_REQUEST` | `reason` is missing, empty or blank. |
| `CONFLICT` | No `trade_report refused` fault is raised, or the private consumer or the private-data stream is down, so no trade report could arrive. |

The transport-wide codes (`UNAUTHENTICATED`, `RATE_LIMITED`, `INTERNAL`) may also occur; see the [Error reference](#errors).

#### Example

```json
{"action": "ack_trade_ingest_fault", "req_id": "…", "reason": "balancing; support desk paged"}
// → result: {"ttl_sec": 1800, "expires_at_ms": 1791648000000, "renewed": false}
```

### <a id="cmd-set_order_pos_limit" name="cmd-set_order_pos_limit"></a>`Command` `action "set_order_pos_limit"`

Set the global per-contract net position limit. Mirrors REST `PUT /contract_limit` and gRPC `SetContractLimit`.

**Required permission:** `set_position_limit`. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `limit` | `i32` | sub-MW (MW × 1000) | Yes | New limit. Must be non-negative; `0` is the operator kill-switch (blocks all new position-taking). |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `order_pos_limit` | `i32` | sub-MW (MW × 1000) | always | The limit as it now stands. |

#### Errors

| Error code | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `set_position_limit`. |
| `BAD_REQUEST` | A negative limit (`"limit must be non-negative"`). |

The transport-wide codes (`UNAUTHENTICATED`, `RATE_LIMITED`, `INTERNAL`) may also occur; see the [Error reference](#errors).

#### Example

```json
{"action": "set_order_pos_limit", "req_id": "…", "limit": 5000}  // sub-MW
// → result: {"order_pos_limit": 5000}
// limit < 0 is rejected with BAD_REQUEST ("limit must be non-negative")
```

### <a id="cmd-set_cash_limit" name="cmd-set_cash_limit"></a>`Command` `action "set_cash_limit"`

Set or clear the **operator cap** on one cash pool. The House limit itself comes from the exchange and is not settable; a cap only tightens it. A cap above the ECC limit is **rejected, not clamped**; one cannot be set before the exchange has reported a limit to tighten; and one that would leave `house_cents` below `allocated_cents` is refused as well, because Voltnir never shrinks a member's allocation on its own, all three are `BAD_REQUEST`, and nothing is written. Clearing a cap is always allowed. Takes effect immediately. Mirrors REST `PUT /cash_limit` and gRPC `SetCashLimit`.

**Required permission:** `set_cash_limit`. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `cap_cents` | `i64?` | cents (currency × 100) | No | New cap in the target currency. Must be at least `0` and at or below the ECC limit. `null` or omitted removes the cap; `0` is a deliberate cap of zero (no trading in that pool). |
| `currency` | `string` | none | No | `"eur"` (default) or `"gbp"`. Unknown values are `BAD_REQUEST`. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `eur` / `gbp` | `object` | cents (currency × 100) | always | Both pools after the change, in the [`get_cash_limit`](#cmd-get_cash_limit) shape. |

#### Errors

| Error code | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `set_cash_limit`. |
| `BAD_REQUEST` | An unknown `currency`; a cap above the ECC limit; a cap set before the exchange has reported a limit; or a cap that would leave `house_cents` below `allocated_cents`. |

The transport-wide codes (`UNAUTHENTICATED`, `RATE_LIMITED`, `INTERNAL`) may also occur; see the [Error reference](#errors).

#### Example

```json
{"action": "set_cash_limit", "req_id": "…", "cap_cents": 5000000}                    // cap the EUR pool
{"action": "set_cash_limit", "req_id": "…", "cap_cents": null, "currency": "gbp"}    // remove the GBP cap
// → result: both pools, in the get_cash_limit shape
```

### <a id="cmd-set_self_trade_policy" name="cmd-set_self_trade_policy"></a>`Command` `action "set_self_trade_policy"`

Set the self-trade prevention policy. Under `reject`, an order that would cross your own resting order is refused with `SELF_CROSS_BLOCKED`, on `new_order`, and on `modify_order` at the order's new price. Mirrors REST `PUT /self_trade_policy` and gRPC `SetSelfTradePolicy`.

**Required permission:** `set_self_trade_policy`. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `policy` | `string` | none | Yes | `"observe"` or `"reject"`. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `policy` | `string` | none | always | The policy as it now stands. |

#### Errors

| Error code | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `set_self_trade_policy`. |
| `BAD_REQUEST` | A `policy` other than `"observe"` or `"reject"`. |

The transport-wide codes (`UNAUTHENTICATED`, `RATE_LIMITED`, `INTERNAL`) may also occur; see the [Error reference](#errors).

#### Example

```json
{"action": "set_self_trade_policy", "req_id": "…", "policy": "reject"}
// → result: {"policy": "reject"}
```

### <a id="cmd-set_holidays" name="cmd-set_holidays"></a>`Command` `action "set_holidays"`

Replace one currency's whole holiday calendar. Mirrors REST `PUT /holidays` and gRPC `SetHolidays`. A replace is not a deletion: a derived TARGET2 date it leaves out is restocked at the next hourly check.

**Required permission:** `set_cash_limit`. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `currency` | `string` | none | Yes | `"eur"` or `"gbp"`. |
| `holidays` | `array` | none | No | `{date, label?}` objects; `date` is `YYYY-MM-DD`. Omitted means an empty list, which empties the calendar until the next hourly check adds the derived closing days back. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `eur` / `gbp` | `array of Holiday` | none | always | Both calendars after the change. |

#### Errors

| Error code | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `set_cash_limit`. |
| `BAD_REQUEST` | An unknown currency, a malformed `YYYY-MM-DD` date, or a duplicate date. |

The transport-wide codes (`UNAUTHENTICATED`, `RATE_LIMITED`, `INTERNAL`) may also occur; see the [Error reference](#errors).

#### Example

```json
{"action": "set_holidays", "req_id": "…", "currency": "gbp",
 "holidays": [{"date": "2026-05-01", "label": "Labour Day"}, {"date": "2026-12-25"}]}
// → result: {"eur": […], "gbp": […]}  (both calendars after the change)
```

### <a id="cmd-add_holiday" name="cmd-add_holiday"></a>`Command` `action "add_holiday"`

Add one date to a currency's calendar. Mirrors REST `POST /holidays` and gRPC `AddHoliday`. Adding a previously-deleted derived TARGET2 date lifts the deletion.

**Required permission:** `set_cash_limit`. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `currency` | `string` | none | Yes | `"eur"` or `"gbp"`. |
| `date` | `string` | none | Yes | `YYYY-MM-DD`. |
| `label` | `string` | none | No | Human label for the date. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `eur` / `gbp` | `array of Holiday` | none | always | Both calendars after the change. |

#### Errors

| Error code | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `set_cash_limit`. |
| `BAD_REQUEST` | An unknown currency, a malformed `YYYY-MM-DD` date, or a duplicate date. |

The transport-wide codes (`UNAUTHENTICATED`, `RATE_LIMITED`, `INTERNAL`) may also occur; see the [Error reference](#errors).

#### Example

```json
{"action": "add_holiday", "req_id": "…", "currency": "eur",
 "date": "2026-01-01", "label": "New Year's Day"}
// → result: {"eur": […], "gbp": […]}  (both calendars after the change)
```

### <a id="cmd-remove_holiday" name="cmd-remove_holiday"></a>`Command` `action "remove_holiday"`

Remove one date from a currency's calendar. Mirrors REST `DELETE /holidays` and gRPC `RemoveHoliday`. Deleting one of the six derived TARGET2 dates keeps it out of the automatic fill for that currency until the date is added again.

**Required permission:** `set_cash_limit`. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `currency` | `string` | none | Yes | `"eur"` or `"gbp"`. |
| `date` | `string` | none | Yes | `YYYY-MM-DD`. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `eur` / `gbp` | `array of Holiday` | none | always | Both calendars after the change. |

#### Errors

| Error code | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `set_cash_limit`. |
| `NOT_FOUND` | The date is not in that currency's calendar. |
| `BAD_REQUEST` | An unknown currency or a malformed `YYYY-MM-DD` date. |

The transport-wide codes (`UNAUTHENTICATED`, `RATE_LIMITED`, `INTERNAL`) may also occur; see the [Error reference](#errors).

#### Example

```json
{"action": "remove_holiday", "req_id": "…", "currency": "eur", "date": "2026-01-01"}
// → result: {"eur": […], "gbp": […]}  (both calendars after the change)
// removing an absent date → NOT_FOUND
```

### <a id="cmd-restart" name="cmd-restart"></a>`Command` `action "restart"`

Restart the gateway process. Mirrors REST `POST /restart` and gRPC `Restart`. The response is written first; the gateway then drains its transports, logs out of M7, commits every queued write (for up to 30 seconds; a write it cannot commit in that time is counted in `writes_dropped` (a trade in `trades_persist_failed`)), records the shutdown in the audit trail with the run's lost writes per stream, and exits with status **75**, so the host supervisor starts a fresh process that re-reads its configuration.

**Required permission:** `restart_system`. (see [Permissions](#permissions))

#### Request

This command takes no fields beyond the envelope's `action` and `req_id`.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `status` | `string` | none | always | `"restart initiated"`. Expect this socket to close shortly after, and every other one with it. |

#### Errors

| Error code | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `restart_system`. |

The transport-wide codes (`UNAUTHENTICATED`, `RATE_LIMITED`, `INTERNAL`) may also occur; see the [Error reference](#errors).

#### Example

```json
{"action": "restart", "req_id": "…"}
// → result: {"status": "restart initiated"}
```

**This ends the process.** Without a supervisor configured to restart it, the gateway stops and stays stopped. The exit status is 75 rather than 0 on purpose: the shipped supervisor unit restarts on failure, so a restart request comes back while a plain stop stays stopped. Reconnect with a fresh `auth` and re-issue every subscription, subscriptions are per-connection and none survive. Outstanding export tokens are lost; database state and the persisted profile (kill switch, per-contract limit, slot limit mode and House slot limit, self-trade policy, holiday calendars) survive. Not to be confused with the gateway's own internal exchange reconnect, which cycles the M7 subsystems and leaves your connection up.

### <a id="cmd-restore_trade_history" name="cmd-restore_trade_history"></a>`Command` `action "restore_trade_history"`

Repopulate the persistent trade store from the exchange over `[now − effective_days, now]`. Mirrors REST `POST /restore-trade-history` and gRPC `RestoreTradeHistory`. The break-glass for the audit tape after a wiped or migrated database, or after trades roll off the cash-exposure window. The result returns the plan at once; the trades then arrive asynchronously over paced chunks, so watch `trades_received` / `trades_persisted` on the [`state`](#stream-state) stream for progress.

**Required permission:** `restore_trade_history`. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `days` | `u32` | days | No | Days of history to restore. `effective_days` is clamped to the exchange's reach, so an omitted `days` restores the whole reach and a larger value is clamped. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `chunk_count` | `u32` | count | always | How many chunks the window tiled into (0 for an empty window). Delivery is asynchronous and paced. |
| `effective_from_ms` | `i64` | Unix epoch ms (UTC) | always | The oldest instant requested. |
| `effective_days` | `u32` | days | always | Days of history requested after clamping to the exchange's reach; may be less than the requested `days`. |

#### Errors

| Error code | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `restore_trade_history`. |
| `NOT_OPERATIONAL` | The exchange has not yet reported its trade-history reach. |

The transport-wide codes (`UNAUTHENTICATED`, `RATE_LIMITED`, `INTERNAL`) may also occur; see the [Error reference](#errors).

#### Example

```json
{"action": "restore_trade_history", "req_id": "…", "days": 3}
// → result: {"chunk_count": 11, "effective_from_ms": 1725600000000, "effective_days": 3}
// omit "days" to restore the exchange's whole reach
```

A restore is **isolated from cash correctness**: its chunks are not registered with the cash-exposure coverage gate, so it never affects order admission. The restored tape is complete: cancelled and recalled trades are included, carrying their exchange state; a granted recall (`RGRA`) or a cancellation (`CNCL`) adds no exposure, as on a live report (see [Trade states](#trade-states)). Trades only, the exchange serves no history for filled or cancelled orders.

<a id="ops-slot-limit" name="ops-slot-limit"></a>

## Slot position limit

The slot position limit caps the net MW a desk may hold in one quarter-hour of one delivery area, summing every contract that covers that quarter-hour.

An hour counts its full MW in each of its four quarter-hours, a half-hour in each of its two and a block in every quarter-hour it spans; MW is never divided by duration.

It works alongside the per-contract limit: an order must pass both, and the per-contract limit is unchanged by it.

A slot is one 15-minute delivery period, keyed by its UTC start, so the doubled hour of the October clock change is eight distinct slots.

For each slot the check reads the executed net position and the reachable bounds: `max_long` is the net plus every open buy, and `max_short` the net minus every open sell. An open buy on one contract never offsets an open sell on another. An order is refused only when, in some slot its contract covers, it pushes a bound past the limit and leaves it worse, so an order that reduces the position passes even on a desk that is over.

The House slot limit counts every order and trade on the desk. A member with its own `max_slot_position` is held to that limit as well, counting only its own orders and trades. A member with no slot limit (absent) is held to the House slot limit alone; a limit of `0` is flat-only, not off. Limits are sub-MW (MW × 1000).

Three modes: `off` (the default; the check is never run), `observe` (every order is admitted, and one that `reject` would refuse is written to the audit trail as `slot_limit_would_refuse`) and `reject` (such an order is refused before it reaches the exchange). The `slot_limit` section of `config.yml` seeds a fresh database only; after that the mode and the House slot limit are set at runtime and persisted, and each set writes a `slot_limit_set` audit row carrying the mode and the House limit before and after.

When a delivery window the check needs cannot be placed on the quarter-hour grid, the check fails closed: only cancels and amendments that add no quantity pass, and every other order is refused with `slot_window_unknown`. That is an order on a contract with no window; every order in the area while an open order's contract has none; and every order on a slot a trade with no window can deliver in, which is up to the end of the delivery day after the one the trade executed on (in GB, to 23:00 London two days after it), until then, or every slot of its area when its execution time is unknown too.

**Refusals.** On `new_order` and `modify_order` the error code is `SLOT_POSITION_LIMIT_EXCEEDED` or `SLOT_WINDOW_UNKNOWN` (422 / `FailedPrecondition`), with a message starting `slot position limit exceeded:` or `slot window unknown:`. `slot_position_limit_exceeded` names the area, the slot start and end, the side (`long` or `short`), the scope (`house` or the member's short id), the position the order would reach and the limit. `slot_window_unknown` names what has no delivery window: the order's contract, an open order's contract, or a trade. A caller without `read_status`, which cannot see the House limit elsewhere, is not shown the House figures: a refusal by the House slot limit reads `slot position limit exceeded: refused by the desk slot limit, <area> <slot start> to <slot end>, <long|short> side`, and a trade that has no delivery time is not named. A refusal by the member's own slot limit keeps the member's figures. The `order_rejected` audit row carries every field either way.

### <a id="cmd-get_slot_limit" name="cmd-get_slot_limit"></a>`Command` `action "get_slot_limit"`

The slot position limit's mode and the House slot limit. Mirrors REST `GET /slot_limit` and gRPC `GetSlotLimit`.

**Required permission:** `read_status`, the gate of [`get_contract_limit`](#cmd-get_contract_limit). (see [Permissions](#permissions))

#### Request

This command takes no fields beyond the envelope's `action` and `req_id`.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `mode` | `string` | none | always | `off`, `observe` or `reject`. |
| `house_limit` | `i64` | sub-MW (MW × 1000) | always | The House slot limit per quarter-hour. `0` is flat-only. |

#### Errors

| Error code | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `read_status`. |

The transport-wide codes (`UNAUTHENTICATED`, `RATE_LIMITED`, `INTERNAL`) may also occur; see the [Error reference](#errors).

#### Example

```json
{"action": "get_slot_limit", "req_id": "…"}
// → result: {"mode": "observe", "house_limit": 20000}
```

### <a id="cmd-set_slot_limit" name="cmd-set_slot_limit"></a>`Command` `action "set_slot_limit"`

Set the mode and the House slot limit together. Takes effect for the next order and is persisted; a mode other than `off` announces at once any area already locked by a trade with no delivery window. Mirrors REST `PUT /slot_limit` and gRPC `SetSlotLimit`.

**Required permission:** `set_position_limit`. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `mode` | `string` | none | Yes | `off`, `observe` or `reject`. |
| `house_limit` | `i64` | sub-MW (MW × 1000) | Yes | The House slot limit per quarter-hour. Must be ≥ 0; `0` is flat-only, not off. |

#### Response

The setting as it now stands, in the shape [`get_slot_limit`](#cmd-get_slot_limit) returns.

#### Errors

| Error code | Condition |
| --- | --- |
| `BAD_REQUEST` | `mode must be 'off', 'observe' or 'reject'`: an unknown mode. Nothing changes. |
| `BAD_REQUEST` | `house_limit must be non-negative`: a negative limit. Nothing changes. |
| `BAD_REQUEST` | `house_limit is required`: `house_limit` missing or `null`. Nothing changes. |
| `PERMISSION_DENIED` | The caller does not hold `set_position_limit`. |

The transport-wide codes (`UNAUTHENTICATED`, `RATE_LIMITED`, `INTERNAL`) may also occur; see the [Error reference](#errors).

#### Example

```json
{"action": "set_slot_limit", "req_id": "…", "mode": "observe", "house_limit": 20000}
// → result: {"mode": "observe", "house_limit": 20000}
```

### <a id="cmd-get_slot_positions" name="cmd-get_slot_positions"></a>`Command` `action "get_slot_positions"`

Per-slot usage of the slot position limit. The usage read takes a delivery area, a range of at most 48 hours (`[from_ms, to_ms)` in UTC epoch milliseconds, `from_ms` rounded down to the quarter-hour, the 48 hours measured from there) and an optional member. It lists every slot in the range that holds exposure in a scope the caller sees, with, per scope, `net`, `max_long`, `max_short`, the `limit` that applies and the `buy_headroom` and `sell_headroom` left before that limit refuses an order, never below 0, all sub-MW. A caller sees the House scope only with `read_status`, and a member scope only for a member assigned to it and active. The read answers in every mode, `off` included, and reads the same sums the check reads. Mirrors REST `GET /slot_positions` (the same JSON) and gRPC `GetSlotPositions`; the live form is the [`slot_positions`](#stream-slot_positions) stream.

**Required permission:** none (authenticated caller); results are scoped to the members assigned to the caller and active. `read_status` widens the result to the House scope. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `delivery_area` | `string` | none | Yes | The delivery area (EIC code). |
| `from_ms` / `to_ms` | `i64` | Unix ms UTC | Yes | The range `[from_ms, to_ms)`, `from_ms` rounded down to the quarter-hour, at most 48 hours long. |
| `v_member_short_id` | `string` | none | No | Only that member's scope. `PERMISSION_DENIED` unless the member is assigned to the caller and active. |

#### Response

The same object as REST `GET /slot_positions`: `delivery_area`, `from_ms`, `to_ms`, `mode`, `house_limit` (with `read_status` only), `locked` and `slots[]`, each with `slot_start_ms`, `slot_end_ms` and `scopes[]` of `scope`, `net`, `max_long`, `max_short`, and `limit`, `buy_headroom`, `sell_headroom` when a limit applies. All figures are sub-MW.

#### Errors

| Error code | Condition |
| --- | --- |
| `BAD_REQUEST` | `the range is at most 48 hours from from_ms rounded down to the quarter-hour`, `to_ms must be after from_ms` or `delivery_area is required`. |
| `PERMISSION_DENIED` | `v_member_short_id` names a member not assigned to the caller, or an inactive one. |

The transport-wide codes (`UNAUTHENTICATED`, `RATE_LIMITED`, `INTERNAL`) may also occur; see the [Error reference](#errors).

#### Example

```json
{"action": "get_slot_positions", "req_id": "…", "delivery_area": "10YDE-RWENET---I",
 "from_ms": 1791194400000, "to_ms": 1791201600000}
```

<a id="ops-users" name="ops-users"></a>

## Users & members

Self queries (`get_me`, `get_my_members`) are open to any authenticated caller. Management commands require the noted permission and, where marked, the desk-management licence; a trader licence returns `PERMISSION_DENIED` (`LICENSE_DESK_REQUIRED`). `rotate_api_key` and `list_permissions` use `manage_users` but are not desk-gated.

### <a id="cmd-get_me" name="cmd-get_me"></a>`Command` `action "get_me"`

Your own user record: id, username, short id, permission set. Mirrors REST `GET /users/me` and gRPC `GetMe`.

**Required permission:** none (authenticated caller). (see [Permissions](#permissions))

#### Request

This command takes no fields beyond the envelope's `action` and `req_id`.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `id` | `string` | none | always | The user's UUID. |
| `username` | `string` | none | always | The user's login name. |
| `short_id` | `string` | none | always | Compact handle (e.g. `U002`) used in audit attribution. |
| `permissions` | `array of string` | none | always | The permission codes the user holds. |

#### Errors

| Error code | Condition |
| --- | --- |
| `UNAUTHENTICATED` | Missing or invalid credentials. No permission is required to call this op. |

The transport-wide codes (`RATE_LIMITED`, `INTERNAL`) may also occur; see the [Error reference](#errors).

#### Example

```json
{"action": "get_me", "req_id": "…"}
// → result: {"id": "…", "username": "…", "short_id": "U002", "permissions": […]}
```

### <a id="cmd-get_my_members" name="cmd-get_my_members"></a>`Command` `action "get_my_members"`

The virtual members assigned to you: the only member short ids you may set on orders (unless you hold `bypass_member_check`). Returns the same per-member objects as [`get_members`](#cmd-get_members), live cash-usage fields included. Mirrors REST `GET /users/me/members` and gRPC `GetMyMembers`.

**Required permission:** none (authenticated caller). (see [Permissions](#permissions))

#### Request

This command takes no fields beyond the envelope's `action` and `req_id`.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `result` | `array of Member` | none | always | The caller's assigned members, same per-member shape as [`get_members`](#cmd-get_members). |

#### Errors

| Error code | Condition |
| --- | --- |
| `UNAUTHENTICATED` | Missing or invalid credentials. No permission is required to call this op. |

The transport-wide codes (`RATE_LIMITED`, `INTERNAL`) may also occur; see the [Error reference](#errors).

#### Example

```json
{"action": "get_my_members", "req_id": "…"}
// → result: [Member…], same shape as get_members
```

### <a id="cmd-get_users" name="cmd-get_users"></a>`Command` `action "get_users"`

List all users with their ids, usernames, short ids, and permission sets. Mirrors REST `GET /users` and gRPC `ListUsers`.

**Required permission:** `manage_users` and the desk-management licence. (see [Permissions](#permissions))

#### Request

This command takes no fields beyond the envelope's `action` and `req_id`.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `result` | `array of UserProfile` | none | always | Each user's `id`, `username`, `short_id` and `permissions`. |

#### Errors

| Error code | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `manage_users`, or the licence does not enable desk management. |

The transport-wide codes (`UNAUTHENTICATED`, `RATE_LIMITED`, `INTERNAL`) may also occur; see the [Error reference](#errors).

#### Example

```json
{"action": "get_users", "req_id": "…"}
// → result: [{"id": "…", "username": "…", "short_id": "U001", "permissions": […]}, …]
```

### <a id="cmd-create_user" name="cmd-create_user"></a>`Command` `action "create_user"`

Create a user, optionally granting permissions in the same call (validated *before* any write, so a bad request never leaves a half-created user). Mirrors REST `POST /users` and gRPC `CreateUser`.

**Required permission:** `manage_users` and the desk-management licence. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `username` | `string` | none | Yes | Non-empty, unique. |
| `permissions` | `array of string` | none | No | Permission codes to grant on creation (see [`list_permissions`](#cmd-list_permissions)). |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `id` · `username` · `short_id` · `permissions` | `object` | none | always | The created user record. |
| `api_key` | `string` | none | once | The raw plaintext key, shown only in this response. It cannot be retrieved again, only rotated. |

#### Errors

| Error code | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `manage_users`, or the licence does not enable desk management. |
| `BAD_REQUEST` | An unknown permission string, or a missing username; no user is created. |
| `CONFLICT` | `username already exists`: the username is taken, by a current user or a deleted one. A username is never reissued. |

The transport-wide codes (`UNAUTHENTICATED`, `RATE_LIMITED`, `INTERNAL`) may also occur; see the [Error reference](#errors).

#### Example

```json
{"action": "create_user", "req_id": "…", "username": "alice", "permissions": ["create_order"]}
// → result: {id, username, short_id, permissions, api_key}
```

> [!CAUTION]
> `api_key` is the raw plaintext key, shown **only in this response**. It cannot be retrieved again, only rotated.

### <a id="cmd-delete_user" name="cmd-delete_user"></a>`Command` `action "delete_user"`

Delete a user; every session of that user ends with it, and its open connections close. Its key stops working, its permissions and member assignments are removed, and it leaves [`get_users`](#cmd-get_users); every user write on its id (`delete_user`, `set_permissions`, `rotate_api_key`, `set_user_members`) then answers `NOT_FOUND` `user not found`, and `get_user_members` returns an empty list, as for an unknown id. Its orders, trades and audit rows keep its attribution: its short id and username keep naming it, and neither is ever given to another user. You cannot delete yourself or the `admin` account. Mirrors REST `DELETE /users/{id}` and gRPC `DeleteUser`.

**Required permission:** `manage_users` and the desk-management licence. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `user_id` | `string` | none | Yes | UUID of the user to delete. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `result` | `object` | none | always | Empty object `{}` on success. |

#### Errors

| Error code | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `manage_users`, or the licence does not enable desk management. |
| `PERMISSION_DENIED` | `cannot delete the admin account`. |
| `BAD_REQUEST` | `cannot delete yourself`. |
| `NOT_FOUND` | `user not found`: no user with that id, or the user is already deleted. |

The transport-wide codes (`UNAUTHENTICATED`, `RATE_LIMITED`, `INTERNAL`) may also occur; see the [Error reference](#errors).

#### Example

```json
{"action": "delete_user", "req_id": "…", "user_id": "…"}
// → result: {} on success
```

### <a id="cmd-set_permissions" name="cmd-set_permissions"></a>`Command` `action "set_permissions"`

Replace a user's permission set. Mirrors REST `PUT /users/{id}/permissions` and gRPC `SetPermissions`.

**Required permission:** `manage_users` and the desk-management licence. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `user_id` | `string` | none | Yes | UUID of the user. |
| `permissions` | `array of string` | none | Yes | The full replacement permission set; an empty set revokes everything. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `result` | `object` | none | always | Empty object `{}` on success. |

#### Errors

| Error code | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `manage_users`, the licence does not enable desk management, or the target is the built-in `admin` account, whose permissions are immutable. |
| `BAD_REQUEST` | An unknown permission string. |
| `NOT_FOUND` | No user with that id. |

The transport-wide codes (`UNAUTHENTICATED`, `RATE_LIMITED`, `INTERNAL`) may also occur; see the [Error reference](#errors).

#### Example

```json
{"action": "set_permissions", "req_id": "…", "user_id": "…", "permissions": [...]}
// → result: {} on success
// the admin account's permissions are immutable → PERMISSION_DENIED if targeted
```

### <a id="cmd-rotate_api_key" name="cmd-rotate_api_key"></a>`Command` `action "rotate_api_key"`

Rotate a user's API key; the old key and every session of that user stop working immediately. Mirrors REST `POST /users/{id}/rotate-api-key` and gRPC `RotateApiKey`. **Not desk-gated**, unlike the other user-management commands.

**Required permission:** `manage_users`. On a trader licence it is self-only (the target must be the caller). (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `user_id` | `string` | none | Yes | UUID of the user whose key to rotate. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `api_key` | `string` | none | once | The new key, shown only once. |

#### Errors

| Error code | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `manage_users`. |
| `NOT_FOUND` | No user with that id, or (trader tier) a target other than the caller. |

The transport-wide codes (`UNAUTHENTICATED`, `RATE_LIMITED`, `INTERNAL`) may also occur; see the [Error reference](#errors).

#### Example

```json
{"action": "rotate_api_key", "req_id": "…", "user_id": "…"}
// → result: {"api_key": "…"}  (shown once)
// trader tier: self-only, user_id must be the caller; any other target → NOT_FOUND
// desk tier: manage_users may rotate any user
```

Rotating your **own** key invalidates this connection's credential, so the server closes your open WebSocket sessions. Reconnect and re-authenticate with the new key.

### <a id="cmd-get_user_members" name="cmd-get_user_members"></a>`Command` `action "get_user_members"`

The member assignments of any user, as an array of member ids. Mirrors REST `GET /users/{id}/members` and gRPC `GetUserMembers`.

**Required permission:** `manage_users` and the desk-management licence. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `user_id` | `string` | none | Yes | UUID of the user. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `result` | `array of string` | none | always | The user's assigned member UUIDs (the member `id` values, not short ids). |

#### Errors

| Error code | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `manage_users`, or the licence does not enable desk management. |
| `NOT_FOUND` | No user with that id. |

The transport-wide codes (`UNAUTHENTICATED`, `RATE_LIMITED`, `INTERNAL`) may also occur; see the [Error reference](#errors).

#### Example

```json
{"action": "get_user_members", "req_id": "…", "user_id": "…"}
// → result: ["<member-id>", …]  (the user's assigned member ids)
```

### <a id="cmd-set_user_members" name="cmd-set_user_members"></a>`Command` `action "set_user_members"`

Replace a user's member assignments. Mirrors REST `PUT /users/{id}/members` and gRPC `SetUserMembers`.

**Required permission:** `manage_users` and the desk-management licence. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `user_id` | `string` | none | Yes | UUID of the user. |
| `member_ids` | `array of string` | none | Yes | The full replacement set of member UUIDs. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `result` | `object` | none | always | Empty object `{}` on success. |

#### Errors

| Error code | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `manage_users`, or the licence does not enable desk management. |
| `NOT_FOUND` | `user not found`: no user with that id, or the user is deleted (checked first). `member not found`: a listed member id that does not exist, or a deleted member. Nothing is written. |

The transport-wide codes (`UNAUTHENTICATED`, `RATE_LIMITED`, `INTERNAL`) may also occur; see the [Error reference](#errors).

#### Example

```json
{"action": "set_user_members", "req_id": "…", "user_id": "…", "member_ids": [...]}
// → result: {} on success
```

### <a id="cmd-get_members" name="cmd-get_members"></a>`Command` `action "get_members"`

List all virtual members with their configured limits and live cash usage. Mirrors REST `GET /members` and gRPC `ListMembers`.

**Required permission:** `manage_members` and the desk-management licence. (see [Permissions](#permissions))

#### Request

This command takes no fields beyond the envelope's `action` and `req_id`.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `result` | `array of Member` | cents / sub-MW | always | Each member's `id`, `short_id`, `name`, `max_position` (sub-MW, the per-contract limit), `max_slot_position` (sub-MW, the member's [slot position limit](#ops-slot-limit); `null` = none, `0` = flat-only), `active`, `delivery_areas` (`{"all": bool, "area_ids": [EIC]}`: `all` is every area, otherwise only `area_ids`, and an empty list permits none; a member order in any other area is refused `MEMBER_AREA_NOT_ALLOWED` on every action), its `cash_limit` / `cash_limit_gbp` allocations (cents), and the live `*_consumed_cents` / `*_limit_cents` / `*_remaining_cents` usage per pool. |

#### Errors

| Error code | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `manage_members`, or the licence does not enable desk management. |

The transport-wide codes (`UNAUTHENTICATED`, `RATE_LIMITED`, `INTERNAL`) may also occur; see the [Error reference](#errors).

#### Example

```json
{"action": "get_members", "req_id": "…"}
// → result:
// [{"id":"…","short_id":"VM001","name":"Desk A","max_position":5000,
//   "cash_limit":10000000,"cash_limit_gbp":0,"active":true,
//   "eur_consumed_cents":4200000,"eur_limit_cents":10000000,"eur_remaining_cents":5800000,
//   "gbp_consumed_cents":0,"gbp_limit_cents":0,"gbp_remaining_cents":0,
//   "delivery_areas":{"all":false,"area_ids":["10YNL----------L"]}}, …]
```

`cash_limit` / `cash_limit_gbp` are the member's **allocation** out of the desk's cash limit, in EUR / GBP cents. `*_limit_cents` is that same number as the enforced limit, no inheritance from the desk, no clamping to it, so the two always agree. `consumed` = this member's open-order + executed-trade exposure; `remaining = limit − consumed` (negative when over). A limit of `0` means **no allocation**: no order may add exposure in that pool. Per currency the allocations of all members, inactive included, sum to at most the desk's `house_cents`, which is what stops one member spending another's; untagged orders draw on the remainder (`unallocated_cents` on [`get_cash_limit`](#cmd-get_cash_limit)). [`get_my_members`](#cmd-get_my_members) returns the same per-member objects for the caller's assigned members.

### <a id="cmd-create_member" name="cmd-create_member"></a>`Command` `action "create_member"`

Create a virtual member (auto-generated sequential `short_id`). Mirrors REST `POST /members` and gRPC `CreateMember`.

**Delivery areas.** A member trades only in the delivery areas it is given. A member created without `delivery_areas` has none and every order under it is refused `MEMBER_AREA_NOT_ALLOWED`, so give it areas here or later with [patch_member](#cmd-patch_member): `{"all": true}` for every area, or `{"area_ids": [EIC, …]}` for a list taken from the gateway’s configured `epex_settings.delivery_areas` (an unconfigured id is `BAD_REQUEST` naming the configured ones). Read the current areas from [get_members](#cmd-get_members). The rule covers every order action of the member, new, modify, activate, deactivate and cancel, whoever places it; House orders and market data are not restricted.

**Required permission:** `manage_members` and the desk-management licence. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `name` | `string` | none | Yes | Display name. |
| `max_position` | `i64` | sub-MW (MW × 1000) | No | Per-member per-contract limit. |
| `max_slot_position` | `i64 \| null` | sub-MW (MW × 1000) | No | The member's own [slot position limit](#ops-slot-limit). Omitted or `null` = no member slot limit; `0` = flat-only. Negative is `BAD_REQUEST` `max_slot_position must be non-negative`. |
| `cash_limit` / `cash_limit_gbp` | `i64` | cents (currency × 100) | No | The member's allocation out of the desk's cash limit for that pool. `0`/omitted = no allocation: the member cannot add exposure there. `BAD_REQUEST` when it would push the pool's allocations past the desk's House limit, or when the exchange has reported no limit for that pool. |
| `delivery_areas` | `object` | none | No | `{"all": bool, "area_ids": [EIC]}`, both fields optional. Absent = no areas: the member can place no order until it is given some. Each id must be one of the gateway’s configured `epex_settings.delivery_areas`; duplicates collapse and the list is stored in the configuration’s order. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `result` | `Member` | cents / sub-MW | always | The created member, same shape as a [`get_members`](#cmd-get_members) entry; a fresh member has `*_consumed_cents` 0 and `*_remaining_cents` equal to its allocation. |

#### Errors

| Error code | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `manage_members`, or the licence does not enable desk management. |
| `BAD_REQUEST` | A missing or invalid member name, a `delivery_areas` id the gateway does not trade (the message names it and the configured list), `all: true` with `area_ids`, an allocation that would exceed the desk's House limit, or an allocation set before the exchange has reported a pool limit. |

The transport-wide codes (`UNAUTHENTICATED`, `RATE_LIMITED`, `INTERNAL`) may also occur; see the [Error reference](#errors).

#### Example

```json
{"action": "create_member", "req_id": "…", "name": "Desk A", "max_position": 5000,
 "cash_limit": 10000000, "cash_limit_gbp": 0,
 "delivery_areas": {"area_ids": ["10YNL----------L", "10YBE----------2"]}}
// → result: the created Member object, same shape as get_members; a fresh member has
//   *_consumed_cents 0 and *_remaining_cents == its allocation. Without
//   delivery_areas the member is created with none and can place no order.
```

### <a id="cmd-patch_member" name="cmd-patch_member"></a>`Command` `action "patch_member"`

Update a member; all update fields optional. Mirrors REST `PATCH /members/{id}` and gRPC `PatchMember`.

**Required permission:** `manage_members` and the desk-management licence. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `member_id` | `string` | none | Yes | UUID of the member to update. |
| `name` | `string` | none | No | New display name. |
| `max_position` | `i64` | sub-MW (MW × 1000) | No | New per-member per-contract limit. |
| `max_slot_position` | `i64 \| null` | sub-MW (MW × 1000) | No | The member's [slot position limit](#ops-slot-limit): omit it to leave it, `null` to remove it (no member slot limit), a number to set it (`0` = flat-only). Negative is `BAD_REQUEST` and changes nothing. |
| `cash_limit` / `cash_limit_gbp` | `i64` | cents (currency × 100) | No | New allocation out of the desk's limit. `0` takes it away entirely and always succeeds; raising it is `BAD_REQUEST` when the pool's allocations would then exceed the desk's House limit (the member's own current allocation is not counted against the value replacing it). |
| `active` | `bool` | none | No | Activate or deactivate the member. |
| `delivery_areas` | `object` | none | No | Replaces the member’s delivery areas whole, same shape and rules as on `create_member`; absent leaves them. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `result` | `object` | none | always | Empty object `{}` on success. |

#### Errors

| Error code | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `manage_members`, or the licence does not enable desk management. |
| `NOT_FOUND` | `member not found`: no member with that id, or the member is deleted. |
| `BAD_REQUEST` | A raised allocation that would push the pool's allocations past the desk's House limit; a `delivery_areas` id the gateway does not trade, or `all: true` with `area_ids`; or `delivery_areas` that would leave any of the member’s resting or pending orders outside it (`member … has N open orders in …; cancel them before removing the area`; nothing is written). |

The transport-wide codes (`UNAUTHENTICATED`, `RATE_LIMITED`, `INTERNAL`) may also occur; see the [Error reference](#errors).

#### Example

```json
{"action": "patch_member", "req_id": "…", "member_id": "…", "name": "…",
 "max_position": 6000, "cash_limit": 10000000, "cash_limit_gbp": 0,
 "active": false}
// cash_limit in cents: the member's allocation out of the desk's limit. 0 takes it
// away entirely and always succeeds; raising it is BAD_REQUEST when the pool's
// allocations would then exceed the desk's House limit (the member's own current
// allocation is not counted against the value replacing it).
// → result: {} on success
```

```json
{"action": "patch_member", "req_id": "…", "member_id": "…",
 "delivery_areas": {"all": true}}
{"action": "patch_member", "req_id": "…", "member_id": "…",
 "delivery_areas": {"area_ids": ["10YNL----------L"]}}
// delivery_areas replaces the member's areas whole; a patch without it leaves them.
// Removing an area while the member has open orders in it is BAD_REQUEST:
// "member VM002 has 1 open order in 10YBE----------2; cancel them before removing the area"
```

### <a id="cmd-delete_member" name="cmd-delete_member"></a>`Command` `action "delete_member"`

Delete a member. Refused while the member has a resting or unconfirmed pending order, a non-zero executed position on a contract whose delivery has not ended, or consumed cash still counted in the current exposure window (trades executed since the last booking cut): cancel the orders, flatten the positions, and wait for the cut. A deleted member takes no order (one naming it is refused `BAD_REQUEST` `v-member '…' not found`), is unassigned from every user, and leaves [`get_members`](#cmd-get_members) and every user's members; `patch_member`, a `set_user_members` naming it, or a second `delete_member` answers `NOT_FOUND` `member not found`, as for an unknown id. Its orders and trades stay in history and keep its name, and its short id is never given to another member. Audited as `member_deleted`. Mirrors REST `DELETE /members/{id}` and gRPC `DeleteMember`.

**Required permission:** `manage_members` and the desk-management licence. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `member_id` | `string` | none | Yes | UUID of the member to delete. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `result` | `object` | none | always | Empty object `{}` on success. |

#### Errors

| Error code | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `manage_members`, or the licence does not enable desk management. |
| `BAD_REQUEST` | `member … has N open orders; cancel them before deleting the member` (one order: `has 1 open order; cancel it`): resting or unconfirmed pending orders, checked first. `member … holds a position on N contracts whose delivery has not ended: … in …; flatten them before deleting the member`: each contract named by its catalogue name or as `contract <id>`, with its delivery area; a position that nets to zero, or one on a delivered contract, does not count. `member … has consumed cash counted until the next booking cut (EUR N cents, GBP N cents); delete it after the cut`: checked last, the consumed cash the member cash check reads, per non-zero pool, in cents. Any non-zero figure, a credit included, holds the delete until the cut; a credit is named `EUR credit N cents`, never with a minus sign, and each figure is rounded up to whole cents. `consumed cash cannot be fully priced yet; retry the delete`: the gateway's carried cash sums are not fully priced at that moment (a desk-wide state, not this member's), so the figure would be short; retry. Nothing changes. |
| `NOT_FOUND` | `member not found`: no member with that id, or the member is already deleted. |

The transport-wide codes (`UNAUTHENTICATED`, `RATE_LIMITED`, `INTERNAL`) may also occur; see the [Error reference](#errors).

#### Example

```json
{"action": "delete_member", "req_id": "…", "member_id": "…"}
// → result: {} on success
```

### <a id="cmd-list_permissions" name="cmd-list_permissions"></a>`Command` `action "list_permissions"`

The catalog of assignable permissions with human-readable descriptions. Render it; don't hardcode your own copy. Mirrors REST `GET /permissions` and gRPC `ListPermissions`.

**Required permission:** `manage_users` (not desk-gated). (see [Permissions](#permissions))

#### Request

This command takes no fields beyond the envelope's `action` and `req_id`.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `permissions` | `array of PermissionInfo` | none | always | Each entry is `{code, description}`. |

#### Errors

| Error code | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `manage_users`. |

The transport-wide codes (`UNAUTHENTICATED`, `RATE_LIMITED`, `INTERNAL`) may also occur; see the [Error reference](#errors).

#### Example

```json
{"action": "list_permissions", "req_id": "…"}
// → result: {"permissions": [{"code": "create_order", "description": "…"}, …]}
```

<a id="ops-audit" name="ops-audit"></a>

## Audit & reports

Cursor-paged reads from the store. Report exports are REST-only: request an order, trade or audit-trail file with [`POST /audit/export/orders`](rest_api_v1.md#post-export-orders), [`POST /audit/export/trades`](rest_api_v1.md#post-export-trades) or [`POST /audit/export/events`](rest_api_v1.md#post-export-events) and download it by token; there is no export command. Each read uses the standard request/response [envelope](#envelope); the result shapes below are the `result` body. On WebSocket the five paged audit reads share the one `audit_query` command, keyed by `entity`. The data matches the equivalent REST endpoint and gRPC RPC.

### <a id="cmd-audit_query" name="cmd-audit_query"></a>`Command` `action "audit_query"`

Cursor-paginated audit history from the store. `entity` selects the log: `orders`, `trades`, `public_trades`, `events`, or `m7_errors`, mirroring REST `GET /audit/{orders,trades,public_trades,events,m7_errors}` and the gRPC `QueryAudit*` / `QueryM7Errors` RPCs.

**For `entity=orders`: who wrote a row.** The order history records what the gateway observed. Each row carries `source`: `exchange` for a row parsed from an execution report the exchange sent, `gateway` for a row the gateway wrote because M7 no longer held the order when the gateway reconnected, so the outcome was not observed. Such a row sits above the last `revision` the gateway knew, with `order_state` inactive, `timestamp` the time the gateway noticed, and the `action` and `quantity` last known to the gateway. Read `source` before `action`. Fills are in `entity=trades` (no order-id filter: page a date range that covers the order's delivery, then take the trades whose `buy_json` or `sell_json` leg carries the order's id as `@ordrId`). Every login re-reads the fills of the current cash-exposure window from the exchange; an older fill is there only after `restore_trade_history` (permission `restore_trade_history`). Pre-arranged (OTC) orders are not closed this way. The full rule is under REST `GET /audit/orders`.

<a id="order-history-names" name="order-history-names"></a>**Coded columns are names.** Nine columns hold a value the exchange sends as a code. In every `entity=orders` row and every row of an orders export each one is a name wherever the code has one: where the live `orders` stream carries the field (`side`, `order_type`, `order_state`, `action`) it is the same word the stream uses, so an order reads the same in the stream, the history and the export, except for `0`, which the history writes as `"0"` and the stream reads as `UNKNOWN`. A code with no name is written as its number in text. In practice that is `"0"`: `0` is the exchange's unset value, and a value the exchange sends that this gateway does not know is stored as `0` too, so the row cannot say which value it was. A column the exchange left out is `null` (an empty cell in a CSV export). The `status` filter takes the `order_state` names. A trade row holds no codes: its `state` and `contract_phase` are the exchange's own text (`ACTI`, `CONT`), as on the live `trades` stream.

| Column | Names |
| --- | --- |
| `side` | `BUY`, `SELL` |
| `order_type` | `REGULAR`, `BLOCK`, `BALANCE`, `ICEBERG`, `STOP`, `EXCHANGE_PRE_ARRANGED`, `PRIVATE` |
| `order_state` | `ACTIVE`, `INACTIVE`, `HIBERNATED`, `UNKNOWN` (a state the exchange itself reports as unknown) |
| `action` | The exchange's four-letter action: `UADD`, `UHIB`, `UMOD`, `UDEL`, `UREJ`, `AADD`, `AHIB`, `AMOD`, `ADEL`, `AREJ`, `SADD`, `SHIB`, `SMOD`, `SDEL`, `SREJ`, `FEXE`, `PEXE`, `IADD`, `SERR`, `SNAV` |
| `aggressor_indicator` | `YES`, `NO`, `UNKNOWN` |
| `validity_restriction` | `NON`, `GFS`, `GTD`, the exchange's codes; order entry takes the same values in lower case |
| `order_execution_restriction` | `NON`, `AON`, `FOK`, `IOC`, the exchange's codes; order entry takes the same values in lower case |
| `open_close_indicator` | `OPEN`, `CLOSE` |
| `execution_instruction_type` | `NONE`, `VALID`, `LINKED` |

**For `entity=events`: lifecycle rows and lost writes.** Each clean shutdown ends the trail with a `system_shutdown` row, written once every queued write has been committed or counted lost. Its `after` is `{"writes_lost": {"audit": n, "m7_errors": n, "exchange_messages": n, "public_trades": n, "orders": n, "trades": n}}`: what that run lost, per stream. When a run ends without that row (a crash, a kill, a power loss), the next start writes a `system_unclean_exit` row (target `system`, outcome `ok`) just before its own `system_startup`. Its `after` names the previous run's start (`previous_startup_ts`, `previous_startup_ts_ms`) and `last_audit_id`, the `id` of the last row that run stored; writes that run still held in memory may be missing, and how many is not known. Row ids are assigned when a row is stored, so a gap in them is not how a loss shows: these two rows and `writes_dropped` are. The `system_startup` row's `after` records the trade-ingest fault policy the run started under: `{"trade_ingest_fault": "close" | "continue", "trade_ingest_fault_ack_ttl_sec": n}`.

**Required permission:** none for `orders`/`trades` (member-scoped; `read_orders` widens to firm-wide) · `read_audit` for `public_trades`/`events` · `read_m7_errors` for `m7_errors`. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `entity` | `string` | none | Yes | `orders` · `trades` · `public_trades` · `events` · `m7_errors`. |
| `cursor` | `string` | none | No | `null` on the first page; pass back the previous response's `next_cursor`. |
| `limit` | `u32` | count | No | Default 50, max 200; an explicit `limit=0` is rejected (`BAD_REQUEST`). |
| `filters` | `object` | none | No | Entity-specific filter set; see the examples below. |
| `filters.sort_order` | `string` | none | No | Page direction, honoured by every entity. `"DESC"` (the default) returns the newest rows first, `"ASC"` the oldest. Any other value is `BAD_REQUEST`. |
| `filters.time_basis` | `string` | none | No | `trades` only: which time `date_from`/`date_to` bound. `delivery` (the default, also for an empty value; the contract delivery window, overlap semantics: `delivery_end ≥ date_from` and `delivery_start ≤ date_to`) or `execution` (execution time), in any case. Any other value is `BAD_REQUEST`. Ignored for every other entity. |
| `filters.contract_id` | `string` | none | No | `trades` only: Filter to one contract by its M7 contract id, as the string the trade rows carry. An id no trade carries returns an empty page, not an error. An empty string is no filter. Ignored for every other entity. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `entity` | `string` | none | always | Echoes the queried entity. |
| `items` | `array` | none | always | The page of rows for the entity (order / trade / public-trade / event / m7-error shape). |
| `next_cursor` | `string\|null` | none | always | Feed back as `cursor` for the next page; `null` on the last page. |

#### Errors

| Error code | Condition |
| --- | --- |
| `PERMISSION_DENIED` | Missing `read_audit` (`public_trades`/`events`) or `read_m7_errors` (`m7_errors`); or a `v_member_short_id` filter naming a member the caller may not see. |
| `BAD_REQUEST` | An unknown `entity`, a malformed date filter or cursor, an explicit `limit=0`, an unrecognised `sort_order`, or (for `trades`) a `time_basis` other than `delivery` or `execution`, as `invalid time_basis '…': expected 'execution' or 'delivery'`. |

The transport-wide codes (`UNAUTHENTICATED`, `RATE_LIMITED`, `INTERNAL`) may also occur; see the [Error reference](#errors).

> [!NOTE]
> **Member scope (`orders`, `trades` and `events`).** The history is narrowed the same way the live `list_orders` is: a caller holding `read_orders` (or `bypass_member_check`) reads the firm-wide history; everyone else reads only the rows tagged with a virtual member assigned to them, with untagged rows withheld. A `v_member_short_id` filter narrows further inside that scope; naming a member the caller may not see returns `PERMISSION_DENIED`. For `events` the `read_audit` gate comes first, and only the order actions carry a member (`order_submitted`, `order_modified`, `order_cancelled`, `order_rejected`, `order_command_rejected`, in the row's `v_member_short_id`): every other row, a House order's included, is withheld from a member-scoped caller. The entities with no member column (`public_trades`, `m7_errors`, `exchange_messages`) are unaffected.
>
> **A trade between two of your own members.** When two virtual members of the desk trade with each other, a member-scoped caller finds the trade under either member and receives it as the row of an ordinary fill of that member's own leg: the other leg (`buy_json` or `sell_json`) `null`; `v_member_short_id`, `voltnir_user_id`, `voltnir_user_short_id`, `voltnir_username` and `delivery_area` those of the kept leg, exactly as on a fill of that leg against an outside counterparty; and `self_trade` `false`. `self_trade` is `false` for a member-scoped caller whenever it cannot see both legs, including on a trade only one half of which has arrived. Under a member scope the `delivery_area` and `voltnir_user_short_id` filters match only on a leg the caller may see, and `voltnir_username` names a current Voltnir user and matches the same way; an unknown name matches nothing. A caller holding `read_orders` (or `bypass_member_check`) receives the whole trade, whose member, Voltnir user and `delivery_area` are those of its buy leg when that leg belongs to a member, else of its sell leg, whichever half arrived last, and its filters match those. A member filter narrows even such a caller to that member's view, so the trade then reads as that member's own fill. The public trade tape is market data and is not narrowed: it carries the exchange's own self-trade flag and both legs' delivery areas under the same trade id. The desk is told of each such trade once, on the audit trail (`member_self_cross`).

> [!CAUTION]
> **No total count.** The `audit_query` and `list_exchange_messages` results carry no total-count field. Iterate by following `next_cursor` until it is `null`.

#### Example: orders / trades / public_trades

```json
{"action": "audit_query", "req_id": "…", "entity": "orders", "cursor": null,
 "limit": 100, "filters": {"date_from": "…", "date_to": "…", "area": "DE",
 "product": "H", "status": "ACTIVE", "user_code": "TRADER1", "v_member_short_id": "VM001",
 "voltnir_user_short_id": "U001", "voltnir_username": "j.doe",
 "sort_order": "DESC"}}
// → result: {"entity": "orders", "items": [...],
//            "next_cursor": "…" | null}
```

`user_code` = EPEX trader/user code; `voltnir_user_short_id` / `voltnir_username` attribute the submitting Voltnir user. A `contract_id` filter (string) is accepted for `entity: "trades"` only; every other entity ignores it. A trade's date window bounds its delivery period unless `time_basis` is `execution`, as REST `GET /audit/trades`. For `orders`, `status` is the order state M7 reported: `ACTIVE` (`ACTI`), `INACTIVE` (`INAC`, a deleted or fully filled order) or `HIBERNATED` (`HIB`), in any case. Absent or empty is no filter; any other value is refused with `BAD_REQUEST`, naming the accepted values. `REJECTED` is not an M7 order state: a plain order the exchange refuses has no row in this history, and its refusal is on the audit trail as `order_rejected`. A refused pre-arranged order, or a remote order that failed validation, keeps its rows, with the state M7 reported and the refusal as the row’s `action` (`UREJ`, `AREJ`, `SREJ` or `SERR`). `public_trades` uses only the date/`area`/`product`/`state` filters: `state` is the M7 trade state (`ACTI`, `CNCL`, see [Trade states](#trade-states)), as REST and gRPC name it, and is ignored for every other entity; `status` is ignored for `public_trades`. `sort_order` applies to every entity including `public_trades`. A `trades` row carries the [recall fields](#recall-fields) as the `trades` stream does, with the same names and values.

#### Example: events

**`entity: "events"`** queries the compliance audit-event log, the append-only who-did-what record of actor-driven mutations (user/permission/member/limit changes, kill-switch and self-trade toggles, every order submit / modify / cancel and the rejections, report exports, system/license lifecycle). It uses the events-only filters `action` / `target_type` / `actor_short_id` / `outcome` (`ok` · `denied` · `error`; plus the shared date/ cursor/limit and `v_member_short_id`, inside the member scope above). Each item carries the actor, transport, source IP, `before`/`after` snapshots, outcome, reason and `v_member_short_id` (the member of the order an order action is about, `null` otherwise).

```json
{"action": "audit_query", "req_id": "…", "entity": "events", "cursor": null,
 "limit": 100, "filters": {"action": "permissions_set", "target_type": "user",
 "actor_short_id": "U001", "outcome": "ok", "date_from": "…", "date_to": "…"}}
// → result: {"entity": "events", "items": [{"ts": "…", "actor_short_id": "U001",
//            "transport": "ws", "action": "permissions_set", "target_type": "user",
//            "before": [...], "after": [...], "outcome": "ok",
//            "source_ip": "203.0.113.7", ...}],
//            "next_cursor": "…" | null}
```

**Order actions.** Every accepted order action appends exactly one row: `order_submitted` when a placement is accepted and the exchange does not refuse it, `order_modified` when a modify / activate / deactivate is acknowledged, `order_cancelled` when a single-order cancel is acknowledged, and `order_rejected` when the placement is refused, by the pre-trade gate before it is published, or by the exchange after it acknowledged receipt (with the reason: `position_limit_exceeded`, `slot_position_limit_exceeded`, `slot_window_unknown`, `cash_limit_exceeded`, `self_cross_blocked`, `trading_disabled`, `load_management_throttled`, `member_area_not_allowed`, `exchange_rejected`). A `member_area_not_allowed` row, written for a refused placement, modify or cancel, carries an `after` of `member` and `area`. An `exchange_rejected` row carries the `after` snapshot the placement was published with, plus `state: "REJECTED"` and the exchange's own words in `exchange_reason`. A slot-limit refusal (`slot_position_limit_exceeded` or `slot_window_unknown`), of a placement or of a modify or activation, carries an `after` with the refusal's own fields, because its reason alone does not say which bound was hit: `delivery_area`; then, for `slot_position_limit_exceeded`, `slot_start_ms` and `slot_end_ms` (UTC epoch milliseconds), `side` (`long` or `short`), `scope` (`house` or the member's short id), `bound_after` (sub-MW, positive long, negative short) and `limit` (sub-MW); and, for `slot_window_unknown`, one of `order_contract_id`, `open_order_contract_id` or `trade_id`, naming what has no delivery window. A caller holding none of `read_orders`, `bypass_member_check` and `read_status` is shown such a row as the refusal itself is shown to it: a `house`-scope breach without `bound_after` and `limit`, and a trade with no window without its `trade_id`. The stored row keeps them, so a `read_status` holder and a firm-wide reader read them. Every other gate refusal carries no `after` snapshot, because nothing reached the exchange. `target_id` is the `client_order_id`. The `before` / `after` snapshots carry `v_member_short_id`, `delivery_area`, `contract_id`, `side`, `price_cents` and `quantity_sub_mw`, plus `state` on a submit and `modify_action` on a modify. `cancel_all_orders` stays a single `order_cancel_all` row and does not fan out into a row per order: `after: {"deleted": n}` on success; on a failure, outcome `error` with the failure as `reason`, plus `after: {"deleted": <acknowledged>, "targeted": <targeted>}` when a member-scoped cancel fails part-way. A report export, made over REST, writes one `report_exported` row once the request is decided: outcome `ok` when it is accepted, outcome `error` when it is refused, with the refusal text, or `export_busy` when another export was generating, as `reason`.

**Slot limit in `observe`.** An order the slot position limit would refuse is admitted, and recorded as a `slot_limit_would_refuse` row (system actor, target type `order`, no target id, outcome `ok`). Identical would-refusals (same reason, delivery area, slot, scope and side) within 10 seconds are one row. Its `after` carries the refusal's fields as an `order_rejected` row of the same refusal would, plus `reason` (`slot_position_limit_exceeded` or `slot_window_unknown`), `contract_id`, `order_side` (`BUY` or `SELL`), `quantity` (sub-MW, the size the order asked for), `member` (the member's short id, or `null` for a House order), `count` (how many would-refusals the row stands for) and `window_s` (`10`). The row is written when its 10-second window closes, or at a clean shutdown if that comes first.

**Trade recalls.** A recall appends rows with target type `trade` and the exchange trade id as target. `trade_recall_requested` (by the caller) when a sent recall was not refused at its receipt, its `after` carrying `revision_no`, `state`, `receipt` (`acknowledged` or `unknown`), `correlation_id` and `parent_trade_id`. `trade_recall_refused` (outcome `error`, by the caller) once per refusal: `recall_not_possible` or `trade_changed` for the gateway's own refusals, `exchange_refused` with `m7_err_code`, `m7_error_key` and `exchange_reason` for the exchange's, before or after its receipt, and `not_processed` for a request handed back undelivered. `trade_recall_resolved` (system actor) once per trade, the first time the gateway sees it `RGRA` or `RREJ`, carrying the state, revision and the recall times and `recall_requestor` as the exchange reported them, and `first_seen_resolved`. It is written for a recall asked outside the gateway too, with no `trade_recall_requested` row before it, and for a trade first seen already decided at login, with `first_seen_resolved: true`.

**Trades between two of the desk's members.** When two virtual members of the desk trade with each other, the gateway appends one `member_self_cross` row (system actor, target type `trade`, target id the trade id) whose `after` snapshot carries `trade_id`, `contract_id`, `qty` (sub-MW), `px` (cents), `buy_member_short_id` and `sell_member_short_id`. A member-scoped reader of the trade sees only its own leg, so this row is where the desk sees the cross whole: it names no one member, so it is readable with `read_audit` by a caller who also holds `read_orders` or `bypass_member_check`, and the matching warning-level log line reaches holders of `read_logs` when the log level includes warnings; neither reaches the trade streams, contract detail or trade history of a member-scoped caller. A trade already on the trail is not recorded again, also after a restart; a failed lookup of the trail records it rather than lose it.

**Refusals.** A refused credential writes an `auth_failed` row, a refused permission (or a desk-gated command on a trader license) writes `permission_denied`, and crossing the per-key request bound writes `rate_limited`, all with `outcome` `denied` and `target_type` `auth`. `reason` is the permission's code, `license_desk_required`, `member_scope` when the caller holds the permission but asked for a virtual member it is not assigned to, or why the credential failed (`invalid_token`, `missing_credentials`, `malformed_request`, `auth_timeout`), never the credential itself. `auth_failed` and `rate_limited` are written at most once per source per minute, so a client in a retry loop cannot flood the trail. The source of every row a connection writes is resolved once, at the upgrade: the connection's peer address, unless that peer is listed in `system.trusted_proxies`, in which case it is the client the proxy named in the upgrade request's `X-Forwarded-For`, read from the right.

#### Example: m7_errors

**`entity: "m7_errors"`** queries the M7 exchange-error log, the append-only record of M7-side faults off the AMQP line. **Gated by `read_m7_errors`** (not `read_audit`). Uses the m7-errors-only filters `kind` / `category` / `err_code` (plus the shared date/cursor/ limit). `err_resp` rows are enriched from the official EPEX SPOT M7 API documentation with a human `err_identifier` + `category`; the other kinds (`parse_error`, `unknown_type`, `ack_uncorrelated`, `seq_gap`) carry no code/category. One exchange error response can carry several errors, since the exchange refuses a request that names several orders with a single response listing each refusal. Each error is its own `err_resp` row with its own `err_code`, `err_text` and `cl_ordr_id`, and `raw_payload` holds the whole response. The refused order is told the texts of the errors that name it, joined with `;`, and their code only when they share one. An error response the gateway cannot read is a `parse_error` row carrying the raw response, and the request it answered is still reported refused.

```json
{"action": "audit_query", "req_id": "…", "entity": "m7_errors", "cursor": null,
 "limit": 100, "filters": {"kind": "err_resp", "category": "limits",
 "err_code": 1149, "date_from": "…", "date_to": "…"}}
// → result: {"entity": "m7_errors", "items": [{"received_at": "…", "kind": "err_resp",
//            "category": "order_entry", "err_code": 1149,
//            "err_identifier": "order_rejected_self_trade_protection",
//            "err_text": "…", "cl_ordr_id": "…", "var_list": [...],
//            "severity": "error", ...}],
//            "next_cursor": "…" | null}
```

### <a id="cmd-list_exchange_messages" name="cmd-list_exchange_messages"></a>`Command` `action "list_exchange_messages"`

Cursor-paginated history of the exchange-message log, the append-only record of what the exchange said. Mirrors REST `GET /audit/exchange_messages` and gRPC `ListExchangeMessages` field for field, including the paging contract.

**Required permission:** `read_m7_errors`, the same permission as the M7-error log; no new permission. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `cursor` | `string` | none | No | `null` on the first page; pass back the previous response's `next_cursor`. |
| `limit` | `u32` | count | No | Default 50, max 200; an explicit `limit=0` is rejected (`BAD_REQUEST`). |
| `filters.date_from` / `filters.date_to` | `string` | RFC 3339 | No | Bounds on receive time. |
| `filters.severity` | `string` | none | No | `urgent` · `error` · `high` · `medium` · `low` · `unknown`. |
| `filters.scope` | `string` | none | No | `public` (market-wide) or `private` (this member). |
| `filters.code` | `i64` | none | No | Vendor message code, e.g. `158`. |
| `filters.sort_order` | `string` | none | No | Page direction; see [`audit_query`](#cmd-audit_query). Default `"DESC"`, newest first. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `items` | `array of ExchangeMessage` | none | always | The page of exchange messages. `id` is the backend row id (`null` on a streamed-but-not-stored message); `msg_id` is the exchange's own stable de-duplication key; `key` is `null` for a code the catalogue does not list; `text` is the exchange's template with placeholders substituted from `vars`, with every instant inside a variable restated in UTC, RFC 3339 with `Z`; `vars` keeps the exchange's own spelling. |
| `next_cursor` | `string\|null` | none | always | Feed back as `cursor`; `null` on the last page. |

#### Errors

| Error code | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `read_m7_errors`. |
| `BAD_REQUEST` | A malformed date filter or cursor, or an explicit `limit=0`. |

The transport-wide codes (`UNAUTHENTICATED`, `RATE_LIMITED`, `INTERNAL`) may also occur; see the [Error reference](#errors).

#### Example

```json
{"action": "list_exchange_messages", "req_id": "…", "cursor": null, "limit": 100,
 "filters": {"severity": "error", "scope": "private", "code": 158}}

// → result: {"items": [{"id": 4187, "received_at": "…", "exchange_ts": "…",
//    "msg_id": 90210, "scope": "private", "code": 158,
//    "key": "cash_limit_breached_member", "severity": "error",
//    "text": "Cash limit in GBP breached! …", "product": null,
//    "account_id": "10XDE-BG-------W", "buy_area": null, "sell_area": null,
//    "market_supervision": false, "vars": [{"id": 6, "value": "GBP"}]}],
//    "next_cursor": "…"}
```

The messages that are never stored, the ones the exchange marks non-persistent, and the per-contract lifecycle broadcasts (codes `74`, `76` and `77`), are streamed on [`exchange_messages`](#stream-exchange_messages) only, so they never appear in this result.

### <a id="cmd-list_system_log" name="cmd-list_system_log"></a>`Command` `action "list_system_log"`

A page of the **gateway's own diagnostic log**. Mirrors REST `GET /system/logs` and gRPC `ListSystemLog` field for field, including the paging contract.

**Required permission:** `read_logs`, the dedicated log permission, not `read_m7_errors`, which is about the exchange's side of the line. (see [Permissions](#permissions))

**Not an audit record.** The buffer is a bounded in-memory ring: capped by entry count first (a configured entry-count cap, default 20,000) and age second (an age cap, default 24 hours), lost on every restart, and lossy under load. Read the `buffer` block on the result before presenting it. Entries are returned **oldest-first**, and the cursor is the entry's own `seq`, not an opaque token.

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `cursor` | `u64` | none | No | Return entries whose `seq` is greater than this. `null` (or absent) returns the newest page. |
| `limit` | `u32` | count | No | Default 50, max 200; an explicit `limit=0` is rejected (`BAD_REQUEST`). |
| `min_level` | `string` | none | No | `error` · `warn` · `info` · `debug`. An unrecognised value is rejected (`BAD_REQUEST`) rather than ignored, a silently dropped filter would make a quiet panel look like a healthy gateway. |
| `date_from` / `date_to` | `string` | RFC 3339 | No | Inclusive bounds on capture time. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `items` | `array of SystemLogItem` | none | always | Log entries, oldest-first. Each `message` is truncated at 4 KiB with the cut marked in the text. |
| `next_cursor` | `u64\|null` | none | always | The last entry's `seq`; `null` on an empty page. |
| `truncated` | `bool` | none | always | `true` when your resume point had already been evicted, so this page resumes from the oldest surviving entry. |
| `buffer` | `object` | none | always | Ring diagnostics: `enabled`, `level`, `capacity`, `len`, `oldest_seq`, `oldest_ts_ms`, `newest_seq`, `started_at_ms` (how far back the buffer reaches) and `dropped` (entries evicted by capacity or age). The three `*_seq`/`*_ts_ms` fields are `null` on an empty ring. |

#### Errors

| Error code | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `read_logs`. |
| `BAD_REQUEST` | An explicit `limit=0`, or an unrecognised `min_level`. |

The transport-wide codes (`UNAUTHENTICATED`, `RATE_LIMITED`, `INTERNAL`) may also occur; see the [Error reference](#errors).

#### Example

```json
{"action": "list_system_log", "req_id": "…", "cursor": null, "limit": 100,
 "min_level": "warn"}

// → result: {"items": [{"seq": 18344, "ts_ms": 1788610323180, "level": "warn",
//     "target": "voltnir_backend m7 amqp connection",
//     "message": "AMQP connection lost, reconnecting in 5s"}],
//    "next_cursor": 18344, "truncated": false,
//    "buffer": {"enabled": true, "level": "info", "capacity": 20000,
//      "len": 20000, "oldest_seq": 12346, "oldest_ts_ms": 1788592000000,
//      "newest_seq": 18345, "started_at_ms": 1788500000000,
//      "dropped": 12346}}
```

<a id="streaming" name="streaming"></a>

## Streaming

Live push. Subscribe and unsubscribe with control messages. A successful subscribe gets no response envelope: the data arrives as stream frames; only a *denied* subscribe on a permission-gated stream is answered with an error envelope (`op: "subscribe"`), and an open gated stream whose permission is revoked is closed with the same envelope.

```json
{"action": "subscribe", "stream": "<name>"}     // contracts also takes
                                                //   "areas": [...], "products": [...],
                                                //   "contract_ids": [...]
                                                // public_trades also takes
                                                //   "contract_ids": [...]
                                                // slot_positions takes
                                                //   "delivery_area", "from_ms", "to_ms",
                                                //   "v_member_short_id"
{"action": "unsubscribe", "stream": "<name>"}
```

Every stream is opt-in: nothing is pushed until you subscribe to it. Streams marked *no permission* are open to any authenticated caller; streams carrying a permission tag are additionally gated server-side at subscribe.

<a id="stream-gated-close" name="stream-gated-close"></a>**A gated stream closes when its permission is revoked.** The gateway re-reads the caller’s permissions on every command and whenever a user, permission or member assignment changes. When the permission an open `audit`, `m7_errors`, `exchange_messages`, `system_log` or `state` stream needs is gone, the stream stops at once: nothing more of it is sent, rows already queued for the next frame included. The connection receives the envelope a refused subscribe gets, with the stream and the permission beside the error triple, and the refusal is written to the audit trail as a `permission_denied` row (operation `subscribe`, the permission as its reason). Revoking `read_m7_errors` closes both `m7_errors` and `exchange_messages`. The connection stays open and every other stream keeps running; once the permission is granted back, subscribe again.

```
// server → client (text), a refused subscribe or a closed stream alike
{"type": "response", "op": "subscribe", "ok": false,
 "error": {"code": "PERMISSION_DENIED", "http_status": 403, "grpc_status": "PermissionDenied",
           "message": "caller lacks read_audit permission",
           "stream": "audit", "permission": "read_audit"}}
```

Stream frames are zstd-compressed binary, tagged by `"stream"`. Most send a `snapshot` (full current state) on first subscribe, then `deltas` thereafter; both fields are omitted when empty to save bytes (a frame with neither is a heartbeat; only the `contracts` stream emits these, every tick). Every frame carries `sent_at_ms` for latency measurement. Field-level semantics of the payload objects (`OwnOrder`, `OwnTrade`, `AreaContract`, `PnlSnapshot`, and the rest) match the REST responses of the same name.

**Streaming has no REST peer.** WebSocket streams correspond to the gRPC `Watch*` RPCs by data, not shape: `contracts` is `WatchContracts` (the same filter), `orders` is `WatchOrder` / `WatchOrders`, `trades` is `WatchTrades`, `messages` is `WatchMessages`, `pnl` is `WatchPnl`, `slot_positions` is `WatchSlotPositions`, `status` is `WatchStatus`, `state` is `WatchState`, `public_trades` is `WatchPublicTrades`, `trade_tape` is `WatchTradeTape`, `audit` is `WatchAuditEvents`, `m7_errors` is `WatchM7Errors`, `exchange_messages` is `WatchExchangeMessages`, `system_log` is `WatchSystemLog`, and the `watch_hub2hub` command's stream is `WatchHub2Hub`. Every live stream has a gRPC peer.

### <a id="stream-orders" name="stream-orders"></a>`Stream` `orders`

_no permission_

Your orders, split by lifecycle. Re-sent in full whenever any order changes.

#### Frame

```json
{"stream": "orders", "orders_acknowledged": [OwnOrder…],
 "orders_pending": [PendingOrder…], "sent_at_ms": 1718…}
```

**Scoping.** Every `orders` frame is narrowed to what the connection's caller may see, exactly like the [`list_orders`](#cmd-list_orders) command (no member filter). A caller holding `read_orders` (or `bypass_member_check`) receives the firm-wide order book; everyone else receives only the orders tagged with a virtual member assigned to them, with untagged house orders withheld.

#### Refusal frame

```json
{"stream": "orders", "type": "rejected", "reason": "ValDate cannot be in the past.",
 "rejected_action": "modify", "err_code": 1070, "orders": [OwnOrder], "sent_at_ms": 1718…}
```

**Attribution.** A record carries the virtual member and the Voltnir user behind it twice over: `v_member_short_id` / `v_member_name` and `voltnir_user_short_id` / `voltnir_username`. The short ids are what the audit endpoints filter on; the names are what a person reads. All four are empty for a record from another gateway, a colleague's on the same membership, whose tags that gateway wrote and which are deliberately not read here, or anything not placed through Voltnir, leaving the exchange `user_code` as the only attribution such a row carries. An order on the house account names a user and no member. A deleted user keeps its short id and its username, and a deleted member its short id and its name; neither short id is ever given to another user or member, so a filter by a user's short id or username, or by a member's short id, finds only that user's or member's records. A trade the gateway reloads from its store after a restart carries the names the directory holds at that moment, as a live trade does, so a renamed user or member shows the new name.

**Baskets.** An order entered in a basket carries `basket_ref`, the basket reference, read back from the order’s own text, so it survives a gateway restart; it is empty for an order not entered in a basket, and is read only on the login user’s own orders. `list_exec_inst` is the exchange’s own list instruction for the order: `none`, `valid` or `linked`, empty when the report names none. `basket_id` is the exchange’s basket id, reported only for a basket of two or more orders.

**Recognising your order in a public order book.** A book row names an order by id, and which id that is depends on the book. A local book lists the order under `order_id`; a remote (XBID) book lists it under `remote_order_id`, which the shared order book assigns and which bears no relation to `order_id`. `remote_order_id` is `null` for an order on a local contract. Match a book row against **either** id: a remote book published EPEX-originated orders under the local id before M7 6.22 and under the remote id from 6.22, so matching `order_id` alone leaves your own resting orders looking like strangers’ on the newer release. The same field is on REST `GET /api/v1/orders` and gRPC `OwnOrder`.

**A modify or cancel the exchange refuses after acknowledging receipt**, and a refused `ack_only` submission, arrives on this same `orders` stream as a frame carrying `type: "rejected"`. `orders` holds the unchanged order (do not mutate your state from it), `reason` the exchange's own words, `rejected_action` the refused action (`submit` / `modify` / `activate` / `deactivate` / `cancel`) and `err_code` the exchange's numeric code (omitted when it sent none). The field names mirror the gRPC `OrdersEvent` `REJECTED` event. It is emitted whether or not a caller was waiting on the outcome, so an `ack_only` caller learns of the refusal here. Snapshot frames (above) never carry `type`.

### <a id="stream-trades" name="stream-trades"></a>`Stream` `trades`

_no permission_

Your fills. Snapshot on subscribe, then per-`trade_id` deltas. Each `OwnTrade` carries an `attribution` field: `"full"` when the exchange's trade report parsed completely, or `"partial"` when only the trade's financial core (quantity, price, execution time, contract) could be read and per-leg attribution may be incomplete, a `partial` trade is financially final: report it, no action.

#### Frame

```json
{"stream": "trades", "snapshot": [OwnTrade…] | absent,
 "deltas": [OwnTrade…], "sent_at_ms": 1718…}
```

**Scoping.** Every `trades` frame, the subscribe snapshot, each delta, and the fresh snapshot sent when the connection falls behind, is narrowed exactly like the [`orders`](#stream-orders) stream. A caller holding `read_orders` (or `bypass_member_check`) receives every member's trades plus the untagged house-account trades; everyone else receives only the trades tagged with a virtual member assigned to them. A caller with no assigned members receives an empty snapshot and no deltas. A change to the caller's member assignment applies to deltas from then on. A trade between two virtual members of the desk reaches a member-scoped caller as the ordinary fill of its own leg: only the leg its members placed, carrying that leg's own member, member name, Voltnir user and user name exactly as a fill against an outside counterparty would, with the other leg, its member and its Voltnir user withheld; a caller holding `read_orders` (or `bypass_member_check`) sees both legs. The exchange reports such a trade in two halves; when the other member's half lands, a member-scoped caller whose view of the trade it leaves unchanged is not sent the trade again. A later change to its own view (a new state or revision) is sent. A caller holding `read_orders` receives the trade on each half.

**What the snapshot holds.** It holds the trades of the current cash-exposure window (since the most recent 16:00 booking cut on an ECC business day) and every trade on a contract whose delivery day, in its market's local time, is today or later. A trade recorded without its delivery window is kept for up to seven days after it executed. Earlier trades come from the trade history: [`audit_query`](#cmd-audit_query) with `entity: "trades"`. A trade that leaves this set is not announced on the stream; it is absent from the next snapshot.

#### <a id="recall-fields" name="recall-fields"></a>Recall fields

Each `OwnTrade` carries these fields as the exchange sent them, each `null` until it applies. A later revision of the trade that omits one keeps the value already reported. Times are in the format the exchange sends, as `exec_time` is.

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `recall_req_time` | `string \| null` | date-time | optional | When a recall of the trade was requested. |
| `recall_granted_time` | `string \| null` | date-time | optional | When market operations granted the recall. The exchange also sets it when market operations cancel the trade. |
| `recall_rejected_time` | `string \| null` | date-time | optional | When market operations rejected the recall. |
| `latest_recall_process_time` | `string \| null` | date-time | optional | Until when market operations can process a recall request. It is a live deadline while a recall is pending (`state` `RREQ` or `RSFA`). |
| `recall_requestor` | `string \| null` | none | optional | Member id of the party that asked for the recall. The exchange sends it to the balancing group of the requesting party when that party is a member known to the exchange. |
| `parent_trade_id` | `string \| null` | none | optional | For a cross-contract trade, the id of its parent trade. The parent itself is never reported. Recalling a trade that carries a `parent_trade_id` recalls the parent and every trade with the same `parent_trade_id` at once. |
| `prearrange_type` | `string \| null` | none | optional | `OTC` for a pre-arranged trade, which cannot be recalled. `OPT` and `PNC` are deprecated exchange values. |

#### <a id="trade-states" name="trade-states"></a>Trade states

A trade counts for position, cash and P&L in every `state` but `RGRA` and `CNCL`, including a code not listed here.

| State | Meaning |
| --- | --- |
| `ACTI` | Active. |
| `RREQ` | Recall requested. The trade still counts. |
| `RSFA` | Recall sent for approval to the XBID shared order book (SOB). The trade still counts. |
| `RREJ` | Recall rejected by market operations. The trade stands. |
| `RGRA` | Recall granted by market operations. The trade is reversed and no longer counts. |
| `CREQ` | Cancellation requested from market operations. The trade still counts. |
| `CREJ` | Cancellation rejected by market operations. The trade stands. |
| `CNCL` | Cancelled by market operations. The trade is reversed and no longer counts. |

### <a id="stream-messages" name="stream-messages"></a>`Stream` `messages`

_no permission_

System and order-rejection messages. Snapshot then new-message deltas. An `order_executed` entry is written once per side of a trade, when that side first reaches the gateway; a later state change of the trade (a recall or a cancellation), a re-delivery of a trade the gateway still holds, or a side that reaches the gateway on a trade the exchange has already reversed (`RGRA` or `CNCL` in the newest revision the gateway holds, as the login backfill can return a trade the exchange reversed while the gateway was not connected) writes none. The gateway holds every trade in the cash-exposure window and every trade on a contract delivering today or later, so an older trade brought back by `restore_trade_history`, or by the login's inquiry for the trades the exchange updated while the gateway was not connected, is written again unless the exchange has since reversed it.

#### Frame

```json
{"stream": "messages", "snapshot": [SystemMessage…] | absent,
 "deltas": [SystemMessage…], "sent_at_ms": 1718…}
```

**Scoping.** Every order entry (`order_added`, `order_modified`, `order_deleted`, `order_hibernated`, `order_executed`, `order_rejected`) belongs to the virtual member of the order or trade leg it describes, and is narrowed exactly like the [`orders`](#stream-orders) stream, on the snapshot and on every delta. A caller holding `read_orders` (or `bypass_member_check`) receives every entry, the untagged house-account ones included; everyone else receives only the entries of the virtual members assigned to them. A refusal that names no member, such as an undeliverable request no order is waiting on, is a house-account entry. `license_notice`, `throttling_notice` and `m7_client_cert_notice` are about the whole login and reach every caller. A caller with no assigned members receives only those three kinds. An `m7_client_cert_notice` is written when the M7 client certificate crosses 30, 14, 7 or 1 days before expiry, expires, is not yet valid, cannot be read, or is valid again after a replacement. A `slot_limit_notice` names a trade with no delivery window and the delivery area it locks for the slot position limit, once per trade per run (in `observe` and `reject`); it carries no member, so it is a house-account entry. A slot-limit `order_rejected` entry tagged with a member reaches that member's readers, so it reads as a caller without `read_status` is told (see `SLOT_POSITION_LIMIT_EXCEEDED` and `SLOT_WINDOW_UNKNOWN` under error codes); a house-account one keeps every figure. A trade between two virtual members of the desk logs one `order_executed` per leg, and each member receives only its own. A change to the caller's member assignment applies to deltas from then on; an entry already withheld is not sent later.

### <a id="stream-status" name="stream-status"></a>`Stream` `status`

_1 Hz_

The caller-scoped trading-posture aggregate, streamed. The streaming companion of the unary [`get_status`](#cmd-get_status) command / REST `GET /status` / gRPC `GetStatus`; the gRPC `WatchStatus` RPC is its streaming twin.

> [!NOTE]
> Open to every authenticated caller. Each frame is re-projected per caller, the base posture and the caller's own `accounts` always, the desk-wide money and full licence only with `read_status` (those keys are absent from the frame otherwise). Because the projection is per frame, a member reassigned, deactivated or re-limited shows on the next tick.

#### Frame

```json
{"stream": "status", "throttling": {…}, "trading_enabled": true,
 "operational": true,
 "license_summary": {"status": {"kind": "active"}, "expires_at": "2027-01-01T00:00:00Z", "mode": "desk"},
 "accounts": [{"is_house": true, "position_limit": 50000, "effective_position_limit": 50000,
               "eur_limit_cents": 10000000, "eur_consumed_cents": 3500000, "eur_remaining_cents": 6500000,
               "gbp_limit_cents": 0, "gbp_consumed_cents": 0, "gbp_remaining_cents": 0}],
 // the keys below are present only with `read_status`
 "cash_limits": {…}, "order_pos_limit": 50000,
 "cash_limit": {
   "eur_limit_cents": 10000000, "eur_consumed_cents": 3500000, "eur_remaining_cents": 6500000,
   "gbp_limit_cents": 0,        "gbp_consumed_cents": 0,       "gbp_remaining_cents": 0
 },
 "license": {…},
 "stranded_pending_count": 0, "stranded_pending_qty": 0,
 "claims_count": 0, "claims_qty": 0, "claims_held_count": 0, "claims_held_qty": 0,
 "m7_client_cert": {"status": {"kind": "valid"}, "not_after": "2027-03-01T12:00:00Z"},
 "sent_at_ms": 1718…}
```

`license_summary` (base) carries only `status` (the tagged `{kind, days?}`), `expires_at`, and `grace_end` (present only while `in_grace`), what an expiry banner needs, and `mode`, the licence tier (`"trader"` or `"desk"`), so a client hides the management screens a trader licence refuses; none of the holder / identity / provenance the full `license` block has. Each `accounts` entry is an account the caller may trade for, the House account (`is_house: true`, with `trade_global`) or an assigned active member (`short_id` + `name`). `position_limit` is the account's own per-contract limit (sub-MW); `effective_position_limit` is what binds an order on it, `min(order_pos_limit, max_position)` for a member, since the House and member limits stack. A `0` limit or allocation is flat-only, carried as `0`, never dropped. `slot_limit` is the account's [slot position limit](#ops-slot-limit) (sub-MW): the House slot limit for House, the member's `max_slot_position` for a member; it is absent for a member with no slot limit, and on the House entry for a caller without `read_status`, which is not shown the House slot figures anywhere. `slot_mode` is the slot limit mode (`off`, `observe` or `reject`), the same on every account. Each entry's six `*_cents` fields are its own cash: a member's allocation/consumed/remaining, or for the House account what bounds an untagged order, `*_limit_cents` the House remainder (desk limit minus member allocations, negative when over-allocated), `*_consumed_cents` the untagged book's own exposure, and `*_remaining_cents` the headroom admission allows (the tighter of that remainder and the aggregate desk guard). This is distinct from the `read_status`-only `cash_limit` block, which is the desk-wide view.

`cash_limit` is the **desk cash-limit state**: the effective House limit, current consumption, and remaining headroom per currency pool, in cents (`remaining = limit − consumed`; `*_limit_cents == 0` means no order may add exposure in that pool). Exposure is summed exactly and rounded once: `*_consumed_cents` rounds up and `*_remaining_cents` rounds down from the exact figure, matching the exchange's own remaining limit to the cent, so `limit − consumed = remaining` holds exactly. `eur_pool` / `gbp_pool` carry where that limit came from, the ECC limit with its revision and effective date, what the exchange still has available, the operator cap, the allocation split (`allocated_cents` / `unallocated_cents`), and the `over_allocated` / `cap_above_ecc` / `breached` / `stale` flags, in the same shape [`get_cash_limit`](#cmd-get_cash_limit) returns. Distinct from `cash_limits`, the raw M7-reported feed. Cash-limit order bounces arrive on the [`messages`](#stream-messages) stream as order-rejection entries.

`cash_limit.delivery_risk_applied` (bool) says whether the GB delivery-risk add-on (a risk set's price-independent `alpha` per MWh on GB sells, or the configured GBP fallback rate) is charged in the GBP figures. The exchange charges it only to a member whose record says so, and states that record only when it changes, never on request. `cash_limit.delivery_risk_source` is `"exchange"` once this member's own record has been seen, in this session or stored from an earlier one, and `"config"` while the gateway's `cash_limit.delivery_risk_applied` setting decides (default `true`, charged). With it `false`, a GB order or trade is priced with its product's default risk set, the set the exchange prices such a member's GB legs with, instead of the GB delivery-risk set; with it `true`, with the GB set and its add-on, a pricing that has not been measured against the exchange. A change of the flag re-prices every open order and every trade in the exposure window at once. The source is always one of those two strings, never empty. Same fields and meaning as REST `GET /status` and gRPC `GetStatus`.

`stranded_pending_count` and `stranded_pending_qty` are the **held pending headroom**: new orders past their expiry bound with no answer from the exchange, where the gateway cannot rule out a missed report or a late XBID answer, so they keep consuming position and cash headroom until their report or refusal, the first order snapshot after the bound, a restart, or about an hour after their contract’s delivery ends. Each one is announced once on the [`messages`](#stream-messages) stream when it is held; these two are the running total afterwards. `stranded_pending_qty` is in **sub-MW**, the unit `order_pos_limit` and every order quantity use. Both are `0` on a healthy gateway; a non-zero pair means the limits are short by that much with no resting order to show for it, and is the figure to weigh a [`restart`](#cmd-restart) against, a restart re-reads the book from the exchange and releases every hold.

`claims_count` and `claims_qty` are the amendments and activations whose added exposure (a larger size, a costlier price, an activation’s whole returning size) counts against the limits from admission until the exchange answers them or their expiry bound passes; `claims_held_count` and `claims_held_qty` are those held past the bound, for the same reasons and until the same events as a held new order, each announced once on the [`messages`](#stream-messages) stream. Quantities are in **sub-MW**. A claim in flight is normal for the moments after an amendment; a non-zero held pair is headroom lost to commands the exchange has not answered.

`throttling` is the same object [`get_throttling`](#cmd-get_throttling) returns: M7's order load-management report plus this gateway's own `guard`. Watch `guard.headroom` to pace a burst, and `guard.blocked_reason` to know why order actions are bouncing with `LOAD_THROTTLED`. A change in M7's member status also lands on the [`messages`](#stream-messages) stream as a `throttling_notice` entry.

`m7_client_cert` (`read_status`) is the M7 client certificate’s expiry, the same object [`get_status`](#cmd-get_status) describes. The gateway reads the file at startup and every hour, so a replacement shows here within the hour; each change of state also lands on the [`messages`](#stream-messages) stream as an `m7_client_cert_notice` entry.

### <a id="stream-pnl" name="stream-pnl"></a>`Stream` `pnl`

_1 Hz_

Per-contract, per-(area,product), and per-virtual-member P&L. A snapshot computed at subscribe, then one frame per second: the desk's P&L is computed once a second and the same snapshot goes to every `pnl` subscriber and every gRPC `WatchPnl` stream, narrowed to each caller. A frame reflects every fill, every mark move on any contract (whether or not this connection subscribed to it or filtered it out) and every delivery day the clock has passed before the second it was computed, so a connection subscribed to `pnl` alone stays current. A connection that reads slowly receives the newest snapshot, not a backlog. `PnlSnapshot` is the same shape REST [`get_pnl`](#cmd-get_pnl) returns: every row carries its settlement `currency` (`EUR`/`GBP`), `totals` sums realized/unrealized per currency (no cross-currency sum), money is q8 (**currency × 100,000**) energy-scaled by the contract's delivery duration, and `unpriced_trades` counts trades the exchange has not reversed (any state but `RGRA` or `CNCL`) whose duration is not yet known. Each per-contract row carries its local `delivery_day` (`YYYY-MM-DD`; empty when unknown), and the snapshot covers only contracts delivering today or later. `mark_source` gains `Close` / `CloseLast`, a closed contract's residual valued at M7's closing reference price, or the gateway's own last mark frozen at close until one arrives, and each side of a trade is attributed to its own member. Not modelled: fees, FX, imbalance valuation.

#### Frame

```json
{"stream": "pnl", "pnl": PnlSnapshot, "sent_at_ms": 1718…}
```

**Scoping.** Every `pnl` frame is narrowed to what the connection's caller may see, exactly like the [`get_pnl`](#cmd-get_pnl) command (no member filter). A caller holding `read_pnl` (or `bypass_member_check`) receives the firm-wide snapshot; everyone else receives only their assigned members' `per_vm`/`per_vm_area_prod` rows, with the firm-wide `per_contract`/`per_area_prod` rollups empty.

### <a id="stream-slot_positions" name="stream-slot_positions"></a>`Stream` `slot_positions`

_on change_

Live usage of the [slot position limit](#ops-slot-limit) for one area and range, scoped like [`get_slot_positions`](#cmd-get_slot_positions). Every message is the full set of slots for the range, never a delta, so a client replaces what it holds. The first message is sent at subscribe; after it, a message is sent only when something in the set changed: at most once per second from fills and orders, plus an immediate message when the slot settings or a member's slot limit change. Each message carries the mode, the House limit (with `read_status` only), the area's `locked` flag and a sequence number `seq` that rises by one with every set the shared computation publishes. A subscriber can see gaps in `seq`: a slow reader skips to the newest set, and on WS a set that shows the caller nothing new is not sent. A gap loses nothing, since every message carries the full set. Every subscriber of the same area, range and scopes shares one computation, on either transport, and a subscriber that reads slowly receives the newest set, not a backlog. gRPC `WatchSlotPositions` carries the same sets.

Subscribe with the parameters `get_slot_positions` takes; a second subscribe replaces the first. A refused subscribe (a range over 48 hours, no area, or a member the caller may not see) is answered with a `{"type":"response","op":"subscribe","ok":false,"error":{…}}` envelope carrying the same code and message as the command, and no stream.

```json
{"action": "subscribe", "stream": "slot_positions", "delivery_area": "10YDE-RWENET---I",
 "from_ms": 1791194400000, "to_ms": 1791201600000, "v_member_short_id": "VM001"}
```

#### Frame

```json
{"stream": "slot_positions", "seq": 3, "sent_at_ms": 1718…,
 "delivery_area": "…", "from_ms": …, "to_ms": …, "mode": "observe", "house_limit": 20000,
 "locked": false, "slots": [{"slot_start_ms": …, "slot_end_ms": …, "scopes": [ … ]}]}
```

**Scoping.** The scopes are resolved at subscribe. A member reassignment or a lost `read_status` narrows the next frame to what the caller may still see; a scope gained needs a new subscribe.

### <a id="stream-state" name="stream-state"></a>`Stream` `state`

_1 Hz_

Full runtime-health snapshot, same shape as [`get_state`](#cmd-get_state) / REST `GET /state`, under `state`.

> [!NOTE]
> Permission-gated server-side (`read_state`): a subscribe without it is answered with a `{"type":"response","op":"subscribe","ok":false,"error":{…}}` envelope and no stream. An open stream closes with the same envelope when the permission is revoked ([see above](#stream-gated-close)).

#### Frame

```json
{"stream": "state", "state": SystemState, "sent_at_ms": 1718…}
```

**If you see `admission: degraded`**, the gateway is admitting orders on figures it knows are incomplete, by the desk's own choice: an exchange trade report it could not read is missing from position, cash and P&L, so its own position and cash limits are measured short (the exchange still checks the member's cash limit on every order). Stop adding exposure you would not add blind, reconcile your book against the exchange, and contact the support desk with the `parse_error` rows from the m7-errors audit. It returns to `open` by itself once the missed trade is ingested; under the default `close` policy an acknowledgement ([`ack_trade_ingest_fault`](#cmd-ack_trade_ingest_fault)) lasts `system.trade_ingest_fault_ack_ttl_sec` (1800 s by default), ends early when the fault clears, and is dropped by a restart. While admission is `degraded` the gateway does not reconnect its exchange session over the fault, and it keeps polling the exchange's throttling status, which the load check (`load_management`) needs fresh to admit an order that adds exposure. Orders are admitted the moment admission reopens, unless the throttling report went stale while admission was closed (closed for about `load_management.max_report_age_sec` or longer, 30 s by default; the report ages from its last poll, so a slightly shorter closure can already count); then an order that adds exposure can be refused for about two seconds after admission reopens, until the first throttling poll answers. From then on orders stay admitted until the trade report is read or the acknowledgement runs out. Any other order-critical issue still closes admission, and one that outlasts the health allowance still makes the gateway reconnect its exchange session, with admission closed while it does; an acknowledgement keeps counting down meanwhile. `operational`, `/readyz` and the gRPC health service keep reporting the gateway not operational throughout, so alerts on them still fire.

`state.issues` carries one stable string per failing condition, the same set as REST `GET /state` and gRPC `GetState`: `exchange is down`, `amqp_broadcast_consumer unhealthy`, `amqp_private_consumer unhealthy`, `amqp_publisher unhealthy`, `ws_order_book not synchronized`, `ws_order_book_stream not connected`, `ws_order_book_stream sequence gap`, `m7_heartbeat lost`, `cash_exposure_window not covered`, `product_parameters not loaded`, `trade_report refused`. `trade_report refused` means the gateway could not read an exchange trade report's financial core, so a trade the exchange executed is missing from its own count and position, cash-exposure and P&L are understated; order entry is held closed (the exchange's own cash limit is still the backstop) until the exposure window is covered again, the outstanding chunk re-asked, or (for an unsolicited or foreign report) the whole window re-planned and re-asked, and the missed trade is ingested. The desk can choose to trade on through it instead: with `system.trade_ingest_fault: continue`, or for `system.trade_ingest_fault_ack_ttl_sec` after an operator acknowledges the fault ([`ack_trade_ingest_fault`](#cmd-ack_trade_ingest_fault)), new orders and modifies are admitted while it stands and no other issue is present, and `admission` reads `degraded`. The desk can always get flat, `delete_order`, `cancel_all_orders` and `deactivate` are never gated; do not “correct” the missed trade through ComTrader (the Voltnir figures will still be wrong once it is ingested), pull the `parse_error` rows from the `m7_errors` stream/audit (they carry the raw report) and escalate to Voltnir, and after the fix and a restart the first login's backfill ingests it and the condition clears itself. `cash_exposure_window not covered` means the gateway has not yet had the exchange confirm every trade in the current cash-exposure window, up to 72 hours over a weekend, so consumed cash could be under-counted and orders admitted that the exchange would refuse. It is raised at login and cleared once the exchange has answered the chunked trade backfill: the window's trades by match time, and every trade the exchange updated since Voltnir last heard from it; it persists only when the exchange cannot serve the whole window, which needs a higher `contractStoreTimeInDays` from EPEX. `m7_heartbeat lost` means three of M7's advertised heartbeat intervals have passed with no application heartbeat from the exchange, about **15 seconds**, since M7 advertises a 5-second interval. The M7 backend has stopped publishing even though the connection may still be up, so market and private data are frozen and order submission is refused until it resumes. It clears on the next heartbeat; after a reconnect the same three intervals are counted from the re-subscribe. It is never raised on an environment that has never sent a heartbeat at all. One condition does not close order entry and is reported as the boolean `last_update_pass_refused` beside `issues`, not in it: the exchange refused the login's inquiry for the trades it updated while Voltnir was not connected.

### <a id="stream-contracts" name="stream-contracts"></a>`Stream` `contracts`

_10 Hz_

Order book + contract metadata for the contracts the subscribe names, by `{areas, products}` or by `{areas, contract_ids}`. Snapshot on subscribe (and on lag recovery), then upsert/delete deltas; emits a heartbeat every tick for latency diagnostics. Each upsert carries the contract’s complete current book and metadata as the gateway holds it when the frame is sent (latest state): changes within one 100 ms tick are coalesced per contract, and a client that falls behind skips intermediate versions and lands on the latest complete book. A stream never goes back to an older book and never sends the same change twice: each upsert’s `version` is higher than the last one sent for that contract. gRPC `WatchContracts` is the same stream, with the same filter and the same latest-state rule, one event per change. `build_us` / `encode_us` report server-side frame cost. The `buy` / `sell` depth entries of each `AreaContract` carry `price` in cents and `quantity` in sub-MW, the same scale as an order price and `best_bid` / `best_ask`; the product's exchange decimal scale is applied before an entry is served, so no per-contract factor applies.

#### Example

```
// a whole product
{"action": "subscribe", "stream": "contracts", "areas": ["DE"], "products": ["H"]}

// one contract
{"action": "subscribe", "stream": "contracts", "areas": ["DE"], "contract_ids": [12345]}

// frame
{"stream": "contracts",
 "snapshot": [AreaContract…] | absent,
 "deltas": [{"type": "Upsert", "contract": AreaContract}
          | {"type": "Delete", "area_id": "DE", "contract_id": "12345"}] | absent,
 "sent_at_ms": 1718…, "build_us": 120, "encode_us": 45}
```

**Which contracts.** A contract is included when its area is in `areas`, and then: with no `contract_ids`, when its product is in `products`; with `contract_ids`, when its id is one of them and, if `products` is not empty, its product is in `products` as well. An empty `areas` matches nothing, and so does an empty `products` without `contract_ids`: the subscribe is not refused, the snapshot is empty and no data follows. An id that names no contract is absent from the snapshot, not an error. A second `subscribe` on `contracts` replaces the whole filter (and re-sends a snapshot).

The *subscribe* snapshot includes each contract's `last_history` trend-chip prefill. *Lag-recovery* snapshots omit it (kept small so a slow client can catch up), so treat `last_history` as optional and retain any prefill you already hold when it is absent.

**Reference prices arrive on this stream.** Each `AreaContract` carries the exchange's reference price for the contract in its delivery area, `ref_px_cents`, `ref_px_type` (`"C"` closing, the exchange's default, or `"O"` opening), `ref_px_date` (`YYYY-MM-DD`) and `ref_px_updated_ms`. They are all `null` until the exchange publishes one, and a new or changed price is an ordinary `Upsert` delta with a bumped `version`, so no separate subscription is needed. A price that has not changed emits nothing. See the [REST units table](rest_api_v1.md#units) for the scale; `0` and negative are real prices, so `null` is the only "not reported".

> [!CAUTION]
> Each `AreaContract` carries `predefined`: `false` marks a **user-defined block** contract, where the exchange rejects regular limit orders (M7 error 1051, `"Can't enter OPEN order for user-defined blocks"`); only block orders are accepted. Do not offer regular order entry on a contract with `predefined: false`. `null` means metadata not yet received (not a block).

### <a id="stream-public_trades" name="stream-public_trades"></a>`Stream` `public_trades`

_no permission_

Public trade tape (raw) for the subscribed `contract_ids`. There is no snapshot: the first frame after subscribe is an empty confirmation; seed per-contract history via [`public_trades_for_contract`](#cmd-public_trades_for_contract), then live deltas follow.

#### Example

```
// subscribe scoped to the contracts you plot
{"action": "subscribe", "stream": "public_trades", "contract_ids": [12345]}

// frame
{"stream": "public_trades", "deltas": [PublicTrade…], "sent_at_ms": 1718…}
```

**`remote_trade_id`.** Each `PublicTrade` carries the XBID remote trade id when the trade executed on a remote (XBID) contract, and `null` when it is local, where the exchange omits it. It is present for every trade state, recalls and cancellations included, and is the join key onto the EPEX market-data transaction reports, which carry the same id. The same field is on REST `GET /api/v1/public_trades` and gRPC `PublicTrade`.

**`contract_ids` filters server-side.** Prints on other contracts are dropped before they are serialised, so a client that names the contracts it plots pays for nothing else. The field is optional: omitting it, or sending an empty list, subscribes to the whole market's tape. A second `subscribe` on `public_trades` replaces the active filter; deltas buffered under the previous one are discarded rather than delivered.

### <a id="stream-trade_tape" name="stream-trade_tape"></a>`Stream` `trade_tape`

_no permission_

Same source as [`public_trades`](#stream-public_trades), pre-enriched with each trade's `area_id`, `prod`, `name`, and `delivery_start` so you can render a cross-product tape without your own contract lookup. Snapshot is the rows of up to the 200 most recent prints, oldest-first: a print whose contract the gateway no longer holds is dropped. A print is listed once per delivery area it touches, so a cross-border print appears under both areas. Live rows are coalesced per tick. The gRPC peer is `WatchTradeTape`, with the same rows.

#### Frame

```json
{"stream": "trade_tape", "snapshot": [TradeTapeRow…] | absent,
 "deltas": [TradeTapeRow…], "sent_at_ms": 1718…}
```

### <a id="stream-watch_hub2hub" name="stream-watch_hub2hub"></a>`Stream` `watch_hub2hub`

_no permission_

Live hub-to-hub ATC for an area + delivery window. The destination may be any hub in the XBID network, not only a neighbour across a shared border: M7 publishes hub-to-hub capacity, the transfer the network can carry from one hub to the other. Unlike the other streams this is text-framed: an initial `hub2hub_response` snapshot, then per-entry `hub2hub_update` deltas and `hub2hub_heartbeat` connection-state frames. Updates are filtered server-side to entries whose hub matches `delivery_area` and whose delivery start falls in `[delivery_from, delivery_to)`. A second `watch_hub2hub` on the same connection replaces the prior subscription. A connection that falls behind the update stream is sent a fresh `hub2hub_response` for its subscription; replace the whole matrix with it, since the updates it missed are not replayed. (For a one-shot fetch without a subscription, use [`hub2hub_query`](#cmd-hub2hub_query).) The gRPC peer is `WatchHub2Hub`, with the same filter, snapshot and lag rules. Two cases differ: an unparseable window answers here with an empty response and no subscription, and on gRPC with `INVALID_ARGUMENT`; with hub-to-hub disabled the connection here stays open, and the gRPC stream sends one snapshot and then ends.

#### Example

```json
{"action": "watch_hub2hub", "delivery_area": "DE",
 "delivery_from": "2026-06-16T06:00:00Z", "delivery_to": "2026-06-16T22:00:00Z"}
{"action": "unwatch_hub2hub"}

// snapshot: {"type": "hub2hub_response", "delivery_area": "DE", …, "data": [AtcEntry…]}
// delta:    {"type": "hub2hub_update", "delivery_area": "DE", "entry": AtcEntry}
// liveness: {"type": "hub2hub_heartbeat", "connected": true, "ts_ms": 1718…}
```

### <a id="stream-audit" name="stream-audit"></a>`Stream` `audit`

_Permission: read_audit_

Live tail of the compliance audit log. There is **no snapshot**: seed page 0 with the [`audit_query`](#cmd-audit_query) `events` entity, then subscribe. The feed is **event-driven, not polled**. The server pushes each audit row as it is committed, batched into at most one frame per tick (rows that existed before you subscribed are not replayed; that's what the seed query is for), so there is no per-client database polling. Each row is the same JSON the `audit_query` `events` entity returns, keyed by a stable per-row `id` (use it to dedup against the seeded page). The tail is member-scoped as that entity is: a caller without `read_orders` or `bypass_member_check` is sent only the rows its unfiltered `events` query would page. Apply your panel's filters to the tail client-side.

> [!NOTE]
> Permission-gated server-side (`read_audit`): a subscribe without it is answered with a `{"type":"response","op":"subscribe","ok":false,"error":{…}}` envelope and no stream. An open stream closes with the same envelope when the permission is revoked ([see above](#stream-gated-close)).

#### Example

```json
{"action": "subscribe", "stream": "audit"}
{"action": "unsubscribe", "stream": "audit"}

// delta: {"stream": "audit", "deltas": [AuditEvent…], "sent_at_ms": 1718…}
```

### <a id="stream-m7_errors" name="stream-m7_errors"></a>`Stream` `m7_errors`

_Permission: read_m7_errors_

Live tail of the M7 exchange-error log. Same tail semantics as [`audit`](#stream-audit) but gated by `read_m7_errors`; seed via the [`audit_query`](#cmd-audit_query) `m7_errors` entity. Rows carry the stable `id` key.

#### Example

```json
{"action": "subscribe", "stream": "m7_errors"}
{"action": "unsubscribe", "stream": "m7_errors"}

// delta: {"stream": "m7_errors", "deltas": [M7Error…], "sent_at_ms": 1718…}
```

### <a id="stream-exchange_messages" name="stream-exchange_messages"></a>`Stream` `exchange_messages`

_Permission: read_m7_errors_

Live tail of the exchange's own message feed: cash-limit breaches, market and delivery-area halts, member suspensions, failover notices, automated order transfers. This is what the exchange *says*; [`m7_errors`](#stream-m7_errors) is what goes *wrong*. No snapshot on subscribe, seed history via [`list_exchange_messages`](#cmd-list_exchange_messages) and de-duplicate the tail on `msg_id`.

Gated by `read_m7_errors`, the same permission the *history* of this log carries on [`list_exchange_messages`](#cmd-list_exchange_messages): a subscribe without it is answered with a `{"type":"response","op":"subscribe","ok":false,"error":{…}}` envelope and no stream, and an open stream closes with the same envelope when the permission is revoked ([see above](#stream-gated-close)). The tail and the history are the same rows, so subscribing is not a way around the gate on reading them.

The stream also carries the messages that are never stored, the ones the exchange marks non-persistent, and the per-contract lifecycle broadcasts, codes `74` (`x_contract_closed`), `76` (`x_contract_closed_tsos`) and `77` (`x_contract_in_balancing_phase`), which Voltnir drops because one arrives per contract per phase and none names an order, trade or position of yours. Their `id` is `null` and they cannot be re-fetched afterwards, so a client that needs them must be subscribed when they arrive.

#### Example

```json
{"action": "subscribe", "stream": "exchange_messages"}
{"action": "unsubscribe", "stream": "exchange_messages"}

// delta: {"stream": "exchange_messages", "deltas": [ExchangeMessage…], "sent_at_ms": 1718…}
```

### <a id="stream-system_log" name="stream-system_log"></a>`Stream` `system_log`

_Permission: read_logs_

Live tail of the **gateway's own diagnostic log**: the running process's internal log output. Not the exchange's messages ([`exchange_messages`](#stream-exchange_messages)), not the exchange's faults ([`m7_errors`](#stream-m7_errors)) and not the compliance trail ([`audit`](#stream-audit)). No snapshot on subscribe, seed history via [`list_system_log`](#cmd-list_system_log) and de-duplicate the tail on `seq`.

**Gated by `read_logs`**, a dedicated permission rather than `read_m7_errors`: this feed carries gateway internals, file paths, database errors, module names, which is a different audience and a different blast radius from the exchange side of the line. A subscribe without it is answered with `{"type":"response","op":"subscribe","ok":false,"error":{…}}` and no stream, and an open stream closes with the same envelope when the permission is revoked ([see above](#stream-gated-close)).

**Not an audit record.** The buffer behind this feed is a bounded in-memory ring, capped by entry count first and age second, lost on every restart, and lossy under load. There is deliberately **no level parameter**: the gateway captures at its configured level and this stream carries everything captured, so a client that narrowed the stream and later widened it would have a hole in its history it could not explain. Filter on the client.

An entry whose `seq` is `null` and whose `target` is `voltnir.system_log` is a **marker the server generated**, not a captured line: this session fell behind the tail and the marker names how many entries were dropped on the way to it. Re-query `list_system_log` to fill the gap. The loss is reported in band rather than logged, because logging it would feed a new entry into the very stream that is already behind.

#### Example

```json
{"action": "subscribe", "stream": "system_log"}
{"action": "unsubscribe", "stream": "system_log"}

// delta: {"stream": "system_log", "deltas": [
//    {"seq": 18344, "ts_ms": 1788610323180, "level": "warn",
//     "target": "voltnir_backend::m7::amqp::connection",
//     "message": "AMQP connection lost, reconnecting in 5s"}],
//    "sent_at_ms": 1788610323200}
```

<a id="errors" name="errors"></a>

## Error reference

A failed command returns `ok: false` with an `error` object carrying the canonical `code` plus its REST and gRPC equivalents, so the same failure reads identically no matter which transport you use, and a client bridging transports can map cleanly in either direction.

| code | http_status | grpc_status | meaning |
| --- | --- | --- | --- |
| `PERMISSION_DENIED` | 403 | PermissionDenied | missing permission, or a desk-gated op on a trader license (`LICENSE_DESK_REQUIRED`) |
| `UNAUTHENTICATED` | 401 | Unauthenticated | missing / invalid credentials |
| `BAD_REQUEST` | 400 | InvalidArgument | malformed or invalid input |
| `NOT_FOUND` | 404 | NotFound | order / contract / user / member does not exist |
| `CONFLICT` | 409 | Aborted | state conflict (not active, modify already in progress, see [`modify_order`](#cmd-modify_order) for how long that lock is held) |
| `ORDER_CHANGED` | 409 | Aborted | The order changed at the exchange before the command was applied, a fill, or another modify, moved its revision while the command was on its way, so the exchange refused it on its revision guard. Nothing was applied and the order is resting exactly as it was, one revision further on. Retry the same command: it is rebuilt on the revision the gateway now holds. Bound the retry rather than looping, a repeatedly filling order can lose the race more than once, and a cancel may find the order already gone next time |
| `ORDER_PENDING` | 409 | Aborted | A `modify_order` or `delete_order` named an order the exchange has not yet acknowledged, so there is no exchange order to act on; nothing was sent. Retry once it is acknowledged, or wait for it on the [`orders`](#stream-orders) stream. The message reads `ORDER_PENDING: the order is accepted but not yet acknowledged by the exchange, so retry once it is`. Only a caller who may act on the order’s member gets it; anyone else gets `NOT_FOUND`. Also the code of a member-scoped `cancel_all_orders` left incomplete by such an order. |
| `POSITION_LIMIT_EXCEEDED` | 422 | FailedPrecondition | order would breach the position limit |
| `SLOT_POSITION_LIMIT_EXCEEDED` | 422 | FailedPrecondition | the order's own quarter-hour slots, summed over every contract covering each, would pass the slot position limit (House or the member's own) while the slot limit mode is `reject`; the message names the area, the slot, the side, the scope, the position the order would reach and the limit. A caller without `read_status`, which cannot see the House limit elsewhere, is not shown the House figures: a refusal by the House slot limit reads `slot position limit exceeded: refused by the desk slot limit, <area> <slot start> to <slot end>, <long\|short> side`, and a refusal by the member's own slot limit keeps the member's figures. The `order_rejected` audit row carries every field either way |
| `SLOT_WINDOW_UNKNOWN` | 422 | FailedPrecondition | a delivery window the slot position limit needs cannot be placed on the quarter-hour grid (the order's own contract, open orders on a contract with no known window, or a trade with no window that can deliver in a slot the order covers: up to the end of the delivery day after the one it executed on (in GB, to 23:00 London two days after it), or any slot of its area when its execution time is unknown) and the order adds exposure; an order that adds none is not refused by it. A caller without `read_status` is not told which trade: the message reads `slot window unknown: a trade in <area> has no delivery time`, and the `order_rejected` audit row still names it |
| `CASH_LIMIT_EXCEEDED` | 422 | FailedPrecondition | the exposure the exchange's risk parameters put on this order would push consumed cash past one of the pool's bounds, the desk's House limit, the House remainder, the member's allocation, or what the exchange still has available, the pool is already breached, or no bank-holiday calendar is configured for the pool's settlement currency (`no_holiday_calendar`, the exposure window those bounds are measured over cannot be placed on ECC Business Days without one, so the pool admits no new exposure until a date is entered via [`set_holidays`](#cmd-set_holidays)) or its calendar holds no date in the current or next calendar year (`stale_holiday_calendar`, last year's closings place none of this year's boundaries). The gateway fills in each year's TARGET2 closing days itself, so either refusal arises only when that fill cannot supply them, such as after an operator deleted them, or, after a replace that leaves them out, until the next hourly check restores them. The other currency's pool is unaffected, and an order that adds no exposure still passes under any of these. The same refusal also covers a consumed-cash figure the gateway could not finish computing: it is measured short when that happens, so the check refuses rather than admitting an order against it, and the message feed carries a line saying no limit was exceeded. |
| `SELF_CROSS_BLOCKED` | 422 | FailedPrecondition | order would cross your own resting order under reject policy, on `new_order`, and on `modify_order` at the order's new price |
| `TRADING_DISABLED` | 422 | FailedPrecondition | operator kill-switch is engaged (`trading_allowed = false`); `new_order` and `modify_order` are rejected before reaching M7. Cancels (`delete_order` / `cancel_all_orders`) are not gated; they only reduce exposure |
| `LOAD_THROTTLED` | 422 | FailedPrecondition | the M7 load-management guard refused the action (defined in the official EPEX SPOT M7 API documentation). Either admitting it would take the projected order-management-transaction count in one of M7's observation windows to the `L1` warning threshold, in which case only `new_order` and `modify_order` are refused, never a cancel, or the exchange already has the whole member `RESTRICTED`, in which case every order action including cancels is refused, because M7 would reject it anyway and the attempt would push the release further out. The operator kill switch (`toggle_trade_enabled` with `enabled: false`) is exempt: its account-wide flatten is dispatched whatever the guard and the exchange say, and an exchange rejection is reported in its `flatten.error` as usual. The message names the rule and the figures, or the indicative release time. Remaining headroom is on [`get_throttling`](#cmd-get_throttling) |
| `PRODUCT_SCALE_UNSUPPORTED` | 422 | FailedPrecondition | M7 published a decimal scale or quantity unit for the contract's product that this gateway cannot denominate in its cents-and-sub-MW store, a `qtyUnit` other than MW, or a scale finer than the gateway's own. Trading the product is refused until M7 changes it; on `modify_order` and `activate` too, since every arm restates the order's price and size to the wire |
| `BLOCK_DELIVERY_END_INVALID`, `BLOCK_RESTRICTION_NON`, `BLOCK_WINDOW_TOO_SHORT` | 400 | InvalidArgument | a `new_order` block refusal on a malformed request; see [`new_order`](#cmd-new_order) |
| `BLOCK_SWEEP_UNSUPPORTED`, `BLOCK_NOT_SUPPORTED`, `BLOCK_WINDOW_NOT_CONTIGUOUS`, `BLOCK_WINDOW_TOO_LONG` | 422 | FailedPrecondition | a `new_order` block refusal on the product’s settings or the catalogue; see [`new_order`](#cmd-new_order) |
| `CONTRACT_IN_DELIVERY` | 422 | FailedPrecondition | a command that adds exposure (`new_order`, or `modify_order` with `activate`, a larger size or a new price) on a contract that has reached its delivery start on the gateway’s clock; refused before anything reaches M7, whatever state the exchange still lists the contract in. A shrink at the same price is not refused with this code, though like any modify it is refused `BAD_REQUEST` once the exchange shows the contract closed; `deactivate` and a cancel are refused by neither |
| `MEMBER_AREA_NOT_ALLOWED` | 422 | FailedPrecondition | an order under a member, in a delivery area outside the member’s `delivery_areas`, on `new_order`, `modify_order` (every action) and `delete_order`, for every caller. The message leads with the code and names the member and the area. Not transient. |
| `PRODUCT_SCALE_UNKNOWN` | 503 | Unavailable | the contract's product decimal scale is not yet recorded, so the gateway cannot convert the order to the M7 wire integers. A transient login prerequisite: a targeted parameter inquiry has been issued and the order is safe to retry once the report lands. A resting order whose contract has left the book falls here on `modify_order`/`activate`/`deactivate`; the kill-switch flatten needs no scale |
| `BAD_REQUEST` | 400 | InvalidArgument | a price or size that is a valid gateway integer but is not exactly expressible on the product's own M7 decimal grid; the message names the scale (`decShftQty …`). A client-correctable value, not a scale fault |
| `TIMEOUT` | 504 | DeadlineExceeded | exchange did not acknowledge in time. The outcome is *unknown*, not failed, the request may still have been processed |
| `RATE_LIMITED` | 429 | ResourceExhausted | the API key is over its per-key request bound, counted across REST, WS and gRPC together. Every command the connection sends is charged, subscriptions included; the handshake is not. The window is fixed, not sliding, so the whole allowance is available again at the next boundary, and the message states the bound to back off to. Cancelling an order, cancelling all orders and *disabling* trading are never refused by the bound: every other rule in the gateway leaves the exposure-reducing route out open, and a rate limit must not be the one that closes it. Re-*enabling* trading admits exposure again, so it is ordinary traffic and is bounded like any other call. `delete_order`, `cancel_all_orders` and a `toggle_trade_enabled` carrying `enabled: false` therefore never return this code. The kill-switch exemption belongs to a caller that holds `toggle_trading`: one that does not has no switch to be locked out of, since the permission gate refuses it whichever way the bound falls, so its `toggle_trade_enabled` is charged and bounded in both directions and may return `RATE_LIMITED` rather than `PERMISSION_DENIED`. Every frame is charged, including one that does not parse, a client sending garbage in a loop is exactly the traffic the bound exists to stop, and its refusal names the operation `unknown` |
| `NOT_OPERATIONAL` | 503 | Unavailable | gateway prerequisites not met / database unavailable |
| `NOT_PROCESSED` | 503 | Unavailable | the exchange handed the request back undelivered, so it definitely was not processed. The one negative acknowledgement the exchange protocol offers, and the only outcome that is safe to resubmit blind, a returned `new_order` may be resubmitted **with the same `client_order_id`**, because the exchange never saw the key and the gateway frees it. That order is also recorded `REJECTED` with the same reason and gives back the limit headroom it was holding |
| `TRADE_NOT_FOUND` | 404 | NotFound | `recall_trade`: no trade, or no trade of the order, that the caller may recall |
| `TRADE_CHANGED` | 409 | Aborted | `recall_trade`: the trade's revision moved past the `revision_no` named; nothing was sent |
| `RECALL_NOT_POSSIBLE` | 409 | FailedPrecondition | `recall_trade`: the trade is not `ACTI`; nothing was sent |
| `RECALL_REFUSED` | 409 | FailedPrecondition | `recall_trade`: the exchange refused the recall; the error carries `m7_err_code` and `m7_error_key` |
| `OUTCOME_UNKNOWN` | 504 | DeadlineExceeded | `recall_trade`: no acknowledgement in time; the request may have reached the exchange |
| `INTERNAL` | 500 | Internal | unexpected server-side failure |

Copyright © 2026 Voltnir B.V. The Voltnir gateway is proprietary software, licensed under separate terms.
