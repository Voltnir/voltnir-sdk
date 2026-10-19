# Voltnir REST API v1: Reference

> Auto-generated from the Voltnir API reference.

<a id="overview" name="overview"></a>

## Overview

The Voltnir REST API is the request/response transport onto the EPEX SPOT M7 intraday gateway. Every operation is one HTTP endpoint under `/api/v1`; each mirrors a gRPC RPC and a WebSocket command with the same fields, units, permissions and errors. Two unauthenticated [probes](#probes), `/livez` and `/readyz`, sit at the root of the port, outside `/api/v1`; they are not operations.

- **Parity with gRPC and WebSocket.** Every endpoint here has a gRPC and a WebSocket peer with the same behaviour, except the REST-only ones the permission table marks: the report exports, the terminal sessions and `/metrics`. The permission table is identical across the three references.
- **REST has no live streams.** Live order, trade, contract and status feeds are on WebSocket and gRPC; REST serves point-in-time reads and the report exports.
- **Errors are HTTP status codes** with a JSON `{"error": "..."}` body; the [Error reference](#errors) maps each one.

Read [Connecting and authentication](#connecting) first, then [Permissions](#permissions) and [Conventions](#conventions). The operations follow, grouped by domain, then the [Error reference](#errors).

<a id="connecting" name="connecting"></a>

## Connecting and authentication

The REST API listens on port `3000` by default, alongside the WebSocket and gRPC transports. Every endpoint under `/api/v1` requires a Bearer token in the `Authorization` header; only the two [probes](#probes) at the root of the port take none. Tokens are stored as SHA-256 hashes; the raw key is shown only once, at creation or rotation.

The bearer is either an **API key** or a **session token**. A session token is minted from an API key with [POST /sessions](#post-sessions) and starts with `vs_`. It acts as its user with exactly that user's permissions and member assignments, including any change made after it was minted. Sessions exist so a browser never has to keep the key: the trading terminal trades the typed key for a session at sign-in and presents the session from then on. A session ends on [DELETE /sessions/current](#delete-sessions-current), when its user's key is rotated, when its user is deleted, and, for one created without "stay signed in", twelve hours after creation. An ended or expired session is refused exactly like a wrong key. Only the terminal needs a session; a program connecting to the gateway authenticates with its API key. Every transport accepts a session token wherever it accepts a key, so the same token also works in the WebSocket auth frame and in gRPC metadata, but minting and ending one are REST-only.

> [!NOTE]
> **Required header on every request:**
>  `Authorization: Bearer <your_api_key or session token>`

#### Auth errors (apply to every endpoint)

| Status | Body | Condition |
| --- | --- | --- |
| 401 | `{"error": "Unauthorized"}` | Missing or invalid token, or a session that has ended or expired |
| 403 | `{"error": "Forbidden"}` | Valid token but the user lacks the required permission for this endpoint |
| 429 | `{"error": "RATE_LIMITED", "message": "request rate limit exceeded: at most N requests per Ws per API key"}` | The key is over the per-key request bound, a fixed number of requests in a fixed window, counted across REST, WS and gRPC together. The window is fixed, not sliding, so the whole allowance is available again at the next boundary; the message states the bound to back off to. Cancelling an order, cancelling all orders and *disabling* trading are never refused by the bound: every other rule in the gateway leaves the exposure-reducing route out open, and a rate limit must not be the one that closes it. Re-*enabling* trading admits exposure again, so it is ordinary traffic and is bounded like any other call. `DELETE /order`, `DELETE /orders` and a `PUT /trading_allowed` carrying `enabled: false` therefore never return `429`. The kill-switch exemption belongs to a caller that holds `toggle_trading`: one that does not has no switch to be locked out of, since the permission gate refuses it whichever way the bound falls, so its toggle is charged and bounded in both directions and may return `429` rather than `403`. A `PUT /trading_allowed` whose body does not parse is charged too, nothing readable said it was a kill switch being thrown. |

> [!NOTE]
> **Refusals are audited.** A rejected token writes an `auth_failed` event, a refused permission writes `permission_denied`, and crossing the request bound writes `rate_limited`, all with `outcome: "denied"` and `target_type: "auth"`, readable through [GET /audit/events](#get-audit-events). A report export request that passes the permission gate writes one `report_exported` row once it is decided: `outcome: "ok"` when it is accepted (`202`), and `outcome: "error"` when it is refused, with the `400`'s own text (such as `export range exceeds 31 days`) or `export_busy` for a `409` as the `reason`, so an export that never started is never on the trail as one that did. The `reason` of a denial is the permission's code, `license_desk_required` when the desk tier is what refused, `member_scope` when the caller holds the permission but asked for a virtual member it is not assigned to, or `forbidden` for a guard that is none of those. An `auth_failed` event names the transport, the source and the route attempted, never the credential presented, and is written at most once per source per minute so a key-guessing run cannot flood the trail; when a minute closes on more attempts than that, one extra event with `reason: "repeated_failures"` carries the count in `after.attempts`, so the magnitude survives the throttling. `rate_limited` is likewise one event per window, not one per refused request. The source of an event is the **peer address of the connection**, unless that peer is listed in `system.trusted_proxies`: then it is the client the proxy named in `X-Forwarded-For`, read from the right. With the list empty (the default), every attempt behind a reverse proxy collapses onto the proxy's address, so these rows say that traffic arrived, not where on the internet it came from, and the one-row-per-source-per-minute throttle applies to the proxy as a whole.

> [!CAUTION]
> API keys cannot be retrieved after initial creation. If a key is lost, use [POST /users/{id}/rotate-api-key](#post-rotate-key) to issue a new one. The old key, and every session of that user, is invalidated immediately.

<a id="probes" name="probes"></a>

## Probes

Two routes at the root of the REST port, outside `/api/v1`, answer a monitoring system or an orchestrator without a key. They are infrastructure, not API operations: no permission applies, and they have no WebSocket peer. On gRPC the same two signals come from the standard `grpc.health.v1.Health` service, described in the gRPC reference.

| Route | Answer | Meaning |
| --- | --- | --- |
| `GET /livez` | 200 `{"live":true}` | The process is up and answering. Independent of the exchange: it stays `200` through an exchange outage. |
| `GET /readyz` | 200 `{"ready":true}`  
503 `{"ready":false}` | Whether the gateway is operational: the same signal as `operational` on [GET /state](#get-state) and the `voltnir_operational` gauge. It is `503` from start until the exchange login completes and the streams have synchronised, and during any exchange outage or maintenance. The trading kill switch does not affect it. |

- **No authentication.** An `Authorization` header is ignored, a wrong one included, and no key is needed.
- **Nothing written, nothing charged.** A probe writes no audit event, is not counted against any key's request bound, and is not counted in `voltnir_client_requests_total`. It reads in-memory state only, with no database access, so a short probe interval costs nothing and fills nothing.
- **Nothing disclosed.** Each body is a constant: live, or ready or not. Why the gateway is not ready is on [GET /state](#get-state) (`read_state`), in its `issues` list.
- **GET only.** `HEAD` is answered too; any other method is `405`, `OPTIONS` included. The probes carry no cross-origin headers, so a web page on another origin cannot read them. The same paths under `/api/v1` do not exist.

> [!CAUTION]
> **Readiness is a monitoring signal, not a traffic gate.** One gateway serves one M7 login, so there is no second instance to send traffic to. Point a Kubernetes or load-balancer readiness check at `/livez`, and alert on `/readyz`. A readiness check on `/readyz` takes the gateway out of service during every exchange outage and maintenance window, which blacks out the trading terminal and the API exactly when the desk needs to see state and cancel orders.

#### Example

```bash
curl -s https://gateway.example:3000/livez     # {"live":true}
curl -s -w ' %{http_code}\n' https://gateway.example:3000/readyz
# {"ready":true} 200, or {"ready":false} 503
```

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

The request is refused with `403 Forbidden` and body `{"error": "Forbidden"}`, and the denial is recorded as a `permission_denied` audit event.

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

All numeric fields use fixed-point integer encoding. No floating-point values are used anywhere in the API. Every field, unit and default below is identical on gRPC and WebSocket.

> [!NOTE]
> Convert price: divide cents by 100 to get CCY/MWh. Convert quantity/position: divide sub-MW by 1000 to get MW.

#### <a id="units" name="units"></a>Units reference

| Field | Wire type | Unit | Example value | Human-readable |
| --- | --- | --- | --- | --- |
| `price` | `i64` | Cents (CCY/MWh × 100) | `5000` | 50.00 CCY/MWh |
| `quantity` | `u32` | Sub-MW (MW × 1000) | `1000` | 1.0 MW |
| `display_qty` | `u32` | Sub-MW | `500` | 0.5 MW (iceberg visible portion) |
| `hidden_quantity` | `u32 \| null` | Sub-MW | `1500` | 1.5 MW hidden for iceberg |
| `contract_limit` | `i32` | Sub-MW | `5000` | 5.0 MW max net position per contract |
| `max_position` | `i64` | Sub-MW | `10000` | 10.0 MW member position limit |
| `cash_limit` / `cap_cents` | `i64` | EUR cents | `10000000` | €100,000 cash limit (executed-trade + open-order exposure) |
| `{eur,gbp}_{consumed,limit,remaining}_cents` | `i64` | Pool cents | `4200000` | Per-member live cash usage (see [members list](#get-members)); `remaining = limit − consumed` |
| `net_pos` | `i64` (signed) | Sub-MW | `-1000` | −1.0 MW (net short). Executed trades the exchange has not reversed (any state but `RGRA` or `CNCL`) only; open orders excluded |
| `entry_ts_ms` | `i64` | Unix ms (UTC) | `1713600000000` | 2026-04-20T10:00:00Z |
| `timestamp_ms` | `i64` | Unix ms (UTC) | `1713600000000` | 2026-04-20T10:00:00Z |
| `validity_time_ms` | `i64 \| null` | Unix ms (UTC) | `1713610800000` | 2026-04-20T13:00:00Z |
| `duration` | `string` | Decimal hours | `"1.0"` | 1-hour delivery window. M7 sends decimal hours as a string, passed through verbatim: `"0.25"`, `"0.5"`, `"1.0"`, `"2.0"`; `null` until contract metadata arrives |
| `ref_px_cents` | `i64 \| null` | Cents (CCY/MWh × 100) | `8250` | 82.50 CCY/MWh, the exchange's reference price for the contract in that delivery area. Same scale as `price`, and may be `0` or negative, so `null` is the only "not reported" |

#### Timestamps and IDs

Two timestamp shapes cross the wire: RFC 3339 strings (for example `2026-04-20T22:00:00Z`) and Unix-millisecond integers in UTC, whose field names end `_ms`. A field that can be absent is `null` on REST. An order is identified by its `client_order_id`, a UUID you supply at submission or the gateway generates for you; any UUID spelling is accepted and echoed back in canonical lowercase-hyphenated form. Contract ids are M7 numeric ids assigned by the exchange.

#### Pagination

The audit reads are cursor-paged. Pass `limit` (default 50, capped at 200; an explicit `limit=0` is rejected) and read `next_cursor` from the response, then feed it back as `cursor` on the next call. `next_cursor` is `null` on the last page. History responses carry no total count, so iterate until `next_cursor` is `null`. `sort_order` chooses page direction (`DESC`, newest first, is the default). A date window on the trade reads defaults to the delivery basis and orders the page accordingly, so a just-executed row can fall outside page one of a windowed query. An empty audit parameter is the same as leaving it out: `area=` filters nothing and `date_from=` sets no bound, as on gRPC and WS.

#### Error envelope

Every error is an HTTP status code with a JSON body `{"error": "<message>"}`; some validation errors add a `message` field. The [Error reference](#errors) lists the status codes and what each means. The auth statuses (`401`, `403`, `429`) apply to every endpoint and are described under [Connecting and authentication](#connecting).

#### <a id="advisory" name="advisory"></a>Security advisory

Voltnir is a trading gateway. Mistakes have real financial consequences. Read this before integrating.

> [!WARNING]
> **This system connects directly to a live exchange.** Orders submitted through this API create real obligations. There is no sandbox mode. Test integrations against a dedicated non-production environment if one is available.

> [!WARNING]
> **API keys must be treated as secrets.** They are transmitted as Bearer tokens. Use HTTPS at all times. Never log or embed raw API keys in source code. Rotate keys immediately if exposure is suspected.

> [!CAUTION]
> **Permissions are enforced server-side.** A user with `create_order` but not `delete_order` cannot cancel orders, not even their own. Review permission assignments carefully before going live.

> [!CAUTION]
> **PUT /trading_allowed with `enabled: false` blocks new order traffic and flattens the resting book.** This is a kill-switch. Use it deliberately: it sends a DeleteAllOrders command to the exchange with no undo, and while disabled new orders (`POST /order`) and modifies (`PUT /order`) are rejected with `422`. Cancels (`DELETE /order`, `DELETE /orders`) stay allowed; they only reduce exposure. The flag is off whether or not the cancel reached the exchange, so **check `flatten.ok` in the response** before assuming M7 took it.

> [!CAUTION]
> **POST /restart ends the gateway process.** It drains the transports, logs out of the exchange and exits with status **75**, relying on the host supervisor (systemd, Docker, and the like) to start a fresh one, which is how a configuration change is applied. Every WebSocket connection is dropped and every export token is lost. **A gateway running without a supervisor simply stops.** Do not call this endpoint unless you understand the operational impact.

### <a id="order-types" name="order-types"></a>Order types guide

Voltnir maps its order type and restriction enums to M7 protocol values. Understanding these is essential for building correct order submission logic.

#### OrderType

Sent in the `order_type` field. Default: `"regular"`.

- **`regular`**: Standard lit order. No special conditions. M7 type: O.
- **`block`**: User-defined block: one order on at least two consecutive contracts of one product, traded all at once or not at all. Create one with `delivery_end` (see [POST /order](#post-order)); join one with its `contract_id`. Takes `exe_restriction` `aon` or `fok`. M7 type: B.
- **`iceberg`**: Hidden quantity. Only `display_qty` is visible in the order book. Requires `display_qty` < `quantity`. M7 type: I.
- **`balance`**: Balance order for portfolio management. M7 type: L.
- **`pre_arranged`**: Pre-arranged trade with a known counterparty. Requires `pre_arranged_acct`. M7 type: E.

> [!NOTE]
> **In the order book, `order_type` is an integer, not these strings.** The values above are what you *send* when [creating an order](#post-order). When you *read* the public order book (the `buy`/`sell` arrays on [a contract](#contract-object)), each resting order's `order_type` is an M7 order-book integer from a smaller, read-only set (mirrors the public order-book report in the official EPEX SPOT M7 API documentation):
>
> | int | Order-book type | = entry type |
> | --- | --- | --- |
> | `0` | unspecified / unknown | none |
> | `1` | regular limit order (default) | `regular` (M7 `O`) |
> | `2` | user-defined block order | `block` (M7 `B`) |
> | `3` | balance order | `balance` (M7 `L`) |
> | `4` | not provided by the Shared Order Book (XBID cross-border) | none |
>
> Iceberg and pre-arranged never appear in the book: an iceberg only exposes its `display_qty`, and pre-arranged trades aren't lit.

#### ExeRestriction

Sent in the `exe_restriction` field. Default: `"non"`.

- **`non`**: No execution restriction. Default behaviour. M7: NON.
- **`fok`**: Fill-or-Kill: must execute completely and immediately or be cancelled. Requires `validity_res: "non"`. M7: FOK.
- **`ioc`**: Immediate-or-Cancel: execute available portion immediately, cancel remainder. Requires `validity_res: "non"`. M7: IOC.
- **`aon`**: All-or-None: order must be completely filled or not at all. M7: AON.

> [!NOTE]
> In the order book, `order_execution_restriction` is likewise an integer: `0` = unspecified, `1` = not restricted, `2` = AON. Only AON is reported per resting order; `fok`/`ioc` are entry-time immediacy conditions, so they never rest in the book.

#### ValidityRestriction

Sent in the `validity_res` field. Default: `"gfs"`.

- **`gfs`**: Good-for-Session: valid until end of trading session. Default. M7: GFS.
- **`gtd`**: Good-till-Date: valid until a specific datetime. Requires `validity_date`. M7: GTD.
- **`non`**: No validity restriction (immediate). Mandatory for FOK and IOC execution restrictions. M7: NON.

#### EntryState

Sent in the `entry_state` field at order creation. Default: `"active"`.

- **`active`**: Order enters the book immediately. Default. M7: ACTI.
- **`hibernated`**: Order is registered but not yet visible in the book. Activate later with `PUT /order` using `modify_action: "activate"`. M7: HIBE.

#### Member-specific orders

Use the `v_member_short_id` field to tag an order against a virtual member (for example `"VM001"`). This short ID is written into the M7 `Txt` field. It does not change exchange routing; it provides attribution for audit and reporting.

> [!NOTE]
> If the user does not have the `bypass_member_check` permission, the `v_member_short_id` must be from the list of members assigned to that user (see [GET /users/me/members](#get-me-members)). An order submitted *without* a `v_member_short_id` trades on the global (house) account and requires the `trade_global` permission; a caller lacking it must submit the order under a member (400 otherwise), so the member's MW and cash limits bind and the order stays attributable. A member order is also limited to the member’s `delivery_areas` (see [GET /members](#get-members)): an order in any other area is refused `422` `MEMBER_AREA_NOT_ALLOWED`, for every caller.

<a id="orders" name="orders"></a>

## Orders

Order management: create, modify, cancel, and query your resting orders on the exchange. Orders are identified by a `client_order_id` (UUID) which you supply at submission time. See [Order types](#order-types) in Conventions for the type, restriction and validity enums.

> [!NOTE]
> All order submissions flow through M7. A `201` response means the exchange accepted the order. A `422` with `"state":"REJECTED"` means M7 received it but rejected it (check the `reason` field). A `503` means the system is not connected to the exchange.

### <a id="post-order" name="post-order"></a>`POST` `/api/v1/order`

Submit a new order to the exchange. Specify the contract either by `contract_id` or by `product` + `delivery_start`, or create a user-defined block with `product` + `delivery_start` + `delivery_end`. Returns the exchange-assigned state.

**Required permission:** `create_order`. `bypass_member_check` and `trade_global` widen where the order may be placed. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `side` | `string` | none | Yes | `"BUY"` or `"SELL"`. |
| `price` | `i64` | cents (CCY/MWh × 100) | Yes | Cents/MWh, e.g. `5000` = 50.00 CCY/MWh. May be negative. |
| `quantity` | `u32` | sub-MW (MW × 1000) | Yes | Sub-MW, e.g. `1000` = 1.0 MW. Must be > 0. |
| `delivery_area_id` | `string` | none | Yes | EIC area code, exactly 16 characters (e.g. `10YNL----------L`). Any other length is refused with 400 before anything is sent. Only the length is checked: whether a 16-character code names an area you trade is the exchange’s call. |
| `contract_id` | `i64` | none | Cond* | M7 contract ID. Either this OR `product`+`delivery_start`. |
| `product` | `string` | none | Cond* | Product code (e.g. `"H"`). Used with `delivery_start`. |
| `delivery_start` | `string` | RFC 3339 | Cond* | Used with `product` to look up the contract. Any RFC 3339 instant: `2026-10-25T00:00:00Z`, `2026-10-25T00:00:00.000Z` and `2026-10-25T02:00:00+02:00` name the same contract. The doubled hour of a clock change is two instants: on 2026-10-25, 02:00 CEST is `00:00Z` (hour `02A`) and 02:00 CET is `01:00Z` (hour `02B`). |
| `delivery_end` | `string` | RFC 3339 | No | Creates a user-defined block over `[delivery_start, delivery_end)`. Only with `order_type` = `"block"`, `product` and `delivery_start`, and no `contract_id`; anywhere else it is refused with `400` `BLOCK_DELIVERY_END_INVALID`. See *User-defined blocks* below. |
| `order_type` | `string` | none | No | Default `"regular"`. See [Order types](#order-types). |
| `exe_restriction` | `string` | none | No | Default `"non"`. Options: `non`, `fok`, `ioc`, `aon`. `fok`/`ioc` require `validity_res` = `"non"`. |
| `validity_res` | `string` | none | No | Default `"gfs"`. Options: `gfs`, `gtd`, `non`. |
| `entry_state` | `string` | none | No | Default `"active"`. Use `"hibernated"` to submit inactive. Refused on a `pre_arranged` order. |
| `display_qty` | `u32` | sub-MW (MW × 1000) | Cond | Required for iceberg orders, and rejected on any other order type. Must be < `quantity`. |
| `validity_date` | `string` | RFC 3339 | Cond | An RFC 3339 instant, e.g. `2026-10-25T01:30:00Z`, in the form the exchange’s schema takes: an uppercase `T` and `Z`, seconds up to 59, and an offset within ±14:00, which is forwarded unchanged; a space for the `T`, a lowercase `t` or `z` and a leap second are refused; the exchange works in UTC, so send `Z`; the exchange GUI’s `02:30A` form is refused. Required when `validity_res` = `"gtd"`. |
| `pre_arranged_acct` | `string` | none | Cond | Required when `order_type` = `"pre_arranged"`. 1-32 printable ASCII characters without spaces, quotes, angle brackets or `&`; anything else is refused. |
| `v_member_short_id` | `string` | none | No | Virtual member short ID (e.g. `"VM001"`). Tagged in the M7 Txt field. Max 64 chars. |
| `client_order_id` | `string` | none | No | Optional idempotency key (must be a UUID). Omitted → the gateway generates one, returned in the response. Reusing one the gateway still holds is rejected (`400`); see *Reusing a `client_order_id`* below. |
| `ack_only` | `bool` | none | No | Default `false` waits for the exchange's outcome. `true` returns as soon as the exchange acknowledges receipt. See *Receipt vs. outcome* below. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `client_order_id` | `string` | none | always | The order's idempotency key; the gateway's generated UUID when you sent none. |
| `state` | `string` | none | always | Post-ack order state: `PENDING`, `ACTIVE`, `INACTIVE`, `HIBERNATED`, `REJECTED`, `UNKNOWN`. |
| `reason` | `string \| null` | none | when rejected | The exchange's rejection reason when `state` is `REJECTED`; `null` otherwise. |
| `err_code` | `i64 \| null` | none | always | The exchange's numeric error code when `state` is `REJECTED` and the refusal carried one code (e.g. `1051`); `null` otherwise. |

A `422` with `"state":"REJECTED"` indicates the exchange accepted the message but rejected the order; inspect `reason` and `err_code`. This holds for a refusal that names no order as well: the exchange answers the request it was sent under, so the caller is told at once rather than at the acknowledgement timeout.

**Receipt vs. outcome (`ack_only`).** By default an order command waits for the exchange's outcome: the confirming execution report (*confirmed*) or the exchange's refusal (*rejected*). Setting `ack_only: true` returns as soon as the exchange acknowledges receipt (*acknowledged*, received, outcome not yet known); the same *acknowledged* answer is returned when a waited call's outcome does not arrive inside the order outcome timeout. An `ack_only` caller manages the order lifecycle itself and follows the order stream (WS `orders` / gRPC `WatchOrders`) for the resulting state or a later refusal. For a new order: *confirmed* → `201`; *acknowledged* → `202` with `"state":"PENDING"`; *rejected* → `422`.

**Product parameters and gate closure.** Price and size are measured against the parameters the exchange publishes for the contract’s product, the minimum price increment, the price bounds, the quantity increment, the quantity bounds and the minimum iceberg peak, and against the contract’s own trading state in the delivery area, before anything is sent. An order that breaks one is refused here with a `400` naming the bound, rather than costing a round trip and returning as an exchange rejection that still counts a full order-management transaction. The bounds are the exchange’s own, read off its product reference data rather than transcribed, so a market’s tick, increment and closing rule are always the current ones. Nothing is enforced that the exchange has not published: a contract or a product no report has named yet is left to the exchange to judge, so a late report never costs a legitimate order. Gate closure is read from the contract’s published trading-phase end, which is where a market’s “60 minutes before delivery in XBID, 30 nationally, 5 in a local TSO area” already lives, with a two-second tolerance for clock differences, so the last seconds before closure are never refused early.

**User-defined blocks.** `delivery_end` with `order_type` `"block"`, `product` and `delivery_start` creates one order on the window `[delivery_start, delivery_end)`, traded all at once or not at all. The exchange has no contract for the window until the first order for it: the order is sent naming the product and the window instead of a contract, and the exchange creates the block’s contract, listed in the catalogue and on the contract streams with `predefined: false` and its own window. Until the exchange names it, the pending order carries a gateway placeholder `contract_id` (250 and above); its first report replaces it. Before anything is sent the gateway checks only what the product’s settings and the catalogue state: the product takes blocks (`BLOCK_NOT_SUPPORTED` when its settings say it does not), the window is covered end to end by at least two consecutive contracts of the product in the area (`BLOCK_WINDOW_TOO_SHORT`, `BLOCK_WINDOW_NOT_CONTIGUOUS`), it groups no more contracts than the product’s `blockMaximumHours` (`BLOCK_WINDOW_TOO_LONG`, refused only where the window exceeds that figure both as a count of base contracts and as hours), and the restriction is `aon` or `fok` (`BLOCK_RESTRICTION_NON`; `ioc`, a market sweep, is `BLOCK_SWEEP_UNSUPPORTED`). A setting the product does not publish refuses nothing. The local close, the delivery-day boundary, a clock-change day and the contracts’ trading phase are the exchange’s to judge, and its refusal returns with its own text and `err_code`. The position, slot and cash limits measure the block across every quarter-hour of its window at its full length. Its price and size meet the product’s published bounds, and its size your member’s own order limit, as any order’s do. A block the exchange has already created is joined with its `contract_id` and `order_type` `"block"`; the restriction rule applies to it too. A resting block is modified and cancelled like any order, and its modify restates it as a block with its own restriction (see [`PUT /order`](#put-order)); the exchange modifies one only while every contract under it is active.

**Request expiry.** Every request that adds exposure, a new order, an amendment and an activation, is sent to the exchange with an expiry of `system.order_request_expiration_ms` (10 seconds by default). The exchange drops such a request when it has not taken it off its queue within the expiry, and drops one it took off the queue but had not processed within the expiry again, so a request is executed within twice the expiry of reaching the exchange, or never: a request the exchange cannot process in time is dropped, not executed late. A cancel, cancel-all and a deactivation carry no expiry of their own and keep the exchange’s 45-second default: they only remove exposure, and a dropped cancel would leave an order live exactly when the exchange is backlogged.

**After a 504.** The order keeps counting against your position and cash limits until the exchange answers it with its execution report or its refusal. Without an answer it is released at its **expiry bound**, measured from when the gateway sent it: twice the request expiry plus 5 seconds (25 seconds by default), or, for an order in a delivery area coupled to XBID, twice the expiry plus 25 seconds (45 seconds by default), because the exchange may wait another 20 seconds for XBID’s answer. `system.pending_order_reap_age_ms` can only lengthen that wait. The release needs one more certainty, that no answer can have been missed: the exchange’s order feed has been continuously connected since the order was sent. An acknowledgement of receipt changes nothing either way: the exchange may omit it for an order it processed, and may lose an order it acknowledged. That release is recorded in the order-event message log (the WS [`messages`](ws_api_v1.md#stream-messages) stream and gRPC [`WatchMessages`](grpc_api_v1.md#rpc-WatchMessages); REST has no stream of it), which shows each caller only the entries of its own virtual members, the house-account entries only to a `read_orders` or `bypass_member_check` holder, and the licence, throttling and M7 client certificate notices to everyone, and in the audit log as an `order_rejected` event from the `order_reaper` component.

**If that certainty is not available**, because the order feed dropped or gapped since the order was sent, the order is **held, not released**. It goes on consuming both limits and is reported once in the message log, because the gateway cannot rule out that it is resting at the exchange. It is settled by the first order snapshot taken after its bound, which arrives when the gateway next resubscribes to the exchange’s order feed: if the snapshot carries it, it becomes a normal live order; if not, it is released then, because it can no longer land. A snapshot taken before the bound settles only the orders it carries. An order in an XBID-coupled area is held until its own execution report or refusal, or a restart, when the exchange warned that XBID has not answered it (error 1142), or when the gateway’s connection to the exchange’s message feed reset since it was sent, so such a warning may have been lost: the exchange documents no bound on XBID’s answer. Any held order is released at the latest about an hour after its contract’s delivery ends, when no market still trades the contract; the release is reported in the message log, and an exchange report that still arrives for it counts the order again. The number and size of held orders are on the status aggregate (`stranded_pending_count`, `stranded_pending_qty`). [POST /restart](#post-restart) restarts the process, which releases every held order and rebuilds the order book from the exchange’s own snapshot.

**Reusing a `client_order_id`.** A key is refused for as long as the gateway holds a record of the order it named, whatever that order’s state. A key held by a pending order (including one a `504` left counting), by a resting, hibernated, filled or deleted order, or by an order the exchange rejected is refused with `400` (`"client_order_id '…' is already in use"`). A key whose submission was written off after a `504`, released as described above, or released by a snapshot that did not carry a held order, is **retired** and refused with `400` (`"client_order_id '…' was reclaimed after no exchange acknowledgement; use a new id"`): the written-off order may still be resting at the exchange, and a late report carrying that id must not attach to a different order. If such a report does arrive, the order is confirmed under its own id, its exposure counts again, the event is recorded in the message log, and from then on the key is `already in use`. Retry a timed-out submission with a **new** id. Two keys are free at once: one whose request the gateway refused before sending it to the exchange, and one whose only record is a `NOT_PROCESSED` rejection, which the resubmission replaces.

**How long a key is held.** The record lives in the gateway’s memory, not in the database, so a held key becomes free again when the record goes: when the order has finished and its contract has been swept from the gateway, about an hour after its delivery end (an order still live at the exchange then keeps its record until it finishes, and goes on the next sweep after that), or when the gateway resubscribes to the exchange’s order feed (a restart does too), because the records are then rebuilt from the exchange’s snapshot, which carries only the orders still on the market, the keys of filled and deleted orders are free from that point. An order the exchange rejected was never on its book, so the snapshot does not drop it: its key stays held, and the lookup still answers it `REJECTED` with the exchange’s reason, until the sweep, or until a restart for an order on a contract the gateway never listed, such as a refused new block order, which the sweep does not reach. A pending order’s key and a retired key survive a resubscription and are dropped by a restart; a retired key also survives the sweep, and the 10,000 most recent are remembered. The refusal guards against two orders under one key; it is not a history of every key ever used, so do not reuse a key on purpose except after `NOT_PROCESSED`.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "delivery_area_id is required"}` | Empty `delivery_area_id` |
| 400 | `{"error": "delivery_area_id must be a 16-character EIC code"}` | `delivery_area_id` is not exactly 16 characters |
| 400 | `{"error": "quantity must be greater than zero"}` | `quantity` = 0 |
| 400 | `{"error": "v_member_short_id exceeds maximum length"}` | `v_member_short_id` > 64 chars |
| 400 | `{"error": "display_qty is required for iceberg orders"}` | iceberg type without `display_qty` |
| 400 | `{"error": "display_qty must be less than total quantity for iceberg orders"}` | `display_qty` ≥ `quantity` |
| 400 | `{"error": "pre_arranged_acct is required for pre-arranged trades"}` | `pre_arranged` type without account, or with an empty one |
| 400 | `{"error": "a pre-arranged order cannot be entered hibernated"}` | `pre_arranged` type with `entry_state: "hibernated"`: the exchange reports a hibernated pre-arranged order as inactive, so it could be neither activated nor cancelled |
| 400 | `{"error": "pre_arranged_acct must be 1-32 printable ASCII characters without spaces, quotes, angle brackets or '&'"}` | `pre_arranged_acct` longer than 32 characters, or carrying whitespace, a control or non-ASCII character, or one of `" < > &` |
| 400 | `{"error": "validity_date is required when validity_res is gtd"}` | GTD without `validity_date`, or with an empty one |
| 400 | `{"error": "validity_date must be an RFC 3339 timestamp written as 2026-09-22T16:00:00Z or 2026-09-22T18:00:00+02:00"}` | `validity_date` is not an RFC 3339 timestamp in the form the exchange’s schema takes |
| 400 | `{"error": "validity_res must be \"non\" for fok or ioc orders"}` | FOK/IOC with non-`"non"` validity |
| 400 | `"price must be a multiple of the product tick size of …"` / `"price is below the product minimum of …"` / `"price is above the product maximum of …"` | The price is off the grid the exchange publishes for the contract's product, or outside its price bounds |
| 400 | `"quantity must be a multiple of the product increment of … MW"` / `"quantity is below the product minimum of … MW"` / `"quantity is above the product maximum of … MW"` | The size is off the product's quantity increment or outside its quantity bounds |
| 400 | `"quantity is above the member order limit of … MW"` | The size, an iceberg's full size included, is above the largest single order the exchange allows your member on the contract's product. Checked after the product bounds, so an order outside those is refused for them first. A product with no member limit reported is left to the exchange |
| 400 | `"display_qty is below the product minimum iceberg peak of … MW"` / `"display_qty must be a multiple of the product increment of … MW"` | An iceberg peak under the product's minimum, or off its quantity increment |
| 400 | `"the contract's trading session has closed in this delivery area"` and the related closed / expired / inactive / deactivated / standby messages | The exchange has closed the contract in this delivery area, gate closure, expiry, or a state the exchange has taken it out of service in |
| 400 | `{"error": "provide contract_id or both product and delivery_start"}` | No contract identifier given |
| 400 | `{"error": "delivery_start must be an RFC 3339 timestamp, e.g. 2026-10-25T00:00:00Z"}` | `delivery_start` is not an RFC 3339 timestamp |
| 400 | `{"error": "client_order_id must be a valid UUID"}` | Supplied `client_order_id` is not a UUID. Any UUID spelling is accepted and stored and echoed back in canonical lowercase-hyphenated form |
| 400 | `{"error": "client_order_id '…' is already in use"}` | Supplied `client_order_id` names an order the gateway still holds, in any state. A key whose only record is a request the exchange never received (`NOT_PROCESSED`) is not held and may be reused |
| 400 | `{"error": "client_order_id '…' was reclaimed after no exchange acknowledgement; use a new id"}` | Supplied `client_order_id` named a submission the gateway wrote off after a `504`. The key is retired: submit under a new one |
| 400 | `"v-member '…' not found"` / `"v-member '…' is inactive"` / `"v-member '…' is not assigned to your account"` | `v_member_short_id` names an unknown, deactivated, or unassigned member (assignment is bypassed by `bypass_member_check`) |
| 400 | `{"error": "not permitted to trade on the global account; submit the order under a v-member"}` | No `v_member_short_id` given and the caller lacks `trade_global` |
| 403 | `{"error": "Forbidden"}` | Missing `create_order` permission |
| 404 | `{"error": "contract not found for given delivery parameters"}` | `product`+`delivery_start` lookup failed |
| 422 | `{"error": "position limit exceeded"}` | Net position would exceed the contract limit |
| 422 | `{"error": "slot position limit exceeded: ..."}` | The order's own quarter-hour slots, summed over every contract covering each, would pass the slot position limit (House or the member's own) while the slot limit mode is `reject`; the message names the area, the slot, the side, the scope, the position the order would reach and the limit. A caller without `read_status`, which cannot see the House limit elsewhere, is not shown the House figures: a refusal by the House slot limit reads `slot position limit exceeded: refused by the desk slot limit, <area> <slot start> to <slot end>, <long\|short> side`, and a refusal by the member's own slot limit keeps the member's figures. The `order_rejected` audit row carries every field either way |
| 422 | `{"error": "slot window unknown: ..."}` | A delivery window the slot position limit needs cannot be placed on the quarter-hour grid (the order's own contract, open orders on a contract with no known window, or a trade with no window that can deliver in a slot the order covers: up to the end of the delivery day after the one it executed on (in GB, to 23:00 London two days after it), or any slot of its area when its execution time is unknown) and the order adds exposure; an order that adds none is not refused by it. A caller without `read_status` is not told which trade: the message reads `slot window unknown: a trade in <area> has no delivery time`, and the `order_rejected` audit row still names it |
| 422 | `{"error": "cash limit exceeded"}` | The exposure the exchange's risk parameters put on this order would push consumed cash past one of the pool's bounds, the desk's House limit, the House remainder, the member's allocation, or what the exchange still has available; the pool is already breached; or the pool's holiday calendar is missing (`no_holiday_calendar`) or out of date (`stale_holiday_calendar`). An order that adds no exposure still passes. It also covers a consumed-cash figure the gateway could not finish computing, measured short and refused rather than admitted, with a message-feed line saying no limit was exceeded. See [GET /cash_limit](#get-cash-limit) |
| 422 | `{"error": "SELF_CROSS_BLOCKED: ..."}` | Order would cross one of your own resting orders while `self_trade_policy` is `reject` |
| 422 | `{"error": "trading is disabled by the operator kill-switch..."}` | Trading is disabled (`PUT /trading_allowed` set `enabled:false`). Order traffic is rejected before reaching M7 |
| 422 | `{"error": "M7 load management: ..."}` / `{"error": "M7 has order-throttled this member..."}` | The client-side load-management guard refused the action, or the exchange already has the member restricted. See [GET /throttling](#get-throttling) |
| 422 | `PRODUCT_SCALE_UNSUPPORTED` | M7 published a decimal scale or quantity unit for the product this gateway cannot denominate. Not malformed and not transient: trading this product is refused until M7 changes it |
| 422 | `{"error": "CONTRACT_IN_DELIVERY: contract … in … has reached its delivery start and takes no order that adds exposure"}` | The contract has reached its delivery start on the gateway’s clock. Refused before anything reaches M7, whatever state the exchange still lists the contract in; on the production markets the exchange’s published gate-closure parameters close trading at or before the delivery start, so there this refuses nothing the exchange would still take. The refusal does not depend on the exchange refusing such an order, and applies as well in a test environment that still accepts one after the delivery start. Not transient. Orders already resting on the contract stay listed by [GET /orders](#get-orders) and are cancelled with [DELETE /order](#delete-order) |
| 422 | `{"error": "MEMBER_AREA_NOT_ALLOWED: member … may not trade delivery area …"}` | The order is tagged with a member whose [delivery areas](#get-members) do not include `delivery_area_id`. Refused before anything reaches M7, for every caller, `bypass_member_check` included; a block and a pre-arranged order alike. Not transient: give the member the area first |
| 400 | `{"error": "BLOCK_DELIVERY_END_INVALID: …"}` | `delivery_end` without `order_type` `"block"`, with a `contract_id`, or without `product` and `delivery_start` |
| 400 | `{"error": "BLOCK_RESTRICTION_NON: …"}` | A block order, created or joined, with `exe_restriction` `"non"`; a block takes `aon` or `fok` |
| 400 | `{"error": "BLOCK_WINDOW_TOO_SHORT: …"}` | The block window covers fewer than two contracts of its product |
| 422 | `{"error": "BLOCK_SWEEP_UNSUPPORTED: …"}` | A block order with `exe_restriction` `"ioc"`: a market sweep, not supported |
| 422 | `{"error": "BLOCK_NOT_SUPPORTED: …"}` | The product’s settings say it takes no user-defined blocks |
| 422 | `{"error": "BLOCK_WINDOW_NOT_CONTIGUOUS: …"}` | The window does not start and end on the product’s contract boundaries, or a contract is missing between them, in the area’s catalogue |
| 422 | `{"error": "BLOCK_WINDOW_TOO_LONG: …"}` | The window exceeds the product’s `blockMaximumHours` |
| 400 | `"… is not on the product's M7 grid (decShftQty …)"` | The price or size is a valid gateway integer but is not exactly expressible on the product's own M7 decimal grid; the message names the scale. A client-correctable value, not a scale fault |
| 503 | `{"error": "…"}` | System not connected / not operational |
| 503 | `PRODUCT_SCALE_UNKNOWN` | The product's per-product decimal scale has not yet been recorded. A transient login prerequisite: a targeted parameter inquiry has been issued and the order is safe to retry once the report lands |
| 503 | `{"error": "NOT_PROCESSED: the request was returned undelivered by the exchange and was not processed (…)"}` | The exchange handed the request back undelivered, so the order definitely was not placed. Unlike `504`, which is unknown, this is safe to resubmit **with the same `client_order_id`**: the exchange never saw the key, so it is freed and the resubmission replaces the record. The order is recorded `REJECTED` with the same reason and gives back the limit headroom it was holding |
| 504 | `{"error": "…"}` | M7 did not acknowledge within the order acknowledgement timeout (2 seconds by default). The outcome is *unknown*, not failed, the request may still have been processed, so re-check before resubmitting |
| 500 | `{"error": "…"}` | Publish failed or internal error |

#### Example

```bash
curl -X POST https://gateway.example:3000/api/v1/order \
  -H "Authorization: Bearer $VOLTNIR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "side": "BUY",
    "price": 5000,
    "quantity": 1000,
    "delivery_area_id": "10YNL----------L",
    "product": "H",
    "delivery_start": "2026-04-20T22:00:00Z",
    "order_type": "regular",
    "exe_restriction": "non",
    "validity_res": "gfs"
  }'
```

```
HTTP/1.1 201 Created
{
  "client_order_id": "550e8400-e29b-41d4-a716-446655440000",
  "state": "ACTIVE",
  "reason": null
}
```

### <a id="put-order" name="put-order"></a>`PUT` `/api/v1/order`

Modify an existing order: change price and quantity (`modify`), hibernate it (`deactivate`), or un-hibernate it (`activate`).

**Required permission:** `modify_order`, plus the right to act on the existing order's member. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `client_order_id` | `string` | none | Yes | UUID of the order to modify. |
| `modify_action` | `string` | none | No | Default `"modify"`. Options: `modify`, `activate`, `deactivate`. |
| `price` | `i64` | cents (CCY/MWh × 100) | Cond | Required when `modify_action` = `"modify"`. |
| `quantity` | `u32` | sub-MW (MW × 1000) | Cond | Required when `modify_action` = `"modify"`, and must be greater than zero. |
| `display_qty` | `u32` | sub-MW (MW × 1000) | No | For iceberg orders. Checked only when `modify_action` = `"modify"` and `quantity` is also provided; it must then be < `quantity`. |
| `validity_res` | `string` | none | No | Optional change to validity restriction. |
| `validity_date` | `string` | RFC 3339 | Cond | An RFC 3339 instant, e.g. `2026-10-25T01:30:00Z`, in the form the exchange’s schema takes: an uppercase `T` and `Z`, seconds up to 59, and an offset within ±14:00, which is forwarded unchanged; a space for the `T`, a lowercase `t` or `z` and a leap second are refused; the exchange works in UTC, so send `Z`; the exchange GUI’s `02:30A` form is refused. Required when `validity_res` = `"gtd"`. |
| `v_member_short_id` | `string` | none | No | Max 64 chars. May only restate the order's own member; a different one is `404`. Omit it and the order keeps the member it has. |
| `ack_only` | `bool` | none | No | Default `false` waits for the exchange's outcome. `true` returns as soon as the exchange acknowledges receipt. See *Receipt vs. outcome* below. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `status` | `string` | none | always | `"modified"` on a confirmed change (`200`), or `"acknowledged"` when only the receipt is known (`202`). |

The result waits for the exchange to acknowledge receipt before responding: `200` means M7 accepted the request, `409` means M7 rejected it (for example the order was concurrently filled or deleted), `503` means the request was returned undelivered and definitely not applied, and `504` means no acknowledgement arrived in time (unknown, not failed). The resulting order state is delivered on the order stream.

**Member isolation.** Beyond the `modify_order` capability, the caller must be authorized to act on the *existing* order's member: assigned to it, or holding `bypass_member_check`; an untagged house order requires `trade_global`. An order outside that scope returns `404` (identical to a missing one), so a desk cannot modify or re-tag another member's order.

**One modify at a time, and the conflict clears itself.** While a modify is in flight, a second modify on the same `client_order_id` is refused with `409 modify already in progress` and a cancel with `409 modify in progress, retry after confirmation`: the exchange replaces an order on modify, so a second command dispatched in that window would target an order id that no longer exists. The lock is released by the exchange's execution report, and it expires on its own after the receipt wait plus the outcome wait together (5 seconds by default, floored at 1 second) from when it was taken, a moment before the modify's own waits do, by design. An execution report that never arrives therefore costs one such window, not the order: retry after it and the next modify takes the lock.

> [!WARNING]
> **A modify is a full pre-trade entry.** The exchange re-creates an order on every amendment, so `modify` and `activate` both run the *whole* gate, position limits (House and member), slot position limits, cash limits, and self-trade prevention, with the same rejections as [`POST /order`](#post-order), and can be refused. For a live order the gate measures the *change*: it is checked on the price and quantity the order will carry, against sums that already contain the order being amended, so a reprice or resize that lowers exposure always passes. The exposure an admitted amendment adds, a larger size or a costlier price, and the whole returning size of an activation, count against your limits from the moment it is sent until the exchange's answer settles it, so two amendments sent at once cannot both spend the same room. An amendment that lowers exposure frees nothing until the exchange confirms it. Self-trade prevention is checked at the new price, and an order is never treated as crossing itself. It also sees where your other orders are *going*: an amendment to an order *on the book*, already sent to the exchange but not yet confirmed, is measured at both the price it rests at and the price it is moving to, so two amendments in flight at once cannot cross each other. That second reading is dropped as soon as the exchange settles the amendment, or after the same window as the modify lock if no answer arrives. Only orders that can actually fill are counted, and the check never refuses an amendment that can only shrink a cross. A hibernated order holds no exposure, so it is off the book, is not a self-cross counterparty, and `activate` is gated for the order's whole returning size, while a `modify` on an already-hibernated order changes no live exposure and is checked when it is activated instead. `deactivate` only removes exposure: it is never refused on a limit, and, like [`DELETE /order`](#delete-order), it is not gated on the gateway being operational either, so the way out of the market stays open through an outage. It still awaits the exchange's receipt, so it never reports a hibernation the exchange did not take. A `modify` also faces the product’s bounds and your member’s own order limit on its new price and size; an `activate` brings back the size the exchange already accepted and is measured against neither.

**An order's member is fixed for its life.** M7 re-creates an order on every amendment, so the member tag this request publishes is what the new revision comes back on. Every action does it, a re-price, an activation and a hibernation all re-send the order's own text, because M7 re-creates an order on an amendment and does not define what an omitted text field leaves behind. The text an amendment sends is never poorer than the one the order already holds: the delivery duration, delivery start and product it was entered with ride along even when the contract is no longer in the gateway's own order book, so a quarter-hour leg cannot come back looking like an hour. That tag is always the order's existing one, never a value in the body: naming a different member, or naming any member on an untagged house order, is refused with the same `404` an out-of-scope order gets, so the endpoint is not a way to learn which member an order belongs to. To move exposure between members, cancel and re-enter.

**An order keeps its execution restriction.** The exchange re-creates an order on every amendment and reads an amendment that names no restriction as `non`, which it refuses on a block. So every action, a re-price, a resize, an activation and a hibernation, restates the order’s own type and execution restriction as the exchange last reported it, or all-or-none for a block whose report names none: a block goes out as a block with its `aon` or `fok`, and an order without a restriction is sent exactly as before. A modify cannot change the restriction; to change it, cancel and re-enter.

**Receipt vs. outcome (`ack_only`).** By default a modify waits for the exchange's outcome: the confirming execution report (*confirmed* → `200 {"status":"modified"}`) or the exchange's refusal (*rejected* → `409`, led by `ORDER_CHANGED` when the order's revision moved under the command). A waited call is confirmed only on its own command's report: when two commands on the order are at the exchange at once and one report could be either's (a modify retried at the same revision), neither is confirmed on it. The one the exchange refuses is answered with that refusal, the other is then confirmed, and with no refusal on either command's correlation id inside the order outcome timeout both are answered *acknowledged*. Setting `ack_only: true` returns as soon as the exchange acknowledges receipt (*acknowledged* → `202 {"status":"acknowledged"}`); the same *acknowledged* answer is returned when a waited call's outcome does not arrive inside the order outcome timeout. An `ack_only` caller manages the order lifecycle itself and follows the order stream (WS `orders` / gRPC `WatchOrders`) for the resulting state or a later refusal. A modify on an order the exchange has not yet acknowledged, which a new order answered *acknowledged* may still be, is refused `409` led by `ORDER_PENDING`: retry once the order is acknowledged, or wait for it on the order stream.

**Expiry and held headroom.** An amendment and an activation carry the request expiry described under [POST /order](#post-order), and the exposure they add is released the same way as a pending order’s: at any time on the exchange’s answer (the command’s own execution report or refusal, a later revision of the order, or the order leaving the book), and without one only at the command’s expiry bound with the order feed continuously connected; otherwise it is held and reported once. An XBID timeout warning (error 1142) is not a refusal: the added exposure stays held until the command’s own report or a restart, and a caller still waiting is answered `202 {"status":"acknowledged"}`, never a refusal. The number and size of these claims, and of the held ones, are on the status aggregate (`claims_count`, `claims_qty`, `claims_held_count`, `claims_held_qty`).

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "price is required for modify action"}` | `modify` action without `price` |
| 400 | `{"error": "quantity is required for modify action"}` | `modify` action without `quantity` |
| 400 | `{"error": "display_qty must be less than quantity"}` | `modify_action` = `"modify"` with both `display_qty` and `quantity` and `display_qty` ≥ `quantity` |
| 400 | The product tick, bounds, increment, iceberg peak and grid messages listed under [POST /order](#post-order) | Restated price or size off the product grid or outside its bounds |
| 400 | The contract closed / expired / inactive / deactivated / standby messages listed under [POST /order](#post-order) | The exchange has taken the contract out of service in this delivery area |
| 400 | `{"error": "validity_date is required when validity_res is gtd"}` | GTD without `validity_date`, or with an empty one |
| 400 | `{"error": "validity_date must be an RFC 3339 timestamp written as 2026-09-22T16:00:00Z or 2026-09-22T18:00:00+02:00"}` | `validity_date` is not an RFC 3339 timestamp in the form the exchange’s schema takes |
| 403 | `{"error": "Forbidden"}` | Missing `modify_order` permission |
| 404 | `{"error": "order not found"}` (may carry the exchange order id) | `client_order_id` not found, the order's member is outside the caller's scope, or `v_member_short_id` names a member other than the order's own |
| 409 | `{"error": "modify already in progress"}` | Another modify on the same order is in flight. Self-clearing after the receipt wait plus the outcome wait together (5 seconds by default, floored at 1 second) |
| 409 | `{"error": "exchange rejected the request: ..."}` | M7 rejected the modify (for example the order was concurrently filled or deleted) |
| 409 | `{"error": "ORDER_CHANGED: the order changed at the exchange before the command was applied ... (…)"}` | A fill or another modify moved the order's revision while the command was on its way, so the exchange refused it on its revision guard. Nothing was applied. Retry the same command: it is rebuilt on the revision the gateway now holds. Bound the retry rather than looping |
| 409 | `{"error": "ORDER_PENDING: the order is accepted but not yet acknowledged by the exchange, so retry once it is"}` | The order was sent and the exchange has not yet acknowledged it, so there is no exchange order to modify. Nothing was sent. Retry once the order is acknowledged, or wait for it on the order stream. Answered only to a caller who may act on the order’s member; anyone else gets the `404` an unknown order gets |
| 422 | `{"error": "trading is disabled by the operator kill-switch..."}` | Trading is disabled (`PUT /trading_allowed` set `enabled:false`) |
| 422 | `{"error": "position limit exceeded"}` / `{"error": "cash limit exceeded"}` | The change, or, on `activate`, the returning exposure, would breach the per-contract limit or the cash limit (the same pre-trade checks as `POST /order`) |
| 422 | `{"error": "slot position limit exceeded: ..."}` / `{"error": "slot window unknown: ..."}` | The change, or, on `activate`, the returning exposure, would breach the slot position limit, or a window it needs cannot be placed (the same slot check as `POST /order`) |
| 422 | `{"error": "SELF_CROSS_BLOCKED: order would cross your own resting order (self-trade)"}` | The order's new or parked price would cross one of the desk's own resting or in-flight orders while the self-trade policy is `reject` |
| 422 | `{"error": "M7 load management: ..."}` / `{"error": "M7 has order-throttled this member..."}` | The client-side load-management guard refused the action, or the exchange already has the member restricted. See [GET /throttling](#get-throttling) |
| 422 | `PRODUCT_SCALE_UNSUPPORTED` | The product's published decimal scale or quantity unit is one the gateway cannot denominate; trading it is refused until M7 changes it |
| 422 | `{"error": "CONTRACT_IN_DELIVERY: ..."}` | The contract has reached its delivery start on the gateway’s clock and the command adds exposure: `activate` (a re-entry at the exchange), or `modify` with a larger `quantity` or any new `price` (a delete and re-entry at M7). A shrink at the same price is not refused with this error, though like any `modify` it is refused `400` (for example `the contract has expired`) once the exchange shows the contract closed. `deactivate` and a cancel are refused by neither |
| 422 | `{"error": "MEMBER_AREA_NOT_ALLOWED: member … may not trade delivery area …"}` | The order belongs to a member whose [delivery areas](#get-members) no longer include the order’s area. Refused on every `modify_action` (`modify`, `activate`, `deactivate`) for every caller |
| 400 | `"… is not on the product's M7 grid (decShftQty …)"` | On a `modify`, the restated price/size is not exactly expressible on the product's own M7 grid; the message names the scale |
| 503 | `{"error": "…"}` | System not operational. Applies to `modify` and `activate`, which add exposure; `deactivate` passes through a degraded gateway exactly as `DELETE /order` does. It still waits for the exchange's receipt, so a refusal comes back as `409` and an unanswered request as `504` |
| 503 | `PRODUCT_SCALE_UNKNOWN` | The product's decimal scale is not yet recorded, so no arm can convert the order to the M7 wire; a parameter inquiry has been issued and the amendment is safe to retry once it lands |
| 503 | `{"error": "NOT_PROCESSED: the request was returned undelivered by the exchange and was not processed (…)"}` | The exchange handed the request back undelivered, so it definitely was not applied. Unlike `504`, this is safe to resubmit unchanged |
| 504 | `{"error": "…"}` | M7 did not acknowledge within the order acknowledgement timeout (2 seconds by default). The outcome is *unknown*, not failed, so re-check before resubmitting |
| 500 | `{"error": "…"}` | Publish failed |

#### Example

```bash
curl -X PUT https://gateway.example:3000/api/v1/order \
  -H "Authorization: Bearer $VOLTNIR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"client_order_id": "550e8400-e29b-41d4-a716-446655440000", "modify_action": "modify", "price": 5200, "quantity": 2000}'
```

```
HTTP/1.1 200 OK
{"status": "modified"}
```

### <a id="delete-order" name="delete-order"></a>`DELETE` `/api/v1/order`

Cancel a single resting order. The order must be in `ACTIVE` or `HIBERNATED` state, and no concurrent modify may be in progress.

**Required permission:** `delete_order`, plus the right to act on the order's member. Not gated by the trading kill-switch: a cancel only reduces exposure. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `client_order_id` | `string` | none | Yes | UUID of the order to cancel. |
| `ack_only` | `bool` | none | No | Default `false` waits for the exchange's outcome. `true` returns as soon as the exchange acknowledges receipt. See *Receipt vs. outcome* below. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `status` | `string` | none | always | `"cancelled"` when the deletion's execution report confirmed the cancel (`200`), or `"acknowledged"` when only the receipt is known (`202`). |

The result waits for the exchange's outcome before responding (for its receipt only with `ack_only`): `200` confirms the cancel, `202` means the exchange received it but its outcome is not yet known, `409` means M7 rejected it, `503` means the cancel was returned undelivered and definitely not applied, and `504` means no acknowledgement arrived in time (unknown, not failed).

**Member isolation.** Beyond the `delete_order` capability, the caller must be authorized to act on the order's member (assigned to it, or holding `bypass_member_check`); an untagged house order requires `trade_global`. This is the same gate as order submission, and it is *not* the read grant: `read_orders` lets you see an order, not cancel it. An order you may not act on returns `404`, identical to a missing one.

**Receipt vs. outcome (`ack_only`).** By default a cancel waits for the exchange's outcome: the deletion's execution report (*confirmed* → `200 {"status":"cancelled"}`) or the exchange's refusal (*rejected* → `409`, led by `ORDER_CHANGED` when the order's revision moved under the command). A waited call is confirmed only on its own command's report: when two cancels of the order are at the exchange at once, the deletion's report could be either's, so neither is confirmed on it. The exchange deletes the order for one and refuses the other (M7 error 2014, order not found); the losing cancel is answered with that refusal, the other is then confirmed, and with no refusal on either command's correlation id inside the order outcome timeout both are answered *acknowledged*. Setting `ack_only: true` returns as soon as the exchange acknowledges receipt (*acknowledged* → `202 {"status":"acknowledged"}`); the same *acknowledged* answer is returned when a waited call's outcome does not arrive inside the order outcome timeout. An `ack_only` caller follows the order stream (WS `orders` / gRPC `WatchOrders`) for the resulting state or a later refusal. A cancel of an order the exchange has not yet acknowledged, which a new order answered *acknowledged* may still be, is refused `409` led by `ORDER_PENDING`: retry once the order is acknowledged, or wait for it on the order stream. A cancel carries no request expiry: it keeps the exchange’s 45-second default, so a cancel queued behind a backlog is still executed rather than dropped.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 403 | `{"error": "Forbidden"}` | Missing `delete_order` permission |
| 404 | `{"error": "order not found"}` | `client_order_id` not found, or the order's member is outside the caller's scope |
| 409 | `{"error": "order is not active (state: …)"}` | Order not in ACTIVE or HIBERNATED state |
| 409 | `{"error": "modify in progress, retry after confirmation"}` | A modify on the same order is in flight. Bounded like the `PUT /order` conflict: at most the receipt wait plus the outcome wait together (5 seconds by default, floored at 1 second) |
| 409 | `{"error": "exchange rejected the request: ..."}` | M7 rejected the cancel (for example the order was concurrently filled or deleted) |
| 409 | `{"error": "ORDER_CHANGED: the order changed at the exchange before the command was applied ... (…)"}` | A fill or another modify moved the order's revision while the command was on its way. Nothing was applied. Retry the same command; bound the retry rather than looping, and a cancel may find the order already gone next time |
| 409 | `{"error": "ORDER_PENDING: the order is accepted but not yet acknowledged by the exchange, so retry once it is"}` | The order was sent and the exchange has not yet acknowledged it, so there is no exchange order to cancel. Nothing was sent, and the order may rest once it is acknowledged: retry the cancel then, or wait for the order on the order stream. Answered only to a caller who may act on the order’s member; anyone else gets the `404` an unknown order gets |
| 422 | `{"error": "M7 has order-throttled this member..."}` | M7 has the whole member order-throttled, so the exchange would reject this cancel. Cancels are otherwise never refused by the load-management guard. See [GET /throttling](#get-throttling) |
| 422 | `{"error": "MEMBER_AREA_NOT_ALLOWED: member … may not trade delivery area …"}` | The order belongs to a member whose [delivery areas](#get-members) no longer include the order’s area. Refused for every caller; [DELETE /orders](#delete-orders) skips such an order, and an account-wide cancel-all or the kill switch still pulls it |
| 503 | `{"error": "NOT_PROCESSED: the request was returned undelivered by the exchange and was not processed (…)"}` | The exchange handed the request back undelivered, so it definitely was not applied. Unlike `504`, this is safe to resubmit unchanged |
| 504 | `{"error": "…"}` | M7 did not acknowledge within the order acknowledgement timeout (2 seconds by default). The outcome is *unknown*, not failed, so re-check before resubmitting |
| 500 | `{"error": "…"}` | Publish failed |

#### Example

```bash
curl -X DELETE https://gateway.example:3000/api/v1/order \
  -H "Authorization: Bearer $VOLTNIR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"client_order_id": "550e8400-e29b-41d4-a716-446655440000"}'
```

```
HTTP/1.1 200 OK
{"status": "cancelled"}
```

### <a id="delete-orders" name="delete-orders"></a>`DELETE` `/api/v1/orders`

Cancel all resting orders the caller is authorized to act on. Returns the count of orders whose cancel the exchange acknowledged. No request body required.

**Required permission:** `delete_order`. Not gated by the trading kill-switch: it only reduces exposure. (see [Permissions](#permissions))

#### Request

None. No request body or parameters.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `deleted` | `integer` | count | always | Number of orders whose cancel the exchange acknowledged: for the account-wide cancel, the login user's own active orders, pre-arranged ones included, when the command was sent; for a member-scoped cancel, the orders whose own cancel it acknowledged. |

**Member isolation.** A *full-authority* caller, holding both `bypass_member_check` (any member) and `trade_global` (the house book), cancels the whole account in a single atomic exchange command. A member-scoped caller instead cancels only the orders whose member they may act on, one per order; other desks' orders, and (without `trade_global`) the house orders, are left untouched. `read_orders` does not grant cancellation. Either arm acts only on orders this gateway's own login user placed, never a colleague's on the same membership.

**Member delivery areas.** A member-scoped cancel skips an order whose member may not trade the order’s area (see [members](#get-members)): it is neither cancelled nor counted as targeted. The account-wide cancel of a full-authority caller is one exchange command and pulls it with everything else.

> [!CAUTION]
> For a full-authority caller this cancels all of the account's resting orders simultaneously. It is also triggered automatically when `PUT /trading_allowed` sets `enabled: false` (an operator/system action, full authority).

**Waits for the exchange’s receipt** before responding: the account-wide cancel is one request and one receipt; a member-scoped cancel sends one cancel per order and awaits each receipt. It does not wait for each deletion’s execution report: the resulting order states arrive on the order stream.

**A member-scoped cancel succeeds only when the exchange acknowledges the cancel for every order it targeted.** If the exchange refuses one, or one cannot be sent because its product’s price scale is unknown or unsupported, the cancel still goes out for every other order and the request then fails. If the route to the exchange fails, it stops at that order. Either way the error carries that failure’s own status, so a refusal is `409`, and its message ends with the counts, for example `(cancel-all incomplete: the exchange acknowledged the cancel for 2 of 3 targeted orders; 1 may still be resting)`. The account-wide cancel is one exchange command with no partial outcome, so its errors carry no counts.

**An order not yet acknowledged leaves a member-scoped cancel incomplete.** One of the caller’s orders that the exchange has not yet acknowledged has no exchange order id to cancel by. The cancel still goes out for every acknowledged order, and the request then fails `409` led by `ORDER_PENDING`, with that order counted as targeted and not acknowledged, for example `ORDER_PENDING: … (cancel-all incomplete: the exchange acknowledged the cancel for 1 of 2 targeted orders; 1 may still be resting)`. Call it again once the order is acknowledged. A refusal of one of the acknowledged orders stays the error’s cause, and the counts still include the unacknowledged order. Another desk’s unacknowledged order does not count. The account-wide cancel is unchanged.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 403 | `{"error": "Forbidden"}` | Missing `delete_order` permission |
| 409 | `{"error": "exchange rejected the request: …"}` | M7 rejected the account-wide cancel, or one of a member-scoped cancel’s orders; the message then ends with the counts |
| 409 | `{"error": "ORDER_PENDING: … (cancel-all incomplete: …)"}` | A member-scoped cancel met one or more of the caller’s orders the exchange has not yet acknowledged; every other order’s cancel went out. Call it again once they are acknowledged |
| 422 | `{"error": "…"}` | The exchange has the member order-restricted, so load management refused the cancel; or a member-scoped cancel met an order whose product’s price scale is unsupported |
| 503 | `{"error": "NOT_PROCESSED: the request was returned undelivered by the exchange and was not processed (…)"}` | The exchange handed the request back undelivered, so it definitely was not applied. Unlike `504`, this is safe to resubmit unchanged. Also returned when a member-scoped cancel met an order whose product’s price scale is not yet known |
| 504 | `{"error": "…"}` | M7 did not acknowledge within the order acknowledgement timeout (2 seconds by default). The outcome is *unknown*, not failed, so re-check before resubmitting |
| 500 | `{"error": "…"}` | Publish failed |

#### Example

```bash
curl -X DELETE https://gateway.example:3000/api/v1/orders \
  -H "Authorization: Bearer $VOLTNIR_API_KEY"
```

```
HTTP/1.1 200 OK
{"deleted": 3}
```

### <a id="post-basket" name="post-basket"></a>`POST` `/api/v1/basket`

Enter 1 to 100 orders as one exchange order entry under one list instruction.

**Required permission:** `create_order`. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `basket_ref` | `string` (UUID) | none | optional | Idempotency key; absent has the gateway mint one. |
| `list_exec_inst` | `string` | none | required | `none`, `valid` or `linked`. |
| `orders` | `array` | none | required | 1 to 100 orders, each the body of a [`POST /order`](#post-order). |

- `none`: the exchange validates and processes each order on its own.
- `valid`: every order must pass the exchange’s entry validation or the whole list is rejected; accepted orders then rest independently.
- `linked`: every order must be `fok` (with validity `non`); the list executes whole or the exchange deletes it whole, and its orders never match each other. All orders must be on local products or all on remote products; different products may be mixed.

**All or none at the gateway.** Every order is checked before anything is sent, with the checks a single order takes: the field rules, member and delivery area, the contract and its product’s bounds, position, slot and cash limits and the self-cross policy. Every order is evaluated, and one failure refuses the whole basket with `BASKET_REFUSED`, whose message lists each failing order as `[<index>] <CODE>: <text>` joined by `"; "`. Nothing reaches the exchange then. A field the single-order validator refuses keeps its own code, with the order’s index leading its message. A `none` or `valid` basket is checked as if its orders were entered one after another, so a later order sees the earlier ones resting and an order crossing an earlier one meets the self-cross policy, because the exchange matches them. A `linked` basket fills whole or not at all, so position and slot limits are checked on its net effect: an hourly buy and the four quarter-hour sells of that hour, of equal size, move no slot. Its cash is the sum of each order’s own requirement, because the exchange checks cash per order, and the self-cross scan passes over its own orders, which cannot match each other, but sees every other order of the desk.

**Load management.** A basket spends one order transaction per order. One that would take the member past the gateway’s throttling threshold is refused whole and spends nothing.

**The basket reference.** `basket_ref` is a UUID idempotency key; leave it out and the gateway mints one. Every order of the basket carries it as `basket_ref` on the order views, read back from the order’s own text, so it survives a gateway restart. Whether the orders do is the exchange's decision: it may delete every order of a basket when the gateway logs out or disconnects, a restart included, although on the exchange's simulator it kept them through a restart. The gateway shows what the exchange reports afterwards. A reference the gateway still holds a basket under is refused `BASKET_REF_IN_USE`. Each order may carry its own `client_order_id`; two orders under one id are refused. A basket always waits for its outcomes, so an order’s `ack_only` is not read. A block create (`delivery_end`) is refused; join an existing block by its `contract_id`.

#### Response

`201` once every order has its outcome, `202` while any is `PENDING`, `422` when the exchange rejected every order.

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `basket_ref` | `string` | none | always | The basket reference, as sent or as minted. |
| `list_exec_inst` | `string` | none | always | As sent. |
| `basket_id` | `u64 \| null` | none | always | The exchange’s basket id; `null` when it reported none. |
| `orders` | `array` | none | always | Each order’s `client_order_id`, `state`, `reason` and `err_code`, in request order. |

**The answer** lists each order’s outcome in request order with the fields a single submit answers. It waits for every order’s outcome, within the order acknowledgement window and then the outcome window; an order without one is `PENDING`. The exchange’s rejection of a `valid` list, the kill of a `linked` list and the refusal of single orders are each order’s `state` and `err_code`, never an error. The exchange rejects a `valid` or `linked` list whole, so when it refuses one, every order of the list is answered `REJECTED`, an order the refusal did not name with the refusal’s own `reason` and `err_code`; a refusal naming some orders of a `none` list rejects those alone. `basket_id` is the exchange’s own id, reported only for a basket of two or more orders.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "[1] …"}` | An order the single-order validator refuses; its index leads the message, which keeps its own status. |
| 400 | `{"error": "list_exec_inst must be one of none, valid, linked"}` | An unknown list instruction. |
| 400 | `{"error": "BASKET_EMPTY: …"}` | The basket carries no order. |
| 400 | `{"error": "BASKET_TOO_LARGE: …"}` | The basket carries more than 100 orders. |
| 400 | `{"error": "BASKET_LINKED_REQUIRES_FOK: …"}` | A `linked` basket with an order that is not `fok`; the message names it. |
| 400 | `{"error": "BASKET_DUPLICATE_ORDER_ID: …"}` | Two orders under one `client_order_id`. |
| 400 | `{"error": "BASKET_BLOCK_UNSUPPORTED: …"}` | An order would create a user-defined block. |
| 400 | `{"error": "BASKET_REF_IN_USE: …"}` | The gateway still holds a basket under this `basket_ref`. |
| 422 | `{"error": "BASKET_LINKED_NOT_SUPPORTED: …"}` | A `linked` basket on a product that publishes `linked_order_product` false. |
| 422 | `{"error": "BASKET_REFUSED: …"}` | One or more orders failed an admission check; each is listed with its own code. |
| 422 | `{"error": "trading is disabled …"}` | The kill switch is engaged; or load management refused the basket. |
| 503 | `{"error": "NOT_PROCESSED: …"}` | The exchange handed the basket back undelivered: no order of it was processed, and it is safe to resubmit with the same references. |

#### Example

```
POST /api/v1/basket
{"list_exec_inst": "linked",
 "orders": [
  {"side": "BUY",  "price": 5000, "quantity": 1000, "delivery_area_id": "10YDE-RWENET---I", "contract_id": 111, "exe_restriction": "fok", "validity_res": "non"},
  {"side": "SELL", "price": 5100, "quantity": 1000, "delivery_area_id": "10YDE-RWENET---I", "contract_id": 222, "exe_restriction": "fok", "validity_res": "non"}]}
// → 201 {"basket_ref": "…", "list_exec_inst": "linked", "basket_id": 4711,
//    "orders": [{"client_order_id": "…", "state": "INACTIVE", "reason": null, "err_code": null}, …]}
```

### <a id="delete-basket" name="delete-basket"></a>`DELETE` `/api/v1/basket`

Cancel every resting order of one basket that the caller may act on: the login user’s own orders in the caller’s member scope. One cancel per order, each awaiting the exchange’s receipt, never a multi-order request. A basket with no order the caller may act on is not found. A cancel only takes exposure off, so load management never refuses it for headroom; while the exchange has the member restricted it is refused, as a single cancel is.

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

| Status | Body | Condition |
| --- | --- | --- |
| 403 | `{"error": "Forbidden"}` | Missing `delete_order` permission |
| 404 | `{"error": "BASKET_NOT_FOUND: …"}` | No order of the basket is held for this caller. |
| 422 | `{"error": "…"}` | The exchange has the member order-restricted, so load management refused the first cancel. |

### <a id="post-trade-recall" name="post-trade-recall"></a>`POST` `/api/v1/trade/recall`

Ask the exchange to recall an executed trade (a mistrade), or every recallable trade of one order. Mirrors gRPC `RecallTrade` and the WebSocket `recall_trade` command, with the same fields, codes and statuses.

**Required permission:** `recall_trade`. (see [Permissions](#permissions))

**Whose trade.** Only a trade this gateway's exchange login placed can be recalled, and only for a member you may act on: a member you are assigned to (or any member with `bypass_member_check`); a House trade needs `trade_global`. A trade placed by another exchange user on your balancing group, which the exchange reports to your login too, is refused as not your own. A trade you cannot see, or one of a member you may not act on, is not found.

**The exchange's rules, not the gateway's.** The exchange accepts a recall only within its windows: a trade can be recalled within 5 minutes of its execution (error 2013 after that), not too close to its delivery (2012, 3007), not below its turnover floor (3008), and never for an auction (3009) or OTC trade (3017); a trade already recalled, rejected, granted or requested is refused too (3001, 3004, 3005, 3006). The gateway applies none of these windows: it forwards the request and reports the exchange's refusal with its code. It refuses only a trade that is not `ACTI` and a `revision_no` it has seen move on. Market operations decide a recall that was accepted; the decision arrives later as the trade's new state, `RGRA` (granted, the trade is reversed) or `RREJ` (rejected, the trade stands).

**Cascade.** A cross-contract trade carries a `parent_trade_id`, and recalling it recalls every trade with the same parent at once. A recall by `client_order_id` therefore sends one request per parent; the other trades of that parent follow it: `cascaded` when the exchange took the request (`requested` or `submitted`), otherwise the request's own outcome, reason and code (`refused`, `unknown`, `not_sent`), so a trade is never shown recalled when its group's request was not; a recall by `trade_id` names them in `cascaded_with`.

**One order, every fill.** An order that filled in several trades needs one recall per trade, each inside the exchange's window. A recall by `client_order_id` recalls every trade of the order you hold (its modifications keep the id, so every fill of the order is found) and sends the requests at once, so the whole order is answered within one wait rather than one per trade.

**Limits.** A recall is not an order management transaction and never counts against the exchange's load-management limits. Each request the gateway sends counts once against your per-key request bound: a recall by `client_order_id` counts each request after the first, and a request the bound refuses is answered `not_sent`.

#### Request

Name exactly one of `trade_id` and `client_order_id`.

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `trade_id` | string | none | one of | The exchange trade id (numeric) of one trade to recall. |
| `client_order_id` | string | none | one of | Recall every own trade of this order you may act on: the `ACTI` ones are sent, the others are answered `not_recallable`. |
| `revision_no` | i64 | none | No | With `trade_id` only: the revision you saw. If the gateway holds a newer one, nothing is sent and the answer is `409 TRADE_CHANGED`, so you recall the trade you looked at. Omitted, the gateway's latest revision is used. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `client_order_id` | string | none | by `client_order_id` | The order you named. |
| `results` | array | none | always | One result per trade, in execution order. |
| `counts` | object | count | by `client_order_id` | How many results carry each outcome, every outcome listed. |

Each result:

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `trade_id` | string | none | always | The exchange trade id. |
| `outcome` | string | none | always | What became of the recall; see *Outcomes* below. |
| `state` | string | none | always | The trade's state when the answer was built ([Trade states](#trade-states)). |
| `revision_no` | i64 | none | always | The trade's revision when the answer was built. |
| `recall_req_time` | string | RFC 3339 | when it applies | When the exchange registered the recall request. |
| `latest_recall_process_time` | string | RFC 3339 | when it applies | Until when market operations can decide the recall. |
| `m7_err_code` | i64 | none | when it applies | The exchange's error code, on `refused` only. |
| `m7_error_key` | string | none | when it applies | The code's key in the exchange's error catalogue (for example `trade_execution_too_long_ago` for 2013, `recall_already_requested` for 3006, `otc_cannot_be_recalled` for 3017). |
| `reason` | string | none | when it applies | The exchange's words on `refused`; the state on `not_recallable`; why on `unknown` and `not_sent`. |
| `cascaded_with` | string[] | none | when it applies | For a trade whose recall was sent: the other trades you hold with the same `parent_trade_id`, which the exchange recalls with it. For the other trades of its parent: that trade, whatever its outcome. |

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

A recall by `trade_id` answers with its one result's status, and the body always carries the result: `requested` `200`; `submitted` `202`, the body adding `"code": "RECALL_SUBMITTED"`; `refused` `409 RECALL_REFUSED`; `not_recallable` `409 RECALL_NOT_POSSIBLE`; `unknown` `504 OUTCOME_UNKNOWN`; `not_sent` `503 NOT_PROCESSED`. An error answer adds `error`, `code`, `m7_err_code` and `m7_error_key` beside `results`. A recall by `client_order_id` answers `200` whenever the order has a trade you may recall, whatever each outcome is.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "…", "code": "BAD_REQUEST"}` | Both targets or neither, `revision_no` with `client_order_id`, an empty `client_order_id`, or a `trade_id` that is not numeric. The message names the rule. |
| 403 | `{"error": "Forbidden"}` | Missing `recall_trade` permission |
| 403 | `{"error": "…", "code": "PERMISSION_DENIED"}` | The trade is one you can see but this gateway's exchange login did not place |
| 404 | `{"error": "…", "code": "TRADE_NOT_FOUND"}` | No such trade, or no trade of that order, that you may recall |
| 409 | `{"error": "…", "code": "TRADE_CHANGED"}` | The trade's revision moved past `revision_no`; nothing was sent |
| 409 | `{"code": "RECALL_NOT_POSSIBLE", "results": […], …}` | The trade is not `ACTI`; nothing was sent |
| 409 | `{"code": "RECALL_REFUSED", "m7_err_code": 2013, "m7_error_key": "trade_execution_too_long_ago", "results": […], …}` | The exchange refused the recall |
| 429 | `{"error": "request rate limit exceeded: …"}` | Over the per-key request bound |
| 503 | `{"error": "…", "code": "NOT_OPERATIONAL"}` | The gateway's exchange login is not known yet, so no trade can be shown to be its own; retry once it is logged in |
| 503 | `{"code": "NOT_PROCESSED", "results": […], …}` | The exchange never received the request; safe to retry |
| 504 | `{"code": "OUTCOME_UNKNOWN", "results": […], …}` | No acknowledgement in time; read the trade before asking again |

#### Example

```bash
curl -X POST https://gateway.example:3000/api/v1/trade/recall \
  -H "Authorization: Bearer $VOLTNIR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"trade_id": "1500000001", "revision_no": 1}'
```

```
HTTP/1.1 200 OK
{"results": [{"trade_id": "1500000001", "outcome": "requested", "state": "RREQ", "revision_no": 2,
  "recall_req_time": "2026-10-13T07:02:00.000Z", "latest_recall_process_time": "2026-10-13T07:32:00.000Z"}]}
```

### <a id="get-order" name="get-order"></a>`GET` `/api/v1/order`

Look up a single order by `client_order_id`: the pending store is checked first, then the confirmed order store, so the response shape depends on which store holds it.

**Required permission:** none (authenticated). `read_orders` or `bypass_member_check` widens lookup to any order. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `client_order_id` | `string` | none | Yes | Query parameter. UUID of the order to retrieve. |

#### Response (confirmed order)

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `order_id` | `u64` | none | always | M7 order id. A local book lists the order under this id. |
| `initial_order_id` | `u64` | none | always | The id the order first carried; unchanged across amendments. |
| `parent_order_id` | `u64 \| null` | none | optional | The parent order for a priority modify (delete plus re-add); `null` otherwise. |
| `revision` | `u64` | none | always | The exchange revision number; bumps on every amendment and partial fill. |
| `account_id` | `string` | none | always | The M7 clearing account the order trades on. |
| `contract_id` | `u64` | none | always | M7 contract id. |
| `delivery_area` | `string` | none | always | EIC delivery area code. |
| `side` | `string` | none | always | `BUY` or `SELL`. |
| `price` | `i64` | cents (CCY/MWh × 100) | always | Order limit price. |
| `quantity` | `u32` | sub-MW (MW × 1000) | always | Current open quantity. |
| `initial_quantity` | `u32` | sub-MW (MW × 1000) | always | Quantity the order was entered with. |
| `hidden_quantity` | `u32 \| null` | sub-MW (MW × 1000) | iceberg | Hidden portion of an iceberg; `null` on a non-iceberg order. |
| `displayed_quantity` | `u32 \| null` | sub-MW (MW × 1000) | iceberg | Visible portion of an iceberg; `null` on a non-iceberg order. |
| `order_type` | `string` | none | always | See the order_type values below. |
| `state` | `string` | none | always | See the state values below. |
| `action` | `string` | none | always | The last execution-report action; see the action values below. |
| `client_order_id` | `string \| null` | none | optional | Your idempotency key; `null` on a re-created order M7 did not echo it back on. |
| `user_code` | `string` | none | always | The EPEX trader/user code that placed the order. |
| `pre_arranged` | `bool` | none | always | Whether the order is a pre-arranged trade. |
| `timestamp_ms` | `i64` | Unix ms (UTC) | always | Order entry time. |
| `validity_time_ms` | `i64 \| null` | Unix ms (UTC) | GTD | Good-till-date expiry; `null` unless `validity_res` is `gtd`. |
| `last_update_time_ms` | `i64 \| null` | Unix ms (UTC) | always | When the exchange last reported a change to this order; `null` before its first report. |
| `text` | `string` | none | always | The M7 Txt field the order carries. |
| `basket_id` | `u64 \| null` | none | optional | M7 numeric basket id; `null` for standalone orders (on gRPC the same value is `uint64` with `0` as the standalone sentinel). |
| `basket_ref` | `string \| null` | none | optional | The basket the order was entered in through this gateway (see [`POST /basket`](#post-basket)); read back from the order’s own text, so it survives a restart. `null` for an order not entered in a basket. |
| `list_exec_inst` | `string \| null` | none | optional | The exchange’s list instruction for the order: `none`, `valid` or `linked`; `null` when the report names none. |
| `v_member_short_id` | `string \| null` | none | optional | Virtual-member tag recovered from the M7 Txt field; `null` for the house account or a non-Voltnir order. |
| `remote_order_id` | `u64 \| null` | none | remote | The shared-order-book (XBID) id; `null` on a local contract. A remote book lists the order under this id. |
| `voltnir_user_short_id` | `string \| null` | none | optional | Short id of the Voltnir user who submitted it; `null` for a non-Voltnir order. |
| `voltnir_username` | `string \| null` | none | optional | Username of that Voltnir user, a deleted one included; `null` for a non-Voltnir order. |
| `v_member_name` | `string \| null` | none | optional | The desk's own name for the member; `null` for the house account. A deleted member keeps its name. |

#### Response (pending order)

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `client_order_id` | `string` | none | always | Your idempotency key. |
| `contract_id` | `i64` | none | always | M7 contract id. |
| `delivery_area` | `string` | none | always | EIC delivery area code. |
| `side` | `string` | none | always | `BUY` or `SELL`. |
| `price` | `i64` | cents (CCY/MWh × 100) | always | Order limit price. |
| `quantity` | `u32` | sub-MW (MW × 1000) | always | Submitted quantity. |
| `entry_ts_ms` | `i64` | Unix ms (UTC) | always | When the gateway submitted the order. |
| `v_member_short_id` | `string \| null` | none | optional | Virtual-member tag; `null` for the house account. |

**Scoping.** Member-isolated, like [GET /orders](#get-orders). An order tagged with a virtual member the caller may not see (or an untagged house order, for a caller without broad read) returns `404`, **identical** to a genuinely unknown `client_order_id`. The two are indistinguishable on purpose. A caller holding `read_orders` (or `bypass_member_check`) can look up any order.

**Recognising your order in a public order book.** A local book lists the order under `order_id`; a remote (XBID) book lists it under `remote_order_id`, which the shared order book assigns and which bears no relation to `order_id`. `remote_order_id` is `null` for an order on a local contract. Match a book row against **either** id: a remote book published EPEX-originated orders under the local id before M7 6.22 and under the remote id from 6.22, so matching `order_id` alone leaves your own resting orders looking like strangers’ on the newer release.

**Attribution.** `v_member_short_id`, `v_member_name`, `voltnir_user_short_id` and `voltnir_username` are recovered from the M7 Txt field. All four are `null` for an order from another gateway, a colleague's on the same membership, or any order not placed through Voltnir, leaving `user_code` as the only attribution such a row carries. A deleted user keeps its short id and its username here, and a deleted member its short id and its name; neither short id is ever given to another user or member, so a filter by a user's short id or username, or by a member's short id, finds only that user's or member's rows.

**state values:** `PENDING` `ACTIVE` `INACTIVE` `HIBERNATED` `REJECTED` `UNKNOWN`

**order_type values:** `REGULAR` `BLOCK` `BALANCE` `ICEBERG` `STOP` `EXCHANGE_PRE_ARRANGED` `PRIVATE` `UNKNOWN`

**action values:** `UADD` `UHIB` `UMOD` `UDEL` `UREJ` `AADD` `AHIB` `AMOD` `ADEL` `AREJ` `SADD` `SHIB` `SMOD` `SDEL` `SREJ` `FEXE` `PEXE` `IADD` `SERR` `SNAV` `UNKNOWN`

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 404 | `{"error": "order not found"}` | `client_order_id` not in the pending or confirmed store, or its member is outside the caller's scope |

#### Example

```bash
curl "https://gateway.example:3000/api/v1/order?client_order_id=550e8400-e29b-41d4-a716-446655440000" \
  -H "Authorization: Bearer $VOLTNIR_API_KEY"
```

```
HTTP/1.1 200 OK
{
  "order_id": 987654321,
  "revision": 1,
  "contract_id": 100001,
  "delivery_area": "10YNL----------L",
  "side": "BUY",
  "price": 5000,
  "quantity": 1000,
  "state": "ACTIVE",
  "action": "AADD",
  "client_order_id": "550e8400-e29b-41d4-a716-446655440000",
  "v_member_short_id": "VM003",
  "remote_order_id": null
}
```

### <a id="get-orders" name="get-orders"></a>`GET` `/api/v1/orders`

List the caller's confirmed resting orders, optionally filtered by delivery area, contract, or product/delivery start. Returns an array of order objects.

An order the exchange reports filled or deleted leaves the list as soon as the gateway holds that report. Read it with [GET /order](#get-order) while the gateway still holds it, or in the order audit ([GET /audit/orders](#get-audit-orders)). A hibernated order stays listed: it is still yours at the exchange and can be activated or cancelled.

**Required permission:** none (authenticated). `read_orders` or `bypass_member_check` returns the firm-wide book. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `delivery_area` | `string` | none | No | Query parameter. Filter by delivery area EIC code. |
| `contract_id` | `u64` | none | No | Query parameter. Filter by contract id (requires `delivery_area`; without it the request is rejected with 400). |
| `product` | `string` | none | No | Query parameter. Filter by product code (requires `delivery_area`; without it the request is rejected with 400). |
| `delivery_start` | `string` | RFC 3339 | No | Query parameter. Filter by delivery start (used with `product`). Any RFC 3339 instant: `2026-10-25T00:00:00Z`, `2026-10-25T00:00:00.000Z` and `2026-10-25T02:00:00+02:00` name the same contract. The doubled hour of a clock change is two instants: on 2026-10-25, 02:00 CEST is `00:00Z` (hour `02A`) and 02:00 CET is `01:00Z` (hour `02B`). |
| `v_member_short_id` | `string` | none | No | Query parameter. Narrow to a single virtual member. Rejected with `403` unless the caller is assigned to it or holds `read_orders`/`bypass_member_check`. |

#### Response

A JSON array of order objects, each the same shape as the confirmed order from [GET /order](#get-order) (see that response table for every field, type and unit).

**Scoping.** The order book is member-isolated. A caller holding `read_orders` (or `bypass_member_check`) receives the firm-wide order book: every member's orders plus the untagged house-account orders. Every other caller receives only the orders tagged with a virtual member assigned to them; untagged house orders are **withheld**. A caller with no assigned members and no broad-read permission receives an empty list.

Filter priority: (`delivery_area` + `contract_id`) > (`delivery_area` + `product` [+ `delivery_start`]) > `delivery_area` alone > all orders.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "contract_id requires delivery_area"}` | `contract_id` passed without `delivery_area` |
| 400 | `{"error": "product requires delivery_area"}` | `product` passed without `delivery_area` |
| 400 | `{"error": "delivery_start must be an RFC 3339 timestamp, e.g. 2026-10-25T00:00:00Z"}` | `delivery_start` with `product` is not an RFC 3339 timestamp |
| 403 | `{"error": "Forbidden"}` | `v_member_short_id` names a member the caller is not assigned to and has no broad-read permission for |

#### Example

```bash
curl "https://gateway.example:3000/api/v1/orders?delivery_area=10YNL----------L" \
  -H "Authorization: Bearer $VOLTNIR_API_KEY"
```

```
HTTP/1.1 200 OK
[
  {
    "order_id": 987654321,
    "contract_id": 100001,
    "delivery_area": "10YNL----------L",
    "side": "BUY",
    "price": 5000,
    "quantity": 1000,
    "state": "ACTIVE",
    "client_order_id": "550e8400-e29b-41d4-a716-446655440000"
  }
]
```

<a id="contracts" name="contracts"></a>

## Contracts & market data

Query the live order book and contract metadata for delivery areas accessible to your account. Contract data is sourced from the M7 order book stream and reflects real-time market state.

> [!NOTE]
> Contract IDs are assigned by M7. Find them in the contract catalogue, `GET /contract/{area_id}`, which carries no order book and no prices. Read one contract's order book with `GET /contract/{area_id}/{contract_id}`, or look it up by product code and delivery start with the `by-delivery` endpoint.

> [!NOTE]
> Contracts whose delivery period has ended are removed from all contract responses and from the WebSocket feed approximately 60 minutes after their `dlvry_end`. Trades on those contracts remain queryable via the audit and history endpoints.

### <a id="get-contracts" name="get-contracts"></a>`GET` `/api/v1/contract/{area_id}`

The contract catalogue of a delivery area, sorted by delivery start: each contract's id, product, delivery period, state and trading phase, with no order book and no prices. The catalogue covers **every product the exchange has assigned your account**, including an assigned product you have not subscribed market data for.

The catalogue is for finding contract ids: call it at startup or when a new delivery day appears, and do not poll it. One contract's order book comes from [GET /contract/{area_id}/{contract_id}](#get-contract) or the [by-delivery lookup](#get-contract-by-delivery). Live data comes from the WebSocket `contracts` stream and gRPC `WatchContracts`, one stream with one filter on both: by area and product, or by contract id to follow one contract or a few.

**Contracts not open yet.** The catalogue lists the contracts the exchange has created but not yet opened for trading, in every configured delivery area whose exchange product list includes the contract's product. Such a row has `state` `IACT`, `trading_phase` `CLSD`, and `trading_phase_start` and `trading_phase_end` both `null`. Every row the exchange has opened in an area carries a `trading_phase_start`, so a `CLSD` row with a `null` `trading_phase_start` is a contract that has not opened yet. The exchange publishes no opening time. An order on such a row is refused with `400` and `"the contract is not open for trading yet"`. When the exchange's opening report reaches the gateway, the same row turns tradable in place (the same `contract_id`, with the area's own state and phase); while the gateway runs that report is the exchange's broadcast, and a new login also lists the opened row. A contract that opens without one of those areas leaves it. The same rows are on [GET /contract/{area_id}/{contract_id}](#get-contract), the by-delivery lookup and the live `contracts` stream.

**Required permission:** none (authenticated). (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `area_id` | `string` | none | Yes | Path parameter. EIC delivery area code (e.g. `10YNL----------L`). |

#### Response

A JSON array of catalogue rows, one per active contract whose delivery period is known. Each row has exactly these fields:

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `contract_id` | `string` | none | always | M7 contract id. |
| `area_id` | `string` | none | always | EIC delivery area code. |
| `prod` | `string \| null` | none | optional | Product code (the join key to [system_info](#get-system-info) products); `null` until the exchange sends it. |
| `name` / `long_name` | `string \| null` | none | optional | Contract display names; `null` until contract metadata arrives. |
| `dlvry_start` | `string` | RFC 3339 | always | Start of the delivery window; a contract without one is not listed. |
| `dlvry_end` | `string \| null` | RFC 3339 | optional | End of the delivery window; `null` until the exchange sends it. |
| `predefined` | `bool \| null` | none | optional | `true` for a standard exchange contract, `false` for a user-defined block (only block orders are accepted on it), `null` when metadata has not arrived (treat as not-yet-orderable). |
| `state` | `string \| null` | none | optional | M7 contract state (`ACTI`, and the rest); `null` until the exchange sends it. |
| `trading_phase` | `string \| null` | none | optional | The contract's current trading phase (e.g. `CONT`); `null` until the exchange sends it. |
| `trading_phase_start` / `trading_phase_end` | `string \| null` | RFC 3339 | optional | The phase window; the end is the gate-closure time; `null` until the exchange sends it. Both are `null` on a contract not open yet; a `CLSD` row with no start is one. |
| `duration` | `string \| null` | decimal hours | optional | Delivery duration in decimal hours; `null` until metadata arrives. |

The exchange **rejects a regular limit order on a user-defined block** (M7 error 1051), so a client should not offer regular order entry on a contract with `predefined: false`.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 404 | `{"error": "area not found"}` | `area_id` not found in the order book |

#### Example

```bash
curl "https://gateway.example:3000/api/v1/contract/10YNL----------L" \
  -H "Authorization: Bearer $VOLTNIR_API_KEY"
```

```
HTTP/1.1 200 OK
[
  {
    "contract_id": "100001",
    "area_id": "10YNL----------L",
    "prod": "H",
    "name": "20-04-2026 22:00-23:00",
    "long_name": "Intraday Power 22:00-23:00",
    "dlvry_start": "2026-04-20T22:00:00Z",
    "dlvry_end": "2026-04-20T23:00:00Z",
    "duration": "1.0",
    "predefined": true,
    "state": "ACTI",
    "trading_phase": "CONT",
    "trading_phase_start": "2026-04-19T15:00:00Z",
    "trading_phase_end": "2026-04-20T21:55:00Z"
  }
]
```

### <a id="get-contract" name="get-contract"></a>`GET` `/api/v1/contract/{area_id}/{contract_id}`

Get a single contract with its full order book, plus the caller's own acknowledged and pending orders, trades, and net position for this contract and area.

**Required permission:** none (authenticated). `read_orders` or `bypass_member_check` widens the own-orders, trades and position to the firm-wide view. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `area_id` | `string` | none | Yes | Path parameter. EIC delivery area code. |
| `contract_id` | `i64` | none | Yes | Path parameter. M7 contract id. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `contract` | `object` | none | always | The contract with its full order book and reference price ([contract object](#contract-object) below). |
| `orders_acknowledged` | `array` | none | always | Your orders M7 has acknowledged, each with an `order_id` and a `state`; same shape as the confirmed order from [GET /order](#get-order). |
| `orders_pending` | `array` | none | always | Your orders submitted but not yet acknowledged, with no `order_id` and no `state`; same shape as the pending order from [GET /order](#get-order). |
| `trades` | `array` | none | always | Your executed trades on this contract, member-scoped. A trade between two virtual members of the desk reaches a member-scoped caller as the ordinary fill of its own leg: only the leg its members placed, carrying that leg's own member, member name, Voltnir user and user name exactly as a fill against an outside counterparty would, with the other leg, its member and its Voltnir user withheld; a caller holding `read_orders` (or `bypass_member_check`) sees both legs. It holds what the live trade stream holds: the trades of the current cash-exposure window (since the most recent 16:00 booking cut on an ECC business day) and every trade on a contract whose delivery day, in its market's local time, is today or later. A trade recorded without its delivery window is kept for up to seven days after it executed. Earlier trades come from the trade history: [GET /audit/trades](#get-audit-trades). Each trade carries its `state` ([Trade states](#trade-states)) and the [recall fields](#recall-fields). |
| `net_pos` | `i64` | sub-MW (MW × 1000) | always | Executed net position; positive long, negative short. A trade counts until the exchange reverses it (any state but `RGRA` or `CNCL`). Open and pending orders do not count. |

#### <a id="contract-object" name="contract-object"></a>Contract object (`contract`)

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `contract_id` | `string` | none | always | M7 contract id. |
| `area_id` | `string` | none | always | EIC delivery area code. |
| `prod` | `string \| null` | none | optional | Product code (the join key to [system_info](#get-system-info) products); `null` until the exchange sends it. |
| `name` / `long_name` | `string \| null` | none | optional | Contract display names; `null` until contract metadata arrives. |
| `dlvry_start` / `dlvry_end` | `string \| null` | RFC 3339 | optional | The contract's delivery window; `null` until the exchange defines the contract. |
| `predefined` | `bool \| null` | none | optional | `true` for a standard exchange contract, `false` for a user-defined block (only block orders are accepted on it), `null` when metadata has not arrived (treat as not-yet-orderable). |
| `revision_no` / `revision_ob` | `i64 \| null` | none | optional | Contract and order-book revision numbers; `null` until the exchange sends it. |
| `state` | `string \| null` | none | optional | M7 contract state (`ACTI`, and the rest); `null` until the exchange sends it. |
| `trading_phase` | `string \| null` | none | optional | The contract's current trading phase (e.g. `CONT`); `null` until the exchange sends it. |
| `trading_phase_start` / `trading_phase_end` | `string \| null` | RFC 3339 | optional | The phase window; the end is the gate-closure time; `null` until the exchange sends it. Both are `null` on a contract not open yet; a `CLSD` row with no start is one. |
| `duration` | `string \| null` | decimal hours | optional | Delivery duration in decimal hours; `null` until metadata arrives. |
| `last_price` | `i64 \| null` | cents (CCY/MWh × 100) | optional | Last trade price; `null` when none. |
| `last_quantity` | `u32 \| null` | sub-MW (MW × 1000) | optional | Last trade quantity; `null` when none. |
| `last_trade_time` | `string \| null` | RFC 3339 | optional | Time of the last trade; `null` when none. |
| `highest_price` / `lowest_price` | `i64 \| null` | cents (CCY/MWh × 100) | optional | Session high and low; `null` when none. |
| `price_direction` | `integer \| null` | none | optional | `1` = up, `-1` = down, `0` = unchanged; `null` until the exchange sends it. |
| `best_bid` / `best_ask` | `i64` | cents (CCY/MWh × 100) | always | Best resting quote each side; `0` when that side is empty (read the quantity, as 0 is also a real price). |
| `best_bid_qty` / `best_ask_qty` | `u32` | sub-MW (MW × 1000) | always | Quantity at the best quote each side; `0` when that side is empty. |
| `ref_px_cents` | `i64 \| null` | cents (CCY/MWh × 100) | optional | The exchange's reference price for the contract in this area; `null` until one arrives (never `0` to mean absent). |
| `ref_px_type` | `string \| null` | none | optional | `"C"` closing price (default) or `"O"` opening price; `null` until one arrives. |
| `ref_px_date` | `string \| null` | YYYY-MM-DD | optional | The date the reference price refers to; `null` until one arrives. |
| `ref_px_updated_ms` | `i64 \| null` | Unix ms (UTC) | optional | When the gateway last received the reference price; `null` until one arrives. |
| `buy` / `sell` | `array` | none | always | The resting order book each side; each element is an order-book entry (table below). |

The four `ref_px_*` fields move together: all four are `null` until a reference price arrives, and `ref_px_cents` is never `0` to mean absent (0 and negative are real power prices). Reference data for the trader; it is not what [P&L](#get-pnl) marks open positions against. The exchange **rejects a regular limit order on a user-defined block** (M7 error 1051), so a client should not offer regular order entry on a contract with `predefined: false`.

#### Order book entry (`buy` / `sell` element)

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `order_id` | `i64` | none | always | The resting order's id in this book. |
| `quantity` | `u32` | sub-MW (MW × 1000) | always | Resting quantity. |
| `price` | `i64` | cents (CCY/MWh × 100) | always | Resting price, same scale as an order price. |
| `order_entry_time` | `string \| null` | RFC 3339 | optional | `null` when the feed omits it (on gRPC the same absence is the `""` sentinel). |
| `order_execution_restriction` | `integer` | none | always | Read-only integer enum: `0` unspecified, `1` not restricted, `2` AON. See [Order types](#order-types). |
| `order_type` | `integer` | none | always | Read-only integer enum, distinct from the submit strings. See [Order types](#order-types). |

**Scoping.** The orders, trades and position are member-isolated exactly like [GET /orders](#get-orders): a caller holding `read_orders` (or `bypass_member_check`) sees every member's rows plus the untagged house rows, and `net_pos` is the firm-wide executed position. Every other caller sees only its assigned members' rows, house rows withheld. A caller with no assigned members and no broad-read permission gets empty lists and `net_pos` 0.

**orders_acknowledged vs orders_pending.** An order is **never** in both lists; it moves from pending to acknowledged only once M7 acks it. To decide whether you already have an order working on this contract (and avoid re-submitting during the submit-to-ack window), check **both** lists. The same split is exposed on the WebSocket `orders` stream and on gRPC as `ContractDetail.orders_acknowledged` + `orders_pending`. A colleague's order on the same membership (a different M7 `user_code`) carries its `user_code` and neither a virtual member nor a Voltnir user, counting at the membership level like an untagged house order.

`net_pos` reflects **executed trades only**, each until the exchange reverses it (a granted recall, `RGRA`, or a cancellation, `CNCL`): a trade whose recall or cancellation is only requested, or was rejected, still counts. The order-placement position-limit check separately combines open orders and trades, and that combined value is not exposed here. Derive it client-side from `orders_acknowledged` + `orders_pending` + `trades` if needed.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 404 | `{"error": "contract not found"}` | No contract with this ID in this area, or its delivery end has passed on the gateway’s clock. Orders still resting on a finished contract are read through [GET /orders](#get-orders) (with `delivery_area` and `contract_id`) and cancelled with [DELETE /order](#delete-order) |

#### Example

```bash
curl "https://gateway.example:3000/api/v1/contract/10YNL----------L/100001" \
  -H "Authorization: Bearer $VOLTNIR_API_KEY"
```

```
HTTP/1.1 200 OK
{
  "contract": { "contract_id": "100001", "area_id": "10YNL----------L", "state": "ACTI", "best_bid": 5100, "best_ask": 5300, "buy": [], "sell": [] },
  "orders_acknowledged": [ {"order_id": 987654321, "side": "BUY", "price": 5000, "quantity": 1000, "state": "ACTIVE", "client_order_id": "550e8400-e29b-41d4-a716-446655440000", "v_member_short_id": "VM003"} ],
  "orders_pending": [],
  "trades": [],
  "net_pos": 1000
}
```

### <a id="get-contract-by-delivery" name="get-contract-by-delivery"></a>`GET` `/api/v1/contract/{area_id}/by-delivery/{prod}/{dlvry_start}`

Look up a contract by product code and delivery start time rather than by numeric contract ID. Returns the same combined response, member-scoped the same way, as [GET /contract/{area_id}/{contract_id}](#get-contract).

**Required permission:** none (authenticated). `read_orders` or `bypass_member_check` widens the own-orders, trades and position to the firm-wide view. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `area_id` | `string` | none | Yes | Path parameter. EIC delivery area code. |
| `prod` | `string` | none | Yes | Path parameter. Product code (e.g. `H` for hourly, `QH` for quarter-hour). |
| `dlvry_start` | `string` | RFC 3339 | Yes | Path parameter, URL-encoded (e.g. `2026-04-20T22%3A00%3A00Z`; encode `+` as `%2B`). Any RFC 3339 instant: `2026-10-25T00:00:00Z`, `2026-10-25T00:00:00.000Z` and `2026-10-25T02:00:00+02:00` name the same contract. The doubled hour of a clock change is two instants: on 2026-10-25, 02:00 CEST is `00:00Z` (hour `02A`) and 02:00 CET is `01:00Z` (hour `02B`). |

#### Response

Same shape as [GET /contract/{area_id}/{contract_id}](#get-contract): `contract`, `orders_acknowledged`, `orders_pending`, `trades`, `net_pos`.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "dlvry_start must be an RFC 3339 timestamp, e.g. 2026-10-25T00:00:00Z"}` | `dlvry_start` is not an RFC 3339 timestamp |
| 404 | `{"error": "contract not found"}` | No contract matching product + delivery start in this area, or its delivery end has passed on the gateway’s clock (its resting orders are listed by [GET /orders](#get-orders)) |

#### Example

```bash
curl "https://gateway.example:3000/api/v1/contract/10YNL----------L/by-delivery/H/2026-04-20T22%3A00%3A00Z" \
  -H "Authorization: Bearer $VOLTNIR_API_KEY"
```

<a id="hub2hub" name="hub2hub"></a>

## Hub-to-Hub

Query capacity data between delivery hubs. The destination may be any hub in the XBID network, not only a neighbour across a shared border: M7 publishes hub-to-hub capacity, the transfer the network can carry from one hub to the other. This feature must be enabled in the gateway configuration. If disabled, the endpoint returns an empty result without error.

> [!NOTE]
> Hub-to-Hub data is only available when hub-to-hub is enabled in the gateway configuration. The response carries `enabled` (the configuration flag; when `false`, `data` is always empty) and `capacity_connected` (the upstream capacity-feed heartbeat) alongside `data`.

### <a id="get-hub2hub" name="get-hub2hub"></a>`GET` `/api/v1/hub2hub`

Query cross-area hub-to-hub capacity for a delivery time range between two areas.

**Required permission:** none (authenticated). (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `delivery_area_from` | `string` | none | Yes | Query parameter. Source delivery area EIC code. |
| `delivery_area_to` | `string` | none | No | Query parameter. Target delivery area EIC code (optional filter); keeps only that destination's connections, and leaves out an interval with no connection to it. Absent or empty = all destinations. |
| `delivery_from` | `string` | RFC 3339 | Yes | Query parameter. Start of the delivery window. |
| `delivery_to` | `string` | RFC 3339 | Yes | Query parameter. End of the delivery window. The server does not validate that `delivery_from` is before `delivery_to`. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `enabled` | `bool` | none | always | The hub-to-hub configuration flag; when `false`, `data` is always empty. |
| `capacity_connected` | `bool` | none | always | The upstream capacity-feed heartbeat. |
| `data` | `array` | none | always | One entry per delivery window and source hub; each carries `revision_no`, `dlvry_start`, `dlvry_end`, `timestmp`, `hub_from`, and a `connections` array (table below). A row whose delivery period ended more than an hour ago is left out. |

#### Connection fields (`data[].connections[]`)

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `to` | `string` | none | always | Destination delivery area EIC code. |
| `atc_in` | `integer` | sub-MW (MW × 1000) | always | ATC into `hub_from` from `to`. Raw signed M7 value; may be negative during congestion. |
| `atc_out` | `integer` | sub-MW (MW × 1000) | always | ATC out of `hub_from` toward `to`. May be negative. |
| `source_best_bid` | `integer` | cents (CCY/MWh × 100) | optional | Best resting bid in `hub_from`; omitted when no resting quote is available. |
| `source_best_ask` | `integer` | cents (CCY/MWh × 100) | optional | Best resting ask in `hub_from`; omitted when no resting quote is available. |
| `dest_best_bid` | `integer` | cents (CCY/MWh × 100) | optional | Best resting bid in `to`; omitted when no resting quote is available. |
| `dest_best_ask` | `integer` | cents (CCY/MWh × 100) | optional | Best resting ask in `to`; omitted when no resting quote is available. |

The four best-quote fields are joined from the live order-book best-quote state at frame-emit time, so a client can derive a per-border implicit spread (for example `dest_best_bid − source_best_ask` for an export-direction order) without a separate `contracts` subscription per border. A value of `0` in the order book is treated as "no quote" and translated to a missing field, since negative power prices are legitimate.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "invalid delivery_from: …"}` | `delivery_from` is not valid RFC 3339 |
| 400 | `{"error": "invalid delivery_to: …"}` | `delivery_to` is not valid RFC 3339 |

#### Example

```bash
curl "https://gateway.example:3000/api/v1/hub2hub?delivery_area_from=10YNL----------L&delivery_area_to=10YDE-VE-------2&delivery_from=2026-04-20T22%3A00%3A00Z&delivery_to=2026-04-20T23%3A00%3A00Z" \
  -H "Authorization: Bearer $VOLTNIR_API_KEY"
```

```
HTTP/1.1 200 OK
{
  "enabled": true,
  "capacity_connected": true,
  "data": [
    {
      "revision_no": 42,
      "dlvry_start": "2026-04-20T22:00:00Z",
      "dlvry_end": "2026-04-20T22:15:00Z",
      "timestmp": "2026-04-20T21:54:30Z",
      "hub_from": "10YDE-VE-------2",
      "connections": [
        {"to": "10YNL----------L", "atc_in": 800, "atc_out": 400, "source_best_bid": 9450, "source_best_ask": 9510, "dest_best_bid": 9975, "dest_best_ask": 10025}
      ]
    }
  ]
}
```

### <a id="get-public-trades" name="get-public-trades"></a>`GET` `/api/v1/public_trades`

Return up to `limit` most-recent public trades from the market-wide trade tape, oldest first. Sliding-window store: entries older than the retention window are trimmed. The same data is broadcast on the WebSocket `public_trades` stream.

**Required permission:** none (authenticated). (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `limit` | `usize` | count | No | Query parameter. Default 100; hard-capped at 1000. Must be > 0. |
| `contract_id` | `u64` | none | No | Query parameter. Filter to one M7 contract id. |
| `area_id` | `string` | none | No | Query parameter. Filter by EIC delivery area; matches when either the buy- or sell-side area equals this value. Max 64 chars. |

#### Response

A `{"trades": [...]}` object. Each trade:

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `trade_id` | `string` | none | always | M7 trade id. |
| `contract_id` | `i64` | none | always | M7 contract id. |
| `qty` | `u32` | sub-MW (MW × 1000) | always | Traded quantity. |
| `px` | `i64` | cents (CCY/MWh × 100) | always | Traded price. |
| `exec_time` | `string` | RFC 3339 | always | Execution time. |
| `exec_time_ms` | `i64` | Unix ms (UTC) | always | Execution time in Unix ms. |
| `revision_no` | `i64` | none | always | Trade revision number. |
| `state` | `string` | none | always | Trade state; see [Trade states](#trade-states). |
| `buy_dlvry_area` | `string \| null` | none | optional | Buy-side delivery area; may be `null`. |
| `sell_dlvry_area` | `string \| null` | none | optional | Sell-side delivery area; may be `null`. |
| `self_trade` | `bool` | none | always | Whether both sides are the connected member. |
| `remote_trade_id` | `string \| null` | none | remote | The XBID remote trade id on a remote contract; `null` on a local trade. Present for every trade state, and the join key onto the EPEX market-data transaction reports. |
| `attribution` | `string` | none | always | `"full"` when the report parsed completely, or `"partial"` when only the trade's financial core could be read. |

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "limit must be greater than zero"}` | `limit=0` |
| 400 | `{"error": "area_id exceeds maximum length"}` | `area_id` > 64 chars |

#### Example

```bash
curl "https://gateway.example:3000/api/v1/public_trades?limit=100&area_id=10YNL----------L" \
  -H "Authorization: Bearer $VOLTNIR_API_KEY"
```

```
HTTP/1.1 200 OK
{
  "trades": [
    {"trade_id": "T-987654321", "contract_id": 100001, "qty": 1000, "px": 5200, "exec_time": "2026-04-21T10:15:00Z", "exec_time_ms": 1713693300000, "revision_no": 1, "state": "ACTI", "buy_dlvry_area": "10YNL----------L", "sell_dlvry_area": null, "self_trade": false, "remote_trade_id": "XB-77-001", "attribution": "full"}
  ]
}
```

<a id="system" name="system"></a>

## System reads

Inspect gateway health, connection status, throttling counters, reference data and the trading-posture aggregate. These are point-in-time reads; the writes that change trading controls are under [Limits & controls](#put-trading-allowed).

### <a id="get-state" name="get-state"></a>`GET` `/api/v1/state`

Return the full runtime-health snapshot: connectivity, AMQP session, WebSocket stream status, latency, the reference-data readiness counters, the installed license and an `operational` flag.

**Required permission:** `read_state`. (see [Permissions](#permissions))

#### Request

None. No parameters.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `uptime` | `string` | none | always | Human-readable process uptime. |
| `operational` | `bool` | none | always | `true` only when every order-critical subsystem is healthy and the exchange is active. |
| `issues` | `array` | none | always | Human-readable strings, one per failing condition when `operational` is `false`; empty otherwise. Treat as open: a future condition may add a string. |
| `admission` | `string` | none | always | `open`, `closed` or `degraded`: whether new orders and modifies are admitted. `closed` while any order-critical issue is present, except as follows. `degraded` while the only issues are `trade_report refused` and the `cash_exposure_window not covered` it opens, and admission is open anyway because `system.trade_ingest_fault` is `continue` or an operator acknowledged the fault. Cancels are never gated. |
| `amqp_connected` | `bool` | none | always | Whether the AMQP session is up. |
| `amqp_authenticated_with` | `object \| null` | none | optional | The M7 session identity (session/user/account/member); omitted on gRPC `GetState`. |
| `amqp_private_consumer_healthy` | `bool` | none | always | Private-data consumer health. |
| `amqp_broadcast_consumer_healthy` | `bool` | none | always | Broadcast consumer health. |
| `amqp_publisher_healthy` | `bool` | none | always | Publisher health. |
| `amqp_publisher_tx_capacity` | `integer` | count | always | Free slots in the publisher channel. |
| `amqp_market_active` | `bool` | none | always | Whether the exchange market is active. |
| `amqp_broadcast_sequence_healthy` | `bool` | none | always | Whether the broadcast sequence is gap-free. |
| `ws_order_book_*` | `bool` / `i64` / `string` | mixed | always | Order-book stream health family: `_stream_connected`, `_sequence_healthy`, `_synchronized` (bool), `_pong` (Unix ms), `_delta` (Unix ms of the last applied delta; 0 before the first and after a reconnect), `_delta_per_hour` (count), `_avg_processing_time`, `_avg_latency` (formatted durations). |
| `ws_private_data_*` | `bool` / `i64` / `string` | mixed | always | Private-data stream health family, mirroring the order-book family above. `_synchronized` turns true only once every part of the initial order snapshot has arrived and been applied to the order store, together; false from a reconnect until then. |
| `trades_received` | `i64` | count | always | Trade rows handed to the backfill worker since start (cumulative). |
| `trades_persisted` | `i64` | count | always | Trade rows committed since start (cumulative). |
| `trades_persist_failed` | `i64` | count | always | Trade rows lost to a failed database transaction or refused by the database; the signal a persistence loss occurred. At each login the gateway re-requests the current cash-exposure period's trades, so a lost trade from that period can come back at the next reconnect; a desk that stays connected does not get it back that way. [POST /restore-trade-history](#post-restore-trade-history) rebuilds them now. |
| `writes_dropped` | `i64` | count | always | Fire-and-forget writes lost. The writer queues are unbounded, so nothing is shed; a lost write means a writer accepted a batch and its transaction would not commit, the database refused that row, or a shutdown could not commit it within its 30-second drain. Counted per stream on the `stream` label of `voltnir_writes_dropped_total`. It resets on restart; each clean shutdown records the run's totals per stream in its `system_shutdown` audit row. |
| `trade_reports_refused` | `i64` | count | always | Exchange trade-capture reports refused because their financial core could not be read; a non-zero value means a trade the exchange executed was missed and order admission is held closed until the re-asked window brings it in, unless the desk trades on through it (`admission` then reads `degraded`). |
| `product_parameters_loaded` | `bool` | none | always | `false` until the session's first product report has been applied. |
| `product_scale_unrepresentable` | `i64` | count | always | Products whose published scale or quantity unit this gateway cannot denominate. |
| `product_scale_frames_dropped` | `i64` | count | always | Inbound frames dropped because their product's scale was unknown or unrepresentable (cumulative). |
| `product_scale_orders_refused` | `i64` | count | always | Orders refused for the same reason (cumulative). |
| `product_scale_changes` | `i64` | count | always | Product reports that changed a recorded scale (cumulative). |
| `contracts_awaiting_definition` | `i64` | count | always | Book-born contracts streaming a book but with no contract report yet; withheld from the contracts stream until their delivery is known. |
| `contract_reports_broadcast` | `i64` | count | always | Contract reports received as broadcasts this session. |
| `last_update_pass_refused` | `bool` | none | always | `true` when the exchange refused this login's inquiry for the trades it updated while Voltnir was not connected (`dateMeaning=LAST_UPDATE`). Voltnir then trades on the match-time inquiry alone, so a recall or cancellation resolved during that time, on a trade matched before the cash-exposure window, can still count in position, slot sums and P&L until the exchange reports the trade again. It does not close order entry. The refused question is not asked again: the next login asks only about what changed after this session last heard the exchange, so a trade reversed during the outage before this login keeps counting until the exchange reports it again or a trade-history restore brings it back. The flag clears when the gateway next connects to the exchange. |
| `license` | `object` | none | always | The full installed license (status, mode, validity window, holder, EPEX identities). See the note below. |

The `v7_token` field is redacted. The trading-posture aggregate (`trading_enabled`, per-contract limit, throttling, cash limits, license summary) lives on [`GET /status`](#get-status), not here.

`operational` is `true` only when all the AMQP and WebSocket health flags above are healthy and the exchange is active. The private-data feed carries your own orders and execution reports, so while it is degraded new orders (`POST /order`) and modifies (`PUT /order`) are refused with `503` until it recovers. Cancels (`DELETE /order`, `DELETE /orders`) and the trading kill-switch are never gated on `operational`, so a desk can always get flat. The `503` body is `system not operational:` followed by the same `issues` strings, comma-joined.

`license`: `status.kind` is `active`, `expiring_soon`, `expired` or `in_grace` (every kind except `active` adds a `days` field). `mode` is `trader` or `desk` (desk adds user/member/permission management; gRPC is served on every tier). `holder` is the licensed entity, `null` for a free sim license. `epex_any` is `true` when any EPEX identity is authorized (sim); otherwise `epex_identities` lists the permitted account/user pairs. License expiry is informational and never disables an endpoint; under a `trader` license the desk-only management endpoints return `403` with `{"error": "LICENSE_DESK_REQUIRED"}`.

**If you see `admission: degraded`**, the gateway is admitting orders on figures it knows are incomplete, by the desk's own choice: an exchange trade report it could not read is missing from position, cash and P&L, so its own position and cash limits are measured short (the exchange still checks the member's cash limit on every order). Stop adding exposure you would not add blind, reconcile your book against the exchange, and contact the support desk with the `parse_error` rows from the m7-errors audit. It returns to `open` by itself once the missed trade is ingested; under the default `close` policy an acknowledgement ([`POST /trade_ingest_fault/ack`](#post-trade-ingest-fault-ack)) lasts `system.trade_ingest_fault_ack_ttl_sec` (1800 s by default), ends early when the fault clears, and is dropped by a restart. While admission is `degraded` the gateway does not reconnect its exchange session over the fault, and it keeps polling the exchange's throttling status, which the load check (`load_management`) needs fresh to admit an order that adds exposure. Orders are admitted the moment admission reopens, unless the throttling report went stale while admission was closed (closed for about `load_management.max_report_age_sec` or longer, 30 s by default; the report ages from its last poll, so a slightly shorter closure can already count); then an order that adds exposure can be refused for about two seconds after admission reopens, until the first throttling poll answers. From then on orders stay admitted until the trade report is read or the acknowledgement runs out. Any other order-critical issue still closes admission, and one that outlasts the health allowance still makes the gateway reconnect its exchange session, with admission closed while it does; an acknowledgement keeps counting down meanwhile. `operational`, `/readyz` and the gRPC health service keep reporting the gateway not operational throughout, so alerts on them still fire.

**issues strings** include: `exchange is down`, the AMQP and WebSocket health strings, `m7_heartbeat lost`, `cash_exposure_window not covered`, `product_parameters not loaded` and `trade_report refused`. `cash_exposure_window not covered` means the gateway has not yet had the exchange confirm every trade in the current cash-exposure window (up to 72 hours over a weekend), so consumed cash could be under-counted; it is raised at login and cleared once the exchange has answered the chunked trade backfill: the window's trades by match time, and every trade the exchange updated since Voltnir last heard from it. The desk can always get flat while any of these are present. One condition does not close order entry and is reported as the boolean `last_update_pass_refused` beside `issues`, not in it: the exchange refused the login's inquiry for the trades it updated while Voltnir was not connected.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 403 | `{"error": "Forbidden"}` | Missing `read_state` permission |

#### Example

```bash
curl https://gateway.example:3000/api/v1/state \
  -H "Authorization: Bearer $VOLTNIR_API_KEY"
```

```
HTTP/1.1 200 OK
{
  "uptime": "2h 34m 12s",
  "operational": true,
  "issues": [],
  "amqp_connected": true,
  "ws_order_book_synchronized": true,
  "ws_private_data_synchronized": true,
  "trades_received": 41208,
  "trades_persisted": 41208,
  "product_parameters_loaded": true,
  "license": {"status": {"kind": "active"}, "mode": "desk", "expires_at": "2027-05-14T02:07:42Z"}
}
```

### <a id="get-metrics" name="get-metrics"></a>`GET` `/api/v1/metrics`

Expose the gateway's own health and load in OpenMetrics text format, so a monitoring system can scrape it directly instead of polling [GET /state](#get-state) through an exporter you write.

**Required permission:** `read_metrics`. It grants nothing else, so a monitoring key can hold it alone. This endpoint is **REST-only**: it has no gRPC or WebSocket peer. (see [Permissions](#permissions))

#### Request

None. No parameters. The response content type is `application/openmetrics-text; version=1.0.0`; Prometheus negotiates it natively and `curl` reads it as plain text. Prometheus bearer-token auth (`authorization` / `bearer_token_file`) works; issue a monitoring user holding `read_metrics` and nothing else.

#### Response

The exposition lists the families below. Metrics describe the plumbing, never the book: there is no P&L, position, order count or per-contract or per-order label, and every label is bounded.

| Metric | Type | Description |
| --- | --- | --- |
| `voltnir_operational` | gauge | 1 when every order-critical subsystem is healthy and orders are admitted. |
| `voltnir_trading_enabled` | gauge | 1 while the trading kill switch permits new orders. |
| `voltnir_issue_exchange_down` / `voltnir_issue_amqp_broadcast_consumer_unhealthy` / `voltnir_issue_amqp_private_consumer_unhealthy` / `voltnir_issue_amqp_publisher_unhealthy` / `voltnir_issue_amqp_broadcast_sequence_gap` / `voltnir_issue_order_book_not_synchronized` / `voltnir_issue_order_book_stream_disconnected` / `voltnir_issue_order_book_sequence_gap` / `voltnir_issue_private_data_not_synchronized` / `voltnir_issue_private_data_stream_disconnected` / `voltnir_issue_private_data_sequence_gap` / `voltnir_issue_m7_heartbeat_lost` / `voltnir_issue_cash_coverage_incomplete` / `voltnir_issue_product_parameters_missing` / `voltnir_issue_trade_report_refused` | gauge | One fixed 0/1 gauge per order-critical condition: the exchange, the AMQP consumers and publisher, the order-book and private-data streams (synchronised, connected, gap-free), the M7 heartbeat, cash coverage, product parameters and refused trade reports. |
| `voltnir_writes_dropped_total{reason, stream}` | counter | Fire-and-forget writes lost, one series per `stream` (`audit`, `m7_errors`, `exchange_messages`, `public_trades`, `orders`; trades count in `voltnir_trades_persist_failed_total`) and `reason`; `sum by (reason)` gives the totals. `channel_full` is unreachable on the unbounded queues (stays 0 on every stream, kept for wire stability); `writer_failed` means a transaction the writer had accepted would not commit, the database refused one of its rows, or a shutdown could not commit the write within its 30-second drain. |
| `voltnir_db_writer_queue_depth{writer}` | gauge | Items queued behind each writer; steady at 0, so a persistent non-zero value means a writer is not keeping up. |
| `voltnir_trades_received_total` / `voltnir_trades_persisted_total` / `voltnir_trades_persist_failed_total` | counter | Trade rows handed to the backfill worker, committed, and lost to a failed transaction. |
| `voltnir_trade_reports_refused_total` | counter | Exchange trade-capture reports refused because their financial core could not be read. |
| `voltnir_orders_closed_unobserved_total` / `voltnir_orders_unobserved_sweep_failed_total` | counter | Order rows written with `source` `gateway` because M7 no longer held the order when the gateway reconnected (see [GET /audit/orders](#get-audit-orders)), and startup reads of the stored open orders that failed; a failed read runs again only at the next reconnect, and until then an order left open at the restart keeps reading as open. Both reset on restart. |
| `voltnir_db_size_bytes` / `voltnir_db_wal_bytes` | gauge | Store and write-ahead-log size, sampled on a timer. |
| `voltnir_db_rows{table}` / `voltnir_db_rows_pruned_total{table}` | gauge / counter | Row census and rows removed by retention, per table, sampled every ten minutes. |
| `voltnir_db_prune_last_timestamp_seconds` / `voltnir_db_payload_retention_cutoff_timestamp_seconds` | gauge | When retention last ran, and the payload retention cutoff; a prune timestamp more than about two hours behind now means retention has stopped. |
| `voltnir_payloads_write_failed_total` | counter | Captures the database refused: evidence lost for good. |
| `voltnir_payloads_absent{kind,reason}` | gauge | Stored orders and trades with no captured message behind them, split by whether the capture failed or was never attempted. An order row with `source` `gateway` had no message and is not counted. |
| `voltnir_m7_stream_last_message_timestamp_seconds` / `voltnir_m7_stream_up` / `voltnir_amqp_up` / `voltnir_publisher_queue_free` | gauge | Liveness of the M7 streams and AMQP, and free publisher-queue slots. Alert on now minus the last-message time, not on the connected flag. |
| `voltnir_stranded_pending_orders` / `voltnir_stranded_pending_qty_mw` | gauge | New orders held past their expiry bound with no exchange answer, still consuming headroom, and the megawatts they hold. |
| `voltnir_claims_in_flight` | gauge | Amendments and activations whose added exposure counts against the limits until the exchange answers them or their expiry bound passes, held ones included. |
| `voltnir_claims_held` / `voltnir_claims_held_qty_mw` | gauge | Of those, the claims held past their expiry bound, and the megawatts they add. 0 on a healthy gateway. |
| `voltnir_cash_limit_breached` / `voltnir_cash_limit_stale` / `voltnir_cash_reported_timestamp_seconds` | gauge | Cash-pool breach and staleness state, and when the pool was last reported. |
| `voltnir_throttle_no_restriction` / `voltnir_throttle_warning` / `voltnir_throttle_restricted` | gauge | The exchange's current load-management status for the member. |
| `voltnir_throttle_reported` / `voltnir_throttle_stale` / `voltnir_omt_headroom` / `voltnir_omt_guard_enabled` | gauge | Whether the exchange has reported, whether that report is stale, the binding OMT headroom, and whether the client-side guard is enabled. |
| `voltnir_build_info` / `voltnir_start_timestamp_seconds` / `voltnir_supervisor_cycle_start_timestamp_seconds` / `voltnir_uptime_seconds` / `voltnir_license_expiry_timestamp_seconds` | gauge | Build identity, process start (stamped once), last whole-subsystem reconnect, uptime, and license expiry. |
| `voltnir_m7_client_cert_expiry_timestamp_seconds` | gauge | When the M7 client certificate expires (its `notAfter`), read at startup and every hour. Absent while the certificate file cannot be read. Alert on `voltnir_m7_client_cert_expiry_timestamp_seconds - time() < 14*86400`, and on its absence. |
| `voltnir_product_parameters_loaded` / `voltnir_product_scale_frames_dropped_total` / `voltnir_product_scale_orders_refused_total` / `voltnir_contracts_awaiting_definition` / `voltnir_market_active` / `voltnir_m7_stream_last_pong_timestamp_seconds` | gauge / counter | Reference-data readiness (a stuck figure explains a gateway connected but unwilling to trade) and the socket keepalive, published apart from the data-freshness gauge because a pong proves the socket, not the feed. |
| `voltnir_m7_messages_received_total{path,type}` / `voltnir_m7_messages_dropped_total{path,reason}` / `voltnir_m7_exchange_errors_total{path}` | counter | Per-ingress-path throughput, drops and exchange errors, over the four paths `amqp_private`, `amqp_broadcast`, `ws_order_book`, `ws_private_data`. |
| `voltnir_m7_message_processing_seconds{path}` / `voltnir_m7_message_lag_seconds{path}` | histogram | Processing time and end-to-end lag per path, every frame (snapshots included); lag compares the exchange clock with the host, so NTP skew is part of it. |
| `voltnir_m7_update_lag_seconds{path,from}` | histogram | Lag of live updates only, snapshots excluded: order book deltas on `ws_order_book`, execution reports on `ws_private_data`. The `ws_private_data` series times your own order events from M7 to the gateway. `from="gateway"` measures from the M7 WebSocket gateway sending the frame, `from="core"` from the M7 core creating it; the difference between the two is M7's internal hop. Like the per-path lag it compares the exchange clock with the host, so NTP skew is part of it; a sample below zero is observed as 0, and the frame is counted in `voltnir_m7_message_lag_negative_total`. |
| `voltnir_m7_message_lag_negative_total{path}` / `voltnir_m7_last_received_timestamp_seconds{path}` / `voltnir_m7_heartbeats_received_total` | counter / gauge | Samples below zero (an NTP alarm), last-received time per path, and heartbeats received. |
| `voltnir_m7_reconnects_total{component}` / `voltnir_m7_sequence_gaps_total{stream}` / `voltnir_m7_resyncs_total{stream}` / `voltnir_supervisor_cycles_total` / `voltnir_m7_heartbeat_losses_total` | counter | Reconnect, sequence-gap, resync, whole-subsystem cycle and heartbeat-loss counts; a reconnect loop that fails five times counts five. |
| `voltnir_m7_session_logouts_last_hour` | gauge | Sessions M7 logged out unasked in the last hour. Each one ends the process for the service manager to restart, so the count is read from the audit trail (`m7_session_logged_out`) at startup and every minute, and survives those restarts. Above 2 means another login is using this exchange user. |
| `voltnir_order_m7_routing_seconds{op}` | histogram | M7's routing of each order command: from the order clearing M7's intake to M7's core recording it (the confirming execution report's `last_update_time`). That is M7's core and, for an XBID-coupled delivery area, its round trip to the XBID shared order book, since the core records the order only once XBID has answered. Per command it is `voltnir_order_outbound_seconds` less `voltnir_order_arrival_seconds` and `voltnir_m7_pmi_processing_seconds`, so the four legs to M7 and back add up to the round trip. Its far end is on the exchange's clock, so the offset between the clocks is part of it; a value below zero is observed as 0. Recorded when the ack carried `pmi-processing` and the confirming report a stamp; not for `cancel_all`. |
| `voltnir_order_arrival_seconds{op}` / `voltnir_m7_pmi_processing_seconds{op}` | histogram | The order command at M7's door, both on one clock, so no clock offset is in either. `voltnir_m7_pmi_processing_seconds` is M7's PMI Gateway processing the command before acknowledging it, read from the `pmi-processing` header M7 sets on its `AckResp`: M7's intake, before its core and any XBID routing. `voltnir_order_arrival_seconds` is the publish to the command reaching that gateway: half of the ack round trip once M7's processing is taken out, so it assumes the path is as long each way. Recorded for each acknowledged command whose `AckResp` carries the header, by op: the ack round trip differs by command (a modify's can take several times a new order's with the same reported intake), and that time is outside `pmi-processing`, so it lands in the arrival. Buckets every millisecond from 1 to 5 ms. |
| `voltnir_order_outbound_seconds{op}` | histogram | The outbound part of `voltnir_order_confirm_seconds`: from the publish to M7's core processing the command, read from the confirming execution report's `last_update_time`. The rest of the confirm is M7 building the report and the return trip, whose last part `voltnir_m7_update_lag_seconds` shows. Its far end is on the exchange's clock, so the offset between the host clock and the exchange's is part of the figure, in the opposite sign to the return leg; the sum is exact. A sample below zero is observed as 0. Not recorded for `cancel_all`, which has no single confirming report. |
| `voltnir_order_admission_seconds{op}` / `voltnir_order_queue_wait_seconds` / `voltnir_order_ack_seconds{op}` / `voltnir_order_confirm_seconds{op}` / `voltnir_order_end_to_end_seconds{op}` | histogram | The five stages of an order's life, labelled by op (`new`, `modify`, `cancel`, `cancel_all`, `activate`, `hibernate`); the queue-wait is unlabelled because the publisher channel is shared. |
| `voltnir_amqp_publish_seconds{class}` | histogram | The AMQP publish call alone, by `class` (`order` for order commands, `inquiry` for every other request to M7): the time to hand a request to the AMQP client and have it written to the connection. It holds no acknowledgement from the exchange. It is the part of the queue-wait spent publishing, on the same buckets, so the two can be read side by side. |
| `voltnir_order_commands_total{op,outcome}` / `voltnir_order_refusals_total{reason}` / `voltnir_order_slot_would_refuse_total{reason}` / `voltnir_order_late_reports_total{op}` / `voltnir_publisher_queue_capacity` | counter / gauge | Command counts (each counted once under one outcome), refusals by reason, orders the slot position limit admitted in `observe` mode that `reject` would have refused (`slot_limit` or `slot_window_unknown`, every one counted), late reports, and the publisher-queue denominator. |
| `voltnir_order_timers_in_flight` / `voltnir_order_timer_index_entries` | gauge | Round-trip timer state; both rise and fall with activity and return near zero when idle, so an index count climbing past the timer count, or either climbing while idle, is a leak. |
| `voltnir_order_admission_phase_seconds{op,phase}` / `voltnir_order_admission_phase_overshoots_total{op}` | histogram / counter | The admission span split into named phases (`validate`, `order_txt`, `contract_admits`, `scale`, `lock_wait`, `gate_position`, `gate_slot` (recorded only while the slot position limit is in `observe` or `reject`), `gate_cash`, `gate_self_trade`, `claim_key`, `stamp_action`, `publish_handoff`, `other`); `other` is derived, and a non-zero overshoot means that op's split cannot be trusted. For a new order, `validate` is the kill-switch check alone, and `gate_position` also holds the member check, which runs once the position lock is held. |
| `voltnir_client_requests_total{transport,op,outcome}` / `voltnir_client_request_duration_seconds{transport,op_class}` | counter / histogram | Per-transport client request counts and durations; the gRPC outcome is the gRPC status, and a streaming RPC's duration is the time to first response headers. The [probes](#probes) and the gRPC health service are not client requests and are not counted. |
| `voltnir_client_auth_failures_total{transport}` / `voltnir_client_rate_limited_total{transport}` / `voltnir_client_connections{transport}` / `voltnir_client_stream_lagged_total{transport}` / `voltnir_client_stream_messages_lost_total{transport}` / `voltnir_broadcast_channel_depth{channel}` | counter / gauge | Auth failures, rate-limit refusals, open connections and streams, stream lag and loss, and broadcast channel depth per transport. |
| `voltnir_db_commit_seconds{writer}` / `voltnir_db_rows_committed_total{writer}` / `voltnir_db_commit_failed_total{writer}` | histogram / counter | Per-writer commit latency, rows committed and commit failures. |
| `process_resident_memory_bytes` / `process_virtual_memory_bytes` / `process_open_fds` / `process_max_fds` / `process_cpu_seconds_total` / `process_start_time_seconds` / `process_threads` | gauge / counter | Standard process metrics from `/proc/self` on Linux, empty elsewhere, so stock dashboards work. |
| `voltnir_runtime_workers` / `voltnir_runtime_alive_tasks` / `voltnir_runtime_global_queue_depth` | gauge | Async runtime worker count, live tasks and global queue depth. |

**Reading the histograms.** The latency and round-trip families are classic Prometheus histograms (`_bucket` / `_sum` / `_count`, in seconds), so a quantile is a `histogram_quantile` over the bucket rate, for example the order-ack p99 `histogram_quantile(0.99, sum by (le) (rate(voltnir_order_ack_seconds_bucket[5m])))`. Quantiles of separate histograms do not add up, which is why `voltnir_order_end_to_end_seconds` exists as its own measurement.

**Before writing alert rules.** Every condition is emitted on every scrape as `0` or `1`, so a missing series means the scrape failed, not that the gateway is healthy: alert on the value, not on `absent()`. Counters are cumulative since process start and reset on restart, so alert on `increase(...[5m]) > 0` and use `voltnir_start_timestamp_seconds` to detect a restart.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 401 | `{"error": "Unauthorized"}` | No or unknown bearer token |
| 403 | `{"error": "Forbidden"}` | Missing `read_metrics` permission |

#### Example

```bash
curl https://gateway.example:3000/api/v1/metrics \
  -H "Authorization: Bearer $VOLTNIR_METRICS_KEY"
```

```
HTTP/1.1 200 OK
Content-Type: application/openmetrics-text; version=1.0.0

# HELP voltnir_operational 1 when every order-critical subsystem is healthy and orders are admitted.
# TYPE voltnir_operational gauge
voltnir_operational 1
# HELP voltnir_cash_limit_breached 1 while the exchange reports the currency pool below zero.
# TYPE voltnir_cash_limit_breached gauge
voltnir_cash_limit_breached{currency="EUR"} 0
voltnir_cash_limit_breached{currency="GBP"} 0
# EOF
```

### <a id="get-status" name="get-status"></a>`GET` `/api/v1/status`

Return the caller-scoped trading-posture aggregate in one call: base posture and accounts for every authenticated caller, plus the desk-wide money and full licence for a caller holding `read_status`.

**Required permission:** none (authenticated). `read_status` adds the desk-wide money, full licence and M7 client certificate keys; without it those keys are absent (not null). (see [Permissions](#permissions))

#### Request

None. No parameters.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `operational` | bool | none | always | The runtime-health flag, as on [GET /state](#get-state). |
| `admission` | string | none | always | Whether new orders and modifies are admitted, as on [GET /state](#get-state). |
| `trading_enabled` | bool | none | always | Whether the kill switch permits new orders, as on [GET /trading_allowed](#get-trading-allowed). |
| `throttling` | object | none | always | The load-management status, the same object as [GET /throttling](#get-throttling). |
| `license_summary` | object | none | always | What an expiry banner needs: `status` (the tagged `{kind, days?}`), `expires_at`, `grace_end` (only while `in_grace`), and `mode`, the licence tier, `"trader"` or `"desk"`: on `"trader"` every user, member and permission management route answers `403` `LICENSE_DESK_REQUIRED` whatever the caller’s permissions, so a client hides those screens. None of the holder or signing fields. |
| `accounts` | array | none | always | Accounts the caller may submit orders for (the fields below). |
| `cash_limits` | object | none | read_status only | Raw M7-reported cash-limit feed keyed by currency, as on [GET /cash_limits](#get-cash-limits). |
| `order_pos_limit` | i64 | sub-MW (MW × 1000) | read_status only | The global per-contract position limit. |
| `cash_limit` | object | none | read_status only | Desk cash-limit state per pool, as on [GET /cash_limit](#get-cash-limit), plus `delivery_risk_applied` (bool) and `delivery_risk_source` (`"config"` \| `"exchange"`), described below. |
| `license` | object | none | read_status only | The full installed license, the same block as [GET /state](#get-state). |
| `stranded_pending_count` | i64 | count | read_status only | New orders held past their expiry bound: no answer from the exchange, and the gateway cannot rule out a missed report or a late XBID answer, so they go on consuming position and cash headroom until their report or refusal, the first order snapshot after the bound, a restart, or about an hour after their contract’s delivery ends. 0 on a healthy gateway. |
| `stranded_pending_qty` | i64 | sub-MW (MW × 1000) | read_status only | The quantity those held orders hold. |
| `claims_count` | i64 | count | read_status only | Amendments and activations whose added exposure counts against the position and cash limits until the exchange answers them or their expiry bound passes. Held claims included. |
| `claims_qty` | i64 | sub-MW (MW × 1000) | read_status only | What those claims add. |
| `claims_held_count` | i64 | count | read_status only | Of those, the claims held past their expiry bound, for the same reasons and until the same events as a held new order. 0 on a healthy gateway. |
| `claims_held_qty` | i64 | sub-MW (MW × 1000) | read_status only | What the held claims add: headroom lost to commands the exchange has not answered. |
| `m7_client_cert` | object | none | read_status only | The M7 client certificate, the first certificate in the file the gateway's `epex_connection.cert` setting names: `status`, the tagged `{kind, days?, reason?}`, where `kind` is `valid`, `expiring_soon` (from 30 days before expiry, `days` left), `expired` (`days` since expiry), `not_yet_valid` (`days` until it starts) or `unreadable` (`reason`: a missing file, no PEM block, no certificate, or one that does not parse); and `not_after`, RFC 3339 UTC, absent when unreadable. The gateway reads the file at startup and every hour. The exchange refuses the connection under an expired certificate, with no grace period; a replacement file at the same path is used on the next connection attempt, with no restart. |

#### `accounts[]`

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `is_house` | bool | none | always | The House account (present when the caller holds `trade_global`), or a virtual member. |
| `short_id` / `name` | string | none | member | The member's short id and name; absent on the House row. |
| `position_limit` | i64 | sub-MW (MW × 1000) | always | The account's own per-contract net limit. `0` is flat-only. |
| `effective_position_limit` | i64 | sub-MW (MW × 1000) | always | What actually binds an order: the House limit for House, `min(order_pos_limit, max_position)` for a member. |
| `slot_limit` | i64 | sub-MW (MW × 1000) | see description | The account's [slot position limit](#slot-limit): the House slot limit for House, the member's `max_slot_position` for a member. Absent for a member with no slot limit, and on the House row for a caller without `read_status`, which is not shown the House slot figures anywhere. `0` is flat-only. |
| `slot_mode` | string | none | always | The slot position limit mode, `off`, `observe` or `reject`, the same on every account. |
| `{eur,gbp}_consumed_cents` | i64 | pool cents | always | The account's own consumption per pool. For House this is the untagged book's exposure. |
| `{eur,gbp}_limit_cents` | i64 | pool cents | always | The account's allocation per pool. For House this is the remainder (effective House limit minus member allocations, negative when over-allocated); `0` means no allocation. |
| `{eur,gbp}_remaining_cents` | i64 | pool cents | always | Headroom admission would allow. For House, the tighter of the remainder and the aggregate desk guard. |

**`cash_limit.delivery_risk_applied`** says whether the GB delivery-risk add-on (a risk set's price-independent `alpha` per MWh on GB sells, or the configured GBP fallback rate) is charged in the GBP figures. The exchange charges it only to a member whose record says so, and states that record only when it changes, never on request. **`cash_limit.delivery_risk_source`** is `"exchange"` once this member's own record has been seen, in this session or stored from an earlier one, and `"config"` while the gateway's `cash_limit.delivery_risk_applied` setting decides (default `true`, charged). With it `false`, a GB order or trade is priced with its product's default risk set, the set the exchange prices such a member's GB legs with, instead of the GB delivery-risk set; with it `true`, with the GB set and its add-on, a pricing that has not been measured against the exchange. A change of the flag re-prices every open order and every trade in the exposure window at once. The source is always one of those two strings, never empty.

A caller **without** `read_status` receives the same object with the read_status-only keys **absent**; the base posture, `license_summary` and its own `accounts` stay. The three component reads that expose the desk-wide money ([GET /cash_limits](#get-cash-limits), [GET /cash_limit](#get-cash-limit), [GET /contract_limit](#get-contract-limit)) remain gated on `read_status`, so that layer cannot be read field by field. This is the same flat shape broadcast on the WebSocket `status` stream and returned by the gRPC `GetStatus` RPC. Exposure is summed exactly and rounded once: `*_consumed_cents` rounds up and `*_remaining_cents` rounds down, matching the exchange's own remaining limit to the cent.

#### Errors

No permission error: any authenticated caller receives a `200`. A caller lacking `read_status` receives the base layers without the desk-money keys.

#### Example

```bash
curl https://gateway.example:3000/api/v1/status \
  -H "Authorization: Bearer $VOLTNIR_API_KEY"
```

```
HTTP/1.1 200 OK
{
  "operational": true,
  "trading_enabled": true,
  "throttling": { },
  "license_summary": {"status": {"kind": "active"}, "expires_at": "2027-01-01T00:00:00Z", "mode": "desk"},
  "accounts": [
    {"is_house": true, "position_limit": 50000, "effective_position_limit": 50000, "eur_consumed_cents": 3500000, "eur_limit_cents": 10000000, "eur_remaining_cents": 6500000, "gbp_consumed_cents": 0, "gbp_limit_cents": 0, "gbp_remaining_cents": 0}
  ],
  "order_pos_limit": 50000,
  "cash_limit": { },
  "stranded_pending_count": 0,
  "stranded_pending_qty": 0,
  "claims_count": 0,
  "claims_qty": 0,
  "claims_held_count": 0,
  "claims_held_qty": 0,
  "m7_client_cert": {"status": {"kind": "valid"}, "not_after": "2027-03-01T12:00:00Z"}
}
```

### <a id="get-throttling" name="get-throttling"></a>`GET` `/api/v1/throttling`

Return M7's order load-management status for the connected member and this gateway's own client-side guard, in counts per window (no money or positions).

**Required permission:** none (authenticated). The OMT budget belongs to the gateway's single M7 login and the whole desk shares it, so a trader needs it to tell a saturated desk from a bad order. (see [Permissions](#permissions))

#### Request

None. No parameters.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `mbr_id` | string | none | always | The connected member id. |
| `timestamp` | string \| null | UTC, RFC 3339 with `Z` | optional | When `status` became true; `null` until the exchange first states one. The counts beside it may be a few seconds older. |
| `status` / `short_status` / `long_status` | string \| null | none | optional | `"NO_RESTRICTION"`, `"WARNING"` or `"RESTRICTED"`; `null` until the exchange first states one. |
| `short_*` / `long_*` window fields | i64 \| null | seconds / count | optional | Per window (short ~10s, long 24h): `observation_period`, `tolerance_period`, `reconnection_cool_down` (seconds), `omt_limit_l1`, `omt_limit_l2`, `current_omt_count` (counts), and `release_timestamp` (the indicative release moment, UTC, RFC 3339 with `Z`, or `null`). |
| `guard` | object | none | always | This gateway's own client-side guard, current to the millisecond (fields below). |
| `throttling_member_action` | string | none | always | What this gateway asks the exchange, at every login, to do with **every** order of the member when it restricts the member, from the `load_management` configuration. `"HIBE_MBR_ORDERS"` (the default) hibernates them all, whichever client entered them, and overrides every user-level action; `"NONE_MBR_ORDERS"` leaves it to each user's own action. The exchange keeps the member-level value of the last login that stated one, so another client of the member logging in later can replace it until this gateway logs in again. |
| `throttling_user_action` | string | none | always | What this gateway asks the exchange, at every login, to do with the orders of its own exchange user on a restriction: `"HIBE_USER_ORDERS"` (the default) hibernates them, `"HIBE_BG_ORDERS"` hibernates every order of the user's balancing group, `"NONE_USER_ORDERS"` none, unless the member-level action hibernates them anyway. |

#### `guard`

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `enabled` | bool | none | always | `false` when the operator has turned the guard off; loads are still counted but no order action is refused on their account. |
| `reported` | bool | none | always | `true` once M7 has reported, so the thresholds are the exchange's own rather than the pre-report fallbacks. |
| `report_age_sec` | i64 \| null | seconds | optional | How long ago the exchange last reported; `null` before it ever has. A figure that stops advancing means the reports have stopped. |
| `stale` | bool | none | always | `true` once that age passes the load-report age ceiling (30 seconds by default). The member's load is then unknown and no order may add exposure until the exchange reports again; cancels and hibernations are unaffected. |
| `short` / `long` | object | none | always | Per rule: the window and threshold applied, `local_omts` (what this gateway sent), `estimated_load` (the member-wide estimate) and `headroom`. |
| `headroom` | i64 | count | always | The binding value, the smaller of the two rules': how many further exposure-adding order actions will be admitted. |
| `blocked_reason` | string \| null | none | optional | Why exposure-adding order actions are being refused right now; `null` when they are being admitted. |

M7 counts every order management transaction (an entry, modify, activation, hibernation or deletion) the member's API clients send, whether accepted or rejected, in two rolling windows: a short one and a 24h one, each with an `L1` warning and an `L2` hard threshold. At `L1` the status becomes `WARNING`; at `L2`, or when the tolerance runs out at `L1`, the whole member becomes `RESTRICTED` and the exchange rejects every API order action until released. The guard refuses order actions before the warning threshold: a new order, reprice, resize or activation is refused with `422` once `guard.headroom` reaches zero, and every order action is refused while the member is `RESTRICTED`. A cancel or hibernation is *never* refused for headroom alone, so the desk can always get flat. `estimated_load` is an estimate, not a bound: it more often over-states the member's load than under-states it. When the exchange restricts the member it applies the two actions above: the orders it hibernates stay listed on `GET /orders` with `state` `"HIBERNATED"` and action `SHIB` or `UHIB`, hold no exposure, and come back with `PUT /order` and `modify_action: "activate"`, which this guard treats like a new order.

#### Errors

No permission error: any authenticated caller receives a `200`.

#### Example

```bash
curl https://gateway.example:3000/api/v1/throttling \
  -H "Authorization: Bearer $VOLTNIR_API_KEY"
```

```
HTTP/1.1 200 OK
{
  "mbr_id": "MBR001",
  "status": "NO_RESTRICTION",
  "short_omt_limit_l1": 1000,
  "short_current_omt_count": 3,
  "long_omt_limit_l1": 20000,
  "long_current_omt_count": 42,
  "guard": {"enabled": true, "reported": true, "headroom": 996, "blocked_reason": null},
  "throttling_member_action": "HIBE_MBR_ORDERS",
  "throttling_user_action": "HIBE_USER_ORDERS"
}
```

### <a id="get-system-info" name="get-system-info"></a>`GET` `/api/v1/system_info`

Return the M7 reference data this session runs against, read-only: the system snapshot captured at authentication, the `products` table (the bounds every order is measured against), and the `risk_sets` table (the parameters the exchange prices cash exposure with).

**Required permission:** none (authenticated). (see [Permissions](#permissions))

#### Request

None. No parameters.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `market_id` | string \| null | none | optional | The M7 market id (e.g. `EPEX`); `null` until the first system report. |
| `voltnir_version` | string | none | always | This gateway's own build. The one always-present field. |
| `backend_version` | string \| null | none | optional | The M7 backend version; `null` until the first system report. |
| `backend_time_zone` / `backend_market_time_zone` | string \| null | none | optional | The exchange's server and market time zones. |
| `contract_store_time_in_days` | i64 \| null | days | optional | How far back the exchange serves contract and trade history. |
| `trade_pool_store_time_in_hours` | i64 \| null | hours | optional | Public trade-tape retention at the exchange. |
| `max_orders` | i64 \| null | count | optional | The per-session order cap. |
| `capabilities` | string \| null | none | optional | The enabled M7 capabilities (comma-separated). |
| `allowed_clearing_acct_types` | string \| null | none | optional | The clearing account types the account may use. |
| `request_limits` | array | none | always | Per-message-type request rate limits: `{message, duration_ms, rate}`. Empty until the first system report. |
| `products` | array | none | always | One entry per product the exchange has assigned your account (fields below). |
| `risk_sets` | array | none | always | The cash-exposure risk parameters (note below). |

Every M7-sourced scalar is `null` and `request_limits` is empty until the first system report arrives; the two tables come from separate reports, so either can be populated while that answer is still outstanding. **The bounds are the ones actually enforced**, the exchange's own product reference data, in the same wire units an order carries, so they compare directly against [POST /order](#post-order) fields. A `null` bound is not enforced: the exchange judges it instead.

#### `products[]`

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `name` | string | none | always | The product a contract names in its `prod` field, the join key from a contract to this row. |
| `currency` / `state` / `revision_no` | string / i64 | none | always | As the exchange reports them; `state` is `ACTI`, `IACT` or `HIBE`. |
| `cash_limit_enabled` | bool | none | always | Whether the exchange applies cash limits to this product. |
| `default_risk_set_id` | i64 | none | always | The `risk_sets` row used for any delivery area that does not name its own. |
| `delivery_areas` | array | none | always | Areas assigned to the product, each `{delivery_area_id, risk_set_id}`; a non-null `risk_set_id` overrides the product default in that area. |
| `tick_cents` | i64 | cents | always | Minimum price increment. A price off this grid is refused with `400`. |
| `min_price_cents` / `max_price_cents` | i64 | cents | always | Inclusive price band; legitimately negative. |
| `lot_sub_mw` | i64 | sub-MW | always | Minimum quantity increment. |
| `min_qty_sub_mw` / `max_qty_sub_mw` | i64 | sub-MW | always | Inclusive size band. |
| `iceberg_min_peak_sub_mw` | i64 | sub-MW | always | Smallest `display_qty` the product accepts on an iceberg order. |
| `dec_shft_px` / `dec_shft_qty` / `qty_unit` | i64 / string \| null | none | optional | M7's own per-product decimal shifts and quantity unit; the bounds and order fields are always on the gateway's cents and sub-MW scale regardless. `null` only when `scale` is `unknown`. |
| `scale` | string | none | always | `representable`, `unrepresentable` (orders refused `PRODUCT_SCALE_UNSUPPORTED`), or `unknown` (orders refused `PRODUCT_SCALE_UNKNOWN`). |
| `block_order_product` | bool \| null | none | always | Whether the product takes user-defined block orders (`blockOrderProduct`). `false` refuses a block create with `BLOCK_NOT_SUPPORTED`; `null` means the product publishes no reading of it, and nothing is refused on it: the exchange decides. |
| `block_maximum_hours` | u32 \| null | none | always | How much one block may group (`blockMaximumHours`), read both as a count of the product's contracts and as hours: a window is refused with `BLOCK_WINDOW_TOO_LONG` only when it exceeds both. `null` means unpublished (a published 0 reads the same), and no window is refused for its length. |
| `dst_block_product` | bool \| null | none | always | The product's treatment of contracts on the 25-hour clock-change day (`dstBlockProduct`), as published. No local check reads it: on that day the exchange decides. `null` means the product publishes no reading of it. |
| `linked_order_product` | bool \| null | none | always | Whether the product takes orders in a `linked` basket (`linkedOrderProduct`), as published. `false` refuses such a basket locally with `BASKET_LINKED_NOT_SUPPORTED`; `null` means the product publishes no reading of it, which refuses nothing and leaves the decision to the exchange. |

**`risk_sets[]`.** One leg contributes `a[case] × signed price × MWh + alpha[case] × MWh` to consumed cash, where `case` is chosen by side (buy/sell), price sign (pos/neg) and whether the exposure is a resting order or an executed trade. `a` is a bare multiplier; `alpha` is in the product's currency per MWh. Which set applies to a leg is decided by its product and delivery area. See [GET /cash_limit](#get-cash-limit) for what those figures are measured against.

#### Errors

No permission error: any authenticated caller receives a `200`.

#### Example

```bash
curl https://gateway.example:3000/api/v1/system_info \
  -H "Authorization: Bearer $VOLTNIR_API_KEY"
```

```
HTTP/1.1 200 OK
{
  "market_id": "EPEX",
  "voltnir_version": "1.0.1",
  "backend_version": "7.21.3",
  "contract_store_time_in_days": 30,
  "products": [
    {"name": "Intraday_Hour_Power", "currency": "EUR", "state": "ACTI", "cash_limit_enabled": true, "default_risk_set_id": 1, "tick_cents": 10, "min_price_cents": -999900, "max_price_cents": 999900, "lot_sub_mw": 100, "iceberg_min_peak_sub_mw": 5000, "dec_shft_px": 2, "dec_shft_qty": 3, "qty_unit": "MW", "scale": "representable", "block_order_product": true, "block_maximum_hours": 6, "dst_block_product": true}
  ],
  "risk_sets": [ {"risk_set_id": 1, "name": "EUR continuous", "revision_no": 3} ]
}
```

### <a id="get-area-table" name="get-area-table"></a>`GET` `/api/v1/area_table`

Return the M7 EIC area reference table, read-only: the structure of every delivery / hub-to-hub area (`areas`) and market area (`market_areas`), with names overlaid from the live M7 area reports when the exchange has named them.

**Required permission:** none (authenticated). (see [Permissions](#permissions))

#### Request

None. No parameters.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `areas` | array | none | always | Every delivery / hub-to-hub area (fields below). |
| `market_areas` | array | none | always | Each carries the market area's `eic`, `name` / `long_name` (same overlay rule as `areas`), and `name_source`. A delivery area's `parent_ma_eic` joins to one of these rows. |

#### `areas[]`

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `eic` | string | none | always | The delivery / hub-to-hub area's EIC (the `dlvryAreaId` a contract and an order name). |
| `short_name` / `long_name` | string | none | always | Display names, overlaid from the live M7 report when it named the area, otherwise the embedded defaults. |
| `parent_ma_eic` | string \| null | none | optional | The parent market area's EIC (a row in `market_areas`); `null` for areas the table groups only by a short name. |
| `fill_country` | string \| null | ISO 3166-1 alpha-2 | optional | The whole country this area fills on a country-fill map, folded to the parent for a virtual / control sub-zone; `null` for a `border_coupling` area, which fills no country. Treat an absent value as "no country". |
| `area_class` | string | none | always | `bidding_zone`, `virtual_optimisation`, `border_coupling`, or `control_area`. |
| `epex_da` | bool | none | always | Whether the area is an EPEX day-ahead / intraday tradeable area. Read tradability here, never infer it from `area_class`. |
| `h2h_only` | bool | none | always | The area exists only for the hub-to-hub capacity matrix (non-EPEX). |
| `assigned_products` | array | none | always | The product names assigned to the area, where the reference data lists them; `[]` otherwise. |
| `name_source` | string | none | always | `static` (embedded default) or `exchange` (a live M7 report named the area). |

Structure and geometry (`fill_country`, `area_class`, `parent_ma_eic`, and the EPEX / hub-to-hub flags) are always the embedded table's: the exchange supplies names, never shape. The embedded table is the always-available floor, so this answers off a fresh connection; a live name lifts that one row's `name_source` to `exchange`.

#### Errors

No permission error: any authenticated caller receives a `200`.

#### Example

```bash
curl https://gateway.example:3000/api/v1/area_table \
  -H "Authorization: Bearer $VOLTNIR_API_KEY"
```

```
HTTP/1.1 200 OK
{
  "areas": [
    {"eic": "10YNO-2--------T", "short_name": "NO2", "long_name": "Norwegian Elspot Area 2", "parent_ma_eic": "50Y-DUMMY-NO2--P", "fill_country": "NO", "area_class": "bidding_zone", "epex_da": true, "h2h_only": false, "assigned_products": ["Intraday_Hour_Power"], "name_source": "static"}
  ],
  "market_areas": [ {"eic": "10Y1001A1001A82H", "name": "DE", "long_name": "Germany", "name_source": "static"} ]
}
```

### <a id="get-pnl" name="get-pnl"></a>`GET` `/api/v1/pnl`

Recompute and return the caller-scoped P&L snapshot from the current trade store and order book. Stateless: every call walks the trade history through a weighted-average-cost state machine.

**Required permission:** none (authenticated). `read_pnl` or `bypass_member_check` returns the firm-wide snapshot. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `v_member_short_id` | string | none | No | Query parameter. Narrow the snapshot to a single virtual member; returns only its `per_vm`/`per_vm_area_prod` rows. Rejected with `403` unless the caller is assigned to it or holds `read_pnl`/`bypass_member_check`. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `per_contract` | array | none | scope | House-account per-contract rollup; **empty** for a caller without broad read. |
| `per_area_prod` | array | none | scope | House-account per-area/product rollup; **empty** for a caller without broad read. |
| `per_vm` | array | none | always | Per virtual-member rows: the caller's assigned members, or every member with broad read. |
| `per_vm_area_prod` | array | none | always | Per member/area/product rows, scoped the same way. |
| `totals` | array | none | always | One `{currency, realized_pnl, unrealized_pnl}` per settlement currency; no figure crosses currencies. |
| `unpriced_trades` | i64 | count | always | Trades left out of the walk because their delivery duration is not yet known (counting trades the exchange has not reversed (any state but `RGRA` or `CNCL`)); they rejoin once the contract report heals the duration. |
| `computed_at_ms` | i64 | Unix ms (UTC) | always | When the snapshot was computed. |
| `compute_us` | i64 | microseconds | always | How long the walk took. |

#### Row fields (`per_contract[]`)

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `area_id` / `currency` / `product` | string | none | always | The contract's area, settlement currency and product. |
| `contract_id` | i64 | none | always | M7 contract id. |
| `delivery_day` | string | YYYY-MM-DD | always | The contract's local delivery day (market timezone); `""` when unknown. |
| `signed_position` | i64 | sub-MW (MW × 1000) | always | Net position; positive long. |
| `avg_open_px` / `mark_px` | i64 | cents (CCY/MWh × 100) | always | Weighted-average open price and mark price; bare prices, never energy-scaled. |
| `mark_source` | string | none | always | `"Mid"`, `"Last"`, `"None"` (uPnL 0), or, once closed, `"Close"` or `"CloseLast"`. |
| `realized_pnl` / `unrealized_pnl` | i64 | q8 (currency × 100,000) | always | Realized and unrealized P&L; divide by 100,000 to render the currency. |

**Units.** Money values are in q8 units = M7-px (currency/MWh × 100) × sub-MW (MWh × 1000) × `duration_min` / 60 = **currency × 100,000**. The money is energy-scaled by the contract's delivery duration: a 15-minute fill is booked at a quarter of its hourly `px × qty`, a 2-hour block at double. `avg_open_px` and `mark_px` stay bare prices. Positions are sub-MW.

**Scoping.** A caller holding `read_pnl` (or `bypass_member_check`) receives the firm-wide snapshot; every other caller receives only its assigned members' `per_vm`/`per_vm_area_prod` rows, with `per_contract`/`per_area_prod` empty. The live snapshot covers only contracts whose delivery day is today or later. Executed trades count until the exchange grants a recall (`RGRA`) or cancels them (`CNCL`); a recall or cancellation that is only requested, or was rejected, leaves the trade counting. Open and pending orders do not count. Not modelled: fees, FX and imbalance valuation. The same shape is broadcast on the WebSocket `pnl` stream; prefer the WebSocket for live polling.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 403 | `{"error": "Forbidden"}` | `v_member_short_id` names a member the caller may not see |

#### Example

```bash
curl https://gateway.example:3000/api/v1/pnl \
  -H "Authorization: Bearer $VOLTNIR_API_KEY"
```

```
HTTP/1.1 200 OK
{
  "per_contract": [ {"area_id": "10YNL----------L", "currency": "EUR", "contract_id": 100001, "product": "H", "delivery_day": "2026-04-20", "signed_position": 1000, "avg_open_px": 5000, "mark_px": 5200, "mark_source": "Mid", "realized_pnl": 0, "unrealized_pnl": 200000} ],
  "per_area_prod": [ ],
  "per_vm": [],
  "per_vm_area_prod": [],
  "totals": [ {"currency": "EUR", "realized_pnl": 0, "unrealized_pnl": 200000} ],
  "unpriced_trades": 0,
  "computed_at_ms": 1713600000000,
  "compute_us": 142
}
```

### <a id="get-trading-allowed" name="get-trading-allowed"></a>`GET` `/api/v1/trading_allowed`

Return whether order submission is currently enabled. When disabled, all order creation and modification is rejected before reaching the exchange.

**Required permission:** none (authenticated). This is the `trading_enabled` base slice of [GET /status](#get-status). (see [Permissions](#permissions))

#### Request

None. No parameters.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `enabled` | bool | none | always | `true` when order submission is permitted. |

#### Errors

No permission error: any authenticated caller receives a `200`.

#### Example

```bash
curl https://gateway.example:3000/api/v1/trading_allowed \
  -H "Authorization: Bearer $VOLTNIR_API_KEY"
# {"enabled": true}
```

### <a id="get-self-trade-policy" name="get-self-trade-policy"></a>`GET` `/api/v1/self_trade_policy`

Return the active self-trade (cross-trade) prevention policy. EPEX M7 does not prevent self-trades server-side; this is a Voltnir-side pre-trade check for one of your own resting orders on the opposite side at a crossing price.

**Required permission:** none (authenticated). (see [Permissions](#permissions))

#### Request

None. No parameters.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `policy` | string | none | always | `observe` (detect and log, allow the order through) or `reject` (block the self-crossing order before it reaches M7). |

#### Errors

No permission error: any authenticated caller receives a `200`.

#### Example

```bash
curl https://gateway.example:3000/api/v1/self_trade_policy \
  -H "Authorization: Bearer $VOLTNIR_API_KEY"
# {"policy": "observe"}
```

### <a id="get-cash-limits" name="get-cash-limits"></a>`GET` `/api/v1/cash_limits`

Return the latest cash/margin limits reported by the M7 exchange, keyed by ISO currency code (the raw M7 feed). Distinct from [GET /cash_limit](#get-cash-limit), which is the desk's own partitioned view.

**Required permission:** `read_status`. (see [Permissions](#permissions))

#### Request

None. No parameters.

#### Response

A `{"limits": {"<CUR>": {...}}}` map, empty until the first cash-limit report arrives. Each currency entry:

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `currency` | string | none | always | ISO currency code. |
| `current_limit` | i64 \| null | raw (see dec_shft) | optional | The current limit; human amount = `current_limit` / 10dec_shft. |
| `current_revision` | i64 \| null | none | optional | Revision of the current-limit figure. |
| `configured_limit` | i64 \| null | raw (see dec_shft) | optional | The configured limit. |
| `dec_shft` | i64 \| null | none | optional | Decimal shift: divide the raw fields by 10dec_shft. |
| `lmt_id` | string \| null | none | optional | The exchange's limit id. |
| `state` | string \| null | none | optional | The limit state. |
| `start_date` | string \| null | YYYY-MM-DD | optional | When the limit takes effect. |
| `revision_no` | i64 \| null | none | optional | Record revision number. |

Every field past `currency` is nullable; partial M7 reports leave fields unset until both the snapshot and detail records have arrived. The same data is broadcast on the WebSocket status frame.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 403 | `{"error": "Forbidden"}` | Missing `read_status` permission |

#### Example

```bash
curl https://gateway.example:3000/api/v1/cash_limits \
  -H "Authorization: Bearer $VOLTNIR_API_KEY"
```

```
HTTP/1.1 200 OK
{"limits": {"EUR": {"currency": "EUR", "current_limit": 1234500, "current_revision": 5, "configured_limit": 5000000, "dec_shft": 2, "lmt_id": "L1", "state": "ACTIVE", "start_date": "2026-01-01", "revision_no": 7}}}
```

### <a id="get-cash-limit" name="get-cash-limit"></a>`GET` `/api/v1/cash_limit`

Return the desk's cash limit for both currency pools (EUR and GBP, independent). The House limit comes from the exchange; an operator cap only tightens it; the limit is then partitioned between virtual members and the House remainder.

**Required permission:** `read_status`. (see [Permissions](#permissions))

#### Request

None. No parameters.

#### Response

An `{"eur": {...}, "gbp": {...}}` object. Each pool:

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `ecc_limit_cents` | i64 \| null | cents | optional | The clearing-house limit in force; `null` when the exchange has reported none. |
| `ecc_revision` | i64 \| null | none | optional | Revision of the record the limit came from. |
| `ecc_effective_from` | string \| null | YYYY-MM-DD | optional | The date that record takes effect, in the exposure timezone; the exchange sends it as an instant, so the calendar day depends on that zone. `null` when none was reported or it could not be read. |
| `m7_remaining_cents` | i64 \| null | cents | optional | What the exchange still has available in the pool before the next booking cut; already nets off open orders and executed trades. |
| `cap_cents` | i64 \| null | cents | optional | The operator cap. `null` = no cap; `0` = a deliberate cap of zero. |
| `house_cents` | i64 | cents | always | The limit every check uses: `min(ecc_limit_cents, cap_cents)`, with an unreported clearing-house limit counted as zero. |
| `allocated_cents` | i64 | cents | always | Sum of every virtual member's allocation, active and inactive alike. Each member spends only its own slice. |
| `unallocated_cents` | i64 | cents | always | What is left for the House (untagged) account: `house_cents − allocated_cents`. Can be negative (see `over_allocated`). Untagged orders are rejected once it reaches zero. |
| `over_allocated` | bool | none | always | `true` when the allocations sum to more than `house_cents`, reachable only when the exchange lowers its limit under allocations already granted. |
| `cap_above_ecc` | bool | none | always | `true` when a standing cap now sits above the clearing-house limit, which binds instead. The cap is never changed behind the operator's back. |
| `breached` | bool | none | always | `true` while the exchange reports the pool below zero; it has deactivated every order in that currency and no order may add exposure until a report shows the limit at or above zero. |
| `reported_at_ms` | i64 \| null | Unix ms (UTC) | optional | When the exchange last reported this pool; `null` when it never has. A value that stops advancing means the reports have stopped. |
| `stale` | bool | none | always | `true` once the figures can no longer be trusted: the channel carrying its reports broke since they arrived, or an optional age ceiling was passed. The pool then refuses every order that adds exposure until it is reported again. |

> [!WARNING]
> A clearing-house limit the exchange has not reported is **zero**, not "unbounded": if no trading limit is set, no exposure can be created. Until the first cash-limit report arrives after startup, no order may add exposure in either pool.

> [!WARNING]
> **A report the gateway can no longer vouch for is treated the same way.** The exchange broadcasts a cash-limit change only when one happens, so on an unbroken channel silence is evidence the limit held. After a reconnect, or a detected sequence gap on the member routing key, a report may have been missed while the limit moved, so those pools go `stale`, their figures count as unknown, and every order that adds exposure in them is rejected with scope `stale_cash_limit` until the exchange reports them again. A desk that simply has not traded for a while is **not** stale.

> [!NOTE]
> **How much an order or trade consumes.** The exchange publishes a risk set per product and delivery area: eight price-dependent `a` parameters and four price-independent `alpha` parameters. One leg consumes `a[case] × signed price × MWh + alpha[case] × MWh`, where `case` is chosen by side, price sign, and whether the exposure comes from a resting order or an executed trade. Voltnir reads those parameters from the exchange and prices with them, so its arithmetic is the exchange's arithmetic. A resting order never contributes a credit (its exposure is floored at zero), and every figure scales with the contract's delivery duration.

> [!NOTE]
> On the exchange's default risk set a buy at a positive price consumes its value, a trade moves the limit by its full signed value, and the risk-free order cases (sell at a positive price, buy at a negative price) cost nothing. The one exception is a trade whose delivery duration Voltnir does not yet know: it is counted as one hour long when it consumes, and credits nothing until its duration is known. A GB delivery area is assigned a risk set carrying a GB price-independent delivery-risk parameter as its `alpha` sell value, so GB sells also decrease the limit for a member the add-on applies to ([`cash_limit.delivery_risk_applied`](#get-status); with it `false` a GB leg is priced with its product's default risk set instead, the set the exchange prices such a member's GB legs with); a GB risk set may charge the price term on a negative-price sell on top of that add-on. Until the exchange has published a risk set for a contract's product and area, Voltnir prices the leg with a stand-in rather than at zero: the EUR rules for a non-GBP area, and the configured GBP delivery-risk rate (see the [gateway configuration guide](config_yml_dist.md)) for a GBP one, charged only with `delivery_risk_applied` on.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 403 | `{"error": "Forbidden"}` | Missing `read_status` permission |

#### Example

```bash
curl https://gateway.example:3000/api/v1/cash_limit \
  -H "Authorization: Bearer $VOLTNIR_API_KEY"
```

```
HTTP/1.1 200 OK
{
  "eur": {"ecc_limit_cents": 10000000, "ecc_revision": 7, "ecc_effective_from": "2026-09-03", "m7_remaining_cents": 8412300, "cap_cents": null, "house_cents": 10000000, "allocated_cents": 7500000, "unallocated_cents": 2500000, "over_allocated": false, "cap_above_ecc": false, "breached": false, "reported_at_ms": 1788336000000, "stale": false},
  "gbp": {"ecc_limit_cents": null, "ecc_revision": null, "ecc_effective_from": null, "m7_remaining_cents": null, "cap_cents": null, "house_cents": 0, "allocated_cents": 0, "unallocated_cents": 0, "over_allocated": false, "cap_above_ecc": false, "breached": false, "reported_at_ms": null, "stale": false}
}
```

### <a id="get-contract-limit" name="get-contract-limit"></a>`GET` `/api/v1/contract_limit`

Return the current per-contract net-position limit in sub-MW. Orders that would push the net position beyond this limit are rejected with a `422`.

**Required permission:** `read_status`. (see [Permissions](#permissions))

#### Request

None. No parameters.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `limit` | i32 | sub-MW (MW × 1000) | always | Maximum net position per contract. Example `5000` = 5.0 MW. |

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 403 | `{"error": "Forbidden"}` | Missing `read_status` permission |

#### Example

```bash
curl https://gateway.example:3000/api/v1/contract_limit \
  -H "Authorization: Bearer $VOLTNIR_API_KEY"
# {"limit": 5000}
```

### <a id="get-holidays" name="get-holidays"></a>`GET` `/api/v1/holidays`

Return the bank-holiday calendars used by the cash-limit exposure window, one list per settlement currency.

**Required permission:** none (authenticated). The calendars are edited under [Limits & controls](#put-holidays) with `set_cash_limit`. (see [Permissions](#permissions))

#### Request

None. No parameters.

#### Response

An `{"eur": [...], "gbp": [...]}` object, one array per currency. Each entry:

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `date` | string | YYYY-MM-DD | always | A holiday the exposure window skips. |
| `label` | string \| null | none | optional | Optional display label, ignored by the window math. A gateway-derived date carries an `(auto)` suffix. |

The cash limit re-bases exposure at 16:00 (exchange timezone) on each clearing business day; configured holidays extend the window across them (a Monday holiday rolls the Friday window to Tuesday). The GBP limit resets on the same days as the EUR limit, so the same six TARGET2 closing days belong in both calendars every year: New Year's Day, Good Friday, Easter Monday, 1 May, Christmas Day and 26 December. **The gateway fills in the TARGET2 dates itself:** it derives the six closing days and adds them to both calendars at startup and on an hourly check, for the current year and, from December, the next one, so the turn of the year needs no action. A date already in a calendar is never overwritten, so an operator's entry always wins.

**Deleting one of the six derived dates sticks:** the remove operation remembers it for that currency and the check does not add it back; the deletion is persisted with the calendar and survives a restart, and adding the date again lifts it. A replace is not a deletion: a date it leaves out is restocked at the next check. There is no machine-readable clearing calendar upstream, so this is a derivation, not a feed: an ad-hoc closure is added through these operations, and a schedule change is made by deleting the derived date that no longer applies and adding the new one.

**An empty calendar is a missing input, not a permissive one:** without it the exposure window can only skip weekends and rolls a day early through every TARGET2 closing day, so that currency's pool refuses every order which adds exposure (`no_holiday_calendar`) until a date is entered. A calendar holding no date in the current or the next calendar year refuses the same orders under `stale_holiday_calendar`; with the derived dates in place this normally never fires. Orders that reduce or do not change exposure keep working, as does the other currency's pool, and entering a date for the current year lifts the refusal immediately.

#### Errors

No permission error: any authenticated caller receives a `200`.

#### Example

```bash
curl https://gateway.example:3000/api/v1/holidays \
  -H "Authorization: Bearer $VOLTNIR_API_KEY"
```

```
HTTP/1.1 200 OK
{
  "eur": [ {"date": "2026-12-25", "label": "Christmas Day"}, {"date": "2026-12-26", "label": null} ],
  "gbp": [ {"date": "2026-12-25", "label": "Christmas Day"}, {"date": "2026-12-26", "label": null} ]
}
```

<a id="controls" name="controls"></a>

## Limits & controls

Set the trading kill switch, the position and cash limits, the self-trade policy and the holiday calendars, restart the gateway, and restore trade history. Each takes effect immediately and is persisted.

> [!WARNING]
> **PUT /trading_allowed with `enabled: false` halts new order traffic and flattens the resting book.** Use it as a kill-switch only. It triggers a DeleteAllOrders command to M7 with no confirmation prompt, and while disabled new orders and modifies are rejected with `422` before reaching M7. Cancels remain available. The response's `flatten` object says whether the exchange confirmed the cancel; a `false` `ok` means trading is halted but orders may still be resting.

### <a id="put-trading-allowed" name="put-trading-allowed"></a>`PUT` `/api/v1/trading_allowed`

Enable or disable order submission. Setting `enabled: false` also sends a DeleteAllOrders command to M7 to flatten the account and reports in `flatten` whether the exchange confirmed it.

**Required permission:** `toggle_trading`. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `enabled` | bool | none | Yes | `true` to allow trading, `false` to halt and cancel all orders. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `enabled` | bool | none | always | The trading flag as it now stands. Always the value you sent; the flip is applied before the flatten and is never rolled back by it. |
| `flatten` | object \| null | none | optional | The outcome of the account-wide cancel; `null` when `enabled: true`, because enabling publishes nothing. |
| `flatten.ok` | bool | none | on disable | `true` only when M7 acknowledged the DeleteAllOrders. `false` means the publisher queue would not take the command inside the ack window, the exchange rejected it, or no receipt arrived inside the order acknowledgement timeout (2 seconds by default); in every case resting orders may still be live and the desk should verify the book directly. |
| `flatten.error` | string \| null | none | optional | The reason when `ok` is `false`; `null` otherwise. |

> [!WARNING]
> Setting `enabled: false` is a kill-switch operation. It cannot be undone; you must re-submit orders after re-enabling trading. **The flag is off whether or not the flatten succeeded**, so read `flatten.ok` to learn whether the exchange confirmed receipt of the cancel, and treat `false` as "orders may still be live on the exchange".

> [!NOTE]
> A failed flatten is not an HTTP error: the response is still `200` because the kill switch itself took effect. A `5xx` would invite a retry, and re-sending the toggle does not re-run the cancel any more reliably than `DELETE /orders` does. Every kill-switch flatten is written to the audit log as `order_cancel_all`.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 403 | `{"error": "Forbidden"}` | Missing `toggle_trading` permission |
| 409 | `{"error": "trading is force-disabled by config…"}` | A start-time flag force-disables trading and overrides the runtime toggle; trading cannot be changed at runtime |

#### Example

```bash
curl -X PUT https://gateway.example:3000/api/v1/trading_allowed \
  -H "Authorization: Bearer $VOLTNIR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}'
```

```
HTTP/1.1 200 OK
{"enabled": false, "flatten": {"ok": true, "error": null}}
```

### <a id="post-trade-ingest-fault-ack" name="post-trade-ingest-fault-ack"></a>`POST` `/api/v1/trade_ingest_fault/ack`

Acknowledge a raised `trade_report refused` fault, reopening order admission on incomplete figures. While the gateway holds a trade report it could not read, a trade the exchange executed is missing from its count, so position, cash and P&L are understated and, under the default `system.trade_ingest_fault: close`, new orders and modifies are refused. An acknowledgement admits them for `system.trade_ingest_fault_ack_ttl_sec` (1800 s by default) while no other issue is present; `admission` on state and status reads `degraded` meanwhile. Meanwhile the gateway does not reconnect its exchange session over the fault; another order-critical issue closes admission as usual, and the TTL keeps running while it does. It ends early when the fault clears, a repeat restarts the TTL, and it lives in the gateway's memory, so a restart drops it (the login backfill raises the fault again if the report is still unreadable). Each acknowledgement writes a `trade_ingest_fault_acknowledged` audit row carrying the reason and the TTL; one that runs out writes `trade_ingest_fault_ack_expired`. The exchange still checks the member's cash limit on every order. The trading terminal has no control for this: it is an API call. Mirrors gRPC `AckTradeIngestFault` and the WS `ack_trade_ingest_fault` command.

**Required permission:** `toggle_trading`. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `reason` | string | none | Yes | Why the desk trades on. Recorded in the audit row. Empty or blank is refused. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `ttl_sec` | u64 | s | always | How long admission is reopened for. |
| `expires_at_ms` | i64 | Unix ms | always | When the acknowledgement expires. It ends earlier when the fault clears. |
| `renewed` | bool | none | always | `true` when it replaced a live acknowledgement, restarting the TTL. |

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "reason is required…", "code": "BAD_REQUEST"}` | The body has no `reason`, or it is empty or blank, or the body does not parse |
| 403 | `{"error": "Forbidden"}` | Missing `toggle_trading` permission |
| 409 | `{"error": "no trade_report refused fault is raised…", "code": "CONFLICT"}` | No fault is raised: there is nothing to acknowledge |
| 409 | `{"error": "amqp_private_consumer unhealthy…", "code": "CONFLICT"}` or `ws_private_data_stream not connected…` | The private consumer or the private-data stream is down, so no trade report could arrive |

#### Example

```bash
curl -X POST https://gateway.example:3000/api/v1/trade_ingest_fault/ack \
  -H "Authorization: Bearer $VOLTNIR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"reason": "balancing; support desk paged"}'
```

```
HTTP/1.1 200 OK
{"ttl_sec": 1800, "expires_at_ms": 1791648000000, "renewed": false}
```

### <a id="put-contract-limit" name="put-contract-limit"></a>`PUT` `/api/v1/contract_limit`

Update the per-contract position limit. Takes effect immediately. Must be non-negative; `0` blocks all new position-taking (a kill-switch clients use as a safeguard) but does not disable the check.

**Required permission:** `set_position_limit`. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `limit` | i32 | sub-MW (MW × 1000) | Yes | New limit. Must be ≥ 0; `0` blocks all new position-taking. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `limit` | i32 | sub-MW (MW × 1000) | always | The limit as it now stands. |

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "limit must be non-negative"}` | `limit` < 0 |
| 403 | `{"error": "Forbidden"}` | Missing `set_position_limit` permission |

#### Example

```bash
curl -X PUT https://gateway.example:3000/api/v1/contract_limit \
  -H "Authorization: Bearer $VOLTNIR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"limit": 5000}'
# {"limit": 5000}
```

### <a id="put-cash-limit" name="put-cash-limit"></a>`PUT` `/api/v1/cash_limit`

Set or clear the operator cap on one cash pool. The House limit itself comes from the exchange and is not settable here; a cap only ever tightens it. EUR and GBP are independent pools; the `currency` field selects which.

**Required permission:** `set_cash_limit`. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `cap_cents` | i64 \| null | cents | No | New cap in cents of the target currency. Must be ≥ 0 and at or below the clearing-house limit. `null` (or omitted) removes the cap; `0` is a deliberate cap of zero. |
| `currency` | string | none | No | `"eur"` (default) or `"gbp"`. Unknown values return 400. |

#### Response

Both pools, in the same shape [GET /cash_limit](#get-cash-limit) returns.

> [!WARNING]
> A cap above the clearing-house limit is **rejected, never clamped**. A cap cannot be set before the exchange has reported a limit to tighten. A cap that would leave `house_cents` **below `allocated_cents`** is rejected too: lower the member allocations first. Clearing a cap (`null`) is always allowed.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "cap_cents must be non-negative"}` | `cap_cents` < 0 |
| 400 | `{"error": "no ECC EUR limit reported, …"}` | A cap was requested for a pool the exchange has published no limit for |
| 400 | `{"error": "cap of … cents exceeds the ECC EUR limit of … cents, …"}` | `cap_cents` is above the clearing-house limit for the pool |
| 400 | `{"error": "that cap would leave a EUR House limit of … cents, below the … cents already allocated to virtual members, …"}` | The cap would put `house_cents` below `allocated_cents`. Nothing is written |
| 400 | `{"error": "unknown currency '…' (expected eur or gbp)"}` | `currency` is not `eur`, `gbp`, or omitted |
| 403 | `{"error": "Forbidden"}` | Missing `set_cash_limit` permission |

#### Example

```bash
curl -X PUT https://gateway.example:3000/api/v1/cash_limit \
  -H "Authorization: Bearer $VOLTNIR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"cap_cents": 5000000, "currency": "eur"}'
```

### <a id="put-self-trade-policy" name="put-self-trade-policy"></a>`PUT` `/api/v1/self_trade_policy`

Set the self-trade prevention policy. Takes effect immediately and is persisted. There is a configured default applied only on a fresh database; this endpoint is the live control.

**Required permission:** `set_self_trade_policy`. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `policy` | string | none | Yes | `observe` or `reject`. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `policy` | string | none | always | The policy as it now stands. |

When `policy` is `reject`, an order that would cross one of your own resting orders is rejected at [POST /order](#post-order) and at [PUT /order](#put-order) (checked at the order's new price) with `422` and `{"error": "SELF_CROSS_BLOCKED: ..."}`.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "policy must be 'observe' or 'reject'"}` | Unknown `policy` value |
| 403 | `{"error": "Forbidden"}` | Missing `set_self_trade_policy` permission |

#### Example

```bash
curl -X PUT https://gateway.example:3000/api/v1/self_trade_policy \
  -H "Authorization: Bearer $VOLTNIR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"policy": "reject"}'
# {"policy": "reject"}
```

### <a id="put-holidays" name="put-holidays"></a>`PUT` `/api/v1/holidays`

Replace one currency's whole calendar with the supplied list. Takes effect on the next cash check and is persisted. Returns both calendars after the change.

**Required permission:** `set_cash_limit` (holidays are part of the cash-limit methodology). (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `currency` | string | none | Yes | `"eur"` or `"gbp"` (case-insensitive). |
| `holidays` | array | none | No | Full replacement list of `{"date": "YYYY-MM-DD", "label": "…"?}`. Order is irrelevant (stored sorted). Omit or pass `[]` to clear the currency's calendar. |

#### Response

Both calendars, in the same shape [GET /holidays](#get-holidays) returns.

A replace is not a deletion: a derived TARGET2 date it leaves out is restocked at the next hourly check, whereas a date removed with [DELETE /holidays](#delete-holidays) stays out.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "…"}` | Unknown currency, a malformed `YYYY-MM-DD` date, or a duplicate date in the list |
| 403 | `{"error": "Forbidden"}` | Missing `set_cash_limit` permission |

#### Example

```bash
curl -X PUT https://gateway.example:3000/api/v1/holidays \
  -H "Authorization: Bearer $VOLTNIR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"currency": "gbp", "holidays": [{"date": "2026-05-01", "label": "Labour Day"}, {"date": "2026-12-25"}]}'
```

### <a id="post-holidays" name="post-holidays"></a>`POST` `/api/v1/holidays`

Add a single date to a currency's calendar. Returns both calendars after the change.

**Required permission:** `set_cash_limit`. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `currency` | string | none | Yes | `"eur"` or `"gbp"`. |
| `date` | string | YYYY-MM-DD | Yes | The date to add. |
| `label` | string | none | No | Optional display label. |

#### Response

Both calendars, in the same shape [GET /holidays](#get-holidays) returns. Adding a previously deleted TARGET2 date lifts the deletion.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "…"}` | Unknown currency, malformed date, or the date is already configured |
| 403 | `{"error": "Forbidden"}` | Missing `set_cash_limit` permission |

#### Example

```bash
curl -X POST https://gateway.example:3000/api/v1/holidays \
  -H "Authorization: Bearer $VOLTNIR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"currency": "eur", "date": "2026-01-01", "label": "New Year'\''s Day"}'
```

### <a id="delete-holidays" name="delete-holidays"></a>`DELETE` `/api/v1/holidays`

Remove a single date from a currency's calendar. Returns both calendars after the change. Deleting one of the six derived TARGET2 dates keeps it out of the automatic fill for that currency until the date is added again.

**Required permission:** `set_cash_limit`. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `currency` | string | none | Yes | `"eur"` or `"gbp"`. |
| `date` | string | YYYY-MM-DD | Yes | The date to remove. |

#### Response

Both calendars, in the same shape [GET /holidays](#get-holidays) returns.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "…"}` | Unknown currency or malformed date |
| 403 | `{"error": "Forbidden"}` | Missing `set_cash_limit` permission |
| 404 | `{"error": "…"}` | The date is not configured for that currency |

#### Example

```bash
curl -X DELETE https://gateway.example:3000/api/v1/holidays \
  -H "Authorization: Bearer $VOLTNIR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"currency": "eur", "date": "2026-01-01"}'
```

### <a id="post-restart" name="post-restart"></a>`POST` `/api/v1/restart`

Restart the gateway process. The endpoint answers `202` first; the gateway then stops accepting requests and finishes the ones in flight on every transport, logs out of M7, commits every queued write (for up to 30 seconds; a write it cannot commit in that time is counted in `writes_dropped` (a trade in `trades_persist_failed`)), records the shutdown in the audit trail with the run's lost writes per stream, and exits, and the host supervisor starts a fresh process, which re-reads its configuration.

**Required permission:** `restart_system`. (see [Permissions](#permissions))

#### Request

None. No request body required.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `status` | string | none | always | `"restart initiated"`. Returned `202` before the process exits. |

> [!CAUTION]
> **This endpoint terminates the Voltnir process.** Ensure your deployment has a process supervisor configured to restart it; **without one the gateway stops and stays stopped.** The process exits with status **75** rather than 0, deliberately: the shipped systemd unit uses `Restart=on-failure`, which brings the unit back on a non-zero status and leaves it stopped on a clean one, so a restart request comes back while a `systemctl stop` (exit 0) stays stopped. See the deployment guide.

> [!NOTE]
> **What survives:** everything in the database, and the persisted profile (kill-switch state, per-contract limit, slot limit mode and House slot limit, self-trade policy and holiday calendars) all come back as they were. **What does not:** every open WebSocket connection, every outstanding export token, and any in-memory throttling and market-state snapshot (rebuilt from the exchange on the new process's first sync). The restart is recorded as a `system_restart` audit event naming the caller, then `system_shutdown` and `system_startup` from the new process.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 403 | `{"error": "Forbidden"}` | Missing `restart_system` permission |

#### Example

```bash
curl -X POST https://gateway.example:3000/api/v1/restart \
  -H "Authorization: Bearer $VOLTNIR_API_KEY"
# HTTP/1.1 202 Accepted
# {"status": "restart initiated"}
```

### <a id="post-restore-trade-history" name="post-restore-trade-history"></a>`POST` `/api/v1/restore-trade-history`

Repopulate the persistent trade store from the exchange over `[now − effective_days, now]`. The break-glass for the audit tape after the database has been wiped or migrated, or after trades have rolled off the cash-exposure window.

**Required permission:** `restore_trade_history`. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `days` | i64 | days | No | Window length. `effective_days = min(days, contractStoreTimeInDays)`, so an omitted body restores the exchange's whole reach and a larger value is clamped. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `chunk_count` | i64 | count | always | Number of paced trade-capture chunks the restore will fetch. |
| `effective_from_ms` | i64 | Unix ms (UTC) | always | The start of the restored window. |
| `effective_days` | i64 | days | always | The clamped window length actually used. |

The endpoint answers `200` with the plan the moment it is armed; the trades then arrive asynchronously, so watch the `trades_received` / `trades_persisted` counters on [GET /state](#get-state) for progress.

> [!NOTE]
> **Isolated from cash correctness.** A restore is a history/audit operation: its chunks are not registered with the cash-exposure coverage gate, so it never advances, clears or raises the `cash_exposure_window not covered` condition and cannot affect order admission. The restored window is the **complete** tape, cancelled and recalled trades included (carrying their exchange state); a granted recall (`RGRA`) or a cancellation (`CNCL`) adds no exposure, as on a live report (see [Trade states](#trade-states)). It restores **trades only**: the exchange serves no history for filled or cancelled orders, so order history is not recoverable once the database is wiped.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 403 | `{"error": "Forbidden"}` | Missing `restore_trade_history` permission |
| 503 | `{"error": "…"}` | The exchange has not yet reported `contractStoreTimeInDays`, so the reach is unknown; retry once the gateway has finished its exchange sync |

#### Example

```bash
curl -X POST https://gateway.example:3000/api/v1/restore-trade-history \
  -H "Authorization: Bearer $VOLTNIR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"days": 3}'
```

```
HTTP/1.1 200 OK
{"chunk_count": 18, "effective_from_ms": 1725600000000, "effective_days": 5}
```

<a id="slot-limit" name="slot-limit"></a>

## Slot position limit

The slot position limit caps the net MW a desk may hold in one quarter-hour of one delivery area, summing every contract that covers that quarter-hour.

An hour counts its full MW in each of its four quarter-hours, a half-hour in each of its two and a block in every quarter-hour it spans; MW is never divided by duration.

It works alongside the per-contract limit: an order must pass both, and the per-contract limit is unchanged by it.

A slot is one 15-minute delivery period, keyed by its UTC start, so the doubled hour of the October clock change is eight distinct slots.

For each slot the check reads the executed net position and the reachable bounds: `max_long` is the net plus every open buy, and `max_short` the net minus every open sell. An open buy on one contract never offsets an open sell on another. An order is refused only when, in some slot its contract covers, it pushes a bound past the limit and leaves it worse, so an order that reduces the position passes even on a desk that is over.

The House slot limit counts every order and trade on the desk. A member with its own `max_slot_position` is held to that limit as well, counting only its own orders and trades. A member with no slot limit (absent) is held to the House slot limit alone; a limit of `0` is flat-only, not off. Limits are sub-MW (MW × 1000).

Three modes: `off` (the default; the check is never run), `observe` (every order is admitted, and one that `reject` would refuse is written to the audit trail as `slot_limit_would_refuse`) and `reject` (such an order is refused before it reaches the exchange). The `slot_limit` section of `config.yml` seeds a fresh database only; after that the mode and the House slot limit are set at runtime and persisted, and each set writes a `slot_limit_set` audit row carrying the mode and the House limit before and after.

When a delivery window the check needs cannot be placed on the quarter-hour grid, the check fails closed: only cancels and amendments that add no quantity pass, and every other order is refused with `slot_window_unknown`. That is an order on a contract with no window; every order in the area while an open order's contract has none; and every order on a slot a trade with no window can deliver in, which is up to the end of the delivery day after the one the trade executed on (in GB, to 23:00 London two days after it), until then, or every slot of its area when its execution time is unknown too.

**Refusals.** Both are `422` on [POST /order](#post-order) and [PUT /order](#put-order), with `{"error": "slot position limit exceeded: ..."}` or `{"error": "slot window unknown: ..."}`. `slot_position_limit_exceeded` names the area, the slot start and end, the side (`long` or `short`), the scope (`house` or the member's short id), the position the order would reach and the limit. `slot_window_unknown` names what has no delivery window: the order's contract, an open order's contract, or a trade. A caller without `read_status`, which cannot see the House limit elsewhere, is not shown the House figures: a refusal by the House slot limit reads `slot position limit exceeded: refused by the desk slot limit, <area> <slot start> to <slot end>, <long|short> side`, and a trade that has no delivery time is not named. A refusal by the member's own slot limit keeps the member's figures. The `order_rejected` audit row carries every field either way.

### <a id="get-slot-limit" name="get-slot-limit"></a>`GET` `/api/v1/slot_limit`

The slot position limit's mode and the House slot limit. Mirrors gRPC `GetSlotLimit` and WS `get_slot_limit`.

**Required permission:** `read_status`, the gate of [GET /contract_limit](#get-contract-limit). (see [Permissions](#permissions))

#### Request

None. No parameters.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `mode` | string | none | always | `off`, `observe` or `reject`. |
| `house_limit` | i64 | sub-MW (MW × 1000) | always | The House slot limit per quarter-hour. `0` is flat-only. |

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 403 | `{"error": "Forbidden"}` | Missing `read_status` permission |

### <a id="put-slot-limit" name="put-slot-limit"></a>`PUT` `/api/v1/slot_limit`

Set the mode and the House slot limit together. Takes effect for the next order and is persisted; a mode other than `off` announces at once any area already locked by a trade with no delivery window. Mirrors gRPC `SetSlotLimit` and WS `set_slot_limit`.

**Required permission:** `set_position_limit`. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `mode` | string | none | Yes | `off`, `observe` or `reject`. |
| `house_limit` | i64 | sub-MW (MW × 1000) | Yes | The House slot limit per quarter-hour. Must be ≥ 0; `0` is flat-only, not off. |

#### Response

The setting as it now stands, in the shape [GET /slot_limit](#get-slot-limit) returns.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "mode must be 'off', 'observe' or 'reject'"}` | Unknown `mode`. Nothing changes |
| 400 | `{"error": "house_limit must be non-negative"}` | `house_limit` < 0. Nothing changes |
| 400 | `{"error": "house_limit is required"}` | `house_limit` missing or `null`. Nothing changes |
| 403 | `{"error": "Forbidden"}` | Missing `set_position_limit` permission |

#### Example

```bash
curl -X PUT https://gateway.example:3000/api/v1/slot_limit \
  -H "Authorization: Bearer $VOLTNIR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"mode": "observe", "house_limit": 20000}'
# {"mode": "observe", "house_limit": 20000}
```

### <a id="get-slot-positions" name="get-slot-positions"></a>`GET` `/api/v1/slot_positions`

Per-slot usage of the slot position limit. The usage read takes a delivery area, a range of at most 48 hours (`[from_ms, to_ms)` in UTC epoch milliseconds, `from_ms` rounded down to the quarter-hour, the 48 hours measured from there) and an optional member. It lists every slot in the range that holds exposure in a scope the caller sees, with, per scope, `net`, `max_long`, `max_short`, the `limit` that applies and the `buy_headroom` and `sell_headroom` left before that limit refuses an order, never below 0, all sub-MW. A caller sees the House scope only with `read_status`, and a member scope only for a member assigned to it and active. The read answers in every mode, `off` included, and reads the same sums the check reads. Mirrors gRPC `GetSlotPositions` and WS `get_slot_positions`; the live form is the WS `slot_positions` stream and gRPC `WatchSlotPositions`.

**Required permission:** none (authenticated caller); results are scoped to the members assigned to the caller and active. `read_status` widens the result to the House scope. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `delivery_area` | string | none | Yes | Query. The delivery area (EIC code). |
| `from_ms` | i64 | Unix ms UTC | Yes | Query. Start of the range, rounded down to the quarter-hour. |
| `to_ms` | i64 | Unix ms UTC | Yes | Query. End of the range, exclusive; after `from_ms` and at most 48 hours after it. |
| `v_member_short_id` | string | none | No | Query. Only that member's scope. `403` unless the member is assigned to the caller and active. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `delivery_area` / `from_ms` / `to_ms` | string / i64 | Unix ms UTC | always | The range as covered: `from_ms` rounded down and `to_ms` rounded up to the quarter-hour. |
| `mode` | string | none | always | The slot limit mode. |
| `house_limit` | i64 | sub-MW (MW × 1000) | `read_status` | The House slot limit; absent for a caller without `read_status`. |
| `locked` | bool | none | always | A trade or an open order in the area has no known delivery window and still locks at least one slot: its exposure may be missing from a sum here, and on a locked slot only cancels and amendments that add no quantity pass the check. An open order, or a trade whose execution time is unknown, locks every slot of the area; a trade with a known execution time locks the slots up to the end of the delivery day after the one it executed on (in GB, to 23:00 London two days after it), until then. |
| `slots[]` | array | none | always | Every slot that holds exposure in a scope the caller sees, in time order: `slot_start_ms`, `slot_end_ms` (Unix ms UTC) and `scopes[]`. |
| `scopes[].scope` | string | none | always | `house` or the member's short id. |
| `scopes[].net` / `max_long` / `max_short` | i64 | sub-MW (MW × 1000) | always | The executed net position, positive long and negative short, and the reachable bounds. |
| `scopes[].limit` | i64 | sub-MW (MW × 1000) | when a limit applies | The slot limit for this scope; absent for a member with none. |
| `scopes[].buy_headroom` / `sell_headroom` | i64 | sub-MW (MW × 1000) | when a limit applies | How much more may be bought or sold in this slot before this scope's limit refuses it, never below 0. An order on a member is held to its member scope and the House scope both. |

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "the range is at most 48 hours from from_ms rounded down to the quarter-hour"}` | The range is longer than 48 hours |
| 400 | `{"error": "to_ms must be after from_ms"}` | An empty or reversed range |
| 400 | `{"error": "delivery_area is required"}` | No area |
| 403 | `{"error": "Forbidden"}` | `v_member_short_id` names a member not assigned to the caller, or an inactive one |

#### Example

```bash
curl "https://gateway.example:3000/api/v1/slot_positions?delivery_area=10YDE-RWENET---I&from_ms=1791194400000&to_ms=1791201600000" \
  -H "Authorization: Bearer $VOLTNIR_API_KEY"
# {"delivery_area": "10YDE-RWENET---I", "from_ms": 1791194400000, "to_ms": 1791201600000,
#  "mode": "observe", "house_limit": 20000, "locked": false,
#  "slots": [{"slot_start_ms": 1791194400000, "slot_end_ms": 1791195300000,
#    "scopes": [{"scope": "house", "net": 15000, "max_long": 25000, "max_short": 15000,
#      "limit": 20000, "buy_headroom": 0, "sell_headroom": 35000}]}]}
```

<a id="users-members" name="users-members"></a>

## Users & members

Manage Voltnir API credentials (users) and virtual trading members. Users hold API keys and permission sets; members are virtual M7 sub-accounts used to tag orders for attribution.

> [!NOTE]
> **Users** are Voltnir API credentials: each has an API key, permissions, and optional member assignments. **Members** are virtual M7 trading members (short IDs like `VM001`) used to tag orders in the M7 Txt field. Members are global; they are assigned to users to control which members that user may trade under.

> [!CAUTION]
> **Desk license required for management routes.** The management surface (`/users` list/create/delete, `/users/{id}/permissions`, `/users/{user_id}/members`, `/members`, `/members/{id}`) requires a `desk`-tier license. Under a `trader` license these routes return `403` with `{"error": "LICENSE_DESK_REQUIRED"}` regardless of the caller's permissions. `GET /users/me`, `GET /users/me/members`, `GET /permissions`, and `POST /users/{id}/rotate-api-key` are *not* desk-gated (rotation is self-only on the trader tier).

### <a id="get-me" name="get-me"></a>`GET` `/api/v1/users/me`

Return the calling user's own profile.

**Required permission:** none (authenticated). (see [Permissions](#permissions))

#### Request

None. No parameters.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `id` | string | none | always | The user's UUID. |
| `username` | string | none | always | The user's username. |
| `short_id` | string | none | always | The user's short id (e.g. `U002`). |
| `permissions` | array | none | always | The user's current permission codes. |

#### Errors

None beyond the auth errors under [Connecting and authentication](#connecting).

#### Example

```bash
curl https://gateway.example:3000/api/v1/users/me \
  -H "Authorization: Bearer $VOLTNIR_API_KEY"
# {"id": "550e8400-e29b-41d4-a716-446655440000", "username": "trader1", "short_id": "U002", "permissions": ["create_order", "delete_order"]}
```

### <a id="get-me-members" name="get-me-members"></a>`GET` `/api/v1/users/me/members`

Return the virtual members assigned to the calling user. These are the only member short IDs the user may set on orders (unless it holds `bypass_member_check`).

**Required permission:** none (authenticated). (see [Permissions](#permissions))

#### Request

None. No parameters.

#### Response

A JSON array of member objects, each the same shape as [GET /members](#get-members) (including the live cash-usage fields). See that endpoint's response table for every field.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 503 | `{"error": "database not available"}` | Database not initialised |
| 500 | `{"error": "…"}` | Database query failed |

#### Example

```bash
curl https://gateway.example:3000/api/v1/users/me/members \
  -H "Authorization: Bearer $VOLTNIR_API_KEY"
```

### <a id="get-users" name="get-users"></a>`GET` `/api/v1/users`

List all users with their IDs, usernames, short IDs and permission sets.

**Required permission:** `manage_users` (desk-gated). (see [Permissions](#permissions))

#### Request

None. No parameters.

#### Response

A JSON array of user objects, each the same shape as [GET /users/me](#get-me) (`id`, `username`, `short_id`, `permissions`).

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 403 | `{"error": "Forbidden"}` | Missing `manage_users` permission |

#### Example

```bash
curl https://gateway.example:3000/api/v1/users \
  -H "Authorization: Bearer $VOLTNIR_API_KEY"
```

### <a id="post-users" name="post-users"></a>`POST` `/api/v1/users`

Create a new user. Returns the new user object including the raw API key. **The API key is shown only once**; store it securely immediately.

**Required permission:** `manage_users` (desk-gated). (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `username` | string | none | Yes | Must not be empty and must be unique. |
| `permissions` | array | none | No | Permission codes to grant on creation (validated before any database write). Omitted or empty = no permissions. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `id` | string | none | always | The new user's UUID. |
| `username` | string | none | always | The username. |
| `short_id` | string | none | always | The generated short id. |
| `permissions` | array | none | always | The granted permission codes. |
| `api_key` | string | none | always | The raw plaintext key, shown **only in this response**. It cannot be retrieved again, only rotated. |

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "username required"}` | Empty username |
| 400 | `{"error": "unknown permissions: …"}` | A `permissions` entry is not a known permission code (no user is created) |
| 403 | `{"error": "Forbidden"}` | Missing `manage_users` permission |
| 409 | `{"error": "username already exists"}` | Username already taken, by a current user or a deleted one: a username is never reissued |
| 503 | `{"error": "database not available"}` | Database not initialised |
| 500 | `{"error": "…"}` | Database error |

#### Example

```bash
curl -X POST https://gateway.example:3000/api/v1/users \
  -H "Authorization: Bearer $VOLTNIR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"username": "newtrader", "permissions": ["create_order", "delete_order"]}'
```

```
HTTP/1.1 201 Created
{"id": "550e8400-e29b-41d4-a716-446655440000", "username": "newtrader", "short_id": "U003", "permissions": ["create_order", "delete_order"], "api_key": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"}
```

### <a id="delete-user" name="delete-user"></a>`DELETE` `/api/v1/users/{id}`

Delete a user by UUID; every session of that user ends with it. You cannot delete yourself or the `admin` account. The user's key stops working, its permissions and member assignments are removed, and it leaves [GET /users](#get-users); every user write on its id (delete, set permissions, rotate key, member assignment) then answers `404 user not found`, and reading its member assignments returns an empty list, as for an unknown id. Its orders, trades and audit rows keep its attribution: its short id and username keep naming it, and neither is ever given to another user.

**Required permission:** `manage_users` (desk-gated). (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `id` | string | none | Yes | Path parameter. The user's UUID. |

#### Response

`204 No Content`, no body.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "cannot delete yourself"}` | Target ID matches the calling user's ID |
| 403 | `{"error": "Forbidden"}` | Missing `manage_users` permission |
| 403 | `{"error": "cannot delete the admin account"}` | Target username is `admin` |
| 404 | `{"error": "user not found"}` | ID not found, or the user is already deleted |
| 503 | `{"error": "database not available"}` | Database not initialised |
| 500 | `{"error": "…"}` | Database error |

#### Example

```bash
curl -X DELETE https://gateway.example:3000/api/v1/users/550e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer $VOLTNIR_API_KEY"
```

### <a id="put-user-permissions" name="put-user-permissions"></a>`PUT` `/api/v1/users/{id}/permissions`

Replace a user's full permission set. Pass an empty array to revoke all permissions. Unrecognised permission codes are rejected. The built-in `admin` account's permissions are immutable.

**Required permission:** `manage_users` (desk-gated). The assignable codes and what each grants are in the [Permissions](#permissions) chapter.

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `id` | string | none | Yes | Path parameter. The target user's UUID. |
| `permissions` | array | none | Yes | The full replacement set of permission codes; empty revokes all. Each must be an assignable code from the [Permissions](#permissions) chapter. |

#### Response

`204 No Content`, no body.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "unknown permissions: [\"bad_perm\"]"}` | Any unrecognised permission code in the array |
| 403 | `{"error": "Forbidden"}` | Missing `manage_users` permission |
| 403 | `{"error": "the admin account's permissions are immutable"}` | Target is the built-in `admin` account |
| 404 | `{"error": "user not found"}` | User ID not found |
| 503 | `{"error": "database not available"}` | Database not initialised |
| 500 | `{"error": "…"}` | Database error |

#### Example

```bash
curl -X PUT https://gateway.example:3000/api/v1/users/42/permissions \
  -H "Authorization: Bearer $VOLTNIR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"permissions": ["create_order", "delete_order", "read_audit"]}'
```

### <a id="post-rotate-key" name="post-rotate-key"></a>`POST` `/api/v1/users/{id}/rotate-api-key`

Generate a new API key for a user; the old key and every session of that user are invalidated immediately. Not desk-gated, so a `trader`-tier license can rotate its own key. On the trader tier it is **self-only**: `{id}` must be the caller's own, and any other target returns `404`. With a desk-tier license a `manage_users` holder may rotate any user.

**Required permission:** `manage_users` (not desk-gated). (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `id` | string | none | Yes | Path parameter. The target user's UUID (own id on the trader tier). No request body. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `api_key` | string | none | always | The new raw key, shown **only in this response**. The old key and every session of the user are invalidated immediately and cannot be recovered. |

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 403 | `{"error": "Forbidden"}` | Missing `manage_users` permission |
| 404 | `{"error": "user not found"}` | User ID not found, or (trader tier) a target that is not the caller |
| 503 | `{"error": "database not available"}` | Database not initialised |
| 500 | `{"error": "…"}` | Database error |

#### Example

```bash
curl -X POST https://gateway.example:3000/api/v1/users/42/rotate-api-key \
  -H "Authorization: Bearer $VOLTNIR_API_KEY"
# {"api_key": "2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae"}
```

### <a id="get-user-members" name="get-user-members"></a>`GET` `/api/v1/users/{user_id}/members`

Return the member UUIDs assigned to a specific user, as an array of UUID strings (not full member objects).

**Required permission:** `manage_users` (desk-gated). (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `user_id` | string | none | Yes | Path parameter. The user's UUID. |

#### Response

A JSON array of member UUID strings.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 403 | `{"error": "Forbidden"}` | Missing `manage_users` permission |
| 503 | `{"error": "database not available"}` | Database not initialised |
| 500 | `{"error": "…"}` | Database error |

#### Example

```bash
curl https://gateway.example:3000/api/v1/users/42/members \
  -H "Authorization: Bearer $VOLTNIR_API_KEY"
# ["a1b2c3d4-e5f6-7890-abcd-ef1234567890"]
```

### <a id="put-user-members" name="put-user-members"></a>`PUT` `/api/v1/users/{user_id}/members`

Replace the full set of member assignments for a user. Pass an empty array to remove all assignments. Every listed member must exist and not be deleted; otherwise nothing is written.

**Required permission:** `manage_users` (desk-gated). (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `user_id` | string | none | Yes | Path parameter. The user's UUID. |
| `member_ids` | array | none | Yes | The full replacement set of member UUIDs; empty removes all assignments. |

#### Response

`204 No Content`, no body.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 403 | `{"error": "Forbidden"}` | Missing `manage_users` permission |
| 404 | `{"error": "user not found"}` | User ID not found, or the user is deleted. Checked before the members |
| 404 | `{"error": "member not found"}` | A listed member ID is not found, or the member is deleted. Nothing is written |
| 503 | `{"error": "database not available"}` | Database not initialised |
| 500 | `{"error": "…"}` | Database error |

#### Example

```bash
curl -X PUT https://gateway.example:3000/api/v1/users/42/members \
  -H "Authorization: Bearer $VOLTNIR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"member_ids": ["a1b2c3d4-e5f6-7890-abcd-ef1234567890"]}'
```

### <a id="get-members" name="get-members"></a>`GET` `/api/v1/members`

List all virtual members with their configured limits and live cash usage per currency pool.

**Required permission:** `manage_members` (desk-gated). (see [Permissions](#permissions))

#### Request

None. No parameters.

#### Response

A JSON array of member objects. Each object (also returned by [GET /users/me/members](#get-me-members), [POST /members](#post-members), and mirrored on gRPC and WS):

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `id` | string | none | always | The member's UUID. |
| `short_id` | string | none | always | The generated short id (e.g. `VM001`). |
| `name` | string | none | always | Display name. |
| `max_position` | i64 | sub-MW (MW × 1000) | always | The member's per-contract limit; `0` blocks all position-taking. |
| `max_slot_position` | i64 \| null | sub-MW (MW × 1000) | always | The member's own [slot position limit](#slot-limit). `null` = no member slot limit (the House slot limit still applies); `0` = flat-only. |
| `delivery_areas` | object | none | always | The delivery areas the member may trade in: `{"all": bool, "area_ids": [EIC]}`. `all: true` is every area, including one the gateway is configured for later; otherwise only `area_ids`, and an empty list permits none. A member order in any other area is refused `422` `MEMBER_AREA_NOT_ALLOWED` on every action: new, modify, activate, deactivate and cancel. Market data is not restricted. |
| `cash_limit` | i64 | EUR cents | always | The member's EUR allocation out of the desk's cash limit. |
| `cash_limit_gbp` | i64 | GBP cents | always | The member's GBP allocation in the independent GBP pool. |
| `active` | bool | none | always | Whether the member is enabled. |
| `{eur,gbp}_limit_cents` | i64 | pool cents | always | The enforced allocation, the same number as `cash_limit`/`cash_limit_gbp` (no inheritance from the desk); `0` means no allocation. |
| `{eur,gbp}_consumed_cents` | i64 | pool cents | always | The member's open-order plus executed-trade exposure. |
| `{eur,gbp}_remaining_cents` | i64 | pool cents | always | `limit − consumed`, negative when over. |

> [!WARNING]
> Per currency, the allocations of **all** members sum to at most the desk's `house_cents`, inactive members included, since the exchange does not release an idle member's share. That is what makes one member unable to spend another's allocation. Orders with no member tag draw on the remainder (`unallocated_cents` on [GET /cash_limit](#get-cash-limit)) and nothing more.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 403 | `{"error": "Forbidden"}` | Missing `manage_members` permission |
| 503 | `{"error": "database not available"}` | Database not initialised |
| 500 | `{"error": "…"}` | Database error |

#### Example

```bash
curl https://gateway.example:3000/api/v1/members \
  -H "Authorization: Bearer $VOLTNIR_API_KEY"
```

```
HTTP/1.1 200 OK
[
  {"id": "uuid", "short_id": "VM001", "name": "Desk A", "max_position": 5000, "cash_limit": 10000000, "cash_limit_gbp": 0, "active": true, "eur_consumed_cents": 4200000, "eur_limit_cents": 10000000, "eur_remaining_cents": 5800000, "gbp_consumed_cents": 0, "gbp_limit_cents": 0, "gbp_remaining_cents": 0, "delivery_areas": {"all": false, "area_ids": ["10YNL----------L"]}}
]
```

### <a id="post-members" name="post-members"></a>`POST` `/api/v1/members`

Create a new virtual member. The `short_id` is auto-generated (VM001, VM002, and so on); you cannot specify it.

**Delivery areas.** A member trades only in the delivery areas it is given. A member created without `delivery_areas` has none and every order under it is refused `422` `MEMBER_AREA_NOT_ALLOWED`, so give it areas here or later with [PATCH /members/{id}](#patch-member): `{"all": true}` for every area, or `{"area_ids": [EIC, …]}` for a list taken from the gateway’s configured `epex_settings.delivery_areas` (an unconfigured id is a `400` that names the configured ones). Read the current areas from [GET /members](#get-members), or [GET /users/me/members](#get-me-members) for a trader’s own members. The rule covers every order action of the member, new, modify, activate, deactivate and cancel, whoever places it; House orders and market data are not restricted.

**Required permission:** `manage_members` (desk-gated). (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `name` | string | none | Yes | Display name. Must not be empty. |
| `max_position` | i64 | sub-MW (MW × 1000) | No | Per-contract limit. Default `0`, which blocks all position-taking for the member. |
| `max_slot_position` | i64 \| null | sub-MW (MW × 1000) | No | The member's own [slot position limit](#slot-limit). Omitted or `null` = no member slot limit; `0` = flat-only. Negative is `400` `{"error": "max_slot_position must be non-negative"}`. |
| `delivery_areas` | object | none | No | `{"all": bool, "area_ids": [EIC]}`, both fields optional. Omitted = no areas: the member can place no order until it is given some. Each id must be one of the gateway’s configured `epex_settings.delivery_areas`; duplicates collapse and the list is stored in the configuration’s order. |
| `cash_limit` | i64 | EUR cents | No | The member's EUR allocation. Default `0` = no allocation. `400` when it would push the pool's allocations past the desk's House limit, or when the exchange has reported no EUR limit. |
| `cash_limit_gbp` | i64 | GBP cents | No | The member's GBP allocation in the independent pool. Same rules; default `0` = no allocation. |

#### Response

The created member object, the same shape as a [GET /members](#get-members) element. A fresh member has no orders or trades, so `*_consumed_cents` is `0` and `*_remaining_cents` equals its allocation.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "name required"}` | Empty name |
| 400 | `{"error": "delivery area … is not one this gateway trades; configured areas: …"}` | An `area_ids` entry the gateway is not configured to trade. Nothing is written |
| 400 | `{"error": "delivery_areas: all: true cannot be combined with area_ids"}` | `all: true` together with a non-empty `area_ids` |
| 400 | `{"error": "EUR allocation of … exceeds the … available to this member …"}` | The allocation would push that pool's member allocations past the desk's House limit. Nothing is written |
| 400 | `{"error": "no ECC EUR limit reported …"}` | A non-zero allocation in a pool the exchange has reported no limit for (an allocation of `0` is always accepted) |
| 403 | `{"error": "Forbidden"}` | Missing `manage_members` permission |
| 503 | `{"error": "database not available"}` | Database not initialised |
| 500 | `{"error": "…"}` | Database error |

#### Example

```bash
curl -X POST https://gateway.example:3000/api/v1/members \
  -H "Authorization: Bearer $VOLTNIR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "Desk B", "max_position": 10000, "delivery_areas": {"area_ids": ["10YNL----------L", "10YBE----------2"]}}'
```

### <a id="patch-member" name="patch-member"></a>`PATCH` `/api/v1/members/{id}`

Partially update a member's name, position limit, allocations, active status or delivery areas. At least one field must be provided.

**Required permission:** `manage_members` (desk-gated). (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `id` | string | none | Yes | Path parameter. The member's UUID. |
| `name` | string | none | No | New display name. At least one body field is required. |
| `max_position` | i64 | sub-MW (MW × 1000) | No | New per-contract limit; `0` blocks all position-taking. |
| `max_slot_position` | i64 \| null | sub-MW (MW × 1000) | No | The member's [slot position limit](#slot-limit): omit it to leave it, `null` to remove it (no member slot limit), a number to set it (`0` = flat-only). Negative is `400` and changes nothing. |
| `cash_limit` | i64 | EUR cents | No | New EUR allocation. `0` takes the allocation away (always succeeds). Raising it is `400` when the pool's allocations would then exceed the desk's House limit; the member's own current allocation is not counted against the value replacing it. |
| `cash_limit_gbp` | i64 | GBP cents | No | New GBP allocation in the independent pool. Same rules. |
| `active` | bool | none | No | Enable or disable the member. |
| `delivery_areas` | object | none | No | Replaces the member’s delivery areas whole, same shape and rules as on create; omit it to leave them. There is no separate clear: `{"all": true}` is every area, `{"area_ids": []}` none. |

#### Response

`204 No Content`, no body.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "nothing to update"}` | All fields null, nothing to change |
| 400 | `{"error": "delivery area … is not one this gateway trades; configured areas: …"}` | An `area_ids` entry the gateway is not configured to trade. Nothing is written |
| 400 | `{"error": "delivery_areas: all: true cannot be combined with area_ids"}` | `all: true` together with a non-empty `area_ids` |
| 400 | `{"error": "member … has N open orders in …; cancel them before removing the area"}` | The new `delivery_areas` would leave one or more of the member’s resting or pending orders outside it. Nothing is written; cancel those orders first. Widening is never refused |
| 400 | `{"error": "EUR allocation of … exceeds the … available to this member …"}` | The new allocation would push that pool's member allocations past the desk's House limit. Nothing is written |
| 400 | `{"error": "no ECC EUR limit reported …"}` | A non-zero allocation in a pool the exchange has reported no limit for |
| 403 | `{"error": "Forbidden"}` | Missing `manage_members` permission |
| 404 | `{"error": "member not found"}` | Member ID not found, or the member is deleted |
| 503 | `{"error": "database not available"}` | Database not initialised |
| 500 | `{"error": "…"}` | Database error |

#### Example

```bash
curl -X PATCH https://gateway.example:3000/api/v1/members/42 \
  -H "Authorization: Bearer $VOLTNIR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "Desk B Updated", "max_position": 20000, "active": false}'
```

Give the member every delivery area, or replace its areas with a list. The object replaces the areas whole; a `PATCH` without `delivery_areas` leaves them as they are.

```bash
curl -X PATCH https://gateway.example:3000/api/v1/members/42 \
  -H "Authorization: Bearer $VOLTNIR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"delivery_areas": {"all": true}}'
```

```bash
curl -X PATCH https://gateway.example:3000/api/v1/members/42 \
  -H "Authorization: Bearer $VOLTNIR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"delivery_areas": {"area_ids": ["10YNL----------L"]}}'
```

Removing an area while the member has open orders in it is refused; cancel those orders first:

```
HTTP/1.1 400 Bad Request
{"error": "member VM002 has 1 open order in 10YBE----------2; cancel them before removing the area"}
```

### <a id="delete-member" name="delete-member"></a>`DELETE` `/api/v1/members/{id}`

Delete a member by UUID. Refused while the member has a resting or unconfirmed pending order, a non-zero executed position on a contract whose delivery has not ended, or consumed cash still counted in the current exposure window (trades executed since the last booking cut): cancel the orders, flatten the positions, and wait for the cut. A deleted member takes no order (one naming it is refused `400 v-member '…' not found`), is unassigned from every user, and leaves [GET /members](#get-members) and every user's members; a [PATCH](#patch-member), a member assignment naming it, or a second delete answers `404 member not found`, as for an unknown id. Its orders and trades stay in history and keep its name, and its short id is never given to another member. Audited as `member_deleted`, with the member's short id and name before and the number of users unassigned after.

**Required permission:** `manage_members` (desk-gated). (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `id` | string | none | Yes | Path parameter. The member's UUID. |

#### Response

`204 No Content`, no body.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "member … has N open orders; cancel them before deleting the member"}` | The member has resting or unconfirmed pending orders (one order reads `has 1 open order; cancel it`). Checked first. Nothing changes |
| 400 | `{"error": "member … holds a position on N contracts whose delivery has not ended: … in …; flatten them before deleting the member"}` | The member's executed trades net to a non-zero position on one or more contracts still to be delivered; each is named, by its catalogue name or as `contract <id>`, with its delivery area. A position that nets to zero, or one on a contract whose delivery has ended, does not count. Nothing changes |
| 400 | `{"error": "member … has consumed cash counted until the next booking cut (EUR N cents, GBP N cents); delete it after the cut"}` | Orders and positions are clear, but trades the member executed since the last booking cut (16:00 on an ECC business day) still count as consumed cash in the EUR or GBP pool, the figure the member cash check reads, in cents; only a non-zero pool is named. Its allocation would be released with the delete while that cash still counts against the desk's limit. Any non-zero figure, a credit included, holds the delete until the cut; a credit is named `EUR credit N cents`, never with a minus sign, and each figure is rounded up to whole cents. Checked last. Nothing changes |
| 400 | `{"error": "consumed cash cannot be fully priced yet; retry the delete"}` | The gateway's carried cash sums are not fully priced at that moment (a desk-wide state, not this member's), so the member's figure would be short. Nothing changes; retry |
| 403 | `{"error": "Forbidden"}` | Missing `manage_members` permission |
| 404 | `{"error": "member not found"}` | Member ID not found, or the member is already deleted |
| 503 | `{"error": "database not available"}` | Database not initialised |
| 500 | `{"error": "…"}` | Database error |

#### Example

```bash
curl -X DELETE https://gateway.example:3000/api/v1/members/42 \
  -H "Authorization: Bearer $VOLTNIR_API_KEY"
```

A member still holding a position is refused until it is flat:

```
HTTP/1.1 400 Bad Request
{"error": "member VM002 holds a position on 1 contract whose delivery has not ended: contract 41870513 in 10YBE----------2; flatten it before deleting the member"}
```

### <a id="get-permissions" name="get-permissions"></a>`GET` `/api/v1/permissions`

Return the catalog of assignable permissions: every permission `code` that can be granted (via [PUT /users/{id}/permissions](#put-user-permissions)) paired with a human-readable `description`. Render this list rather than hardcoding your own, so a new permission appears automatically.

**Required permission:** `manage_users` (not desk-gated). (see [Permissions](#permissions))

#### Request

None. No parameters.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `permissions` | array | none | always | Always an array (never null), ordered canonically. Each element is `{code, description}`. |
| `permissions[].code` | string | none | always | The assignable permission code. |
| `permissions[].description` | string | none | always | A human-readable description of what the code grants. |

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 403 | `{"error": "Forbidden"}` | Missing `manage_users` permission |

#### Example

```bash
curl https://gateway.example:3000/api/v1/permissions \
  -H "Authorization: Bearer $VOLTNIR_API_KEY"
```

```
HTTP/1.1 200 OK
{"permissions": [
  {"code": "create_order", "description": "Submit new orders to the exchange."},
  {"code": "modify_order", "description": "Change the price or quantity of an existing open order."}
]}
```

<a id="sessions" name="sessions"></a>

## Sessions

A session is a second bearer credential for a user, minted from that user's API key, so a browser can stay signed in without keeping the key. The trading terminal is the one client that needs it. Both operations are **REST-only**; the token they mint is accepted on every transport wherever an API key is (see [Connecting and authentication](#connecting)).

> [!NOTE]
> **Lifetime.** A session created with `persistent: true` ("stay signed in") never expires on its own. One created with `persistent: false` is refused from twelve hours after creation. Either way it ends on [DELETE /sessions/current](#delete-sessions-current), on a rotation of its user's API key and on deletion of its user. An ended or expired session is refused with the same `401` as a wrong key, and a WebSocket connection or gRPC status stream open on it closes.

> [!NOTE]
> **Audited.** Creating a session writes a `session_created` event and ending one writes `session_revoked`, with `target_type: "session"` and the session id as `target_id`, never the token. The sessions a key rotation or a user deletion ends are counted on that `api_key_rotated` or `user_deleted` event as `after.sessions_ended`.

### <a id="post-sessions" name="post-sessions"></a>`POST` `/api/v1/sessions`

Mint a session for the calling user. Must be authenticated with an **API key**: a session cannot mint another session. The token is shown only in this response and is stored as a SHA-256 hash.

**Required permission:** none (authenticated with an API key). **REST-only**: it has no gRPC or WebSocket peer. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `persistent` | boolean | none | Yes | `true`: the session never expires on its own. `false`: it is refused from twelve hours after creation. |

#### Response

`201 Created` with:

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `token` | string | none | always | The session token, prefixed `vs_`, shown **only in this response**. Present it as the bearer from then on. |
| `session_id` | string | none | always | The session's id, the `target_id` of its audit events. |
| `persistent` | boolean | none | always | The lifetime requested. |
| `expires_at` | integer \| null | Unix epoch milliseconds | always | The instant from which the session is refused; `null` when `persistent` is `true`. |

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "body must be {\"persistent\": true} or {\"persistent\": false}"}` | The body is missing, not JSON, or `persistent` is not a boolean |
| 401 | `{"error": "Unauthorized"}` | The key was rotated, or its user deleted, while this request was in flight. The same answer a wrong key gets; no session is created. |
| 403 | `{"error": "a session token cannot create a session; authenticate with an API key"}` | The request was authenticated with a session token. Audited as `permission_denied` with `reason: "session_cannot_mint"`. |
| 503 | `{"error": "database not available"}` | Database not initialised |
| 500 | `{"error": "session create failed"}` | Database error |

#### Example

```bash
curl -X POST https://gateway.example:3000/api/v1/sessions \
  -H "Authorization: Bearer $VOLTNIR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"persistent": false}'
```

```
HTTP/1.1 201 Created
{
  "token": "vs_…",
  "session_id": "3f0c…",
  "persistent": false,
  "expires_at": 1790000000000
}
```

### <a id="delete-sessions-current" name="delete-sessions-current"></a>`DELETE` `/api/v1/sessions/current`

End the session this request is authenticated with (sign out). The token is refused from then on, and a WebSocket connection open on it closes. Other sessions of the same user, and the user's API key, are untouched.

**Required permission:** none (authenticated with a session token). **REST-only**: it has no gRPC or WebSocket peer. (see [Permissions](#permissions))

#### Request

None. No parameters, no body.

#### Response

`204 No Content`, no body.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "no current session: this request authenticated with an API key"}` | The request was authenticated with an API key, so there is no current session to end |
| 500 | `{"error": "session revoke failed"}` | Database error |

#### Example

```bash
curl -X DELETE https://gateway.example:3000/api/v1/sessions/current \
  -H "Authorization: Bearer $VOLTNIR_SESSION_TOKEN"
```

<a id="audit" name="audit"></a>

## Audit & reports

Query and export historical order and trade data, the compliance audit trail, the exchange-error and exchange-message logs, and the gateway's own diagnostic log. Order and trade history need no permission (member-scoped like the live reads); public-trade history and compliance events require `read_audit`; the two logs require their own permissions; exports require `export_reports`.

> [!NOTE]
> Audit data is cursor-paged. Use the `next_cursor` from each response to fetch the next page, and iterate until it is `null`. History responses carry no total count.

### <a id="get-audit-orders" name="get-audit-orders"></a>`GET` `/api/v1/audit/orders`

Query paginated order audit history, with optional filters for time range, area, product, status, user and virtual member.

**Required permission:** none (member-scoped). `read_orders` or `bypass_member_check` returns the firm-wide history. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `cursor` | string | none | No | Opaque pagination token from the previous `next_cursor`. Omit for the first page. |
| `limit` | u32 | count | No | Page size. Default 50, max 200. An explicit `limit=0` is rejected with 400. |
| `date_from` / `date_to` | string | RFC 3339 | No | Inclusive lower / upper time bound. |
| `area` | string | none | No | Filter by delivery area EIC code. |
| `product` | string | none | No | Filter by product code. |
| `status` | string | none | No | The order state M7 reported: `ACTIVE` (`ACTI`), `INACTIVE` (`INAC`, a deleted or fully filled order) or `HIBERNATED` (`HIB`), in any case. Absent or empty is no filter; any other value is refused with `400`, naming the accepted values. `REJECTED` is not an M7 order state: a plain order the exchange refuses has no row in this history, and its refusal is on the audit trail as `order_rejected`. A refused pre-arranged order, or a remote order that failed validation, keeps its rows, with the state M7 reported and the refusal as the row’s `action` (`UREJ`, `AREJ`, `SREJ` or `SERR`). |
| `user_code` | string | none | No | Filter by the EPEX trader/user code (e.g. `"TRADER1"`). |
| `v_member_short_id` | string | none | No | Narrow to a single virtual member, within the caller's scope. `403` for a member the caller may not see. |
| `voltnir_user_short_id` | string | none | No | Filter by the submitting Voltnir user's short id. |
| `voltnir_username` | string | none | No | Filter by the submitting Voltnir user's username snapshot. |
| `sort_order` | string | none | No | Page direction: `DESC` (default, newest first) or `ASC`. Any other value is 400. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `items` | array | none | always | The order audit rows for this page. |
| `next_cursor` | string \| null | none | always | Feed back as `cursor` for the next page; `null` on the last page. No total count. |

**Member scope.** A caller holding `read_orders` (or `bypass_member_check`) reads the firm-wide history; everyone else reads only rows tagged with a virtual member assigned to them, untagged house rows withheld. Always paginate large audit logs.

**Who wrote a row: `source`.** The order history records what the gateway observed. Every row carries `source`: `exchange` for a row parsed from an execution report the exchange sent, `gateway` for a row the gateway wrote because M7 no longer held the order when the gateway reconnected, so the outcome was not observed. After a gap in the connection the exchange sends the orders it still holds, in parts (one per balancing group, and more for OTC orders), not the reports missed during the gap, so once every part has arrived the gateway closes its own record of an order none of them lists instead of leaving it open: one row above the last `revision` the gateway knew, `order_state` inactive, `timestamp` the time it noticed, and the `action` and `quantity` last known to the gateway. Read `source` before `action`. Fills are in [GET /audit/trades](#get-audit-trades), which has no order-id filter: query it with `time_basis=execution` over the time the order was open and take the trades whose `buy_json` or `sell_json` leg carries the order's id as `@ordrId`. Every login re-reads the fills of the current cash-exposure window from the exchange; an older fill is there only after [POST /restore-trade-history](#post-restore-trade-history) (permission `restore_trade_history`). An exchange report that later arrives for the same `revision` replaces the gateway's row. Only orders whose entry the gateway recorded under its own exchange user are closed this way, so not covered: an order another user entered, even when its reports are in the history or the gateway changed it (the gateway sees such an order only while that user stays on the balancing group, so one it stops seeing may still be live); an order whose entry the gateway did not record, including one it never saw; a pre-arranged (OTC) order; an order with a modify, cancel or activation in progress when the gateway reconnected, normally until the next restart; and, after a restart, an order whose last report reached the gateway more than 3 days before it reconnected. For any period the gateway was not running, the exchange's own records are authoritative.

<a id="order-history-names" name="order-history-names"></a>**Coded columns are names.** Nine columns hold a value the exchange sends as a code. In every row of this history and of an orders export each one is a name wherever the code has one: where the live `orders` stream carries the field (`side`, `order_type`, `order_state`, `action`) it is the same word the stream uses, so an order reads the same in the stream, the history and the export, except for `0`, which the history writes as `"0"` and the stream reads as `UNKNOWN`. A code with no name is written as its number in text. In practice that is `"0"`: `0` is the exchange's unset value, and a value the exchange sends that this gateway does not know is stored as `0` too, so the row cannot say which value it was. A column the exchange left out is `null` (an empty cell in a CSV export). The `status` filter takes the `order_state` names. A trade row holds no codes: its `state` and `contract_phase` are the exchange's own text (`ACTI`, `CONT`), as on the live `trades` stream.

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

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "invalid date '…': …"}` | `date_from` or `date_to` is not valid RFC 3339 |
| 400 | `{"error": "invalid sort_order '…': expected 'ASC' or 'DESC'"}` | `sort_order` is neither `ASC` nor `DESC` |
| 403 | `{"error": "Forbidden"}` | `v_member_short_id` names a member the caller may not see |
| 503 | `{"error": "database not available"}` | Database not initialised |
| 500 | `{"error": "…"}` | Database query failed |

#### Example

```bash
curl "https://gateway.example:3000/api/v1/audit/orders?limit=50" \
  -H "Authorization: Bearer $VOLTNIR_API_KEY"
# {"items": [ ... ], "next_cursor": "1717000000000.1547"}
```

### <a id="get-audit-trades" name="get-audit-trades"></a>`GET` `/api/v1/audit/trades`

Query paginated trade audit history. Same pagination as [GET /audit/orders](#get-audit-orders); the `status` filter is not available, and the date window filters on either the delivery or the execution axis via `time_basis`.

**Required permission:** none (member-scoped). `read_orders` or `bypass_member_check` returns the firm-wide history. (see [Permissions](#permissions))

**A trade between two of your own members.** When two virtual members of the desk trade with each other, a member-scoped caller finds the trade under either member and receives it as the row of an ordinary fill of that member's own leg: the other leg (`buy_json` or `sell_json`) `null`; `v_member_short_id`, `voltnir_user_id`, `voltnir_user_short_id`, `voltnir_username` and `delivery_area` those of the kept leg, exactly as on a fill of that leg against an outside counterparty; and `self_trade` `false`. `self_trade` is `false` for a member-scoped caller whenever it cannot see both legs, including on a trade only one half of which has arrived. Under a member scope the `delivery_area` and `voltnir_user_short_id` filters match only on a leg the caller may see, and `voltnir_username` names a current Voltnir user and matches the same way; an unknown name matches nothing. A caller holding `read_orders` (or `bypass_member_check`) receives the whole trade, whose member, Voltnir user and `delivery_area` are those of its buy leg when that leg belongs to a member, else of its sell leg, whichever half arrived last, and its filters match those. A member filter narrows even such a caller to that member's view, so the trade then reads as that member's own fill. The public trade tape is market data and is not narrowed: it carries the exchange's own self-trade flag and both legs' delivery areas under the same trade id. The desk is told of each such trade once, on the audit trail (`member_self_cross`).

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `cursor` | string | none | No | Opaque pagination token from the previous `next_cursor`. |
| `limit` | u32 | count | No | Default 50, max 200. An explicit `limit=0` is rejected with 400. |
| `date_from` / `date_to` | string | RFC 3339 | No | Inclusive bounds, applied to the axis selected by `time_basis`. |
| `time_basis` | string | none | No | `delivery` (default; the contract delivery window, overlap semantics) or `execution` (execution time). Any other value is 400. |
| `area` | string | none | No | Filter by delivery area EIC code. |
| `product` | string | none | No | Filter by product code. |
| `contract_id` | string | none | No | Filter to one contract by its M7 contract id, as the string the trade rows carry. An id no trade carries returns an empty page, not an error. An empty `contract_id=` is no filter. The other audit endpoints ignore it. |
| `user_code` | string | none | No | Filter by the EPEX trader/user code. |
| `v_member_short_id` | string | none | No | Narrow to a single virtual member within the caller's scope. `403` for a member the caller may not see. |
| `voltnir_user_short_id` / `voltnir_username` | string | none | No | Filter by the submitting Voltnir user's short id or username snapshot. Under a member scope, only a leg the caller may see matches, and the username names a current user (see the note above). |
| `sort_order` | string | none | No | Page direction; `DESC` default, newest first. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `items` | array | none | always | Trade rows (fields below). |
| `next_cursor` | string \| null | none | always | Feed back as `cursor`; `null` on the last page. |

#### Trade row (`items[]`)

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `trade_id` | string | none | always | M7 trade id. |
| `contract_id` | string | none | always | M7 contract id. |
| `qty` | u32 | sub-MW (MW × 1000) | always | Traded quantity. |
| `px` | i64 | cents (CCY/MWh × 100) | always | Traded price. |
| `state` | string | none | always | Trade state; see [Trade states](#trade-states). |
| `exec_time` / `executed_at` | string | RFC 3339 | always | When the trade matched. |
| `delivery_start` / `delivery_end` | string \| null | RFC 3339 | optional | The contract's delivery window, captured at trade time; `null` only for trades recorded before delivery capture was added. |
| `delivery_area` | string | none | always | Delivery area EIC code. |
| `product` | string | none | always | Product code. |
| `v_member_short_id` | string \| null | none | optional | Virtual-member tag; `null` for the house account. |
| `voltnir_user_id` / `voltnir_user_short_id` / `voltnir_username` | string \| null | none | optional | The submitting Voltnir user; `null` for a non-Voltnir trade. |
| `attribution` | string | none | always | `"full"` when the report parsed completely, or `"partial"` when only the financial core could be read (financially final: report it, no action). |
| The seven recall fields below, each `null` when not applicable. |  |  |  |  |

#### <a id="recall-fields" name="recall-fields"></a>Recall fields

Every trade row here and every trade in a contract's `trades` carries these fields as the exchange sent them. Each is `null` until it applies. A later revision of the trade that omits one keeps the value already reported. Times are in the format the exchange sends, as `exec_time` is.

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `recall_req_time` | string \| null | date-time | optional | When a recall of the trade was requested. |
| `recall_granted_time` | string \| null | date-time | optional | When market operations granted the recall. The exchange also sets it when market operations cancel the trade. |
| `recall_rejected_time` | string \| null | date-time | optional | When market operations rejected the recall. |
| `latest_recall_process_time` | string \| null | date-time | optional | Until when market operations can process a recall request. It is a live deadline while a recall is pending (`state` `RREQ` or `RSFA`). |
| `recall_requestor` | string \| null | none | optional | Member id of the party that asked for the recall. The exchange sends it to the balancing group of the requesting party when that party is a member known to the exchange. |
| `parent_trade_id` | string \| null | none | optional | For a cross-contract trade, the id of its parent trade. The parent itself is never reported. Recalling a trade that carries a `parent_trade_id` recalls the parent and every trade with the same `parent_trade_id` at once. |
| `prearrange_type` | string \| null | none | optional | `OTC` for a pre-arranged trade, which cannot be recalled. `OPT` and `PNC` are deprecated exchange values. |

#### <a id="trade-states" name="trade-states"></a>Trade states

A trade counts for position, cash and P&L in every state but `RGRA` and `CNCL`, including a code not listed here.

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

**Delivery (default) vs. execution.** With `time_basis=delivery` the window filters on the contract delivery period using overlap (a trade is returned when its delivery window intersects the range), the settlement view. With `time_basis=execution` it filters on `executed_at`, the transaction-reporting view. Trades recorded before delivery capture have `null` delivery fields and never match the default delivery filter with a date range; query them with `time_basis=execution`.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "invalid date '…': …"}` | Date parameter is not valid RFC 3339 |
| 400 | `{"error": "invalid sort_order '…': expected 'ASC' or 'DESC'"}` | `sort_order` is neither `ASC` nor `DESC` |
| 400 | `{"error": "invalid time_basis '…': expected 'execution' or 'delivery'"}` | `time_basis` is not `execution` or `delivery` |
| 403 | `{"error": "Forbidden"}` | `v_member_short_id` names a member the caller may not see |
| 503 | `{"error": "database not available"}` | Database not initialised |
| 500 | `{"error": "…"}` | Database query failed |

#### Example

```bash
curl "https://gateway.example:3000/api/v1/audit/trades?time_basis=execution&limit=50" \
  -H "Authorization: Bearer $VOLTNIR_API_KEY"
```

```
HTTP/1.1 200 OK
{
  "items": [ {"trade_id": "26269999001", "contract_id": "100123", "qty": 5000, "px": 5215, "state": "ACTI", "exec_time": "2026-04-20T13:42:07Z", "executed_at": "2026-04-20T13:42:07.000Z", "delivery_start": "2026-04-20T14:00:00Z", "delivery_end": "2026-04-20T15:00:00Z", "delivery_area": "10YNL----------L", "product": "Intraday_Hour_Power", "v_member_short_id": "VM001", "voltnir_user_short_id": "U001", "voltnir_username": "j.doe", "attribution": "full"} ],
  "next_cursor": "1717000000000.892"
}
```

### <a id="get-audit-public-trades" name="get-audit-public-trades"></a>`GET` `/api/v1/audit/public_trades`

Query the saved history of market-wide public trades. Returns rows only when the gateway persists public trades to Postgres; otherwise the table is empty. Data is scoped to the products your M7 account is assigned to; pre-arranged trades are excluded. Prices (`px`) are cents.

**Required permission:** `read_audit`. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `cursor` | string | none | No | Opaque pagination token from the previous `next_cursor`. Omit for the first page. |
| `limit` | u32 | count | No | Default 50, max 200. An explicit `limit=0` is rejected with 400. |
| `date_from` / `date_to` | string | RFC 3339 | No | Inclusive bounds on execution time. |
| `area` | string | none | No | Delivery area EIC code; matches when either the buy or sell delivery area equals it. |
| `product` | string | none | No | Filter by product code. |
| `state` | string | none | No | Trade state; see [Trade states](#trade-states). |
| `sort_order` | string | none | No | Page direction; `DESC` default, newest first. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `items` | array | none | always | Public-trade rows: `trade_id`, `contract_id`, `qty` (sub-MW), `px` (cents), `exec_time`/`executed_at`, `revision_no`, `state`, `buy_dlvry_area`, `sell_dlvry_area`, `self_trade`, `product`, and `remote_trade_id` (the XBID id on a remote trade, `null` on a local one). |
| `next_cursor` | string \| null | none | always | Feed back as `cursor`; `null` on the last page. |

> [!NOTE]
> **Saved history vs. the live feed.** This returns trades stored in the database, which survive restarts; how far back it reaches is set by the public-trade retention window (for example 3 days, with a background cleanup roughly hourly; 0 keeps everything). For the most recent trades happening now, use [GET /public_trades](#get-public-trades), the live in-memory feed.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "invalid date '…': …"}` | Date parameter is not valid RFC 3339 |
| 400 | `{"error": "invalid sort_order '…': expected 'ASC' or 'DESC'"}` | `sort_order` is neither `ASC` nor `DESC` |
| 403 | `{"error": "Forbidden"}` | Missing `read_audit` permission |
| 503 | `{"error": "database not available"}` | Database not initialised |
| 500 | `{"error": "…"}` | Database query failed |

#### Example

```bash
curl "https://gateway.example:3000/api/v1/audit/public_trades?limit=50" \
  -H "Authorization: Bearer $VOLTNIR_API_KEY"
```

### <a id="get-audit-events" name="get-audit-events"></a>`GET` `/api/v1/audit/events`

Query the compliance audit-event log: the append-only, who-did-what record of actor-driven mutations (user, permission, member and limit changes; the trading and self-trade toggles; order rejections; report exports; system and license lifecycle events). To take a window of it as a file, export it with [POST /audit/export/events](#post-export-events).

**Lifecycle rows and lost writes.** Each clean shutdown ends the trail with a `system_shutdown` row, written once every queued write has been committed or counted lost. Its `after` is `{"writes_lost": {"audit": n, "m7_errors": n, "exchange_messages": n, "public_trades": n, "orders": n, "trades": n}}`: what that run lost, per stream. When a run ends without that row (a crash, a kill, a power loss), the next start writes a `system_unclean_exit` row (target `system`, outcome `ok`) just before its own `system_startup`. Its `after` names the previous run's start (`previous_startup_ts`, `previous_startup_ts_ms`) and `last_audit_id`, the `id` of the last row that run stored; writes that run still held in memory may be missing, and how many is not known. Row ids are assigned when a row is stored, so a gap in them is not how a loss shows: these two rows and `writes_dropped` are. The `system_startup` row's `after` records the trade-ingest fault policy the run started under: `{"trade_ingest_fault": "close" | "continue", "trade_ingest_fault_ack_ttl_sec": n}`.

**Member scope.** The trail is member-scoped like [GET /audit/orders](#get-audit-orders), after the `read_audit` gate. A caller who also holds `read_orders` or `bypass_member_check` reads every row. Any other caller reads only the rows of order actions tagged with a virtual member assigned to them: every row with no member (a user, permission, member, limit, licence or system event, a House order, a cancel-all, a `slot_limit_would_refuse` or `member_self_cross` row) is withheld, and a caller assigned to no member reads no row. `v_member_short_id` narrows within that scope. A row carries the member of the order it is about in `v_member_short_id` only for the order actions (`order_submitted`, `order_modified`, `order_cancelled`, `order_rejected`, `order_command_rejected`); a modify row takes the order's own member, which a modify cannot change. Rows written before the column existed carry none.

**Required permission:** `read_audit`. `read_orders` or `bypass_member_check` widens the result to the whole trail; without either it is member-scoped. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `cursor` | string | none | No | Opaque pagination token. Omit for the first page. |
| `limit` | u32 | count | No | Default 50, max 200. An explicit `limit=0` is rejected with 400. |
| `date_from` / `date_to` | string | RFC 3339 | No | Inclusive bounds on event time. |
| `action` | string | none | No | Filter by action token, e.g. `permissions_set`, `cash_limit_set`, `trading_toggled`, `trade_ingest_fault_acknowledged`, `trade_ingest_fault_ack_expired`, `order_rejected`, `order_cancel_all`, `report_exported`, `system_startup`, `system_shutdown`, `system_unclean_exit`, `auth_failed`, `permission_denied`, `rate_limited`. |
| `target_type` | string | none | No | Filter by target kind: `user`, `member`, `profile`, `order`, `trading`, `report`, `license`, `system`, `session`. |
| `actor_short_id` | string | none | No | Filter by the acting user's short id (e.g. `U001`). |
| `outcome` | string | none | No | Filter by outcome: `ok`, `denied` or `error`. |
| `v_member_short_id` | string | none | No | Narrow to one virtual member's order rows, within the caller's scope. `403` for a member the caller may not see. |
| `sort_order` | string | none | No | Page direction; `DESC` default, newest first. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `items` | array | none | always | Event rows (fields below). |
| `next_cursor` | string \| null | none | always | Feed back as `cursor`; `null` on the last page. |

#### Event row (`items[]`)

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `id` | i64 | none | always | Row id; increases with every new event. |
| `ts` / `ts_ms` | string / i64 | RFC 3339 / Unix ms | always | Event time. |
| `actor_user_id` / `actor_short_id` / `actor_username` | string \| null | none | optional | The acting user; for a system/license event the component name is in `actor_username` with the ids `null`. |
| `transport` | string | none | always | `rest`, `ws`, `grpc` or `system`. |
| `action` / `target_type` / `target_id` | string \| null | none | always | What happened and to what; for an order action `target_id` is the `client_order_id`. |
| `before` / `after` | object \| array \| null | none | optional | State snapshots around the change. |
| `outcome` | string | none | always | `ok`, `denied` or `error`. |
| `reason` | string \| null | none | optional | The reason on a denial or error; `null` otherwise. |
| `source_ip` | string \| null | none | optional | The caller's source IP: the connection peer address, or, when that peer is listed in `system.trusted_proxies`, the client it named in `X-Forwarded-For`. |
| `v_member_short_id` | string \| null | none | always | The virtual member of the order an order action is about; `null` for a House order and on every other row. The member scope reads it. |

Rows are immutable and kept forever by default; they are pruned only once the audit retention window is set to a number of days. Every accepted order action appends exactly one row (`order_submitted`, `order_modified`, `order_cancelled`, or `order_rejected` with the refusal reason); `DELETE /orders` stays a single `order_cancel_all` row and does not fan out per order. A slot-limit refusal (`slot_position_limit_exceeded` or `slot_window_unknown`), of a placement or of a modify or activation, carries an `after` with the refusal's own fields, because its reason alone does not say which bound was hit: `delivery_area`; then, for `slot_position_limit_exceeded`, `slot_start_ms` and `slot_end_ms` (UTC epoch milliseconds), `side` (`long` or `short`), `scope` (`house` or the member's short id), `bound_after` (sub-MW, positive long, negative short) and `limit` (sub-MW); and, for `slot_window_unknown`, one of `order_contract_id`, `open_order_contract_id` or `trade_id`, naming what has no delivery window. A caller holding none of `read_orders`, `bypass_member_check` and `read_status` is shown such a row as the refusal itself is shown to it: a `house`-scope breach without `bound_after` and `limit`, and a trade with no window without its `trade_id`. The stored row keeps them, so a `read_status` holder and a firm-wide reader read them. Every other gate refusal carries no `after` snapshot, because nothing reached the exchange.

**Slot limit in `observe`.** An order the slot position limit would refuse is admitted, and recorded as a `slot_limit_would_refuse` row (system actor, target type `order`, no target id, outcome `ok`). Identical would-refusals (same reason, delivery area, slot, scope and side) within 10 seconds are one row. Its `after` carries the refusal's fields as an `order_rejected` row of the same refusal would, plus `reason` (`slot_position_limit_exceeded` or `slot_window_unknown`), `contract_id`, `order_side` (`BUY` or `SELL`), `quantity` (sub-MW, the size the order asked for), `member` (the member's short id, or `null` for a House order), `count` (how many would-refusals the row stands for) and `window_s` (`10`). The row is written when its 10-second window closes, or at a clean shutdown if that comes first.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "invalid date '…': …"}` | Date parameter is not valid RFC 3339 |
| 400 | `{"error": "invalid sort_order '…': expected 'ASC' or 'DESC'"}` | `sort_order` is neither `ASC` nor `DESC` |
| 403 | `{"error": "Forbidden"}` | Missing `read_audit` permission |
| 403 | `{"error": "Forbidden"}` | `v_member_short_id` names a member the caller may not see; the `permission_denied` row's reason is `member_scope` |
| 503 | `{"error": "database not available"}` | Database not initialised |
| 500 | `{"error": "…"}` | Database query failed |

#### Example

```bash
curl "https://gateway.example:3000/api/v1/audit/events?action=permissions_set&limit=50" \
  -H "Authorization: Bearer $VOLTNIR_API_KEY"
```

**Trade recalls.** A recall appends rows with target type `trade` and the exchange trade id as target. `trade_recall_requested` (by the caller) when a sent recall was not refused at its receipt, its `after` carrying `revision_no`, `state`, `receipt` (`acknowledged` or `unknown`), `correlation_id` and `parent_trade_id`. `trade_recall_refused` (outcome `error`, by the caller) once per refusal: `recall_not_possible` or `trade_changed` for the gateway's own refusals, `exchange_refused` with `m7_err_code`, `m7_error_key` and `exchange_reason` for the exchange's, before or after its receipt, and `not_processed` for a request handed back undelivered. `trade_recall_resolved` (system actor) once per trade, the first time the gateway sees it `RGRA` or `RREJ`, carrying the state, revision and the recall times and `recall_requestor` as the exchange reported them, and `first_seen_resolved`. It is written for a recall asked outside the gateway too, with no `trade_recall_requested` row before it, and for a trade first seen already decided at login, with `first_seen_resolved: true`.

**Trades between two of the desk's members.** When two virtual members of the desk trade with each other, the gateway appends one `member_self_cross` row (system actor, target type `trade`, target id the trade id) whose `after` snapshot carries `trade_id`, `contract_id`, `qty` (sub-MW), `px` (cents), `buy_member_short_id` and `sell_member_short_id`. A member-scoped reader of the trade sees only its own leg, so this row is where the desk sees the cross whole: it names no one member, so it is readable with `read_audit` by a caller who also holds `read_orders` or `bypass_member_check`, and the matching warning-level log line reaches holders of `read_logs` when the log level includes warnings; neither reaches the trade streams, contract detail or trade history of a member-scoped caller. A trade already on the trail is not recorded again, also after a restart; a failed lookup of the trail records it rather than lose it.

### <a id="get-audit-m7-errors" name="get-audit-m7-errors"></a>`GET` `/api/v1/audit/m7_errors`

Query the M7 exchange-error log, the append-only record of exchange-side faults. The primary rows are M7 business errors (`kind: "err_resp"`), each enriched from the official EPEX SPOT M7 API documentation with a human `err_identifier` and a `category`. One exchange error response can carry several errors, since the exchange refuses a request that names several orders with a single response listing each refusal. Each error is its own `err_resp` row with its own `err_code`, `err_text` and `cl_ordr_id`, and `raw_payload` holds the whole response. The refused order is told the texts of the errors that name it, joined with `;`, and their code only when they share one. An error response the gateway cannot read is a `parse_error` row carrying the raw response, and the request it answered is still reported refused.

**Required permission:** `read_m7_errors` (deliberately separate from `read_audit`). (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `cursor` | string | none | No | Opaque pagination token. Omit for the first page. |
| `limit` | u32 | count | No | Default 50, max 200. An explicit `limit=0` is rejected with 400. |
| `date_from` / `date_to` | string | RFC 3339 | No | Inclusive bounds on receive time. |
| `kind` | string | none | No | Fault class: `err_resp`, `parse_error`, `unknown_type`, `ack_uncorrelated`, `seq_gap`. |
| `category` | string | none | No | Error category: `order_entry`, `general`, `trade`, `user_right`, `limits`, `wrong_reference`, `unknown` (set only for `kind=err_resp`). |
| `err_code` | i64 | none | No | Filter by the raw numeric M7 error code (e.g. `1149`). |
| `sort_order` | string | none | No | Page direction; `DESC` default, newest first. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `items` | array | none | always | Fault rows: `received_at`/`received_at_ms`, `kind`, `category`, `err_code`, `err_identifier`, `err_text`, `cl_ordr_id` (correlates to the [orders](#get-audit-orders) audit row), `client_correlation_id`, `var_list`, the `voltnir_*` attribution columns, `raw_payload`, and `severity`. The `category`/code fields are set only for `err_resp`. |
| `next_cursor` | string \| null | none | always | Feed back as `cursor`; `null` on the last page. |

Rows are immutable and kept forever by default; they are pruned only once the M7-error retention window is set to a number of days. The `voltnir_*` columns are populated only when the failing order's Voltnir user is resolvable; `cl_ordr_id` always correlates an `err_resp` row to the fully-attributed orders audit row.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "invalid date '…': …"}` | Date parameter is not valid RFC 3339 |
| 400 | `{"error": "invalid sort_order '…': expected 'ASC' or 'DESC'"}` | `sort_order` is neither `ASC` nor `DESC` |
| 403 | `{"error": "Forbidden"}` | Missing `read_m7_errors` permission |
| 503 | `{"error": "database not available"}` | Database not initialised |
| 500 | `{"error": "…"}` | Database query failed |

#### Example

```bash
curl "https://gateway.example:3000/api/v1/audit/m7_errors?kind=err_resp&limit=50" \
  -H "Authorization: Bearer $VOLTNIR_API_KEY"
```

```
HTTP/1.1 200 OK
{
  "items": [ {"received_at": "2026-06-20T14:03:11.123Z", "kind": "err_resp", "category": "order_entry", "err_code": 1149, "err_identifier": "order_rejected_self_trade_protection", "err_text": "Order rejected by self-trade protection", "cl_ordr_id": "3af1…", "severity": "error"} ],
  "next_cursor": "1781013791123.4187"
}
```

### <a id="get-audit-exchange-messages" name="get-audit-exchange-messages"></a>`GET` `/api/v1/audit/exchange_messages`

Query the exchange-message log, the append-only record of what the exchange itself said: cash-limit breaches, market and delivery-area halts, member suspensions, failover notices and automated order transfers.

**Required permission:** `read_m7_errors` (the same permission as the M7-error log; no new permission is introduced). (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `cursor` | string | none | No | Opaque pagination token. Omit for the first page. |
| `limit` | u32 | count | No | Default 50, max 200. An explicit `limit=0` is rejected with 400. |
| `date_from` / `date_to` | string | RFC 3339 | No | Inclusive bounds on receive time. |
| `severity` | string | none | No | `urgent`, `error`, `high`, `medium`, `low`, or `unknown`. |
| `scope` | string | none | No | `public` (market-wide) or `private` (this member). |
| `code` | i64 | none | No | Filter by the vendor message code (e.g. `158` member cash-limit breach, `91` market halt). |
| `sort_order` | string | none | No | Page direction; `DESC` default, newest first. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `items` | array | none | always | Message rows: `id` (backend row id, `null` on a streamed-but-not-stored message), `received_at`/`received_at_ms`, `exchange_ts`/`exchange_ts_ms` (`null` when unparseable), `msg_id` (the exchange's de-duplication key and stable identity), `scope`, `code`, `key` (resolved from the code, `null` when uncatalogued), `severity`, `text` (placeholders substituted from `vars`, with every instant inside a variable restated in UTC, RFC 3339 with `Z`; `vars` keeps the exchange's own spelling), `product`, `account_id`, `buy_area`, `sell_area`, `market_supervision`, and `vars`. |
| `next_cursor` | string \| null | none | always | Feed back as `cursor`; `null` on the last page. |

Rows are immutable, de-duplicated on `msg_id`, and kept forever by default; they are pruned only once the exchange-message retention window is set to a number of days. Two kinds are streamed live but never stored, so never appear here: messages the exchange marks non-persistent, and the per-contract lifecycle broadcasts (codes `74`, `76`, `77`), which Voltnir drops because one arrives per contract per phase and none names an order, trade or position of yours. Subscribe to the WS `exchange_messages` stream or gRPC `WatchExchangeMessages` to see those.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "invalid date '…': …"}` | Date parameter is not valid RFC 3339 |
| 400 | `{"error": "invalid sort_order '…': expected 'ASC' or 'DESC'"}` | `sort_order` is neither `ASC` nor `DESC` |
| 400 | `{"error": "limit must be greater than zero"}` | Explicit `limit=0` |
| 403 | `{"error": "Forbidden"}` | Missing `read_m7_errors` permission |
| 503 | `{"error": "database not available"}` | Database not initialised |
| 500 | `{"error": "…"}` | Database query failed |

#### Example

```bash
curl "https://gateway.example:3000/api/v1/audit/exchange_messages?scope=private&limit=50" \
  -H "Authorization: Bearer $VOLTNIR_API_KEY"
```

```
HTTP/1.1 200 OK
{
  "items": [ {"id": 4187, "received_at_ms": 1788610323180, "msg_id": 90210, "scope": "private", "code": 158, "key": "cash_limit_breached_member", "severity": "error", "text": "Cash limit in GBP breached! All orders in this currency have been deactivated.", "account_id": "10XDE-BG-------W", "vars": [{"id": 6, "value": "GBP"}]} ],
  "next_cursor": "1788610323180.4187"
}
```

### <a id="get-system-logs" name="get-system-logs"></a>`GET` `/api/v1/system/logs`

Read the gateway's own diagnostic log, the running process's internal log output captured in memory. Not the exchange's messages, faults or the compliance trail; it carries file paths, database errors and module names, so it has its own permission.

**Required permission:** `read_logs`. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `cursor` | u64 | none | No | Resume point: return entries whose `seq` is greater than this. Omit for the newest page. |
| `limit` | u32 | count | No | Default 50, max 200. An explicit `limit=0` is rejected with 400. |
| `min_level` | string | none | No | Minimum severity to return: `error`, `warn`, `info` or `debug`. An unrecognised value is rejected with 400, not ignored. It filters what you are shown, not what is captured. |
| `date_from` / `date_to` | string | RFC 3339 | No | Inclusive bounds on capture time. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `items` | array | none | always | Log entries, oldest-first: `seq`, `ts_ms`, `level`, `target` (the emitting module), `message` (capped at 4 KiB, with the cut marked). |
| `next_cursor` | u64 \| null | none | always | Pass back as `cursor` to advance; `null` when the page is empty. |
| `truncated` | bool | none | always | `true` when the `cursor` you passed had already been evicted, so this page resumes from the oldest surviving entry and the entries in between are gone. |
| `buffer` | object | none | always | Ring state: `enabled`, `level`, `capacity`, `len`, `oldest_seq`, `oldest_ts_ms`, `newest_seq` (the seq/ts fields `null` when empty), `started_at_ms` (how far back the buffer reaches), and `dropped` (entries already evicted). |

> [!WARNING]
> **Not an audit record.** The buffer is a bounded in-memory ring, capped by entry count first (20,000 by default) and age second (24 hours by default; the age bound can be disabled). It lives only in the running process, is **lost on every restart**, and drops its oldest entries under load. Anything that must survive an incident belongs in the audit log. The durable copy of this output is the process's standard output, which a deployment normally hands to the system journal. Capture level is a server setting, not a request parameter.

There is no `503` arm: the buffer is in the gateway's own memory and stays readable while the database is unavailable, which is the state an operator most often wants to read it in.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "invalid date '…': …"}` | Date parameter is not valid RFC 3339 |
| 400 | `{"error": "limit must be greater than zero"}` | Explicit `limit=0` |
| 400 | `{"error": "invalid min_level '…': expected error\|warn\|info\|debug"}` | Unrecognised `min_level` |
| 403 | `{"error": "Forbidden"}` | Missing `read_logs` permission |

#### Example

```bash
curl "https://gateway.example:3000/api/v1/system/logs?min_level=warn&limit=50" \
  -H "Authorization: Bearer $VOLTNIR_API_KEY"
```

```
HTTP/1.1 200 OK
{
  "items": [ {"seq": 18344, "ts_ms": 1788610323180, "level": "warn", "target": "m7.amqp.connection", "message": "AMQP connection lost, reconnecting in 5s"} ],
  "next_cursor": 18345,
  "truncated": false,
  "buffer": {"enabled": true, "level": "info", "capacity": 20000, "len": 20000, "oldest_seq": 12346, "newest_seq": 18345, "dropped": 12346}
}
```

### <a id="post-export-orders" name="post-export-orders"></a>`POST` `/api/v1/audit/export/orders`

Initiate an asynchronous export of order audit data. The export runs in a background task; poll the returned `download_url` to retrieve the file when ready. The report carries only the rows the caller may read on [GET /audit/orders](#get-audit-orders), with the same fields, `source` included (a JSON key, and a CSV column). The coded columns carry their names, as on that read ([coded columns are names](#order-history-names)): a name is a plain CSV cell, a code with no name is its number, and `null` is an empty cell.

**Required permission:** `export_reports`. `read_orders` or `bypass_member_check` widens the exported rows to the firm-wide history. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `format` | string | none | Yes | `"json"` or `"csv"`. |
| `from` | string | RFC 3339 | Yes | Start of range (inclusive). |
| `to` | string | RFC 3339 | Yes | End of range (inclusive). Must be after `from`, and at most 31 days plus one hour after it (see *Limits* below). |
| `area` | string | none | No | Filter by delivery area EIC code. |
| `product` | string | none | No | Filter by product code. |
| `status` | string | none | No | Filter by order state, as on [GET /audit/orders](#get-audit-orders): `ACTIVE`, `INACTIVE` or `HIBERNATED` (or `ACTI`, `INAC`, `HIB`), any case. Anything else is `400`. Ignored by the trades export. |
| `user_code` | string | none | No | Filter by the EPEX trader/user code. |
| `v_member_short_id` | string | none | No | Narrow to one virtual member inside the caller's member scope. A member the caller may not read is `403`, as on the history read. |
| `voltnir_user_short_id` | string | none | No | Filter by the submitting Voltnir user's short id (e.g. `"U001"`). |
| `voltnir_username` | string | none | No | Filter by the submitting Voltnir user's username. |

Every filter is an exact match and works as the parameter of the same name on the history read, so a report holds the rows that read pages for the same window and filters. An empty filter is no filter, as it is there.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `token` | string | none | always | The export token (a lookup key, not a bearer credential). Returned `202`. |
| `download_url` | string | none | always | The path to poll and download: [GET /audit/export/{token}](#get-export-token). |

The token is valid for 1 hour and is lost on server restart. The report is readable only by the user that requested it.

> [!NOTE]
> **Limits.** One export covers at most **31 days plus one hour**: `to` may be at most 745 hours after `from`, exactly 745 included. The two bounds are compared as UTC instants, so the cap counts the hours that really pass. The extra hour is the October clock change: written in local time, a 31-day month across it lasts 745 hours, so a whole calendar month always fits, in UTC or in local time. Export a longer history as several windows. **One export runs at a time**, for the whole gateway and every user, every kind of export together: a request that arrives while another export is being generated is refused at once with `409` and nothing is started or queued. Send it again once that export is ready or has failed; a finished report waiting to be downloaded does not hold the gateway up. An export still being generated when the gateway stops is lost with its token: request it again after the restart.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "from: invalid ISO 8601 date"}` / `{"error": "to: invalid ISO 8601 date"}` | `from` or `to` is not valid RFC 3339 |
| 400 | `{"error": "from must be before to"}` | `from` ≥ `to` |
| 400 | `{"error": "export range exceeds 31 days"}` | `to` is more than 31 days plus one hour (745 hours) after `from` |
| 400 | `{"error": "from is required"}` / `{"error": "to is required"}` | Missing `from` or `to` |
| 400 | `{"error": "unknown format '…', must be json or csv"}` | Invalid or missing format value |
| 400 | `{"error": "invalid status '…': expected ACTIVE (ACTI), INACTIVE (INAC) or HIBERNATED (HIB), …"}` | `status` is not an order state (orders export only) |
| 403 | `{"error": "Forbidden"}` | Missing `export_reports` permission, or `v_member_short_id` names a member outside the caller's scope |
| 409 | `{"error": "an export is already running, try again later"}` | Another export, of any kind and by any user, is being generated. Nothing was started; retry once it is ready or has failed |
| 500 | `{"error": "cannot create report directory: …"}` | Server filesystem issue |

#### Example

```bash
curl -X POST https://gateway.example:3000/api/v1/audit/export/orders \
  -H "Authorization: Bearer $VOLTNIR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"format": "csv", "from": "2026-04-01T00:00:00Z", "to": "2026-04-30T23:59:59Z", "area": "10YNL----------L"}'
```

```
HTTP/1.1 202 Accepted
{"token": "550e8400-e29b-41d4-a716-446655440000", "download_url": "/api/v1/audit/export/550e8400-e29b-41d4-a716-446655440000"}
```

### <a id="post-export-trades" name="post-export-trades"></a>`POST` `/api/v1/audit/export/trades`

Initiate an asynchronous export of trade audit data. Same request body, response shape, member scope, limits (31 days plus one hour, one export at a time across every kind) and error conditions as [POST /audit/export/orders](#post-export-orders), except that `status` is ignored: a trade carries no order state. The window filters on the delivery window unless `time_basis` is `execution`, as on [GET /audit/trades](#get-audit-trades).

**Required permission:** `export_reports`. `read_orders` or `bypass_member_check` widens the exported rows to the firm-wide history. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `format` | string | none | Yes | `"json"` or `"csv"`. |
| `from` | string | RFC 3339 | Yes | Start of range. |
| `to` | string | RFC 3339 | Yes | End of range. Must be after `from`, and at most 31 days plus one hour after it. |
| `area` | string | none | No | Filter by delivery area EIC code. |
| `product` | string | none | No | Filter by product code. |
| `user_code` | string | none | No | Filter by the EPEX trader/user code. |
| `v_member_short_id` | string | none | No | Narrow to one virtual member inside the caller's member scope. A member the caller may not read is `403`, as on the history read. |
| `voltnir_user_short_id` | string | none | No | Filter by the submitting Voltnir user's short id (e.g. `"U001"`). |
| `voltnir_username` | string | none | No | Filter by the submitting Voltnir user's username. |
| `time_basis` | string | none | No | Which time `from`/`to` bound: `delivery` (default; the contract delivery window, overlap semantics) or `execution` (execution time), in any case. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `token` | string | none | always | The export token. Returned `202`. |
| `download_url` | string | none | always | The path to poll and download. |

#### Errors

Same as [POST /audit/export/orders](#post-export-orders), plus 400 `{"error": "invalid time_basis '…': expected 'execution' or 'delivery'"}` when `time_basis` is not `execution` or `delivery`; nothing is started.

#### Example

```bash
curl -X POST https://gateway.example:3000/api/v1/audit/export/trades \
  -H "Authorization: Bearer $VOLTNIR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"format": "json", "from": "2026-04-01T00:00:00Z", "to": "2026-04-30T23:59:59Z"}'
```

### <a id="post-export-events" name="post-export-events"></a>`POST` `/api/v1/audit/export/events`

Initiate an asynchronous export of the compliance audit trail. The file holds exactly the rows [GET /audit/events](#get-audit-events) pages for the same window and filters, with the same fields, oldest first. Same response shape, download, limits (31 days plus one hour, one export at a time across every kind) and `report_exported` row as [POST /audit/export/orders](#post-export-orders). The file is member-scoped as the live read is: a caller without `read_orders` or `bypass_member_check` exports only the order rows of the members assigned to them. The `before` and `after` snapshots are JSON values in a JSON file, and their JSON text in a single CSV cell (an empty cell when there is none). The other columns are text, numbers or `null`, as on the live read.

**Required permission:** `export_reports` and `read_audit`, both. `read_orders` or `bypass_member_check` widens the exported rows to the whole trail. (see [Permissions](#permissions))

#### Request

The window and format are the other exports' own; the filters are the [GET /audit/events](#get-audit-events) query parameters of the same names, applied the same way: each an exact match, so a value no row carries gives an empty file, as it gives an empty page there, and an empty one is no filter in both.

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `format` | string | none | Yes | `"json"` or `"csv"`. |
| `from` | string | RFC 3339 | Yes | Start of range on event time (inclusive). |
| `to` | string | RFC 3339 | Yes | End of range on event time (inclusive). Must be after `from`, and at most 31 days plus one hour after it. |
| `action` | string | none | No | Filter by action token, e.g. `permissions_set`. |
| `target_type` | string | none | No | Filter by target kind, e.g. `user`. |
| `actor_short_id` | string | none | No | Filter by the acting user's short id (e.g. `U001`). |
| `outcome` | string | none | No | Filter by outcome: `ok`, `denied` or `error`. |
| `v_member_short_id` | string | none | No | Narrow to one virtual member's order rows, within the caller's scope. `403` for a member the caller may not see. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `token` | string | none | always | The export token. Returned `202`. |
| `download_url` | string | none | always | The path to poll and download: [GET /audit/export/{token}](#get-export-token). |

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | the window and format refusals of [POST /audit/export/orders](#post-export-orders), `{"error": "export range exceeds 31 days"}` among them | A missing, malformed or reversed window, a window over 31 days plus one hour, or a format other than `json` / `csv` |
| 403 | `{"error": "Forbidden"}` | Missing `export_reports` or `read_audit`. The `permission_denied` row names the missing one, `export_reports` first when both are missing |
| 403 | `{"error": "Forbidden"}` | `v_member_short_id` names a member the caller may not see. Nothing was started and no `report_exported` row is written |
| 409 | `{"error": "an export is already running, try again later"}` | Another export, of any kind and by any user, is being generated. Nothing was started |
| 500 | `{"error": "cannot create report directory: …"}` | Server filesystem issue |

#### Example

```bash
curl -X POST https://gateway.example:3000/api/v1/audit/export/events \
  -H "Authorization: Bearer $VOLTNIR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"format": "csv", "from": "2026-04-01T00:00:00Z", "to": "2026-04-30T23:59:59Z", "action": "permissions_set"}'
```

### <a id="get-export-token" name="get-export-token"></a>`GET` `/api/v1/audit/export/{token}`

Poll or download an export by its token: the binary file when ready, a `202` while still generating, or a `500` if generation failed.

**Required permission:** `export_reports`, and the caller must be the user who requested the report. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `token` | string | none | Yes | Path parameter. The token from the export response. |

#### Response

| Status | Body | Description |
| --- | --- | --- |
| 200 | binary file | The report file, streamed from disk, with `Content-Type: application/json` or `text/csv`, a `Content-Disposition: attachment` filename, and the file size in `Content-Length`. If the file cannot be read once the download has started, the connection closes before `Content-Length` bytes arrive. Treat a body shorter than `Content-Length` as a failed download and request the token again while it is valid. The gateway exposes `Content-Disposition` to CORS, so a browser client on another origin can read the filename. |
| 202 | `{"status": "pending"}` | Still generating. |

> [!WARNING]
> The token is a lookup key, **not** a bearer credential. The download requires `export_reports` *and* that the caller is the user who requested the report. A token issued to another user is answered with the same `404 {"error": "token not found"}` an unknown token gets, so a token can never be used to learn whether a report exists. Tokens expire after 1 hour and the registry is in-memory only, so tokens are lost if the server restarts.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 403 | `{"error": "Forbidden"}` | Missing `export_reports` permission (checked before the token is looked up) |
| 404 | `{"error": "token not found"}` | Token not found (expired, never existed, server restarted, or issued to a different user) |
| 500 | `{"error": "…"}` | Background export task failed, or the finished file could not be opened before the download started (`failed to read file: …`) |

#### Example

```bash
curl -OJ "https://gateway.example:3000/api/v1/audit/export/550e8400-e29b-41d4-a716-446655440000" \
  -H "Authorization: Bearer $VOLTNIR_API_KEY"
```

<a id="errors" name="errors"></a>

## Error reference

Every error is an HTTP status code with a JSON `{"error": "..."}` body. The per-endpoint Errors tables give the exact messages; this table is the transport-wide mapping, and it matches the gRPC status enum 1:1, which is useful when porting a client between transports.

| Status | gRPC `StatusCode` | Trigger |
| --- | --- | --- |
| 400 | `INVALID_ARGUMENT` | Malformed input, unknown enum value, parse error, or a value off the product grid. |
| 401 | `UNAUTHENTICATED` | Missing or invalid bearer token. |
| 403 | `PERMISSION_DENIED` | Caller lacks the required permission, or the desk-management licence tier. |
| 404 | `NOT_FOUND` | Unknown contract, order, user or member, or one outside the caller's member scope. |
| 429 | `RESOURCE_EXHAUSTED` | The API key is over its per-key request bound (see [Connecting and authentication](#connecting)). Cancels, cancel-all and disabling trading are never bounded. |
| 409 | `ABORTED` | State conflict, for example a modify already in progress, `ORDER_CHANGED` when the order's revision moved under the command, `ORDER_PENDING` when a modify or cancel names an order the exchange has not yet acknowledged, or a report export requested while another is being generated. |
| 422 | `FAILED_PRECONDITION` | Per-contract limit or slot position limit exceeded, a slot window unknown, self-cross blocked, a member order outside the member’s delivery areas (`MEMBER_AREA_NOT_ALLOWED`), trading disabled by the kill-switch, the load-management guard refusing, or a cash-limit bound (including a missing or stale holiday calendar). See [GET /cash_limit](#get-cash-limit). |
| 409 | `FAILED_PRECONDITION` | [POST /trade/recall](#post-trade-recall): `RECALL_REFUSED` (the exchange refused the recall) or `RECALL_NOT_POSSIBLE` (the trade is not `ACTI`). `TRADE_CHANGED` is `409` / `ABORTED`, `TRADE_NOT_FOUND` `404` / `NOT_FOUND` and `OUTCOME_UNKNOWN` `504` / `DEADLINE_EXCEEDED`. |
| 500 | `INTERNAL` | Unexpected error. |
| 503 | `UNAVAILABLE` | Database unavailable, system not operational, or the exchange handed the request back undelivered (message prefixed `NOT_PROCESSED:`), the one case safe to resubmit blind. |
| 504 | `DEADLINE_EXCEEDED` | M7 did not acknowledge within the order acknowledgement timeout (2 seconds by default). The outcome is *unknown*, not failed, so re-check before resubmitting. |

Copyright © 2026 Voltnir B.V. The Voltnir gateway is proprietary software, licensed under separate terms.
