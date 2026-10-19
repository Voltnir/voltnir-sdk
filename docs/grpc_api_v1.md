# Voltnir gRPC API v1: Reference

> Auto-generated from the Voltnir API reference.

<a id="overview" name="overview"></a>

## Overview

The Voltnir gRPC API is the schema-first transport onto the EPEX SPOT M7 intraday gateway. A single Protocol Buffers schema ([proto_volt/voltnir_api_v1.proto](https://github.com/Voltnir/voltnir-sdk/blob/master/proto_volt/voltnir_api_v1.proto)) is the canonical contract; each operation on this page is one `rpc` on the `voltnir.api.v1.VoltAPI` service.

- **Parity with REST and WebSocket.** Every unary RPC mirrors a REST endpoint and a WebSocket command exactly: same fields, same units, same permission gates, same validation. The permission table is identical across the three references.
- **Streaming.** Server-streaming RPCs (`Watch*`) add live feeds that REST has no equivalent for.
- **Report exports are REST-only.** Request an order, trade or audit-trail file with [`POST /audit/export/orders`](rest_api_v1.md#post-export-orders), [`POST /audit/export/trades`](rest_api_v1.md#post-export-trades) or [`POST /audit/export/events`](rest_api_v1.md#post-export-events) and download it by token; there is no export RPC.
- **Status codes are an enum.** Failures use `grpc.StatusCode`; the [Error reference](#errors) maps each one.
- **Health checking.** The same server also carries the standard `grpc.health.v1.Health` service, unauthenticated, for an orchestrator's probe; see [Health checking](#health). There is no reflection service.

Read [Connecting and authentication](#connecting) first, then [Permissions](#permissions) and [Conventions](#conventions). The operations follow, grouped by domain, then [Streaming](#streaming) and the [Error reference](#errors).

<a id="connecting" name="connecting"></a>

## Connecting and authentication

Standard gRPC over HTTP/2. Any conformant client (tonic, grpcio, grpc-go, @grpc/grpc-js, and the rest) can talk to it.

| Setting | Default | Notes |
| --- | --- | --- |
| Port | `3443` | Set by the gRPC port setting. Independent of the REST port (`3000`); both transports run side by side. |
| TLS | Off | Plaintext HTTP/2 by default. Set the TLS certificate and key in the gateway configuration to enable. Cert rotation requires a server restart. |
| Protocol | HTTP/2 | Standard gRPC framing. No gRPC-Web or HTTP/2 transcoding in v1. |
| Streaming | Server-only | Server-streaming RPCs only: a `Watch*` RPC for every live data type; no client-streaming or bidi streams in v1. |

#### Bare-bones smoke test (grpcurl)

```
grpcurl -plaintext \
  -import-path proto_volt -proto voltnir_api_v1.proto \
  -H 'authorization: Bearer <your_api_key>' \
  localhost:3443 \
  voltnir.api.v1.VoltAPI/GetState
```

If you see `UNAUTHENTICATED: missing bearer token` the metadata header is malformed; the key name is lowercase `authorization` and the scheme is the literal string `Bearer` (capital B, single space).

#### Authentication

Every `VoltAPI` RPC requires an `authorization: Bearer <api-key>` entry in the request **metadata**; only the [health service](#health) takes none. The server SHA-256-hashes the token and validates it against your account. Tokens cannot be retrieved after creation; if a key is lost, rotate it via `RotateApiKey`.

The bearer may also be a **session token** (it starts with `vs_`), accepted exactly like a key and acting as its user with that user's live permissions. The trading terminal signs in this way so the browser never keeps the API key. Sessions are minted and ended over REST only, with [`POST /sessions`](rest_api_v1.md#post-sessions) and [`DELETE /sessions/current`](rest_api_v1.md#delete-sessions-current); a program connecting here authenticates with its API key. An expired or ended session is refused with the same `UNAUTHENTICATED` as a wrong key, and a `WatchStatus` stream opened with it ends on its next tick.

> [!NOTE]
> **Required on every call:**
>  metadata key `authorization` (lowercase) → value `Bearer <your_api_key>` (capital `B`).

#### Auth failures

| Cause | gRPC `StatusCode` |
| --- | --- |
| Missing `authorization` metadata | `UNAUTHENTICATED` |
| Header present but not in `Bearer <token>` form | `UNAUTHENTICATED` |
| Hashed token doesn't match any user, or is a session that has ended or expired | `UNAUTHENTICATED` |
| Caller lacks the required `Permission` | `PERMISSION_DENIED` |
| Key is over its per-key request bound | `RESOURCE_EXHAUSTED` |

Every refusal is written to the audit trail with `outcome` `denied` and `target_type` `auth`: `auth_failed` for a rejected credential, `permission_denied` for a refused permission or a desk-gated RPC on a trader license, `rate_limited` for the request bound. `target_id` is the RPC that was refused; `reason` is the permission's code, `license_desk_required`, `member_scope` when the caller holds the permission but asked for a virtual member it is not assigned to, `forbidden` for a guard that is none of those, or why the credential failed (`invalid_token`, `missing_credentials`), never the credential itself. `auth_failed` and `rate_limited` are written at most once per source per minute, so a client in a retry loop cannot flood the trail; a minute that closes on more attempts than that adds one row with `reason: "repeated_failures"` carrying the count in `after.attempts`. The source of an event is the **peer address of the connection**, unless that peer is listed in `system.trusted_proxies`: then it is the client the proxy named in `x-forwarded-for` metadata, read from the right. With the list empty (the default), every attempt behind a reverse proxy collapses onto the proxy's address, so these rows say that traffic arrived, not where on the internet it came from, and the one-row-per-source-per-minute throttle applies to the proxy as a whole.

### <a id="python-sdk" name="python-sdk"></a>Python SDK: install and quickstart

`voltnir_sdk` wraps the generated gRPC stubs with sync (`VoltnirClient`) and async (`AsyncVoltnirClient`) facades, identical method-for-method. Each RPC on this page is called as the snake_case method of its name (`SubmitOrder` is `client.submit_order(...)`). The [Python SDK reference](python_sdk_v1.md) covers it in full: units, order recovery, streams and every method's permission.

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

The package ships with its generated stubs, so no code generation is required at install time.

License holders can also download a versioned tarball of this SDK (and the raw `.proto` schema bundle for building a client in any other language) from the Voltnir customer portal (see [voltnir.io](https://voltnir.io)). After extracting: `pip install ./voltnir-python-sdk-<version>`. Each artifact ships with a `.sha256` companion (`sha256sum -c`).

```
from voltnir_sdk import VoltnirClient, Side, OrderType

with VoltnirClient(host="localhost", port=3443, api_key="…") as client:
    me = client.get_me()
    print(me.username, list(me.permissions))

    contracts = client.list_contracts(area_id="10YBE----------2")
    first = contracts.contracts[0]

    ids = [int(first.contract_id)]
    for event in client.watch_contracts(areas=[first.area_id], contract_ids=ids):
        for contract in event.contracts:
            print(event.type, contract.last_price)
        break
```

TLS is opt-in; plaintext is the default. Streams have no per-call timeout; they live until the server closes or the client cancels.

<a id="health" name="health"></a>

## Health checking

The server carries the standard gRPC health checking service, `grpc.health.v1.Health` with `Check` and `Watch`, on the same port and under the same TLS as `VoltAPI`. It needs no metadata, so a Kubernetes `grpc` probe or `grpc_health_probe` works without a key. It is infrastructure, not an API operation: no permission applies, and it has no WebSocket peer. On REST the same two signals are [`GET /livez` and `GET /readyz`](rest_api_v1.md#probes).

| Service name | Status |
| --- | --- |
| `""` (empty: the server as a whole) | `SERVING` whenever the server answers. The liveness signal. |
| `voltnir.api.v1.VoltAPI` | `SERVING` while the gateway is operational (the `operational` flag on [`GetState`](#rpc-GetState)), `NOT_SERVING` otherwise: from start until the exchange login completes and the streams have synchronised, and during any exchange outage or maintenance. The trading kill switch does not affect it. The readiness signal. |
| any other name | `Check` fails with `NOT_FOUND`; `Watch` sends `SERVICE_UNKNOWN` and stays open, as the protocol specifies. |

- **`Watch`** sends the current status at once, then one message on each change, within one second of it. It ends when the gateway shuts down.
- **Nothing written, nothing charged.** A health call writes no audit event, is not counted against any key's request bound, and is not counted in `voltnir_client_requests_total`. It reads in-memory state only. An open `Watch` holds one stream and checks twice a second until the caller leaves or the gateway shuts down.
- **Nothing disclosed.** The status is all a health call returns. Why the gateway is not operational is on [`GetState`](#rpc-GetState) (`read_state`), in its `issues`.
- **No reflection.** The server registers `VoltAPI` and the health service and nothing else, so the schema is not published to an unauthenticated caller; tools such as `grpcurl` take it from `voltnir_api_v1.proto`.
- A `VoltAPI` RPC without metadata is still `UNAUTHENTICATED`; the health service opens no way around it.

> [!CAUTION]
> **Readiness is a monitoring signal, not a traffic gate.** One gateway serves one M7 login, so there is no second instance to send traffic to. Point a Kubernetes or load-balancer readiness check at the empty service name, and alert on `voltnir.api.v1.VoltAPI`. A readiness check on `voltnir.api.v1.VoltAPI` takes the gateway out of service during every exchange outage and maintenance window, which blacks out the trading terminal and the API exactly when the desk needs to see state and cancel orders.

#### Example (grpc_health_probe)

```bash
# liveness: the server as a whole
grpc_health_probe -addr gateway.example:3443
# readiness of the trading API
grpc_health_probe -addr gateway.example:3443 -service voltnir.api.v1.VoltAPI
# with TLS enabled on the gRPC port
grpc_health_probe -addr gateway.example:3443 -tls -tls-ca-cert ca.pem
```

`grpc_health_probe` exits `0` on `SERVING` and `4` on `NOT_SERVING`; a failed call, which an unknown service name is, exits `3`.

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

The RPC fails with status `PERMISSION_DENIED`, and the denial is recorded as a `permission_denied` audit event.

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

Integer fixed-point on the wire, no floating-point, identical to REST. The full unit table lives on the [REST page](rest_api_v1.md#units); below is the short version every gRPC integrator hits.

#### <a id="units" name="units"></a>Units and sentinels

| Field | Wire type | Unit | Sentinel for "absent" |
| --- | --- | --- | --- |
| `price` | `sint64` | Cents (CCY/MWh × 100); may be negative | N/A, required where used |
| `quantity` | `uint32` | Sub-MW (MW × 1000) | N/A, required > 0 on submit |
| `display_qty` / `hidden_quantity` | `uint32` | Sub-MW | `0` |
| `contract_id` (orders / trades) | `int64` | M7 numeric ID | `0` |
| `contract_id` (contract / watch) | `string` | M7 string ID | `""` |
| RFC 3339 timestamps | `string` | none | `""` |
| Unix-ms timestamps | `int64` | UTC | `0` |
| `Contract.ref_px_cents` | `optional sint64` | Cents (CCY/MWh × 100); may be negative | field not present |

> [!NOTE]
> `order_type` accepts `REGULAR`, `BLOCK`, `ICEBERG`, `BALANCE`, `PRE_ARRANGED`, `EXCHANGE_PRE_ARRANGED` on submit. `STOP`, `PRIVATE`, and `UNKNOWN_TYPE` are read-only values and are rejected with `INVALID_ARGUMENT`.

#### Timestamps and IDs

Two timestamp shapes cross the wire: RFC 3339 strings (for example `2026-04-16T22:00:00Z`), with `""` as the absent sentinel, and Unix-millisecond integers (UTC), with `0` as absent. Order and trade contract ids are `int64` M7 numeric ids (`0` absent); contract and watch ids are `string` (`""` absent). A `client_order_id` is a UUID string you supply or the gateway generates.

#### Pagination

The audit and report reads are cursor-paged. Pass `limit` (`0` means the default of 50, capped at 200) and read `next_cursor` from the response; an empty `next_cursor` is the last page. Feed it back as `cursor` on the next call. A date window filters on the delivery basis and orders the page accordingly, so a just-executed row can fall outside page one of a windowed query. An empty string field is unset, as on REST and WS: an empty `area` filters nothing and an empty `date_from` sets no bound.

<a id="ops-orders" name="ops-orders"></a>

## Orders

### <a id="rpc-SubmitOrder" name="rpc-SubmitOrder"></a>`Unary` `rpc SubmitOrder`

Submit a new order to the exchange.

**Required permission:** `create_order`. `bypass_member_check`, `trade_global` widens the result. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `side` | `Side` enum | none | Yes | `Side.BUY` or `Side.SELL`. |
| `price` | `sint64` | cents (CCY/MWh × 100) | Yes | Cents/MWh (may be negative). |
| `quantity` | `uint32` | sub-MW (MW × 1000) | Yes | Sub-MW. Must be > 0. |
| `delivery_area_id` | `string` | none | Yes | EIC area code, exactly 16 characters (e.g. `10YNL----------L`). Any other length is refused with `INVALID_ARGUMENT` before anything is sent. Only the length is checked: whether a 16-character code names an area you trade is the exchange’s call. |
| `contract_id` | `int64` | none | Cond* | M7 contract id. Either this OR `product`+`delivery_start`. |
| `product` | `string` | none | Cond* | Product code (e.g. `"H"`), used with `delivery_start`. |
| `delivery_start` | `string` | RFC 3339 | Cond* | Used with `product` to look up the contract. Any RFC 3339 instant: `2026-10-25T00:00:00Z`, `2026-10-25T00:00:00.000Z` and `2026-10-25T02:00:00+02:00` name the same contract. The doubled hour of a clock change is two instants: on 2026-10-25, 02:00 CEST is `00:00Z` (hour `02A`) and 02:00 CET is `01:00Z` (hour `02B`). |
| `delivery_end` | `string` | RFC 3339 | No | Creates a user-defined block over `[delivery_start, delivery_end)`; `""` == not a block create. Only with `order_type` `BLOCK`, `product` and `delivery_start`, and `contract_id` 0; anywhere else it is `INVALID_ARGUMENT` (`BLOCK_DELIVERY_END_INVALID`). The rules are those of REST [POST /order](rest_api_v1.md#post-order), *User-defined blocks*: the window is covered end to end by at least two consecutive contracts of the product in the area and no more than its `blockMaximumHours`, and the order takes `AON` or `FOK`. Until the exchange names the block’s contract the pending order carries a gateway placeholder `contract_id` (250 and above). |
| `order_type` | `OrderType` | none | No | Default `REGULAR`. |
| `exe_restriction` | `ExeRestriction` | none | No | Default `NON`. Options: `NON`, `FOK`, `IOC`, `AON`. **`FOK`/`IOC` require `validity_res` = `VALIDITY_NON`**; leaving the `GFS` default returns `INVALID_ARGUMENT`. |
| `validity_res` | `ValidityRes` | none | No | Default `GFS`. Options: `GFS`, `GTD`, `VALIDITY_NON`. Must be `VALIDITY_NON` when `exe_restriction` is `FOK` or `IOC`. |
| `entry_state` | `string` | none | No | Default `"ACTI"`. Use `"HIBE"` to submit hibernated. Refused on a `PRE_ARRANGED` order. |
| `display_qty` | `uint32` | sub-MW (MW × 1000) | Cond | Required for iceberg orders, and rejected on any other order type. Must be < `quantity`. |
| `validity_date` | `string` | RFC 3339 | Cond | An RFC 3339 instant, e.g. `2026-10-25T01:30:00Z`, in the form the exchange’s schema takes: an uppercase `T` and `Z`, seconds up to 59, and an offset within ±14:00, which is forwarded unchanged; a space for the `T`, a lowercase `t` or `z` and a leap second are refused; the exchange works in UTC, so send `Z`; the exchange GUI’s `02:30A` form is refused. Required when `validity_res` = `GTD`. |
| `pre_arranged_acct` | `string` | none | Cond | Required when `order_type` = `PRE_ARRANGED`. 1-32 printable ASCII characters without spaces, quotes, angle brackets or `&`; anything else is refused. |
| `v_member_short_id` | `string` | none | No | Virtual member tag. `""` submits an untagged House order, which requires `trade_global`; a caller without it gets `INVALID_ARGUMENT` and must name one of its members. |
| `client_order_id` | `string` | none | No | Optional idempotency key (must be a UUID); `""` → the gateway generates one. Reusing one the gateway still holds is rejected (`INVALID_ARGUMENT`); see *Reusing a `client_order_id`* below. |
| `ack_only` | `bool` | none | No | Default `false` waits for the exchange's outcome. `true` returns as soon as the exchange acknowledges receipt (`state == PENDING`). See *Receipt vs. outcome* below. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `client_order_id` | `string` | none | yes | The order's idempotency key, the one you supplied or the UUID the gateway generated. |
| `state` | `OrderState` | none | yes | The post-acknowledgement order state, one of PENDING, ACTIVE, INACTIVE, HIBERNATED or REJECTED. |
| `reason` | `string` | none | yes | The exchange's rejection text when state is REJECTED, otherwise empty. |

> [!NOTE]
> `order_type` accepts `REGULAR`, `BLOCK`, `ICEBERG`, `BALANCE`, `PRE_ARRANGED`, `EXCHANGE_PRE_ARRANGED` on submit. `STOP`, `PRIVATE`, and `UNKNOWN_TYPE` are read-only values and are rejected with `INVALID_ARGUMENT`.

> [!CAUTION]
> A submitted `PRE_ARRANGED` order reads back as `EXCHANGE_PRE_ARRANGED`; the domain stores a single pre-arranged kind. Don't compare submitted vs returned `order_type` for equality.

`SubmitOrderResponse { client_order_id, state, reason, err_code }`: `state` is one of `PENDING`, `ACTIVE`, `INACTIVE`, `HIBERNATED`, `REJECTED`; `REJECTED` always carries a `reason` string, and `err_code` the exchange’s numeric code when the refusal carried one (`0` otherwise). A refusal that names no order is answered at once too: the exchange answers the request the order was sent under. Note an **exchange-side rejection is a successful RPC** (OK with `state = REJECTED`), unlike REST which returns HTTP 422 for the same case; the status-code mapping table above covers gateway-side errors only.

**Receipt vs. outcome (`ack_only`).** By default a new order waits for the exchange's outcome: the confirming execution report (*confirmed*, a settled `state`) or the exchange's refusal (*rejected*, `state == REJECTED`). Setting `ack_only = true` returns as soon as the exchange acknowledges receipt (*acknowledged*, `state == PENDING`, received, outcome not yet known); the same `PENDING` is returned when a waited call's outcome does not arrive inside the order outcome timeout. An `ack_only` caller manages the order lifecycle itself and follows `WatchOrders` for the resulting state or a later refusal. Identical on REST `POST /order` (202) and the WebSocket `new_order` command.

**Product parameters and gate closure.** Price and size are measured against the parameters the exchange publishes for the contract’s product, the minimum price increment, the price bounds, the quantity increment, the quantity bounds and the minimum iceberg peak, and against the contract’s own trading state in the delivery area, before anything is sent. An order that breaks one is refused with `INVALID_ARGUMENT` naming the bound (`"price must be a multiple of the product tick size of …"`, `"quantity is above the product maximum of … MW"`, `"the contract’s trading session has closed in this delivery area"` and the rest), rather than costing a round trip and returning as an exchange rejection that still counts a full order-management transaction. The bounds are the exchange’s own, read off its product reference data rather than transcribed, so a market’s tick, increment and closing rule are always the current ones. Nothing is enforced that the exchange has not published: a contract or a product no report has named yet is left to the exchange to judge, so a late report never costs a legitimate order. Gate closure is read from the contract’s published trading-phase end, which is where a market’s “60 minutes before delivery in XBID, 30 nationally, 5 in a local TSO area” already lives, with a two-second tolerance for clock differences, so the last seconds before closure are never refused early. The same check applies your member’s own order limit, the largest single-order quantity the exchange sets for your member on the product: an order above it, an iceberg measured on its full size, is refused with `"quantity is above the member order limit of … MW"`, after the product bounds. A product with no member limit reported is left to the exchange. Identical on REST `POST /order` and the WebSocket `new_order` command.

**Product decimal scale.** Every price and quantity that crosses to the exchange is converted through the contract’s product decimal scale (`Product.dec_shft_px` / `dec_shft_qty`), so an order on a product whose scale is not usable is refused before anything is sent, with a specific status: `UNAVAILABLE` (message names the product and that a parameter inquiry has been issued) when the scale is not yet recorded, a transient login prerequisite, safe to retry once it lands, and `FAILED_PRECONDITION` when M7 published a scale or quantity unit this gateway cannot denominate (trading the product is refused until M7 changes it). A price or size that is a valid gateway integer but is not exactly expressible on the product’s own M7 grid is an `INVALID_ARGUMENT` naming the scale, not a scale fault. For the products in service every scale is the gateway’s own (2, 3, MW), so the conversion is the identity and none of these arise. Identical on REST and WS.

**Request expiry.** Every request that adds exposure, a new order, an amendment and an activation, is sent to the exchange with an expiry of `system.order_request_expiration_ms` (10 seconds by default). The exchange drops such a request when it has not taken it off its queue within the expiry, and drops one it took off the queue but had not processed within the expiry again, so a request is executed within twice the expiry of reaching the exchange, or never: a request the exchange cannot process in time is dropped, not executed late. A cancel (`CancelOrder`), cancel-all and a deactivation carry no expiry of their own and keep the exchange’s 45-second default: they only remove exposure, and a dropped cancel would leave an order live exactly when the exchange is backlogged.

**After a `DEADLINE_EXCEEDED`.** The order keeps counting against your position and cash limits until the exchange answers it with its execution report or its refusal. Without an answer it is released at its **expiry bound**, measured from when the gateway sent it: twice the request expiry plus 5 seconds (25 seconds by default), or, for an order in a delivery area coupled to XBID, twice the expiry plus 25 seconds (45 seconds by default), because the exchange may wait another 20 seconds for XBID’s answer. `system.pending_order_reap_age_ms` can only lengthen that wait. The release needs one more certainty, that no answer can have been missed: the exchange’s order feed has been continuously connected since the order was sent. An acknowledgement of receipt changes nothing either way: the exchange may omit it for an order it processed, and may lose an order it acknowledged. That release is recorded on `WatchMessages` and in the audit log as an `order_rejected` event from the `order_reaper` component.

**If that certainty is not available**, because the order feed dropped or gapped since the order was sent, the order is **held, not released**. It goes on consuming both limits and is reported once on `WatchMessages`, because the gateway cannot rule out that it is resting at the exchange. It is settled by the first order snapshot taken after its bound, which arrives when the gateway next resubscribes to the exchange’s order feed: if the snapshot carries it, it becomes a normal live order; if not, it is released then, because it can no longer land. A snapshot taken before the bound settles only the orders it carries. An order in an XBID-coupled area is held until its own execution report or refusal, or a restart, when the exchange warned that XBID has not answered it (error 1142), or when the gateway’s connection to the exchange’s message feed reset since it was sent, so such a warning may have been lost: the exchange documents no bound on XBID’s answer. Any held order is released at the latest about an hour after its contract’s delivery ends, when no market still trades the contract; the release is reported on `WatchMessages`, and an exchange report that still arrives for it counts the order again. The number and size of held orders are on the status aggregate (`stranded_pending_count`, `stranded_pending_qty`). `Restart` restarts the process, which releases every held order and rebuilds the order book from the exchange’s own snapshot.

**Reusing a `client_order_id`.** A key is refused for as long as the gateway holds a record of the order it named, whatever that order’s state. A key held by a pending order (including one a `DEADLINE_EXCEEDED` left counting), by a resting, hibernated, filled or deleted order, or by an order the exchange rejected is refused with `INVALID_ARGUMENT` (`"client_order_id '…' is already in use"`). A key whose submission was written off after a `DEADLINE_EXCEEDED`, released as described above, or released by a snapshot that did not carry a held order, is **retired** and refused with `INVALID_ARGUMENT` (`"client_order_id '…' was reclaimed after no exchange acknowledgement; use a new id"`): the written-off order may still be resting at the exchange, and a late report carrying that id must not attach to a different order. If such a report does arrive, the order is confirmed under its own id, its exposure counts again, the event is recorded on `WatchMessages`, and from then on the key is `already in use`. Retry a timed-out submission with a **new** id. Two keys are free at once: one whose request the gateway refused before sending it to the exchange, and one whose only record is a `NOT_PROCESSED` rejection, which the resubmission replaces.

**How long a key is held.** The record lives in the gateway’s memory, not in the database, so a held key becomes free again when the record goes: when the order has finished and its contract has been swept from the gateway, about an hour after its delivery end (an order still live at the exchange then keeps its record until it finishes, and goes on the next sweep after that), or when the gateway resubscribes to the exchange’s order feed (a restart does too), because the records are then rebuilt from the exchange’s snapshot, which carries only the orders still on the market, the keys of filled and deleted orders are free from that point. An order the exchange rejected was never on its book, so the snapshot does not drop it: its key stays held, and the lookup still answers it `REJECTED` with the exchange’s reason, until the sweep, or until a restart for an order on a contract the gateway never listed, such as a refused new block order, which the sweep does not reach. A pending order’s key and a retired key survive a resubscription and are dropped by a restart; a retired key also survives the sweep, and the 10,000 most recent are remembered. The refusal guards against two orders under one key; it is not a history of every key ever used, so do not reuse a key on purpose except after `NOT_PROCESSED`.

Specify the contract either by `contract_id` (numeric, int64) or by `product` + `delivery_start`, or create a user-defined block with `product` + `delivery_start` + `delivery_end`. Returns the post-ack state. Rejected with `FAILED_PRECONDITION` when the operator kill-switch is engaged (`set_trading_allowed(allowed=False)`).

#### Errors

| gRPC status | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `create_order`. |
| `INVALID_ARGUMENT` | An unknown or output-only enum value, an empty delivery_area_id (`delivery_area_id is required`) or one that is not 16 characters (`delivery_area_id must be a 16-character EIC code`), an iceberg without a valid display_qty, FOK or IOC without validity_res VALIDITY_NON, a validity_date not in the form the exchange’s schema takes (`validity_date must be an RFC 3339 timestamp written as 2026-09-22T16:00:00Z or 2026-09-22T18:00:00+02:00`), a pre_arranged_acct outside the printable-ASCII class (or with spaces, quotes, angle brackets or &), a PRE_ARRANGED order entered with entry_state HIBE (`a pre-arranged order cannot be entered hibernated`), a delivery_start that is not an RFC 3339 timestamp (`delivery_start must be an RFC 3339 timestamp, e.g. 2026-10-25T00:00:00Z`), a price or size off the product grid, or a client_order_id already in use. Block orders: `BLOCK_DELIVERY_END_INVALID` (a `delivery_end` outside a block create), `BLOCK_RESTRICTION_NON` (a block order with `NON`) and `BLOCK_WINDOW_TOO_SHORT` (a window of fewer than two contracts), each leading the message. |
| `NOT_FOUND` | The contract named by product and delivery_start does not exist. |
| `FAILED_PRECONDITION` | Trading is disabled, the position limit, the slot position limit or a cash-pool bound would be exceeded, a window the slot position limit needs cannot be placed (the message starts `slot window unknown:`), a self-cross is blocked, or the exchange load guard refuses. A slot refusal is worded for the caller: one without `read_status`, which cannot see the House limit elsewhere, is told `slot position limit exceeded: refused by the desk slot limit, <area> <slot start> to <slot end>, <long\|short> side` for the House slot limit and `slot window unknown: a trade in <area> has no delivery time` for a trade with no window, with no House figure and no trade id; a refusal by the member's own slot limit keeps the member's figures, and the `order_rejected` audit row carries every field either way. |
| `FAILED_PRECONDITION` | Message `CONTRACT_IN_DELIVERY: contract … in … has reached its delivery start and takes no order that adds exposure`: the contract has reached its delivery start on the gateway’s clock. Refused before anything reaches M7, whatever state the exchange still lists the contract in; on the production markets the exchange’s published gate-closure parameters close trading at or before the delivery start, so there this refuses nothing the exchange would still take. The refusal does not depend on the exchange refusing such an order, and applies as well in a test environment that still accepts one after the delivery start. Not transient. Orders already resting on it stay listed by [`list_orders`](#rpc-ListOrders) and are cancelled with [`cancel_order`](#rpc-CancelOrder). |
| `FAILED_PRECONDITION` | Message `MEMBER_AREA_NOT_ALLOWED: member … may not trade delivery area …`: the order is tagged with a member whose [delivery areas](#rpc-GetMyMembers) do not include `delivery_area_id`, for every caller, `bypass_member_check` included; a block and a pre-arranged order alike. Refused before anything reaches M7. Not transient. |
| `FAILED_PRECONDITION` | Block orders, the code leading the message: `BLOCK_SWEEP_UNSUPPORTED` (a block with `IOC`, a market sweep, not supported), `BLOCK_NOT_SUPPORTED` (the product’s settings take no user-defined blocks), `BLOCK_WINDOW_NOT_CONTIGUOUS` (the window is not covered end to end by consecutive contracts of the product in the area’s catalogue) and `BLOCK_WINDOW_TOO_LONG` (more than the product’s `blockMaximumHours`). |
| `DEADLINE_EXCEEDED` | The exchange did not acknowledge within the acknowledgement timeout; the outcome is unknown. |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
from voltnir_sdk import OrderType, Side, ValidityRes, new_client_order_id

order_id = new_client_order_id()     # store it first: it is your recovery key
resp = client.submit_order(
    client_order_id=order_id,
    side=Side.BUY,
    price_cents=5000,            # 50.00 EUR/MWh
    quantity_sub_mw=1000,        # 1.0 MW
    delivery_area_id="10YNL----------L",
    product="H",
    delivery_start="2026-04-20T22:00:00Z",
    order_type=OrderType.REGULAR,
    validity_res=ValidityRes.GFS,
)
print(resp.client_order_id, resp.state)
```

### <a id="rpc-ModifyOrder" name="rpc-ModifyOrder"></a>`Unary` `rpc ModifyOrder`

Modify, activate, or deactivate (hibernate) an existing order.

**Required permission:** `modify_order`. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `client_order_id` | `string` | none | Yes | UUID of the order to modify. |
| `action` | `ModifyAction` | none | No | Default `MODIFY`. Options: `MODIFY`, `ACTIVATE`, `DEACTIVATE`. |
| `price` | `Int64Value` | cents (CCY/MWh × 100) | Cond | Required when `action` = `MODIFY`. Cents. |
| `quantity` | `UInt32Value` | sub-MW (MW × 1000) | Cond | Required when `action` = `MODIFY`, and must be greater than zero. Sub-MW. |
| `display_qty` | `uint32` | sub-MW (MW × 1000) | No | Iceberg display quantity. Sub-MW. |
| `validity_res` | `ValidityRes` | none | No | Optional change to validity restriction. |
| `validity_date` | `string` | RFC 3339 | Cond | An RFC 3339 instant, e.g. `2026-10-25T01:30:00Z`, in the form the exchange’s schema takes: an uppercase `T` and `Z`, seconds up to 59, and an offset within ±14:00, which is forwarded unchanged; a space for the `T`, a lowercase `t` or `z` and a leap second are refused; the exchange works in UTC, so send `Z`; the exchange GUI’s `02:30A` form is refused. Required when `validity_res` = `GTD`. |
| `v_member_short_id` | `string` | none | No | Virtual member tag. May only restate the order's own member; a different one returns `NotFound`. Leave empty and the order keeps the member it has. |
| `ack_only` | `bool` | none | No | Default `false` waits for the exchange's outcome. `true` returns as soon as the exchange acknowledges receipt (`outcome == ACKNOWLEDGED`). See *Receipt vs. outcome* below. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `outcome` | `Outcome` | none | yes | CONFIRMED when the confirming execution report arrived inside the outcome window, ACKNOWLEDGED when only the receipt did or ack_only was set. |

**Member isolation.** Beyond the `modify_order` capability, the caller must be authorized to act on the existing order's member (assigned / `bypass_member_check`; house orders need `trade_global`). `read_orders` grants visibility, not the right to act. An order outside that scope returns `NotFound` (identical to a missing one), so a desk cannot modify or re-tag another member's order. An order's member is fixed for its life: `v_member_short_id` may only restate the member the order already carries, and naming a different one, or naming any member on an untagged house order, returns the same `NotFound`. Every action carries the tag through, `MODIFY`, `ACTIVATE` and `DEACTIVATE` all re-send the order's own text, because the exchange re-creates an order on an amendment and does not define what an omitted text field leaves behind. That text is never poorer than the one the order already holds: the delivery duration, delivery start and product it was entered with ride along even when the contract is no longer in the gateway's own order book, so a quarter-hour leg cannot come back looking like an hour.

> [!CAUTION]
> An unset `action` field is `MODIFY_UNSPECIFIED` (the proto3 zero value), which the server treats as `MODIFY`. Always set `action` explicitly.

**An order keeps its execution restriction.** The exchange re-creates an order on every amendment and reads an amendment that names no restriction as `non`, which it refuses on a block. So every action, a re-price, a resize, an activation and a hibernation, restates the order’s own type and execution restriction as the exchange last reported it, or all-or-none for a block whose report names none: a block goes out as a block with its `aon` or `fok`, and an order without a restriction is sent exactly as before. A modify cannot change the restriction; to change it, cancel and re-enter.

> [!CAUTION]
> **One modify at a time, and the conflict clears itself** (gates `CancelOrder` too). While a modify is in flight, a second `ModifyOrder` on the same `client_order_id` fails `ABORTED` "modify already in progress" and a `CancelOrder` fails `ABORTED` "modify in progress, retry after confirmation": the exchange replaces an order on modify, so a second command dispatched in that window would target an order id that no longer exists. The lock is released by the exchange's execution report, and it expires on its own the order acknowledgement timeout + the order outcome timeout (the receipt wait and the outcome wait together: 5s by default, floored at 1s) after it was taken, a moment before the command reaches the exchange, so it lapses a moment before the modify's own waits do, by design. An execution report that never arrives therefore costs one such window, not the order, retry after it and the next modify takes the lock.

> [!WARNING]
> **A modify is a full pre-trade entry.** The exchange re-creates an order on every amendment, so `MODIFY` and `ACTIVATE` both run the whole gate, position limits (House and member), slot position limits, cash limits, and self-trade prevention, with the same rejections as [`submit_order`](#rpc-SubmitOrder), and can be refused. For a live order the gate measures the *change*: it is checked on the price and quantity the order will carry, against sums that already contain the order being amended, so a reprice or resize that lowers exposure always passes. The exposure an admitted amendment adds, a larger size or a costlier price, and the whole returning size of an activation, count against your limits from the moment it is sent until the exchange's answer settles it, so two amendments sent at once cannot both spend the same room. An amendment that lowers exposure frees nothing until the exchange confirms it. Self-trade prevention is checked at the new price, and an order is never treated as crossing itself. It also sees where your other orders are *going*: an amendment to an order *on the book*, already sent to the exchange but not yet confirmed, is measured at both the price it rests at and the price it is moving to, so two amendments in flight at once cannot cross each other, and neither can slip through on a price the other has not committed to yet. That second reading is dropped as soon as the exchange settles the amendment, or after the same window as the modify lock if no answer arrives. Only orders that can actually fill are counted, and the check never refuses an amendment that can only shrink a cross: an amendment that takes no more size and does not move the price toward the other side is admitted even when the order is already crossing, so a desk is never trapped in a self-cross it is reducing. A hibernated order holds no exposure, the exchange releases its cash allocation and Voltnir excludes it from both sums, so it is off the book, is not a self-cross counterparty, and `ACTIVATE` is gated for the order's whole returning size (and is visible to other orders from the moment the activation is sent), while a `MODIFY` on an order that is already hibernated changes no live exposure, is not measured against the limits, is not made a self-cross counterparty by the amendment either, and is checked when it is activated instead. `DEACTIVATE` only removes exposure: it is never refused on a limit, and, like [`cancel_order`](#rpc-CancelOrder), it is not gated on the gateway being operational either, so the way out of the market stays open through an outage. It still awaits the exchange's receipt, so it never reports a hibernation the exchange did not take. The product’s own bounds apply too: a `MODIFY` restates a price and a size, so both face the product’s tick, increment, price and quantity bounds exactly as a [`submit_order`](#rpc-SubmitOrder) does, including on a hibernated order, because the amendment itself is what the exchange would refuse, and both `MODIFY` and `ACTIVATE` are refused on a contract the exchange has closed in that delivery area. Your member’s own order limit applies to a `MODIFY` the same way; an `ACTIVATE` brings back the size the exchange already accepted and is measured against neither.

`ModifyOrderResponse { Outcome outcome }`: `outcome` is `CONFIRMED` when the confirming execution report landed, or `ACKNOWLEDGED` when only the receipt did (or `ack_only`). `ABORTED` if M7 rejects it (e.g. the order was concurrently filled or deleted), `ABORTED` with an `ORDER_CHANGED:` message if the order's revision moved under the command (not applied; retry the same command), `UNAVAILABLE` with a `NOT_PROCESSED:` message if the exchange returns the request undelivered (definitely not applied), `DEADLINE_EXCEEDED` if no acknowledgement arrives within the order acknowledgement timeout (unknown, not failed). The resulting order state is delivered via `WatchOrder` / `WatchOrders`.

**Receipt vs. outcome (`ack_only`).** By default a modify waits for the exchange's outcome: the confirming execution report (*confirmed* → `outcome == CONFIRMED`) or the exchange's refusal (*rejected* → `ABORTED` carrying M7's words, with an `ORDER_CHANGED:` message when the order's revision moved under the command). A waited call is confirmed only on its own command's report: when two commands on the order are at the exchange at once and one report could be either's (a modify retried at the same revision), neither is confirmed on it. The one the exchange refuses is answered with that refusal, the other is then confirmed, and with no refusal on either command's correlation id inside the order outcome timeout both are answered *acknowledged*. Setting `ack_only = true` returns as soon as the exchange acknowledges receipt (*acknowledged* → `outcome == ACKNOWLEDGED`, received, outcome not yet known); the same *acknowledged* answer is returned when a waited call's outcome does not arrive inside the order outcome timeout. An `ack_only` caller manages the order lifecycle itself and follows `WatchOrders` for the resulting state or a later refusal. Identical on REST `PUT /order` (200/202) and the WebSocket `modify_order` command (`modified`/`acknowledged`). A modify on an order the exchange has not yet acknowledged, which a new order answered `ACKNOWLEDGED` may still be, is refused `ABORTED` with an `ORDER_PENDING:` message: retry once the order is acknowledged, or wait for it on `WatchOrder` / `WatchOrders`.

**Expiry and held headroom.** An amendment and an activation carry the request expiry described under `SubmitOrder`, and the exposure they add is released the same way as a pending order’s: at any time on the exchange’s answer (the command’s own execution report or refusal, a later revision of the order, or the order leaving the book), and without one only at the command’s expiry bound with the order feed continuously connected; otherwise it is held and reported once. An XBID timeout warning (error 1142) is not a refusal: the added exposure stays held until the command’s own report or a restart, and a caller still waiting is answered *acknowledged*, never a refusal. The number and size of these claims, and of the held ones, are on the status aggregate (`claims_count`, `claims_qty`, `claims_held_count`, `claims_held_qty`).

`price` / `quantity` use proto wrapper types: pass the value to change them, omit them otherwise. Rejected with `FAILED_PRECONDITION` when the operator kill-switch is engaged (`set_trading_allowed(allowed=False)`).

#### Errors

| gRPC status | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `modify_order`. |
| `INVALID_ARGUMENT` | action is MODIFY without a price or quantity, quantity is not greater than zero, or a validity_date not in the form the exchange’s schema takes (`validity_date must be an RFC 3339 timestamp written as 2026-09-22T16:00:00Z or 2026-09-22T18:00:00+02:00`). |
| `NOT_FOUND` | No open order with that client_order_id in the caller scope, or v_member_short_id names a different member. |
| `ABORTED` | A modify is already in progress, or the order changed at the exchange first (message prefixed ORDER_CHANGED). |
| `ABORTED` | Message `ORDER_PENDING: the order is accepted but not yet acknowledged by the exchange, so retry once it is`: the order was sent and the exchange has not yet acknowledged it, so there is no exchange order to modify; nothing was sent. Retry once it is acknowledged. A caller who may not act on the order’s member gets `NOT_FOUND` instead, as for an unknown order. |
| `FAILED_PRECONDITION` | Trading is disabled, or a limit or self-cross check refuses the new price or size. |
| `FAILED_PRECONDITION` | Message `CONTRACT_IN_DELIVERY: ...`: the contract has reached its delivery start on the gateway’s clock and the command adds exposure: `activate` (a re-entry at the exchange), or `modify` with a larger `quantity` or any new `price` (a delete and re-entry at M7). A shrink at the same price is not refused with this message, though like any `modify` it is refused `INVALID_ARGUMENT` (for example `the contract has expired`) once the exchange shows the contract closed. `deactivate` and a cancel are refused by neither. |
| `FAILED_PRECONDITION` | Message `MEMBER_AREA_NOT_ALLOWED: member … may not trade delivery area …`: the order belongs to a member whose [delivery areas](#rpc-GetMyMembers) no longer include the order’s area. Refused on every `action` (modify, activate, deactivate), for every caller. |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
from voltnir_sdk import ModifyAction

# Restate price + quantity (plain ints; the SDK does the wrapping)
client.modify_order(
    client_order_id="550e8400-e29b-41d4-a716-446655440000",
    action=ModifyAction.MODIFY,
    price_cents=5200,            # 52.00 EUR/MWh
    quantity_sub_mw=2000,        # 2.0 MW, what is left, not the original size
)

# Hibernate
client.modify_order(
    client_order_id="550e8400-e29b-41d4-a716-446655440000",
    action=ModifyAction.DEACTIVATE,
)
```

### <a id="rpc-CancelOrder" name="rpc-CancelOrder"></a>`Unary` `rpc CancelOrder`

Cancel a single resting order.

**Required permission:** `delete_order`. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `client_order_id` | `string` | none | Yes | UUID of the order to cancel. |
| `ack_only` | `bool` | none | No | Default `false` waits for the exchange's outcome. `true` returns as soon as the exchange acknowledges receipt (`outcome == ACKNOWLEDGED`). See *Receipt vs. outcome* below. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `outcome` | `Outcome` | none | yes | CONFIRMED when the deletion's execution report arrived inside the outcome window, ACKNOWLEDGED when only the receipt did or ack_only was set. |

**Member isolation.** Beyond the `delete_order` capability, the caller must be authorized to act on the order's member (assigned / `bypass_member_check`; house orders need `trade_global`). An order outside that scope returns `NotFound`, identical to a missing one.

`CancelOrderResponse { Outcome outcome }`: `outcome` is `CONFIRMED` when the deletion's execution report landed, or `ACKNOWLEDGED` when only the receipt did (or `ack_only`). `ABORTED` if M7 rejects it (e.g. the order was concurrently filled or deleted), `ABORTED` with an `ORDER_CHANGED:` message if the order's revision moved under the cancel (not applied; retry the same cancel), `UNAVAILABLE` with a `NOT_PROCESSED:` message if the exchange returns the cancel undelivered (definitely not applied), `DEADLINE_EXCEEDED` if no acknowledgement arrives within the order acknowledgement timeout (unknown, not failed).

**Receipt vs. outcome (`ack_only`).** By default a cancel waits for the exchange's outcome: the deletion's execution report (*confirmed* → `outcome == CONFIRMED`) or the exchange's refusal (*rejected* → `ABORTED` carrying M7's words, with an `ORDER_CHANGED:` message when the order's revision moved under the command). A waited call is confirmed only on its own command's report: when two cancels of the order are at the exchange at once, the deletion's report could be either's, so neither is confirmed on it. The exchange deletes the order for one and refuses the other (M7 error 2014, order not found); the losing cancel is answered with that refusal, the other is then confirmed, and with no refusal on either command's correlation id inside the order outcome timeout both are answered *acknowledged*. Setting `ack_only = true` returns as soon as the exchange acknowledges receipt (*acknowledged* → `outcome == ACKNOWLEDGED`, received, outcome not yet known); the same *acknowledged* answer is returned when a waited call's outcome does not arrive inside the order outcome timeout. An `ack_only` caller manages the order lifecycle itself and follows `WatchOrders` for the resulting state or a later refusal. Identical on REST `DELETE /order` (200/202) and the WebSocket `delete_order` command (`cancelled`/`acknowledged`). A cancel of an order the exchange has not yet acknowledged, which a new order answered `ACKNOWLEDGED` may still be, is refused `ABORTED` with an `ORDER_PENDING:` message: retry once the order is acknowledged, or wait for it on `WatchOrder` / `WatchOrders`. A cancel carries no request expiry: it keeps the exchange’s 45-second default, so a cancel queued behind a backlog is still executed rather than dropped.

The order must be in `ACTIVE` or `HIBERNATED` state with no concurrent modify in flight. Not gated by the kill-switch: a cancel only reduces exposure, so it works even when trading is disabled.

#### Errors

| gRPC status | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `delete_order`. |
| `NOT_FOUND` | No open order with that client_order_id in the caller scope. |
| `ABORTED` | The order changed at the exchange before the cancel applied (message prefixed ORDER_CHANGED); it may already be gone. |
| `ABORTED` | Message prefixed `ORDER_PENDING:`: the order was sent and the exchange has not yet acknowledged it, so there is no exchange order to cancel; nothing was sent, and the order may rest once it is acknowledged. Retry the cancel then. A caller who may not act on the order’s member gets `NOT_FOUND` instead, as for an unknown order. |
| `FAILED_PRECONDITION` | Message `MEMBER_AREA_NOT_ALLOWED: member … may not trade delivery area …`: the order belongs to a member whose [delivery areas](#rpc-GetMyMembers) no longer include the order’s area. Refused for every caller; nothing was sent. `CancelAllOrders` skips such an order. |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
client.cancel_order(client_order_id="550e8400-e29b-41d4-a716-446655440000")
```

### <a id="rpc-CancelAllOrders" name="rpc-CancelAllOrders"></a>`Unary` `rpc CancelAllOrders`

Cancel every resting order the caller is authorized to act on.

**Required permission:** `delete_order`. (see [Permissions](#permissions))

#### Request

This RPC takes no request fields.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `deleted` | `uint32` | none | yes | Number of orders whose cancel the exchange acknowledged, counted on receipt rather than on each deletion's report. Account-wide: the login user's own active orders, pre-arranged ones included, when the command was sent. Member-scoped: the orders whose own cancel it acknowledged; a sweep it did not acknowledge in full is an error, not a smaller count. Mirrors the REST `{"deleted": n}` body. |

**Member isolation.** A full-authority caller (`bypass_member_check` + `trade_global`) cancels the whole account in one atomic exchange command. A member-scoped caller cancels only their members' orders, one per order; other desks' and (without `trade_global`) house orders are untouched. `read_orders` does not grant cancellation. Either arm acts only on orders this gateway's own login user placed, never a colleague's on the same membership, and the atomic arm's count is the login user's own orders, pre-arranged ones included, exactly what the exchange's blanket delete removes. `deleted` counts only orders this caller targeted.

**Member delivery areas.** A member-scoped sweep skips an order whose member may not trade the order’s area: it is neither cancelled nor counted as targeted. The account-wide cancel is one exchange command and pulls it with everything else.

> [!CAUTION]
> Also triggered automatically when `set_trading_allowed(allowed=False)` is invoked. Use deliberately. Not gated by the kill-switch: cancel-all only reduces exposure, so it works even when trading is disabled.

None.

`CancelAllOrdersResponse` with a `deleted` count, returned once M7 **acknowledges** the cancel: the account-wide cancel is one request and one receipt; a member-scoped cancel sends one cancel per order and awaits each receipt. It does not wait for each deletion’s execution report: the resulting order states arrive on `WatchOrders`. `deleted` is the number of orders whose cancel the exchange acknowledged: for the account-wide cancel, the login user’s own active orders, pre-arranged ones included, when the command was sent; for a member-scoped cancel, the orders whose own cancel it acknowledged. `ABORTED` on rejection, `UNAVAILABLE` with a `NOT_PROCESSED:` message when the exchange returns the cancel undelivered, `DEADLINE_EXCEEDED` on timeout.

**A member-scoped cancel succeeds only when the exchange acknowledges the cancel for every order it targeted.** If the exchange refuses one, or one cannot be sent because its product’s price scale is unknown or unsupported, the cancel still goes out for every other order and the request then fails. If the route to the exchange fails, no receipt in time, the request returned undelivered, the publish failed, or load management refused the cancel because the exchange has the member order-restricted, it stops at that order. Either way the error carries that failure’s own status, so a refusal is `ABORTED`, and its message ends with the counts, for example `(cancel-all incomplete: the exchange acknowledged the cancel for 2 of 3 targeted orders; 1 may still be resting)`. The account-wide cancel is one exchange command with no partial outcome, so its errors carry no counts.

**An order not yet acknowledged leaves a member-scoped cancel incomplete.** One of the caller’s orders that the exchange has not yet acknowledged has no exchange order id to cancel by. The cancel still goes out for every acknowledged order, and the call then fails `ABORTED` with an `ORDER_PENDING:` message, with that order counted as targeted and not acknowledged, for example `ORDER_PENDING: … (cancel-all incomplete: the exchange acknowledged the cancel for 1 of 2 targeted orders; 1 may still be resting)`. Call it again once the order is acknowledged. A refusal of one of the acknowledged orders stays the error’s cause, and the counts still include the unacknowledged order. Another desk’s unacknowledged order does not count. The account-wide cancel is unchanged.

#### Errors

| gRPC status | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `delete_order`. |
| `UNAVAILABLE` | The exchange did not acknowledge every cancel in the sweep. |
| `ABORTED` | Message prefixed `ORDER_PENDING:` and ending with the counts: a member-scoped sweep met one or more of the caller’s orders the exchange has not yet acknowledged; every other order’s cancel went out. Call it again once they are acknowledged. |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
resp = client.cancel_all_orders()
print(resp.deleted, "orders whose cancel the exchange acknowledged")
```

### <a id="rpc-SubmitBasket" name="rpc-SubmitBasket"></a>`Unary` `rpc SubmitBasket`

Enter 1 to 100 orders as one exchange order entry under one list instruction. Mirrors REST `POST /basket`.

**Required permission:** `create_order`. (see [Permissions](#permissions))

#### Request

`SubmitBasketRequest`: `basket_ref` (string UUID, `""` has the gateway mint one), `list_exec_inst` (`"none"`, `"valid"` or `"linked"`) and `orders` (1 to 100 [`SubmitOrderRequest`](#rpc-SubmitOrder)).

- `none`: the exchange validates and processes each order on its own.
- `valid`: every order must pass the exchange’s entry validation or the whole list is rejected; accepted orders then rest independently.
- `linked`: every order must be `fok` (with validity `non`); the list executes whole or the exchange deletes it whole, and its orders never match each other. All orders must be on local products or all on remote products; different products may be mixed.

**All or none at the gateway.** Every order is checked before anything is sent, with the checks a single order takes: the field rules, member and delivery area, the contract and its product’s bounds, position, slot and cash limits and the self-cross policy. Every order is evaluated, and one failure refuses the whole basket with `BASKET_REFUSED`, whose message lists each failing order as `[<index>] <CODE>: <text>` joined by `"; "`. Nothing reaches the exchange then. A field the single-order validator refuses keeps its own code, with the order’s index leading its message. A `none` or `valid` basket is checked as if its orders were entered one after another, so a later order sees the earlier ones resting and an order crossing an earlier one meets the self-cross policy, because the exchange matches them. A `linked` basket fills whole or not at all, so position and slot limits are checked on its net effect: an hourly buy and the four quarter-hour sells of that hour, of equal size, move no slot. Its cash is the sum of each order’s own requirement, because the exchange checks cash per order, and the self-cross scan passes over its own orders, which cannot match each other, but sees every other order of the desk.

**Load management.** A basket spends one order transaction per order. One that would take the member past the gateway’s throttling threshold is refused whole and spends nothing.

**The basket reference.** `basket_ref` is a UUID idempotency key; leave it out and the gateway mints one. Every order of the basket carries it as `basket_ref` on the order views, read back from the order’s own text, so it survives a gateway restart. Whether the orders do is the exchange's decision: it may delete every order of a basket when the gateway logs out or disconnects, a restart included, although on the exchange's simulator it kept them through a restart. The gateway shows what the exchange reports afterwards. A reference the gateway still holds a basket under is refused `BASKET_REF_IN_USE`. Each order may carry its own `client_order_id`; two orders under one id are refused. A basket always waits for its outcomes, so an order’s `ack_only` is not read. A block create (`delivery_end`) is refused; join an existing block by its `contract_id`.

#### Response

`SubmitBasketResponse`: `basket_ref`, `list_exec_inst`, `basket_id` (`uint64`, 0 when the exchange reported none) and `orders`, one `SubmitOrderResponse` per order in request order.

**The answer** lists each order’s outcome in request order with the fields a single submit answers. It waits for every order’s outcome, within the order acknowledgement window and then the outcome window; an order without one is `PENDING`. The exchange’s rejection of a `valid` list, the kill of a `linked` list and the refusal of single orders are each order’s `state` and `err_code`, never an error. The exchange rejects a `valid` or `linked` list whole, so when it refuses one, every order of the list is answered `REJECTED`, an order the refusal did not name with the refusal’s own `reason` and `err_code`; a refusal naming some orders of a `none` list rejects those alone. `basket_id` is the exchange’s own id, reported only for a basket of two or more orders.

#### Errors

| gRPC status | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `create_order`. |
| `INVALID_ARGUMENT` | An order the single-order validator refuses, its index leading the message; or `list_exec_inst must be one of none, valid, linked`. |
| `INVALID_ARGUMENT` | Message `BASKET_EMPTY: …`. The basket carries no order. |
| `INVALID_ARGUMENT` | Message `BASKET_TOO_LARGE: …`. The basket carries more than 100 orders. |
| `INVALID_ARGUMENT` | Message `BASKET_LINKED_REQUIRES_FOK: …`. A `linked` basket with an order that is not `fok`; the message names it. |
| `INVALID_ARGUMENT` | Message `BASKET_DUPLICATE_ORDER_ID: …`. Two orders under one `client_order_id`. |
| `INVALID_ARGUMENT` | Message `BASKET_BLOCK_UNSUPPORTED: …`. An order would create a user-defined block. |
| `INVALID_ARGUMENT` | Message `BASKET_REF_IN_USE: …`. The gateway still holds a basket under this `basket_ref`. |
| `FAILED_PRECONDITION` | Message `BASKET_LINKED_NOT_SUPPORTED: …`. A `linked` basket on a product that publishes `linked_order_product` false. |
| `FAILED_PRECONDITION` | Message `BASKET_REFUSED: …`. One or more orders failed an admission check; each is listed with its own code. |
| `UNAVAILABLE` | Message `NOT_PROCESSED: …`: the exchange handed the basket back undelivered; safe to resubmit. |

### <a id="rpc-CancelBasket" name="rpc-CancelBasket"></a>`Unary` `rpc CancelBasket`

Cancel every resting order of one basket that the caller may act on: the login user’s own orders in the caller’s member scope. One cancel per order, each awaiting the exchange’s receipt, never a multi-order request. A basket with no order the caller may act on is not found. A cancel only takes exposure off, so load management never refuses it for headroom; while the exchange has the member restricted it is refused, as a single cancel is.

**Required permission:** `delete_order`. (see [Permissions](#permissions))

#### Request

`CancelBasketRequest`: `basket_ref`.

#### Response

`CancelBasketResponse`: `basket_ref`, `cancelled` (`uint32`) and `orders`, one `BasketCancelResult` per resting order: `client_order_id`, `cancelled`, and when not cancelled the `code` and `error` it was refused with (`""` otherwise).

An order-level refusal is reported on that order and the next is tried. A failure of the route to the exchange stops the cancel: before any cancel was acknowledged it is the call’s error, as for a single cancel; after one, it is reported on every order not yet cancelled. An order the exchange has not yet acknowledged is reported `ORDER_PENDING`. `cancelled` counts acknowledged cancels, not confirmed deletions.

#### Errors

| gRPC status | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `delete_order`. |
| `NOT_FOUND` | Message `BASKET_NOT_FOUND: …`: no order of the basket is held for this caller. |
| `FAILED_PRECONDITION` | The exchange has the member order-restricted, so load management refused the first cancel. |

### <a id="rpc-RecallTrade" name="rpc-RecallTrade"></a>`Unary` `rpc RecallTrade`

Ask the exchange to recall an executed trade (a mistrade), or every recallable trade of one order. Mirrors REST `POST /api/v1/trade/recall` and the WebSocket `recall_trade` command, with the same fields, codes and statuses.

**Required permission:** `recall_trade`. (see [Permissions](#permissions))

**Whose trade.** Only a trade this gateway's exchange login placed can be recalled, and only for a member you may act on: a member you are assigned to (or any member with `bypass_member_check`); a House trade needs `trade_global`. A trade placed by another exchange user on your balancing group, which the exchange reports to your login too, is refused as not your own. A trade you cannot see, or one of a member you may not act on, is not found.

**The exchange's rules, not the gateway's.** The exchange accepts a recall only within its windows: a trade can be recalled within 5 minutes of its execution (error 2013 after that), not too close to its delivery (2012, 3007), not below its turnover floor (3008), and never for an auction (3009) or OTC trade (3017); a trade already recalled, rejected, granted or requested is refused too (3001, 3004, 3005, 3006). The gateway applies none of these windows: it forwards the request and reports the exchange's refusal with its code. It refuses only a trade that is not `ACTI` and a `revision_no` it has seen move on. Market operations decide a recall that was accepted; the decision arrives later as the trade's new state, `RGRA` (granted, the trade is reversed) or `RREJ` (rejected, the trade stands).

**Cascade.** A cross-contract trade carries a `parent_trade_id`, and recalling it recalls every trade with the same parent at once. A recall by `client_order_id` therefore sends one request per parent; the other trades of that parent follow it: `cascaded` when the exchange took the request (`requested` or `submitted`), otherwise the request's own outcome, reason and code (`refused`, `unknown`, `not_sent`), so a trade is never shown recalled when its group's request was not; a recall by `trade_id` names them in `cascaded_with`.

**One order, every fill.** An order that filled in several trades needs one recall per trade, each inside the exchange's window. A recall by `client_order_id` recalls every trade of the order you hold (its modifications keep the id, so every fill of the order is found) and sends the requests at once, so the whole order is answered within one wait rather than one per trade.

**Limits.** A recall is not an order management transaction and never counts against the exchange's load-management limits. Each request the gateway sends counts once against your per-key request bound: a recall by `client_order_id` counts each request after the first, and a request the bound refuses is answered `not_sent`.

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `trade_id` | `string` (`oneof target`) | none | one of | The exchange trade id (numeric) of one trade to recall. |
| `client_order_id` | `string` (`oneof target`) | none | one of | Recall every own trade of this order you may act on: the `ACTI` ones are sent, the others are answered `not_recallable`. |
| `revision_no` | `optional int64` | none | No | With `trade_id` only: the revision you saw. If the gateway holds a newer one, nothing is sent and the call fails `ABORTED` (`TRADE_CHANGED`). Unset, the gateway's latest revision is used. |

#### Response

`RecallTradeResponse { string client_order_id, repeated RecallTradeResult results, map<string, uint32> counts }`: `client_order_id` and `counts` are set on a recall by `client_order_id` only (`""` and empty otherwise); `counts` lists every outcome. Each `RecallTradeResult`:

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `trade_id` | `string` | none | always | The exchange trade id. |
| `outcome` | `string` | none | always | What became of the recall; see *Outcomes* below. |
| `state` | `string` | none | always | The trade's state when the answer was built ([Trade states](#trade-states)). |
| `revision_no` | `int64` | none | always | The trade's revision when the answer was built. |
| `recall_req_time` | `string` | RFC 3339 | when it applies | When the exchange registered the recall request. |
| `latest_recall_process_time` | `string` | RFC 3339 | when it applies | Until when market operations can decide the recall. |
| `m7_err_code` | `int64` | none | when it applies | The exchange's error code, on `refused` only. |
| `m7_error_key` | `string` | none | when it applies | The code's key in the exchange's error catalogue (for example `trade_execution_too_long_ago` for 2013, `recall_already_requested` for 3006, `otc_cannot_be_recalled` for 3017). |
| `reason` | `string` | none | when it applies | The exchange's words on `refused`; the state on `not_recallable`; why on `unknown` and `not_sent`. |
| `cascaded_with` | `repeated string` | none | when it applies | For a trade whose recall was sent: the other trades you hold with the same `parent_trade_id`, which the exchange recalls with it. For the other trades of its parent: that trade, whatever its outcome. |

An absent string field is `""`, an absent `m7_err_code` is unset, and an absent `cascaded_with` is empty.

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

A recall by `trade_id` answers with its one result's status: `requested` and `submitted` are `OK`; `refused` is `FAILED_PRECONDITION` (`RECALL_REFUSED`); `not_recallable` is `FAILED_PRECONDITION` (`RECALL_NOT_POSSIBLE`); `unknown` is `DEADLINE_EXCEEDED` (`OUTCOME_UNKNOWN`); `not_sent` is `UNAVAILABLE` (`NOT_PROCESSED`). The status message starts with the code and a colon. A failing status still carries the result, in gRPC's standard rich error model: the `grpc-status-details-bin` trailer holds a `google.rpc.Status` with the same code and message whose one detail is an `Any` of type `type.googleapis.com/voltnir.api.v1.RecallTradeResponse`, so any gRPC client reads it with its rich-error helper (in Python, `grpc_status.rpc_status.from_call`). The Python SDK decodes it for you and returns the result. A recall by `client_order_id` answers `OK` whenever the order has a trade you may recall, whatever each outcome is.

#### Errors

| gRPC status | Condition |
| --- | --- |
| `INVALID_ARGUMENT` | No target, `revision_no` with `client_order_id`, an empty `client_order_id`, or a `trade_id` that is not numeric. The message names the rule. |
| `PERMISSION_DENIED` | The caller does not hold `recall_trade`, or the trade is one the caller can see but this gateway's exchange login did not place. |
| `NOT_FOUND` | `TRADE_NOT_FOUND`: no such trade, or no trade of that order, that the caller may recall. |
| `ABORTED` | `TRADE_CHANGED`: the trade's revision moved past `revision_no`; nothing was sent. |
| `FAILED_PRECONDITION` | `RECALL_NOT_POSSIBLE` (the trade is not `ACTI`) or `RECALL_REFUSED` (the exchange refused it), on a recall by `trade_id`. |
| `DEADLINE_EXCEEDED` | `OUTCOME_UNKNOWN`: no acknowledgement in time; read the trade before asking again. |
| `UNAVAILABLE` | `NOT_PROCESSED`: the exchange never received the request; safe to retry. `NOT_OPERATIONAL`: the gateway's exchange login is not known yet, so no trade can be shown to be its own. |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`) may also occur; see the [Error reference](#errors).

#### Example

```
result = client.recall_trade("1500000001", revision_no=1).results[0]
print(result.outcome, result.state, result.m7_err_code)
order = client.recall_order_trades("6f0c2a54-...")
print(dict(order.counts))
```

### <a id="rpc-GetOrder" name="rpc-GetOrder"></a>`Unary` `rpc GetOrder`

Look up a single order by `client_order_id`.

**Required permission:** Authenticated caller; no permission required. `read_orders` widens the result. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `client_order_id` | `string` | none | Yes | UUID of the order to retrieve. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `confirmed` | `OwnOrder` | none | yes | Exactly one of these is populated depending on where the order currently lives. |
| `pending` | `PendingOrder` | none | yes | The submitted-but-not-yet-acknowledged order, populated only while it is still pending (see [PendingOrder on the REST page](rest_api_v1.md#get-order)). |

**Scoping.** Member-isolated, like `list_orders`. An order tagged with a member the caller may not see (or an untagged house order, for a caller without broad read) returns `NotFound` (identical to an unknown `client_order_id`), so the lookup is not an existence oracle. A caller holding `read_orders`/`bypass_member_check` can look up any order.

`GetOrderResponse` with two message fields: `confirmed` (an `OwnOrder`) and `pending` (a `PendingOrder`, submitted but not yet acked by M7). Exactly one of them is populated. Use `resp.HasField("confirmed")` to branch.

Checks the pending store first; if not there, checks the confirmed store. Exactly one of the two response fields is populated.

#### Errors

| gRPC status | Condition |
| --- | --- |
| `NOT_FOUND` | No pending or confirmed order with that client_order_id in the caller scope. |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
resp = client.get_order(client_order_id="550e8400-e29b-41d4-a716-446655440000")
if resp.HasField("confirmed"):
    print("order_id:", resp.confirmed.order_id, "state:", resp.confirmed.state)
else:
    print("still pending; entry_ts_ms:", resp.pending.entry_ts_ms)
```

### <a id="rpc-ListOrders" name="rpc-ListOrders"></a>`Unary` `rpc ListOrders`

List the caller's confirmed resting orders, optionally filtered.

An order the exchange reports filled or deleted leaves the list as soon as the gateway holds that report. Read it with [`GetOrder`](#rpc-GetOrder) while the gateway still holds it, or in the order audit ([`QueryAuditOrders`](#rpc-QueryAuditOrders)). A hibernated order stays listed: it is still yours at the exchange and can be activated or cancelled.

**Required permission:** Authenticated caller; no permission required. `read_orders` widens the result. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `delivery_area` | `string` | none | No | `""` = no filter. |
| `contract_id` | `int64` | none | Cond | `0` = no filter. Requires `delivery_area` if set; `contract_id` alone returns `INVALID_ARGUMENT`. |
| `product` | `string` | none | Cond | `""` = no filter. Product code (e.g. `"H"`). Requires `delivery_area`; ignored when `contract_id` is set. |
| `delivery_start` | `string` | RFC 3339 | No | Narrows the `product` filter to the single contract with this delivery start. Only meaningful with `product`. Any RFC 3339 instant: `2026-10-25T00:00:00Z`, `2026-10-25T00:00:00.000Z` and `2026-10-25T02:00:00+02:00` name the same contract. The doubled hour of a clock change is two instants: on 2026-10-25, 02:00 CEST is `00:00Z` (hour `02A`) and 02:00 CET is `01:00Z` (hour `02B`). |
| `v_member_short_id` | `string` | none | No | Empty = caller's default scope. Non-empty narrows to one member's orders; `PermissionDenied` unless the caller is assigned to it or holds `read_orders`/`bypass_member_check`. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `orders` | `repeated OwnOrder` | none | yes | The matching resting orders (see [OwnOrder on the REST page](rest_api_v1.md#get-order)). |

**Scoping.** A caller holding `read_orders` (or `bypass_member_check`) gets the firm-wide order book: every member's orders plus the untagged house orders. Everyone else gets only the orders tagged with a virtual member assigned to them; untagged house orders are withheld.

`ListOrdersResponse { repeated OwnOrder orders }`.

**Baskets.** An order entered in a basket carries `basket_ref`, the basket reference, read back from the order’s own text, so it survives a gateway restart; it is empty for an order not entered in a basket, and is read only on the login user’s own orders. `list_exec_inst` is the exchange’s own list instruction for the order: `none`, `valid` or `linked`, empty when the report names none. `basket_id` is the exchange’s basket id, reported only for a basket of two or more orders. On `OwnOrder` the two strings are `""` when absent and `basket_id` is 0.

**Attribution.** A record carries the virtual member and the Voltnir user behind it twice over: `v_member_short_id` / `v_member_name` and `voltnir_user_short_id` / `voltnir_username`. The short ids are what the audit endpoints filter on; the names are what a person reads. All four are empty for a record from another gateway, a colleague's on the same membership, whose tags that gateway wrote and which are deliberately not read here, or anything not placed through Voltnir, leaving the exchange `user_code` as the only attribution such a row carries. An order on the house account names a user and no member. A deleted user keeps its short id and its username, and a deleted member its short id and its name; neither short id is ever given to another user or member, so a filter by a user's short id or username, or by a member's short id, finds only that user's or member's records. A trade the gateway reloads from its store after a restart carries the names the directory holds at that moment, as a live trade does, so a renamed user or member shows the new name.

**Recognising your order in a public order book.** A book row names an order by id, and which id that is depends on the book. A local book lists the order under `order_id`; a remote (XBID) book lists it under `remote_order_id`, which the shared order book assigns and which bears no relation to `order_id`. `remote_order_id` is `0`, the absent sentinel, for an order on a local contract. Match a book row against **either** id: a remote book published EPEX-originated orders under the local id before M7 6.22 and under the remote id from 6.22, so matching `order_id` alone leaves your own resting orders looking like strangers’ on the newer release.

Pending orders (not yet acked) are excluded; query `get_order` for those. Filter priority mirrors REST `GET /orders` exactly: `delivery_area` + `contract_id` (exact contract) wins over `delivery_area` + `product` (+ optional `delivery_start`), which wins over `delivery_area` alone (all orders in that area); no filter returns everything. A negative `contract_id` is rejected with `INVALID_ARGUMENT`.

#### Errors

| gRPC status | Condition |
| --- | --- |
| `INVALID_ARGUMENT` | contract_id or product without delivery_area, a negative contract_id, or a delivery_start with product that is not an RFC 3339 timestamp (`delivery_start must be an RFC 3339 timestamp, e.g. 2026-10-25T00:00:00Z`). |
| `PERMISSION_DENIED` | v_member_short_id names a member the caller is not assigned to and may not read. |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
resp = client.list_orders(delivery_area="10YBE----------2", contract_id=2958876)
for order in resp.orders:
    print(order.client_order_id, order.state, order.quantity)
```

<a id="ops-market" name="ops-market"></a>

## Contracts & market data

### <a id="rpc-ListContracts" name="rpc-ListContracts"></a>`Unary` `rpc ListContracts`

The contract catalogue of an area, ordered by `dlvry_start` ascending: each contract's id, product, delivery period, state and trading phase, with no order book and no prices.

The catalogue is for finding contract ids: call it at startup or when a new delivery day appears, and do not poll it. One contract's order book comes from [`GetContract`](#rpc-GetContract) or [`GetContractByDelivery`](#rpc-GetContractByDelivery). Live data comes from [`WatchContracts`](#rpc-WatchContracts) on gRPC and the `contracts` stream on WebSocket, one stream with one filter: by area and product, or by contract id to follow one contract or a few.

**Contracts not open yet.** The catalogue lists the contracts the exchange has created but not yet opened for trading, in every configured delivery area whose exchange product list includes the contract's product. Such a row has `state_raw` `"IACT"` (so `state` reads `CONTRACT_STATE_UNSPECIFIED`), `trading_phase` `"CLSD"`, and `trading_phase_start` and `trading_phase_end` both `""`. Every row the exchange has opened in an area carries a `trading_phase_start`, so a `"CLSD"` row with an empty `trading_phase_start` is a contract that has not opened yet. `SubmitOrder` on such a row fails with `INVALID_ARGUMENT` and `"the contract is not open for trading yet"`. When the exchange's opening report reaches the gateway, the same row turns tradable in place, sent on `WatchContracts` as an update (the same `contract_id`, with the area's own state and phase); while the gateway runs that report is the exchange's broadcast, and a new login also lists the opened row. A contract that opens without one of those areas leaves it, removed from it with a `DELETE`.

**Required permission:** Authenticated caller; no permission required. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `area_id` | `string` | none | Yes | EIC code of the delivery area (e.g. `"10YBE----------2"`). |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `contracts` | `repeated ContractSummary` | none | yes | One [`ContractSummary`](#msg-ContractSummary) per active contract whose delivery period is known, sorted by dlvry_start ascending. |

`ListContractsResponse { repeated ContractSummary contracts }`. The catalogue covers **every product the exchange has assigned your account**, since the gateway inquires contract definitions account-wide, including an assigned product you have not subscribed market data for.

#### <a id="msg-ContractSummary" name="msg-ContractSummary"></a>ContractSummary

One catalogue row. Each field means what the field of the same name on `Contract` means (see [`GetContract`](#rpc-GetContract)); a field the exchange has not sent reads as the proto3 sentinel `""` or `false`.

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `contract_id` | `string` | none | yes | M7 contract id (string form). |
| `area_id` | `string` | none | yes | EIC delivery area code. |
| `prod` | `string` | none | yes | Product code (the join key to `GetSystemInfo` products). |
| `name` / `long_name` | `string` | none | yes | Contract display names; `""` until contract metadata arrives. |
| `dlvry_start` / `dlvry_end` | `string` | RFC 3339 | yes | The contract's delivery window. |
| `duration` | `string` | decimal hours | yes | Delivery duration as M7 sends it (`"0.25"`, `"1.0"`); `""` until metadata arrives. |
| `predefined` | `bool` | none | yes | `false` for a **user-defined block** contract, on which the exchange rejects regular limit orders (M7 error 1051); do not offer regular order entry there. |
| `state` | `ContractState` | none | yes | The three known M7 codes (`ACTI`/`SUSP`/`CLOS`); anything else reads `CONTRACT_STATE_UNSPECIFIED`. |
| `state_raw` | `string` | none | yes | The verbatim M7 4-char state code (parity with the REST `state` string); `""` until M7 sends one. |
| `trading_phase` | `string` | none | yes | The contract's current trading phase (e.g. `CONT`). |
| `trading_phase_start` / `trading_phase_end` | `string` | RFC 3339 | yes | The phase window; the end is the gate-closure time. Both are `""` on a contract not open yet; a `CLSD` row with no start is one. |

#### Errors

| gRPC status | Condition |
| --- | --- |
| `NOT_FOUND` | The delivery area is unknown. |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
resp = client.list_contracts(area_id="10YBE----------2")
print(len(resp.contracts), "contracts")
for c in resp.contracts[:5]:
    print(c.contract_id, c.name, c.state)
```

### <a id="rpc-GetContract" name="rpc-GetContract"></a>`Unary` `rpc GetContract`

Fetch full detail for one contract: the `Contract` shape (with order book), the caller's orders against it, the caller's trades, and the caller's net position.

**Required permission:** Authenticated caller; no permission required. `read_orders` widens the result. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `area_id` | `string` | none | Yes | EIC code of the delivery area. |
| `contract_id` | `string` | none | Yes | M7 contract id (string form). |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `contract` | `Contract` | none | yes | The contract and its current order book (see [Contract on the REST page](rest_api_v1.md#get-contract)). |
| `orders_acknowledged` | `repeated OwnOrder` | none | yes | The caller's exchange-acknowledged orders on this contract, each with an order_id (see [OwnOrder on the REST page](rest_api_v1.md#get-order)). |
| `trades` | `repeated OwnTrade` | none | yes | The caller's executed trades on this contract (see [OwnTrade on the REST page](rest_api_v1.md#get-contract); its state and recall fields: [Trade states](#trade-states), [OwnTrade recall fields](#recall-fields)). It holds what the live trade stream holds: the trades of the current cash-exposure window (since the most recent 16:00 booking cut on an ECC business day) and every trade on a contract whose delivery day, in its market's local time, is today or later. A trade recorded without its delivery window is kept for up to seven days after it executed. Earlier trades come from the trade history: [`QueryAuditTrades`](#rpc-QueryAuditTrades). |
| `net_pos` | `sint32` | sub-MW | yes | sub-MW; + long, - short |
| `orders_pending` | `repeated PendingOrder` | none | yes | The caller's orders submitted but not yet acknowledged, with no order_id yet (see [PendingOrder on the REST page](rest_api_v1.md#get-order)). |

> [!NOTE]
> `contract_id` is a **string** here (the M7 wire-level identifier). It's distinct from `SubmitOrderRequest.contract_id`, which is an `int64`.

**The `Contract` message.** `contract` carries the contract's state and its order book. The `buy`/`sell` arrays are per-order book rows (`ObEntry`: `price`, `quantity`, `order_id`, `order_entry_time`, `order_execution_restriction`, `order_type`, the same row shape as REST; multiple rows can share a price). `ObEntry.price` is cents and `ObEntry.quantity` sub-MW, the same scale as an order price and `best_bid` / `best_ask`; the product's exchange decimal scale is applied before an entry is served, so no per-contract factor applies. The `state` enum maps the three known M7 codes (`ACTI`/`SUSP`/`CLOS`) and degrades anything else to `CONTRACT_STATE_UNSPECIFIED`; the companion `state_raw` field always carries the verbatim M7 4-char code (parity with the REST `state` string). `predefined` is `false` for a **user-defined block** contract, on which the exchange rejects regular limit orders (M7 error 1051): only block orders are accepted; do not offer regular order entry there. Note: proto3 cannot represent an unset bool, so a contract whose metadata has not yet arrived also serializes as `predefined=false`. Treat `predefined=false` as block-only only for contracts that otherwise carry full metadata (or read REST/WS, where the field is `null` until known). `Contract` also carries the exchange's reference price for the contract in that delivery area: `ref_px_cents` (cents, the same scale as `price`), `ref_px_type` (`"C"` closing, the exchange's default, or `"O"` opening, whichever the contract carries), `ref_px_date` (`YYYY-MM-DD`) and `ref_px_updated_ms`. The four move together and are absent until the exchange publishes a price; `ref_px_cents` uses proto3 field presence because `0` and negative are real prices, so test it with `HasField`, while the two strings and the timestamp use the schema's `""` / `0` sentinels. Reference data for the trader, it is not what [P&L](#rpc-GetPnl) marks open positions against.

`ContractDetail { Contract contract, repeated OwnOrder orders_acknowledged, repeated OwnTrade trades, sint32 net_pos, repeated PendingOrder orders_pending }`. `net_pos` is sub-MW and reflects **executed trades only**, each until the exchange reverses it (a granted recall, `RGRA`, or a cancellation, `CNCL`); open and pending orders are excluded (mirrors REST). Positive = net long, negative = net short.

**orders_acknowledged vs orders_pending.** `orders_acknowledged` holds orders **M7 has acknowledged**; each carries an `order_id` and an order `state`. `orders_pending` (a `repeated PendingOrder`) holds orders **submitted but not yet acknowledged** by M7: no `order_id`, no `state` (implicitly pending). A pending order is **never** in `orders_acknowledged`; it moves there only once acked. To know whether you already have an order working on this contract, check **both**. (Mirrors the REST `orders_acknowledged` + `orders_pending` split and the WS `orders_acknowledged` + `orders_pending` frame.) Both `OwnOrder` and `PendingOrder` carry `v_member_short_id` (the virtual-member tag; `""` for an untagged House order). On an acknowledged `OwnOrder` it is recovered from the M7 `Txt` field, so an order stays attributable to its member across the submit→ack transition, but only for this gateway's own login user: an order placed by a colleague on the same membership (a different M7 `user_code`) carries its `user_code` and neither a virtual member nor a Voltnir user, and counts at the membership level like an untagged house order rather than against any local member.

**Scoping.** The orders, trades and position are member-isolated exactly like [`list_orders`](#rpc-ListOrders): a caller holding `read_orders` (or `bypass_member_check`) sees every member's rows plus the untagged house-account rows, and `net_pos` is the firm-wide executed position. Every other caller sees only the rows tagged with a virtual member assigned to them, house rows withheld, and `net_pos` is the sum of those members' executed positions; with no assigned members the lists are empty and `net_pos` is 0. A trade between two virtual members of the desk reaches a member-scoped caller as the ordinary fill of its own leg: only the leg its members placed, carrying that leg's own member, member name, Voltnir user and user name exactly as a fill against an outside counterparty would, with the other leg, its member and its Voltnir user withheld; a caller holding `read_orders` (or `bypass_member_check`) sees both legs.

#### Errors

| gRPC status | Condition |
| --- | --- |
| `NOT_FOUND` | No contract with that id in the area, or its delivery end has passed on the gateway’s clock. Orders still resting on a finished contract are read through [`list_orders`](#rpc-ListOrders) (with `delivery_area` and `contract_id`) and cancelled with [`cancel_order`](#rpc-CancelOrder). |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
detail = client.get_contract(area_id="10YBE----------2", contract_id="2958876")
print("best bid:", detail.contract.best_bid, "x", detail.contract.best_bid_qty)
print("best ask:", detail.contract.best_ask, "x", detail.contract.best_ask_qty)
print("acknowledged orders:", len(detail.orders_acknowledged))
print("pending (un-acked) orders:", len(detail.orders_pending))
print("my net position:", detail.net_pos, "sub-MW")
```

### <a id="rpc-GetContractByDelivery" name="rpc-GetContractByDelivery"></a>`Unary` `rpc GetContractByDelivery`

Resolve a contract by `(area, product, delivery_start)` and return the same `ContractDetail` shape, member-scoped the same way, as `get_contract`.

**Required permission:** Authenticated caller; no permission required. `read_orders` widens the result. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `area_id` | `string` | none | Yes | EIC code of the delivery area. |
| `prod` | `string` | none | Yes | Product code (e.g. `"H"`, `"Q"`). |
| `dlvry_start` | `string` | RFC 3339 | Yes | Delivery start of the contract. Any RFC 3339 instant: `2026-10-25T00:00:00Z`, `2026-10-25T00:00:00.000Z` and `2026-10-25T02:00:00+02:00` name the same contract. The doubled hour of a clock change is two instants: on 2026-10-25, 02:00 CEST is `00:00Z` (hour `02A`) and 02:00 CET is `01:00Z` (hour `02B`). |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `contract` | `Contract` | none | yes | The contract and its current order book (see [Contract on the REST page](rest_api_v1.md#get-contract)). |
| `orders_acknowledged` | `repeated OwnOrder` | none | yes | The caller's exchange-acknowledged orders on this contract, each with an order_id (see [OwnOrder on the REST page](rest_api_v1.md#get-order)). |
| `trades` | `repeated OwnTrade` | none | yes | The caller's executed trades on this contract (see [OwnTrade on the REST page](rest_api_v1.md#get-contract); its state and recall fields: [Trade states](#trade-states), [OwnTrade recall fields](#recall-fields)). It holds what the live trade stream holds: the trades of the current cash-exposure window (since the most recent 16:00 booking cut on an ECC business day) and every trade on a contract whose delivery day, in its market's local time, is today or later. A trade recorded without its delivery window is kept for up to seven days after it executed. Earlier trades come from the trade history: [`QueryAuditTrades`](#rpc-QueryAuditTrades). |
| `net_pos` | `sint32` | sub-MW | yes | sub-MW; + long, - short |
| `orders_pending` | `repeated PendingOrder` | none | yes | The caller's orders submitted but not yet acknowledged, with no order_id yet (see [PendingOrder on the REST page](rest_api_v1.md#get-order)). |

`ContractDetail`. `NOT_FOUND` if no contract matches.

#### Errors

| gRPC status | Condition |
| --- | --- |
| `INVALID_ARGUMENT` | dlvry_start is not an RFC 3339 timestamp (`dlvry_start must be an RFC 3339 timestamp, e.g. 2026-10-25T00:00:00Z`). |
| `NOT_FOUND` | No contract for that area, product and delivery start, or its delivery end has passed on the gateway’s clock. |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
detail = client.get_contract_by_delivery(
    area_id="10YBE----------2",
    prod="H",
    dlvry_start="2026-04-30T13:00:00Z",
)
print(detail.contract.contract_id, detail.contract.state)
```

### <a id="rpc-GetHub2Hub" name="rpc-GetHub2Hub"></a>`Unary` `rpc GetHub2Hub`

Get the ATC (available transfer capacity) grid for a source delivery area between two timestamps, one row per (source, destination) hub pair. The destination may be any hub in the XBID network, not only a neighbour across a shared border: M7 publishes hub-to-hub capacity, the transfer the network can carry from one hub to the other. For live updates use [`WatchHub2Hub`](#rpc-WatchHub2Hub).

**Required permission:** Authenticated caller; no permission required. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `delivery_area_from` | `string` | none | Yes | EIC code of the source area. |
| `delivery_from` | `string` | RFC 3339 | Yes | RFC 3339: window start (inclusive on `dlvry_start`). |
| `delivery_to` | `string` | RFC 3339 | Yes | RFC 3339: window end (exclusive on `dlvry_start`). |
| `delivery_area_to` | `string` | none | No | `""` = all destinations. EIC code to keep only one destination's rows. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `enabled` | `bool` | none | yes | True when hub-to-hub capacity trading is enabled for this session. |
| `capacity_connected` | `bool` | none | yes | True when the capacity feed is connected and its rows are current. |
| `data` | `repeated AtcEntry` | none | yes | One row per source-to-target area pair for the requested delivery window (see AtcEntry). A row whose delivery period ended more than an hour ago is left out. |

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

Mirrors REST `GET /hub2hub`, including the optional destination filter.

#### Errors

| gRPC status | Condition |
| --- | --- |
| `INVALID_ARGUMENT` | Missing or malformed window timestamps, or delivery_from not before delivery_to. |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

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

### <a id="rpc-ListPublicTrades" name="rpc-ListPublicTrades"></a>`Unary` `rpc ListPublicTrades`

Up to `limit` most-recent public trades from the market-wide tape, oldest first.

**Required permission:** Authenticated caller; no permission required. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `limit` | `uint32` | none | No | 0 = default (100); hard-capped at 1000. |
| `contract_id` | `uint64` | none | No | 0 = all contracts. |
| `area_id` | `string` | none | No | "" = all areas; matches buy- or sell-side. Max 64 chars (over-length → INVALID_ARGUMENT). |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `trades` | `repeated PublicTrade` | none | yes | The matching public-tape trades (see PublicTrade). |

`ListPublicTradesResponse { repeated PublicTrade trades }`. `buy_dlvry_area`, `sell_dlvry_area` and `remote_trade_id` use `""` as the absent sentinel.

`remote_trade_id` is the XBID remote trade id, set on a trade executed on a remote (XBID) contract and `""` on a local trade, where the exchange omits it. It is present for every trade state, recalls and cancellations included, and is the join key onto the EPEX market-data transaction reports, which carry the same id.

Mirrors REST `GET /api/v1/public_trades`. Optional in-memory filters for `contract_id` and `area_id`.

#### Errors

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
resp = client.list_public_trades(limit=50, contract_id=100001)
for t in resp.trades:
    print(t.exec_time, t.px, t.qty)
```

<a id="ops-sysreads" name="ops-sysreads"></a>

## System reads

### <a id="rpc-GetState" name="rpc-GetState"></a>`Unary` `rpc GetState`

Snapshot of overall system health: uptime, AMQP / WS connectivity, operational flag, and a list of any active issues.

**Required permission:** `read_state`. (see [Permissions](#permissions))

#### Request

This RPC takes no request fields.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `uptime` | `string` | none | yes | Process uptime formatted as e.g. "2h 14m 03s" (matches REST shape). |
| `operational` | `bool` | none | yes | `true` when every required subsystem is healthy. |
| `issues` | `repeated string` | none | optional | Human-readable descriptions of failing health checks. Empty when `operational` is true. |
| `admission` | `string` | none | yes | `open`, `closed` or `degraded`: whether new orders and modifies are admitted. `closed` while any order-critical issue is present, except as follows. `degraded` while the only issues are `trade_report refused` and the `cash_exposure_window not covered` it opens, and admission is open anyway because `system.trade_ingest_fault` is `continue` or an operator acknowledged the fault. Cancels are never gated. |
| `amqp_connected` | `bool` | none | yes | Whether the AMQP connection to the exchange is up. |
| `amqp_private_consumer_healthy` | `bool` | none | yes | True while the AMQP private consumer that carries your order acknowledgements and execution reports is alive. |
| `amqp_broadcast_consumer_healthy` | `bool` | none | yes | True while the AMQP broadcast consumer that carries market-state and instrument messages is alive. |
| `amqp_publisher_healthy` | `bool` | none | yes | True while the AMQP publisher that sends commands to the exchange is operational. |
| `amqp_publisher_tx_capacity` | `uint32` | none | yes | Remaining capacity of the bounded publisher_tx channel. |
| `amqp_market_active` | `bool` | none | yes | `true` when M7 has the market open for trading. |
| `amqp_broadcast_sequence_healthy` | `bool` | none | yes | `true` while the broadcast feed's per-routing-key sequence counters are contiguous. Cleared when a broadcast is lost or M7 resets its sequences, and set again only once a fresh subscription has re-established the baseline; order entry and modify are refused while it is false. |
| `ws_order_book_stream_connected` | `bool` | none | yes | Whether the WebSocket connection to the exchange's order-book stream is up. |
| `ws_order_book_sequence_healthy` | `bool` | none | yes | True while the order-book feed's sequence numbers are contiguous, false after a detected gap until it re-syncs. |
| `ws_order_book_synchronized` | `bool` | none | yes | True once the local order book has taken its initial snapshot and is tracking live deltas. |
| `ws_order_book_pong` | `int64` | Unix ms UTC | yes | Time of the last pong on the order-book connection, 0 before the first pong. A pong proves the socket, not the feed. |
| `ws_order_book_delta` | `int64` | Unix ms UTC | yes | Unix ms of the last applied delta; 0 before the first and after a reconnect. The last time market data actually arrived on this feed. |
| `ws_order_book_delta_per_hour` | `uint64` | per hour | yes | Rolling count of order-book deltas applied per hour. |
| `ws_order_book_avg_processing_time` | `string` | none | yes | Rolling-average display strings, same formatting as the REST shape (e.g. "1.2 ms"); "" until the first sample window completes. |
| `ws_order_book_avg_latency` | `string` | none | yes | Rolling-average order-book feed latency as a display string such as "1.2 ms", empty until the first sample window completes. |
| `ws_private_data_stream_connected` | `bool` | none | yes | Whether the WebSocket connection to the exchange's private-data stream (your orders and trades) is up. |
| `ws_private_data_sequence_healthy` | `bool` | none | yes | True while the private-data feed's sequence numbers are contiguous, false after a detected gap. |
| `ws_private_data_synchronized` | `bool` | none | yes | True once every part of the private-data feed’s initial order snapshot has arrived and been applied to the order store, together; false from a reconnect until then. |
| `ws_private_data_pong` | `int64` | Unix ms UTC | yes | Time of the last pong on the private-data connection, 0 before the first pong. |
| `ws_private_data_delta_per_hour` | `uint64` | per hour | yes | Rolling count of private-data messages applied per hour. |
| `ws_private_data_avg_processing_time` | `string` | none | yes | Rolling-average private-data processing time as a display string such as "1.2 ms", empty until the first sample window completes. |
| `ws_private_data_avg_latency` | `string` | none | yes | Rolling-average private-data feed latency as a display string such as "1.2 ms", empty until the first sample window completes. |
| `license` | `LicenseView` | none | yes | Mirrors the REST /state license block. The full installed license; expiry status never gates trading and never drops a connection. |
| `trades_received` | `uint64` | none | yes | Cumulative since process start. A trade-persistence loss is never silent: a failed chunk is counted here rather than swallowed. Trade rows handed to the backfill worker across every drained snapshot. |
| `trades_persisted` | `uint64` | none | yes | Trade rows the worker committed to the database. |
| `trades_persist_failed` | `uint64` | none | yes | Trade rows lost to a failed begin/insert/commit (the load-bearing count). |
| `writes_dropped` | `uint64` | none | yes | Fire-and-forget writes lost (orders, audit, M7 errors, public trades, exchange messages). The writer queues are unbounded, so nothing is shed; a lost write means a writer accepted a batch and its transaction would not commit, the database refused that row, or a shutdown could not commit it within its 30-second drain. Counted per stream on the `stream` label of `voltnir_writes_dropped_total`. It resets on restart; each clean shutdown records the run's totals per stream in its `system_shutdown` audit row. |
| `trade_reports_refused` | `uint64` | none | yes | Cumulative since start: trade capture reports refused because their financial core could not be read. Non-zero means a trade the exchange executed was missed; while the `trade_report refused` issue is present, order admission is closed until the re-asked window brings the trade in, unless the desk trades on through it (`admission` then reads `degraded`). |
| `product_parameters_loaded` | `bool` | none | yes | Whether the session's first product report has been applied, so the gateway knows the per-product decimal scale every wire integer is on. Order admission is refused (after a short login grace) until this is true. |
| `product_scale_unrepresentable` | `uint64` | none | yes | Products whose published decimal scale or quantity unit the gateway cannot denominate in its own cents-and-sub-MW store; orders on them are refused. |
| `product_scale_frames_dropped` | `uint64` | none | yes | Cumulative since start: inbound frames dropped because their product's decimal scale was unknown or unrepresentable. |
| `product_scale_orders_refused` | `uint64` | none | yes | Cumulative since start: orders refused for an unknown or unrepresentable product scale. |
| `product_scale_changes` | `uint64` | none | yes | Cumulative since start: product reports that changed a product's recorded decimal scale. |
| `contracts_awaiting_definition` | `uint64` | none | yes | Book-born contracts streaming a book but with no contract definition from the exchange yet, so they are withheld from the contracts stream and list_contracts until their delivery is known (gauge). |
| `contract_reports_broadcast` | `uint64` | none | yes | Contract definitions the exchange has broadcast to this session without being asked. |
| `last_update_pass_refused` | `bool` | none | yes | `true` when the exchange refused this login's inquiry for the trades it updated while Voltnir was not connected (`dateMeaning=LAST_UPDATE`). Voltnir then trades on the match-time inquiry alone, so a recall or cancellation resolved during that time, on a trade matched before the cash-exposure window, can still count in position, slot sums and P&L until the exchange reports the trade again. It does not close order entry. The refused question is not asked again: the next login asks only about what changed after this session last heard the exchange, so a trade reversed during the outage before this login keeps counting until the exchange reports it again or a trade-history restore brings it back. The flag clears when the gateway next connects to the exchange. |

None.

`SystemState`: the same shape as REST `GET /api/v1/state` (including the four rolling-average display strings `ws_order_book_avg_processing_time`, `ws_order_book_avg_latency`, `ws_private_data_avg_processing_time`, `ws_private_data_avg_latency`, and the four cumulative-since-start trade-persistence counters `trades_received`, `trades_persisted`, `trades_persist_failed` and `writes_dropped` as `uint64`, a non-zero `trades_persist_failed` or `writes_dropped` is a persistence-loss signal (the writer queues are unbounded, so `writes_dropped` reports only `writer_failed`, its `channel_full` reason is unreachable and stays `0`; a lost trade is counted apart in `trades_persist_failed`; the REST `/state` page carries the split), plus `trade_reports_refused` (`uint64`), the count of exchange trade reports refused for an unreadable financial core; while it is non-zero and the `trade_report refused` condition is present, order entry is closed until the re-asked window brings the missed trade in, unless the desk trades on through it (`admission` then reads `degraded`), and the five product decimal-scale fields `product_parameters_loaded` (`bool`) plus the `uint64` gauges `product_scale_unrepresentable`, `product_scale_frames_dropped`, `product_scale_orders_refused` and `product_scale_changes`, all `0`/`true` on a gateway whose products publish the (2, 3, MW) scale the API is denominated in, and the two contract-catalogue `uint64` fields `contracts_awaiting_definition` (book-born contracts withheld from `ListContracts`/`WatchContracts` until their delivery report lands) and `contract_reports_broadcast` (contract reports received as broadcasts this session, a count that grows for the life of the session); the gauge reads `0` once the catalogue has loaded and no straggler remains (a contract M7 created days ahead is legitimately book-born and undefined until its opening broadcast)), with one documented parity divergence: the `amqp_authenticated_with` block is omitted entirely on gRPC (REST returns it with only the `v7_token` secret stripped). The former `trading_enabled` + `order_pos_limit` convenience fields have moved off `SystemState` onto [`SystemStatus` (`GetStatus`)](#rpc-GetStatus); read them there. The nested `license` message (`LicenseView`) carries `status_kind` (`active` / `expiring_soon` / `expired` / `in_grace`), `status_days` (days remaining or elapsed; `0` for `active`), `license_id`, `mode` (`trader` / `desk` capability tier), `environment`, `issued_at`, `expires_at`, the provenance fields `schema_version` / `issuer` / `signing_key_id`, the `holder` sub-message (`LicenseHolder` with `legal_entity` + `portal_user_id`; unset for a free `sim` license), and the authorized EPEX identities: `epex_any` (`true` = any identity, for sim) plus a repeated `epex_identities` (`EpexIdentityView` with `account_id` + `user_id`) when scoped. License expiry does not gate individual RPCs or drop a stream mid-grace, but once the licence is past its grace window the whole gateway shuts down (it also refuses to start). Note: gRPC is served on **every** license tier (`trader` and `desk`); it's a transport, not a desk-only surface. The only desk-only operations are the user/permission/member management RPCs (see [Users & Members](#rpc-ListUsers)).

`operational` is `false` whenever any order-critical subsystem is degraded: the exchange session, the three AMQP channels, or either M7 WebSocket feed, the order book *and* the private-data stream, each connected, synchronized and sequence-healthy. `issues` then carries one string per failing condition; the strings are identical on all three transports and enumerated on the [REST `GET /api/v1/state`](rest_api_v1.md#get-state) page. The private-data feed carries your own orders and execution reports, so while it is degraded the exposure the order gate measures against has stopped advancing: `SubmitOrder` and `ModifyOrder` return `UNAVAILABLE` until it recovers. `CancelOrder`, `CancelAllOrders` and `SetTradingAllowed` are never gated on `operational`.

**If you see `admission: degraded`**, the gateway is admitting orders on figures it knows are incomplete, by the desk's own choice: an exchange trade report it could not read is missing from position, cash and P&L, so its own position and cash limits are measured short (the exchange still checks the member's cash limit on every order). Stop adding exposure you would not add blind, reconcile your book against the exchange, and contact the support desk with the `parse_error` rows from the m7-errors audit. It returns to `open` by itself once the missed trade is ingested; under the default `close` policy an acknowledgement ([`AckTradeIngestFault`](#rpc-AckTradeIngestFault)) lasts `system.trade_ingest_fault_ack_ttl_sec` (1800 s by default), ends early when the fault clears, and is dropped by a restart. While admission is `degraded` the gateway does not reconnect its exchange session over the fault, and it keeps polling the exchange's throttling status, which the load check (`load_management`) needs fresh to admit an order that adds exposure. Orders are admitted the moment admission reopens, unless the throttling report went stale while admission was closed (closed for about `load_management.max_report_age_sec` or longer, 30 s by default; the report ages from its last poll, so a slightly shorter closure can already count); then an order that adds exposure can be refused for about two seconds after admission reopens, until the first throttling poll answers. From then on orders stay admitted until the trade report is read or the acknowledgement runs out. Any other order-critical issue still closes admission, and one that outlasts the health allowance still makes the gateway reconnect its exchange session, with admission closed while it does; an acknowledgement keeps counting down meanwhile. `operational`, `/readyz` and the gRPC health service keep reporting the gateway not operational throughout, so alerts on them still fire.

`issues` (repeated `string`) carries one stable string per failing condition, the same set as REST `GET /api/v1/state` and the WS `state` stream: `exchange is down`, `amqp_broadcast_consumer unhealthy`, `amqp_private_consumer unhealthy`, `amqp_publisher unhealthy`, `ws_order_book not synchronized`, `ws_order_book_stream not connected`, `ws_order_book_stream sequence gap`, `m7_heartbeat lost`, `cash_exposure_window not covered`, `product_parameters not loaded`, `trade_report refused`. `trade_report refused` means the gateway could not read an exchange trade report's financial core, so a trade the exchange executed is missing from its own count and position, cash-exposure and P&L are understated; order entry is held closed (the exchange's own cash limit is still the backstop) until the exposure window is covered again, the outstanding chunk re-asked, or (for an unsolicited or foreign report) the whole window re-planned and re-asked, and the missed trade is ingested. The desk can choose to trade on through it instead: with `system.trade_ingest_fault: continue`, or for `system.trade_ingest_fault_ack_ttl_sec` after an operator acknowledges the fault ([`AckTradeIngestFault`](#rpc-AckTradeIngestFault)), new orders and modifies are admitted while it stands and no other issue is present, and `admission` reads `degraded`. The desk can always get flat, `CancelOrder`, `CancelAllOrders` and a `deactivate` modify are never gated; do not “correct” the missed trade through ComTrader (the Voltnir figures will still be wrong once it is ingested), pull the `parse_error` rows from `WatchM7Errors`/the m7-errors audit (they carry the raw report) and escalate to Voltnir, and after the fix and a restart the first login's backfill ingests it and the condition clears itself. `cash_exposure_window not covered` means the gateway has not yet had the exchange confirm every trade in the current cash-exposure window, up to 72 hours over a weekend, so consumed cash could be under-counted and orders admitted that the exchange would refuse. It is raised at login and cleared once the exchange has answered the chunked trade backfill: the window's trades by match time, and every trade the exchange updated since Voltnir last heard from it; it persists only when the exchange cannot serve the whole window, which needs a higher `contractStoreTimeInDays` from EPEX. `m7_heartbeat lost` means three of M7's advertised heartbeat intervals have passed with no application heartbeat from the exchange, about **15 seconds**, since M7 advertises a 5-second interval. The M7 backend has stopped publishing even though the connection may still be up, so market and private data are frozen and order submission is refused until it resumes. It clears on the next heartbeat; after a reconnect the same three intervals are counted from the re-subscribe. It is never raised on an environment that has never sent a heartbeat at all. One condition does not close order entry and is reported as the boolean `last_update_pass_refused` beside `issues`, not in it: the exchange refused the login's inquiry for the trades it updated while Voltnir was not connected.

Gated by `read_state` (`PERMISSION_DENIED` without it). The trading-posture fields (kill-switch, per-contract limit, throttling, cash limits, license) moved to [`GetStatus`](#rpc-GetStatus).

#### Errors

| gRPC status | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `read_state`. |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
state = client.get_state()
print(state.uptime, "operational:", state.operational)
print("issues:", list(state.issues))
print("license:", state.license.status_kind, state.license.expires_at)
```

### <a id="rpc-GetStatus" name="rpc-GetStatus"></a>`Unary` `rpc GetStatus`

The caller-scoped trading-posture aggregate in one call.

**Required permission:** Authenticated caller; no permission required. `read_status` widens the result (desk money and licence). (see [Permissions](#permissions))

#### Request

This RPC takes no request fields.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `throttling` | `ThrottlingStatus` | none | yes | M7's reported order load-management status, plus this gateway's own client-side guard: OMT headroom left, and why order actions are being refused when they are. Base layer, always present. |
| `trading_enabled` | `bool` | none | yes | Whether trading is currently enabled (the kill switch). Base layer. |
| `operational` | `bool` | none | yes | `true` when every required subsystem is healthy (also on `SystemState`). Base layer. |
| `admission` | `string` | none | yes | Whether new orders and modifies are admitted, the same value as `SystemState.admission`. Base layer. |
| `cash_limits` | `repeated CashLimit` | none | yes | M7-reported per-currency cash/margin feed. Distinct from `cash_limit` (the Voltnir-configured order limit). Same shape as GetCashLimitsResponse. `read_status` only, empty without it. |
| `order_pos_limit` | `optional sint32` | sub-MW | optional | The House per-contract net position limit; `read_status` only, unset without it (each account carries its own limit in `accounts`). |
| `stranded_pending_count` | `optional uint32` | count | optional | New orders held past their expiry bound: no answer from the exchange, and the gateway cannot rule out a missed report or a late XBID answer, so they go on consuming position and cash headroom until their report or refusal, the first order snapshot after the bound, a restart, or about an hour after their contract’s delivery ends. 0 on a healthy gateway. `read_status` only. |
| `stranded_pending_qty` | `optional int64` | sub-MW | optional | The quantity those held orders hold: headroom the desk has lost with no resting order to show for it. `read_status` only. |
| `claims_count` | `optional uint32` | count | optional | Amendments and activations whose added exposure counts against the position and cash limits until the exchange answers them or their expiry bound passes. Held claims included. `read_status` only. |
| `claims_qty` | `optional int64` | sub-MW | optional | What those claims add. `read_status` only. |
| `claims_held_count` | `optional uint32` | count | optional | Of those, the claims held past their expiry bound, for the same reasons and until the same events as a held new order. 0 on a healthy gateway. `read_status` only. |
| `claims_held_qty` | `optional int64` | sub-MW | optional | What the held claims add: headroom lost to commands the exchange has not answered. `read_status` only. |
| `cash_limit` | `CashLimitStatus` | cents (currency × 100) | yes | The desk-wide cash-limit state: effective House limit, live consumption, and remaining headroom per currency pool with pool provenance, in cents, plus `delivery_risk_applied` and `delivery_risk_source`, described below. `read_status` only. |
| `license` | `LicenseView` | none | yes | The full installed license (also on `SystemState`). `read_status` only; the base-layer `license_summary` is what an expiry banner needs. |
| `license_summary` | `LicenseSummary` | none | yes | Base-layer license projection: status kind, expiry, grace-window end while in grace, and `mode`, the licence tier (`"trader"` or `"desk"`; on `"trader"` the user, member and permission management RPCs are refused with `LICENSE_DESK_REQUIRED`). Everything an expiry banner needs, none of the holder / identity / provenance the full `license` carries. Always present. |
| `m7_client_cert` | `M7ClientCert` | none | optional | The M7 client certificate, the first certificate in the file the gateway's `epex_connection.cert` setting names: `status_kind` (`valid`, `expiring_soon` from 30 days before expiry, `expired`, `not_yet_valid` or `unreadable`), `status_days` (days left, days since expiry, or days until it starts; 0 for `valid` and `unreadable`), `status_reason` (set only when unreadable: a missing file, no PEM block, no certificate, or one that does not parse) and `not_after` (RFC 3339 UTC, unset when unreadable). Read at startup and every hour. The exchange refuses the connection under an expired certificate, with no grace period; a replacement file at the same path is used on the next connection attempt, with no restart. `read_status` only, unset without it. |
| `accounts` | `repeated AccountView` | none | optional | The accounts this caller may trade for, the House when it holds `trade_global`, plus each assigned active member, each with its own position limits and cash usage. Always present (empty when the caller may trade for none). |

None.

`SystemStatus`. **Base layer (always set):** `throttling` (`ThrottlingStatus`, same message as [`GetThrottling`](#rpc-GetThrottling), M7's report plus the local `guard`), `trading_enabled` (`bool`; same as `GetTradingAllowed`), `operational` (`bool`), `license_summary` (`LicenseSummary`: `status_kind` / `status_days`, `expires_at`, `grace_end` set only while in grace, and `mode`, `"trader"` or `"desk"`, the licence tier, an expiry banner and the tier without the holder/identity/provenance the full `license` has), and `accounts` (repeated `AccountView`: the accounts the caller may trade for, the House (`is_house`) with `trade_global`, plus each assigned active member by `short_id`+`name`, each with `position_limit` and `effective_position_limit` in sub-MW, where the effective figure is `min(order_pos_limit, max_position)` for a member, and the six per-pool `*_cents` fields of its own cash usage, a member's allocation/consumed/remaining, or for the House account what bounds an untagged order: `*_limit_cents` the House remainder (desk limit minus member allocations, negative when over-allocated), `*_consumed_cents` the untagged book's own exposure, and `*_remaining_cents` the headroom admission allows (the tighter of that remainder and the aggregate desk guard), distinct from the desk-wide `cash_limit` below; a `0` limit or allocation is flat-only; `slot_limit` is the account's [slot position limit](#ops-slot-limit) in sub-MW, the House slot limit for House and the member's `max_slot_position` for a member, unset for a member with no slot limit and on the House entry for a caller without `read_status`, which is not shown the House slot figures anywhere; `slot_mode` is the `SlotLimitMode`, the same on every account). **read_status layer (set only with the permission):** `cash_limits` (repeated `CashLimit`, same as [`GetCashLimits`](#rpc-GetCashLimits)), `order_pos_limit` (`optional sint32`, sub-MW; same as `GetContractLimit`), `cash_limit` (`CashLimitStatus`: the six `int64` cents fields where `*_limit_cents` is the effective House limit and `remaining = limit − consumed`, exposure summed exactly and rounded once, `*_consumed_cents` up and `*_remaining_cents` down, plus `eur_pool` / `gbp_pool` (`CashPool`), the same shape [`GetCashLimit`](#rpc-GetCashLimit) returns, plus `delivery_risk_applied` (`bool`: whether the GB delivery-risk add-on, a risk set's price-independent `alpha` per MWh on GB sells or the configured GBP fallback rate, is charged in the GBP figures; the exchange charges it only to a member whose record says so and states that record only when it changes; with it `false` a GB order or trade is priced with its product's default risk set instead of the GB delivery-risk set, and with it `true` with the GB set and its add-on, a pricing that has not been measured against the exchange; a change re-prices every open order and every in-window trade at once) and `delivery_risk_source` (`DeliveryRiskSource`: `DELIVERY_RISK_SOURCE_EXCHANGE` once this member's own record has been seen, this session or stored from an earlier one, `DELIVERY_RISK_SOURCE_CONFIG` while the gateway's `cash_limit.delivery_risk_applied` setting decides, default `true`; the gateway never sends `UNSPECIFIED`), the same fields and meaning as REST and WS), `license` (`LicenseView`, identical to the [`GetState`](#rpc-GetState) license projection), the held pending headroom, `stranded_pending_count` (`optional uint32`) and `stranded_pending_qty` (`optional int64`, sub-MW): new orders held past their expiry bound, which keep consuming headroom until their report or refusal, the first order snapshot after the bound, a restart, or about an hour after their contract’s delivery ends; and the claims, `claims_count` / `claims_qty` (amendments and activations whose added exposure counts until the exchange answers them or their expiry bound passes) and `claims_held_count` / `claims_held_qty` (those held past the bound); the held figures are `0` on a healthy gateway; and `m7_client_cert` (`M7ClientCert`), the M7 client certificate’s expiry as described in the table above.

Open to every authenticated caller. Same data as REST `GET /api/v1/status` and the WS `status` stream, layered by who asks: the base posture (throttling, kill-switch, operational, `license_summary`) and the caller's own `accounts` are always present; the desk-wide money (M7 cash feed, desk cash projection, per-contract limit, held-headroom and claim gauges), the full `license` and the M7 client certificate’s expiry are set only for a caller holding `read_status`. In proto3 an absent `read_status` layer means the message fields are unset (use presence, `HasField`), the scalar fields are unset, and `cash_limits` is empty.

#### Errors

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
status = client.get_status()
print("trading:", status.trading_enabled, "pos_limit:", status.order_pos_limit)
print("eur remaining:", status.cash_limit.eur_remaining_cents / 100)
```

### <a id="rpc-GetThrottling" name="rpc-GetThrottling"></a>`Unary` `rpc GetThrottling`

M7's order load-management status for the member, plus this gateway's own client-side guard.

**Required permission:** Authenticated caller; no permission required. (see [Permissions](#permissions))

#### Request

This RPC takes no request fields.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `mbr_id` | `optional string` | none | optional | The connected member id; unset until the exchange first reports. |
| `timestamp` | `optional string` | UTC, RFC 3339 with `Z` | optional | When `status` became true: the exchange's calculation time on a status report, or the instant of the change on a status change it announced, in which case the counts beside it are older. Unset until the exchange first states one. |
| `status` / `short_status` / `long_status` | `optional string` | none | optional | `"NO_RESTRICTION"`, `"WARNING"` or `"RESTRICTED"`, overall and per rule. `RESTRICTED` means the exchange rejects every order action the member's API clients send. |
| `short_*` / `long_*` window fields | `optional int64` | seconds / count | optional | Per rule (short: a window of seconds, 10 s in the exchange's published configuration; long: a window of hours, 24 h): `observation_period`, `tolerance_period` and `reconnection_cool_down` in seconds, `omt_limit_l1`, `omt_limit_l2` and `current_omt_count` as counts. The cool-down is the minimum time that must pass, counted from when the load drops back below L1, before a restriction is released. |
| `short_release_timestamp` / `long_release_timestamp` | `optional string` | UTC, RFC 3339 with `Z` | optional | The indicative release time while the rule is restricted, or the end of its tolerance while it is warning; unset otherwise. Every further order action recomputes it. |
| `guard` | `OmtGuard` | none | yes | The client-side guard. Always set: it works from configured fallbacks before M7's first report. |
| `throttling_member_action` | `string` | none | yes | What this gateway asks the exchange, at every login, to do with every order of the member when it restricts the member, from its configuration: `"HIBE_MBR_ORDERS"` (the default) hibernates them all, whichever client entered them, overriding every user-level action; `"NONE_MBR_ORDERS"` leaves it to each user's own action. The exchange keeps the value of the last login that stated one, so another client of the member logging in later can replace it until this gateway logs in again. |
| `throttling_user_action` | `string` | none | yes | The same for the orders of this gateway's own exchange user: `"HIBE_USER_ORDERS"` (the default) hibernates them, `"HIBE_BG_ORDERS"` every order of the user's balancing group, `"NONE_USER_ORDERS"` none, unless the member-level action hibernates them anyway. |

M7 counts every order management transaction (OMT), an order entry, modify, activation, hibernation or deletion, the member's API clients send, **whether the exchange accepts or rejects it**, over a short rolling window (10 s in EPEX's published configuration) and a long one (24 h). Cross a threshold and the whole member is `RESTRICTED`: the exchange rejects every API order action until the restriction is released, and each further attempt pushes that release out.

The reported fields are all `optional` and unset until M7 has sent its first response. **Every period is in seconds.** The `guard` field is always set, it works from configured fallbacks before that first response, and is current to the millisecond.

None.

`ThrottlingStatus`: M7's reported thresholds, counts, per-rule statuses and indicative release times, the statuses and release times also moving on the exchange's own status-change broadcast, ahead of the next report, plus `guard` (`OmtGuard`: `enabled`, `reported`, `report_age_sec`, `stale`, `short` / `long` (`OmtRuleLoad`), `headroom`, `blocked_reason`), plus `throttling_member_action` and `throttling_user_action`, the two order actions every login states.

Open to every authenticated caller, a base slice of [`GetStatus`](#rpc-GetStatus): the OMT budget is shared by the desk's single M7 login, and it carries counts only, no money or positions.

#### Errors

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
th = client.get_throttling()
# Reported fields are proto3 `optional` scalars, so HasField() works directly.
if th.HasField("short_omt_limit_l1"):
    print("short OMT L1 limit:", th.short_omt_limit_l1)

# The guard is always populated: pace a burst off its headroom rather than
# discovering the limit by being throttled.
print("order actions still admitted:", th.guard.headroom)
if th.guard.HasField("blocked_reason"):
    print("refusing order actions:", th.guard.blocked_reason)
```

**What the guard does.** It counts the OMTs this gateway sends against M7's last reported member load and refuses order actions before the warning threshold is reached. `CreateOrder`, `ModifyOrder` (modify / activate) fail with `FAILED_PRECONDITION` once `guard.headroom` reaches zero; while M7 reports the member `RESTRICTED`, *every* order action including `CancelOrder` and `CancelAllOrders` fails the same way, because the exchange would reject it anyway and the attempt would delay the release. A cancel or hibernation is never refused for headroom alone, so the desk can always get flat. The one exemption is the operator kill switch ([`set_trading_allowed(allowed=False)`](#rpc-SetTradingAllowed)): its account-wide flatten is dispatched whatever the guard and the exchange say, because a restriction is not something the operator can clear, and an exchange rejection is reported in its `flatten.error` as usual. `guard.*.estimated_load` is an estimate, not a bound in either direction: it does not see another API client's traffic since the last report, and it carries the exchange's whole reported count even after part of it has rolled out of the exchange's own window, so it more often over-states the member's load than under-states it.

### <a id="rpc-GetSystemInfo" name="rpc-GetSystemInfo"></a>`Unary` `rpc GetSystemInfo`

The M7 reference data this session runs against.

**Required permission:** Authenticated caller; no permission required. (see [Permissions](#permissions))

#### Request

This RPC takes no request fields.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `request_limits` | `repeated RequestLimit` | none | yes | The per-window request-rate limits the gateway enforces (see RequestLimit). |
| `voltnir_version` | `string` | none | optional | This gateway's own software version. Distinct from backend_version (the M7 exchange's build). Always set, even before the exchange's first system-information report arrives, so it is not optional. |
| `products` | `repeated Product` | none | yes | The product reference table: what an order on each product is allowed to be. Arrives on its own report, so it can be populated while the system-info answer above is still outstanding, and vice versa. |
| `risk_sets` | `repeated RiskSet` | none | yes | The risk-set reference table: what an order will cost against the cash limit. Same independence as products. |

> [!NOTE]
> **The bounds are the ones actually enforced.** They come from the exchange's own product reference data, not a table inside the gateway, and they are in the wire units a `SubmitOrderRequest` carries, price in cents, quantity in sub-MW, so they compare directly against its fields with no conversion. An **absent** bound is *not* enforced: the exchange published nothing usable for that rule and judges it itself. Reading this is how a client learns the tick it is held to rather than inferring it from an `INVALID_ARGUMENT`. Field-by-field meanings are tabulated on the [REST `GET /system_info`](rest_api_v1.md#get-system-info) page.

None.

`SystemInfo`: `voltnir_version` (this gateway's build, always set), the M7 backend metadata, a repeated `RequestLimit` (`message`, `duration_ms`, `rate`) list, a repeated `Product` and a repeated `RiskSet`.

`Product`: `name` (joins to `Contract.prod`), `currency`, `state`, `revision_no`, `cash_limit_enabled`, `default_risk_set_id`, a repeated `ProductDeliveryArea` (`delivery_area_id`, optional `risk_set_id` overriding the product default in that area), and the bounds: `tick_cents`, `min_price_cents`, `max_price_cents`, `lot_sub_mw`, `min_qty_sub_mw`, `max_qty_sub_mw`, `iceberg_min_peak_sub_mw`, each `optional`, and absent means not enforced. It also carries the product's M7 decimal scale: `dec_shft_px` / `dec_shft_qty` (`optional int32`) and `qty_unit` (`optional string`), the shifts and unit M7 publishes, set for a representable product and for an unrepresentable one (so a client can see what made it unrepresentable, e.g. a `qty_unit` of `kW`), and unset only when no report has recorded a scale yet; and `scale`, a `ProductScaleClass` enum, `PRODUCT_SCALE_CLASS_REPRESENTABLE`, `_UNREPRESENTABLE` or `_UNKNOWN`. The bounds and every order field are always on the gateway's own cents (`dec_shft_px` 2) and sub-MW (`dec_shft_qty` 3) scale regardless; these fields describe the M7 boundary the gateway converts across. Last, the product's user-defined block settings: `block_order_product` (`optional bool`, whether the product takes blocks; `false` refuses a create with `BLOCK_NOT_SUPPORTED`) and `block_maximum_hours` (`optional uint32`, how much one block may group, read both as a count of the product's contracts and as hours, so a window is refused with `BLOCK_WINDOW_TOO_LONG` only when it exceeds both) and `dst_block_product` (`optional bool`, the product's treatment of contracts on the 25-hour clock-change day, as published; no local check reads it, so on that day the exchange decides). `linked_order_product` (`optional bool`, whether the product takes orders in a `linked` basket, as published; `false` refuses one locally with `BASKET_LINKED_NOT_SUPPORTED`, unset refuses nothing). Each is unset when the product publishes no reading of it (a published `blockMaximumHours` of 0 reads as none), and an unset setting restricts nothing: test presence, never read the zero default as the setting.

`RiskSet`: `risk_set_id`, `name`, `revision_no`, and the twelve parameters as `a` (`RiskSetA`, eight price-dependent) and `alpha` (`RiskSetAlpha`, four price-independent). One leg contributes `a[case] × signed price × MWh + alpha[case] × MWh` to consumed cash, with `case` chosen by side, price sign and order-versus-trade; `a` is a bare multiplier and `alpha` is in the product's currency per MWh. Which set applies is decided by the leg's product and delivery area.

Three independent parts: the system parameters captured on connection (backend version, time zones, data-retention windows, the per-session order cap, capabilities and the per-message-type request rate limits); the `products` table, carrying the bounds every order is measured against before it is published, one entry for **every product the exchange has assigned your account**, not only the ones the gateway subscribes market data for, since it inquires product reference data account-wide; and the `risk_sets` table, carrying the parameters the exchange prices cash-limit exposure with. The M7-sourced scalars are `optional` and `request_limits` is empty until M7 has sent its first system-information report; the two tables come from separate reports, so either can be populated while that answer is still outstanding. `voltnir_version` is this gateway's own software version (not from M7): a plain `string` that is always set.

#### Errors

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
info = client.get_system_info()
if info.HasField("max_orders"):
    print("max resting orders:", info.max_orders)
for rl in info.request_limits:
    print(rl.message, "→", rl.rate, "per", rl.duration_ms, "ms")
```

### <a id="rpc-GetAreaTable" name="rpc-GetAreaTable"></a>`Unary` `rpc GetAreaTable`

The M7 EIC area reference table: every delivery / hub-to-hub area (`areas`) and market area (`market_areas`), with each area’s `short_name` / `long_name` overlaid from the live M7 area reports when the exchange named it.

**Required permission:** Authenticated caller; no permission required. (see [Permissions](#permissions))

#### Request

This RPC takes no request fields.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `areas` | `repeated AreaInfo` | none | yes | One entry per delivery or hub-to-hub area known to the exchange (see AreaInfo). |
| `market_areas` | `repeated MarketAreaInfo` | none | yes | One entry per market area that groups delivery areas (see MarketAreaInfo). |

> [!NOTE]
> **`fill_country` is the whole country an area colours on a country-fill map**, already folded so a virtual or control sub-zone carries its parent country. It is an `optional string` and is **unset** for a `border_coupling` area, which is a border and fills no country, test `HasField("fill_country")` and treat unset as “no country”, never a blank one. Field-by-field meanings are tabulated on the [REST `GET /area_table`](rest_api_v1.md#get-area-table) page.

None.

`AreaTable`: a repeated `AreaInfo` (`areas`) and a repeated `MarketAreaInfo` (`market_areas`).

`AreaInfo`: `eic`, `short_name`, `long_name`, `parent_ma_eic` (`optional string`, unset for areas grouped only by a short name), `fill_country` (`optional string`, unset for a border/coupling area), `area_class` (an `AreaClass` enum, `AREA_CLASS_BIDDING_ZONE`, `_VIRTUAL_OPTIMISATION`, `_BORDER_COUPLING` or `_CONTROL_AREA`), `epex_da` and `h2h_only` flags, a repeated `assigned_products`, and `name_source` (an `AreaNameSource` enum, `AREA_NAME_SOURCE_STATIC` or `_EXCHANGE`). Tradability is `epex_da`, never inferred from `area_class`: a bidding zone can be hub-to-hub only.

`MarketAreaInfo`: `eic`, `name`, `long_name`, `name_source`. A delivery area’s `parent_ma_eic` joins to one of these.

Structure and geometry (`fill_country`, `area_class`, `parent_ma_eic`, the EPEX / hub-to-hub flags) are always the embedded table’s; the exchange supplies names only. The embedded table is the always-available floor, so this answers off a fresh connection with `name_source` `AREA_NAME_SOURCE_STATIC` until a live name lifts a row to `AREA_NAME_SOURCE_EXCHANGE`.

#### Errors

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
table = client.get_area_table()
for a in table.areas:
    if a.HasField("fill_country"):
        print(a.eic, "fills", a.fill_country)
    else:
        print(a.eic, "is a border/coupling area, no fill")
```

### <a id="rpc-GetPnl" name="rpc-GetPnl"></a>`Unary` `rpc GetPnl`

Recompute the caller-scoped PnL snapshot from the live trade store + order book.

**Required permission:** Authenticated caller; no permission required. `read_pnl` widens the result. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `v_member_short_id` | `string` | none | No | Empty = caller's default scope. Non-empty narrows to one member's rows; `PermissionDenied` unless the caller is assigned to it or holds `read_pnl`/`bypass_member_check`. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `per_contract` | `repeated ContractPnl` | none | yes | One entry per (area_id, contract_id) that has any trade the exchange has not reversed (any state but `RGRA` or `CNCL`). |
| `per_area_prod` | `repeated AreaProductPnl` | none | yes | Roll-up across contracts in each (area_id, product) bucket. |
| `per_vm` | `repeated VmContractPnl` | none | yes | One entry per (v_member_short_id, area_id, contract_id). |
| `per_vm_area_prod` | `repeated VmAreaProductPnl` | none | yes | Roll-up per (v_member_short_id, area_id, product). |
| `computed_at_ms` | `int64` | Unix ms UTC | yes | Unix ms UTC |
| `compute_us` | `uint32` | microseconds | yes | microseconds spent in compute() |
| `totals` | `repeated CurrencyTotal` | none | yes | One realized/unrealized total per currency, summed server-side so a client renders the venue figure without adding rows (and never adds EUR to GBP). |
| `unpriced_trades` | `uint64` | none | yes | Trades the exchange has not reversed (any state but `RGRA` or `CNCL`) left out of this snapshot because their delivery duration is not yet known, so the money could not be energy-scaled; they rejoin once the contract report heals the duration. |

**Scoping.** A caller holding `read_pnl` (or `bypass_member_check`) gets the firm-wide snapshot: every member plus the house-account `per_contract`/`per_area_prod` rollups. Everyone else gets only the `per_vm`/`per_vm_area_prod` rows for their assigned members, with the firm-wide rollups empty.

`PnlSnapshot` with four scopes: `per_contract`, `per_area_prod`, `per_vm`, `per_vm_area_prod`; a per-currency `totals`; `unpriced_trades`; plus `computed_at_ms` / `compute_us`.

Mirrors REST `GET /api/v1/pnl` and the WebSocket `pnl` stream. Money is q8 units = M7-px × sub-MW × `duration_min`/60 = **currency × 100,000**, energy-scaled by the contract's delivery duration (a 15-minute fill is a quarter of its hourly value); divide by 100,000 to render the currency. Every row carries its `currency` (`EUR`/`GBP`) and `totals` sums per currency, never across. `unpriced_trades` counts trades the exchange has not reversed (any state but `RGRA` or `CNCL`) whose duration is not yet known (left out of the walk, never guessed). Each row carries its local `delivery_day` (`YYYY-MM-DD` in the market's timezone; empty when unknown), and the live snapshot covers only contracts whose delivery day is today or later, so the total does not depend on restart timing. `MarkSource` adds `MARK_SOURCE_CLOSE` and `MARK_SOURCE_CLOSE_LAST`: a closed contract's residual is valued at M7's closing reference price, or the gateway's own last mark frozen at close until one arrives. The walk attributes each side of a trade (each fill) to its own virtual member. Open / pending orders do not contribute; fees, FX and imbalance valuation are not modelled.

#### Errors

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
snap = client.get_pnl()
# Read the server-summed per-currency totals. Never add EUR to GBP yourself.
for t in snap.totals:
    total = (t.realized_pnl + t.unrealized_pnl) / 100_000
    print(f"PnL: {total:+.2f} {t.currency}")
```

### <a id="rpc-GetTradingAllowed" name="rpc-GetTradingAllowed"></a>`Unary` `rpc GetTradingAllowed`

Read the operator kill-switch.

**Required permission:** Authenticated caller; no permission required. (see [Permissions](#permissions))

#### Request

This RPC takes no request fields.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `allowed` | `bool` | none | yes | True when trading is enabled, false when the kill switch is engaged. |

`TradingAllowedResponse { bool allowed, optional FlattenOutcome flatten }`. A read never carries `flatten`; it is set only by `set_trading_allowed(allowed=False)`.

Open to every authenticated caller, the `trading_enabled` base slice of [`GetStatus`](#rpc-GetStatus), which a trader needs to know whether it may submit at all.

#### Errors

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
print("trading allowed:", client.get_trading_allowed().allowed)
```

### <a id="rpc-GetSelfTradePolicy" name="rpc-GetSelfTradePolicy"></a>`Unary` `rpc GetSelfTradePolicy`

Returns the active self-trade (cross-trade) prevention policy.

**Required permission:** Authenticated caller; no permission required. (see [Permissions](#permissions))

#### Request

This RPC takes no request fields.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `policy` | `SelfTradePolicy` | none | yes | The active self-trade prevention policy, OBSERVE or REJECT. |

`SelfTradePolicyResponse { SelfTradePolicy policy }`: `SELF_TRADE_POLICY_OBSERVE` or `SELF_TRADE_POLICY_REJECT`.

EPEX M7 does not prevent self-trades server-side; this is a Voltnir-side pre-trade check.

#### Errors

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
print(client.get_self_trade_policy().policy)
```

### <a id="rpc-GetCashLimits" name="rpc-GetCashLimits"></a>`Unary` `rpc GetCashLimits`

Snapshot of every currency's M7 cash/margin limit.

**Required permission:** `read_status`. (see [Permissions](#permissions))

#### Request

This RPC takes no request fields.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `limits` | `repeated CashLimit` | none | yes | One entry per currency of the exchange-reported cash-limit slice (see CashLimit). |

None.

`GetCashLimitsResponse { repeated CashLimit limits }`.

Mirrors REST `GET /api/v1/cash_limits`. Raw integer fields pair with `dec_shft`: human amount = raw / 10dec_shft. Every field past `currency` is `optional`; partial reports leave them unset. Gated by `read_status` (`PERMISSION_DENIED` without it), this exposes the desk-wide money that [`GetStatus`](#rpc-GetStatus) carries only under `read_status`.

#### Errors

| gRPC status | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `read_status`. |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
resp = client.get_cash_limits()
for lim in resp.limits:
    if lim.HasField("current_limit") and lim.HasField("dec_shft"):
        print(lim.currency, lim.current_limit / (10 ** lim.dec_shft))
```

### <a id="rpc-GetCashLimit" name="rpc-GetCashLimit"></a>`Unary` `rpc GetCashLimit`

Read the desk's cash limit for both currency pools.

**Required permission:** `read_status`. (see [Permissions](#permissions))

#### Request

This RPC takes no request fields.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `eur` | `CashPool` | none | yes | The EUR cash pool: its exchange House limit, any operator cap, member allocations and remaining headroom, in cents (see CashPool). |
| `gbp` | `CashPool` | none | yes | The GBP cash pool, the same fields in the independent GBP pool, in cents (see CashPool). |

`CashLimitResponse { CashPool eur, CashPool gbp }`. Each `CashPool` carries `ecc_limit_cents` (`Int64Value`, unset when the exchange has reported none), `ecc_revision` (`Int64Value`), `ecc_effective_from` (`string`, the date that record takes effect, `YYYY-MM-DD` in the exposure timezone; the exchange sends it as an instant, so the calendar day it names depends on that zone. `""` when not reported or unreadable; the raw exchange value is on `GetCashLimits`), `m7_remaining_cents` (`Int64Value`, what the exchange still has available, already net of the desk's own open orders and trades), `cap_cents` (`Int64Value`, unset = no cap; `0` = a deliberate cap of zero), `house_cents` (`sint64` = `min(ecc_limit_cents, cap_cents)`, the number every check uses), `cap_above_ecc` (`bool`, a standing cap the exchange has since dropped below; the cap is left untouched and the ECC limit binds) `breached` (`bool`, the exchange reports the pool's current limit below zero and has deactivated every order in that currency), `reported_at_ms` (`Int64Value`, when the exchange last reported this pool, Unix ms UTC; unset when it never has) and `stale` (`bool`, the pool's figures can no longer be vouched for, because the broadcast channel carrying its reports broke since they arrived, or because the optional the cash-report freshness window ceiling is armed and has been passed; they count as unknown and every order that adds exposure in the pool is rejected with scope `stale_cash_limit` until it is reported again. A quiet desk on an unbroken channel is not stale). The House limit is then **partitioned**: `allocated_cents` (`sint64`) is what the virtual members hold between them, active and inactive alike, and `unallocated_cents` (`sint64` = `house_cents − allocated_cents`) is what is left for orders placed on the House account itself, it can go negative, flagged by `over_allocated` (`bool`), when the exchange lowers its limit under allocations already granted. An ECC limit the exchange has not reported counts as **zero**: no order may add exposure in that pool. The two pools are independent (ECC settles them separately).

**How much an order or trade consumes.** The exchange publishes a *risk set* per product and delivery area: eight price-dependent `a` parameters and four price-independent `alpha` parameters. One leg consumes `a[case] × signed price × MWh + alpha[case] × MWh`, where `case` is chosen by side, price sign, and whether the exposure comes from a resting order or an executed trade. Voltnir reads those parameters from the exchange and prices with them, so its arithmetic is the exchange's arithmetic. A resting order never contributes a credit, its exposure is floored at zero, and every figure scales with the contract's delivery duration, so a 15-minute leg counts a quarter of the hourly amount.

On the exchange's default risk set this reproduces ECC's published risk parameters exactly: a buy at a positive price consumes its value, a trade moves the limit by its full signed value, and the risk-free order cases (sell at a positive price, buy at a negative price) cost nothing. The one exception is a trade whose delivery duration Voltnir does not yet know: it is counted as one hour long when it consumes, and credits nothing until its duration is known. A GB delivery area is assigned a risk set carrying ECC's *GB Price Independent Delivery Risk Parameter* as its `alpha` sell value, which is why a GB sell also decreases the limit for a member the add-on applies to (`CashLimitStatus.delivery_risk_applied`; with it `false` a GB leg is priced with its product's default risk set instead, the set the exchange prices such a member's GB legs with), and a GB risk set may charge the price term on a negative-price sell on top of that add-on, and decline to credit a negative-price buy trade.

Until the exchange has published a risk set for a contract's product and area, Voltnir prices the leg with a stand-in rather than at zero: ECC's EUR rules for a non-GBP area, and the operator-configured GBP delivery-risk rate (`cash_limit.gbp_sell_reservation_*`) for a GBP one, charged only with `delivery_risk_applied` on, logged once per delivery area.

**The limit is ECC's:** ECC gives the Trading Participant a Cash Limit per settlement currency, the maximum financial exposure it may build between two ECC Booking Cuts, and the gateway receives it from M7. An operator cap can only tighten it. Mirrors REST `GET /api/v1/cash_limit`. Distinct from `get_cash_limits()` (plural), the raw M7 feed. Gated by `read_status` (`PERMISSION_DENIED` without it), this exposes the desk-wide money that [`GetStatus`](#rpc-GetStatus) carries only under `read_status`.

#### Errors

| gRPC status | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `read_status`. |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
eur = client.get_cash_limit().eur
print("house limit:", eur.house_cents, "EUR cents")
```

### <a id="rpc-GetContractLimit" name="rpc-GetContractLimit"></a>`Unary` `rpc GetContractLimit`

Read the current per-contract net-position cap (sub-MW).

**Required permission:** `read_status`. (see [Permissions](#permissions))

#### Request

This RPC takes no request fields.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `quantity` | `sint32` | sub-MW (MW × 1000) | yes | sub-MW |

`ContractLimitResponse { sint32 quantity }`.

Gated by `read_status` (`PERMISSION_DENIED` without it), this exposes the desk-wide money that [`GetStatus`](#rpc-GetStatus) carries only under `read_status`.

#### Errors

| gRPC status | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `read_status`. |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
resp = client.get_contract_limit()
print("limit:", resp.quantity, "sub-MW")
```

### <a id="rpc-GetHolidays" name="rpc-GetHolidays"></a>`Unary` `rpc GetHolidays`

Read both ECC **bank-holiday calendars** (EUR + GBP) for the cash-limit exposure window.

**Required permission:** Authenticated caller; no permission required. (see [Permissions](#permissions))

#### Request

This RPC takes no request fields.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `eur` | `repeated Holiday` | none | yes | The EUR pool's configured non-working dates after the call (see Holiday). |
| `gbp` | `repeated Holiday` | none | yes | The GBP pool's configured non-working dates after the call (see Holiday). |

`HolidaysResponse { repeated Holiday eur; repeated Holiday gbp }`, where `Holiday { string date; string label }` (`label` empty when unset).

Mirrors REST `GET /api/v1/holidays`. The cash limit re-bases exposure at 16:00 (ECC tz) on each **ECC Business Day**, a weekday that is not a TARGET2 closing day, and the GBP limit resets on the same days as the EUR limit, so the same six TARGET2 dates go in both calendars every year. They are separate lists only so an ad-hoc ECC closure or a non-ECC deployment can be expressed. **The gateway fills in the TARGET2 dates itself:** it derives the six closing days (four fixed dates, two computed from Easter) and adds them to both calendars at startup and on an hourly check, for the current year and, from December, the next one too, so the turn of the year needs no action. Derived entries carry an `(auto)` suffix on their `label`. A date already in a calendar is never overwritten, so an operator's entry for the same day always wins. **Deleting one of the six derived dates sticks:** the remove operation remembers it for that currency, whoever entered the date, and the check does not add it back; the deletion is persisted with the calendar and survives a restart, and adding the date again, by add or replace, lifts it. A replace is not a deletion: a date it leaves out is restocked at the next check. ECC publishes no machine-readable calendar, so this is a derivation, not a feed: an ad-hoc ECC closure is added through these operations, and a change to the TARGET2 schedule is made by deleting the derived date that no longer applies and adding the new one. Runtime-managed and persisted to the database. **An empty calendar is a missing input, not a permissive one:** without it the exposure window can only skip weekends and rolls a day early through every TARGET2 closing day, so that currency's pool refuses every order which adds exposure (`no_holiday_calendar`) until a date is entered. The startup fill and the hourly check keep a calendar stocked with the TARGET2 dates, but never restore one an operator deleted: a calendar emptied by deletions stays empty until a date is added. A deleted TARGET2 date also makes the cash check more permissive, since the exposure window then resets on that day as on a business day, so its deletion is logged at WARN and every start logs, per currency, this year's deleted TARGET2 dates. **A calendar is only current for the year it covers:** one holding no date in the current or the next calendar year refuses the same orders under its own `stale_holiday_calendar`; with the derived dates in place this normally never fires. Orders that reduce or do not change exposure keep working, as does the other currency's pool, and entering a date for the current year lifts the refusal immediately, no restart.

#### Errors

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
for h in client.get_holidays().gbp:
    print(h.date, h.label)
```

<a id="ops-controls" name="ops-controls"></a>

## Limits & controls

### <a id="rpc-SetTradingAllowed" name="rpc-SetTradingAllowed"></a>`Unary` `rpc SetTradingAllowed`

Operator kill-switch.

**Required permission:** `toggle_trading`. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `allowed` | `bool` | none | Yes | `True` = trading on; `False` = kill-switch. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `allowed` | `bool` | none | yes | The trading flag after the call, false when the kill switch is engaged. |

> [!WARNING]
> `set_trading_allowed(allowed=False)` asks the exchange to cancel every resting order. There is no undo. **The flag is off whether or not the cancel reached the exchange**, read `flatten.ok` to learn whether the exchange confirmed receipt of the cancel, and treat `False` as "orders may still be live on the exchange".

> [!CAUTION]
> When the operator has disabled trading in the gateway configuration, this RPC is rejected with `ABORTED`: the config flag is the absolute authority and the runtime toggle cannot override it.

`TradingAllowedResponse { bool allowed, optional FlattenOutcome flatten }` echoing the new state.

| Field | Type | Description |
| --- | --- | --- |
| `allowed` | `bool` | The trading flag as it now stands. Always the value you sent, the flip is applied before the flatten and is never rolled back by it. |
| `flatten` | `FlattenOutcome` | Present only when `allowed=False`; enabling publishes nothing, so the field is absent (`HasField("flatten")` is `False`). |
| `flatten.ok` | `bool` | `True` only when M7 acknowledged the cancel, EPEX's receipt of the command, so it was accepted for processing; the resulting order state converges on the order stream. `False` means the publisher queue would not take the command inside the ack window (the exchange connection is most likely down), the exchange rejected it, or no receipt arrived inside the order acknowledgement timeout (2000 ms by default), in every one of those cases resting orders may still be live and the desk should verify the book directly. |
| `flatten.error` | `string` | The reason when `ok` is `False`; empty otherwise. Every kill-switch flatten is written to the audit log as `order_cancel_all`, outcome `ok` when confirmed, outcome `error` carrying this reason when not. |

> [!NOTE]
> A failed flatten is not an RPC error: the call returns `OK` because the kill switch itself took effect. The distinction is deliberate, a status error would invite a retry, and re-sending the toggle does not re-run the cancel any more reliably than `cancel_all_orders` does.

Setting `allowed=False` rejects exposure-adding traffic (`submit_order` and `modify_order` fail with `FAILED_PRECONDITION`) **and** dispatches an account-wide cancel to the exchange, reporting in `flatten` whether M7 confirmed it. Cancels (`cancel_order` / `cancel_all_orders`) stay available, since pulling an order only reduces exposure.

#### Errors

| gRPC status | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `toggle_trading`. |
| `ABORTED` | The operator has disabled trading in configuration, which the runtime toggle cannot override. |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
resp = client.set_trading_allowed(allowed=False)   # kill-switch on
if not resp.flatten.ok:
    print("cancel NOT confirmed by the exchange:", resp.flatten.error)
```

### <a id="rpc-AckTradeIngestFault" name="rpc-AckTradeIngestFault"></a>`Unary` `rpc AckTradeIngestFault`

Acknowledge a raised `trade_report refused` fault, reopening order admission on incomplete figures. While the gateway holds a trade report it could not read, a trade the exchange executed is missing from its count, so position, cash and P&L are understated and, under the default `system.trade_ingest_fault: close`, new orders and modifies are refused. An acknowledgement admits them for `system.trade_ingest_fault_ack_ttl_sec` (1800 s by default) while no other issue is present; `admission` on state and status reads `degraded` meanwhile. Meanwhile the gateway does not reconnect its exchange session over the fault; another order-critical issue closes admission as usual, and the TTL keeps running while it does. It ends early when the fault clears, a repeat restarts the TTL, and it lives in the gateway's memory, so a restart drops it (the login backfill raises the fault again if the report is still unreadable). Each acknowledgement writes a `trade_ingest_fault_acknowledged` audit row carrying the reason and the TTL; one that runs out writes `trade_ingest_fault_ack_expired`. The exchange still checks the member's cash limit on every order. The trading terminal has no control for this: it is an API call. Mirrors REST `POST /trade_ingest_fault/ack` and the WS `ack_trade_ingest_fault` command.

**Required permission:** `toggle_trading`. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `reason` | `string` | none | Yes | Why the desk trades on. Recorded in the audit row. Empty or blank is refused. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `ttl_sec` | `uint64` | s | yes | How long admission is reopened for. |
| `expires_at_ms` | `int64` | Unix ms | yes | When the acknowledgement expires. It ends earlier when the fault clears. |
| `renewed` | `bool` | none | yes | `true` when it replaced a live acknowledgement, restarting the TTL. |

#### Errors

| gRPC status | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `toggle_trading`. |
| `INVALID_ARGUMENT` | `reason` is empty or blank (message `BAD_REQUEST: …`). |
| `ABORTED` | No `trade_report refused` fault is raised, or the private consumer or the private-data stream is down, so no trade report could arrive (message `CONFLICT: …`). |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
resp = client.ack_trade_ingest_fault("balancing; support desk paged")
print("admission reopened for", resp.ttl_sec, "s")
```

### <a id="rpc-SetContractLimit" name="rpc-SetContractLimit"></a>`Unary` `rpc SetContractLimit`

Update the per-contract net-position cap.

**Required permission:** `set_position_limit`. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `quantity` | `sint32` | sub-MW (MW × 1000) | Yes | New limit in sub-MW. Negative values are rejected. **`0` is fully supported and blocks all new position-taking** (every order that would move \|net position\| above 0 is rejected), the operator kill-switch. `0` does *not* disable the check. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `quantity` | `sint32` | sub-MW (MW × 1000) | yes | sub-MW |

`ContractLimitResponse` echoing the new value.

Applies immediately to subsequent `submit_order` validation.

#### Errors

| gRPC status | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `set_position_limit`. |
| `INVALID_ARGUMENT` | The quantity is not a valid sub-MW value. |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
client.set_contract_limit(quantity=50000)   # 50 MW
```

### <a id="rpc-SetCashLimit" name="rpc-SetCashLimit"></a>`Unary` `rpc SetCashLimit`

Set or clear the **operator cap** on one cash pool.

**Required permission:** `set_cash_limit`. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `cap_cents` | `Int64Value` | cents (currency × 100) | No | New cap in cents of the target currency. Must be ≥ 0 and at or below the ECC limit. Unset removes the cap; `0` is a deliberate cap of zero (no trading in that pool). |
| `currency` | `string` | none | No | `"eur"` (default) or `"gbp"`. Unknown values return `INVALID_ARGUMENT`. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `eur` | `CashPool` | none | yes | The EUR cash pool: its exchange House limit, any operator cap, member allocations and remaining headroom, in cents (see CashPool). |
| `gbp` | `CashPool` | none | yes | The GBP cash pool, the same fields in the independent GBP pool, in cents (see CashPool). |

The House limit itself comes from ECC and is not settable here; a cap only ever tightens it. Applies immediately to subsequent `submit_order` / `modify_order` validation. `currency` selects the pool (EUR and GBP are independent).

#### Errors

`INVALID_ARGUMENT` for a negative cap, a cap above the ECC limit (**rejected, never clamped**, the message names the pool and both amounts), a cap set before the exchange has reported a limit to tighten, a cap that would leave `house_cents` below `allocated_cents` (Voltnir never shrinks a member's allocation on its own, lower the member allocations first), or an unknown currency. Nothing is written on a rejection. Clearing a cap is always accepted.

`CashLimitResponse` with both pools after the update.

#### Errors

| gRPC status | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `set_cash_limit`. |
| `INVALID_ARGUMENT` | currency is neither "eur" nor "gbp". |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
client.set_cash_limit(cap_cents=5000000)                  # cap the EUR pool at €50,000
client.set_cash_limit(cap_cents=None, currency="gbp")    # remove the GBP cap
```

### <a id="rpc-SetSelfTradePolicy" name="rpc-SetSelfTradePolicy"></a>`Unary` `rpc SetSelfTradePolicy`

Set the self-trade prevention policy.

**Required permission:** `set_self_trade_policy`. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `policy` | `SelfTradePolicy` | none | Yes | `SELF_TRADE_POLICY_OBSERVE` or `SELF_TRADE_POLICY_REJECT`; anything else is `INVALID_ARGUMENT`. The Python SDK also accepts `"observe"` or `"reject"`. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `policy` | `SelfTradePolicy` | none | yes | The self-trade prevention policy after the call, OBSERVE or REJECT. |

`SelfTradePolicyResponse` echoing the new policy. An unspecified/unknown value returns `INVALID_ARGUMENT`.

Takes effect immediately and is persisted. With `reject`, an order that would cross one of your own resting orders fails `submit_order` with `FAILED_PRECONDITION` and a `SELF_CROSS_BLOCKED` message; `modify_order` fails the same way, checked at the order's new price. The operator default self-trade policy in the gateway configuration only seeds the default on a fresh database.

#### Errors

| gRPC status | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `set_self_trade_policy`. |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
client.set_self_trade_policy(policy="reject")
```

### <a id="rpc-SetHolidays" name="rpc-SetHolidays"></a>`Unary` `rpc SetHolidays`

Replace one currency's whole calendar (holidays are part of the cash-limit methodology, so gated by `set_cash_limit`).

**Required permission:** `set_cash_limit`. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `currency` | `string` | none | Yes | `"eur"` or `"gbp"`. |
| `holidays` | `repeated Holiday` | none | No | Full replacement list; empty clears the currency. Duplicate dates are rejected (`INVALID_ARGUMENT`). |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `eur` | `repeated Holiday` | none | yes | The EUR pool's configured non-working dates after the call (see Holiday). |
| `gbp` | `repeated Holiday` | none | yes | The GBP pool's configured non-working dates after the call (see Holiday). |

`HolidaysResponse` with both calendars after the change.

Applies immediately on the next cash check. Mirrors REST `PUT /api/v1/holidays`.

#### Errors

| gRPC status | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `set_cash_limit`. |
| `INVALID_ARGUMENT` | A malformed date, or currency is neither "eur" nor "gbp". |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
from voltnir_sdk import Holiday
client.set_holidays(currency="gbp", holidays=[
    Holiday(date="2026-05-01", label="Labour Day"),
    Holiday(date="2026-12-25"),
])
```

### <a id="rpc-AddHoliday" name="rpc-AddHoliday"></a>`Unary` `rpc AddHoliday`

Add a single date to a currency's calendar.

**Required permission:** `set_cash_limit`. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `currency` | `string` | none | Yes | `"eur"` or `"gbp"`. |
| `date` | `string` | YYYY-MM-DD | Yes | `YYYY-MM-DD`. |
| `label` | `string` | none | No | Optional display label. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `eur` | `repeated Holiday` | none | yes | The EUR pool's configured non-working dates after the call (see Holiday). |
| `gbp` | `repeated Holiday` | none | yes | The GBP pool's configured non-working dates after the call (see Holiday). |

`HolidaysResponse` with both calendars after the change.

Mirrors REST `POST /api/v1/holidays`. A duplicate date or malformed `YYYY-MM-DD` is `INVALID_ARGUMENT`.

#### Errors

| gRPC status | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `set_cash_limit`. |
| `INVALID_ARGUMENT` | A duplicate date, a malformed date, or currency is neither "eur" nor "gbp". |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
client.add_holiday(currency="eur", date="2026-01-01", label="New Year's Day")
```

### <a id="rpc-RemoveHoliday" name="rpc-RemoveHoliday"></a>`Unary` `rpc RemoveHoliday`

Remove a single date from a currency's calendar.

**Required permission:** `set_cash_limit`. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `currency` | `string` | none | Yes | `"eur"` or `"gbp"`. |
| `date` | `string` | YYYY-MM-DD | Yes | `YYYY-MM-DD`. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `eur` | `repeated Holiday` | none | yes | The EUR pool's configured non-working dates after the call (see Holiday). |
| `gbp` | `repeated Holiday` | none | yes | The GBP pool's configured non-working dates after the call (see Holiday). |

`HolidaysResponse` with both calendars after the change.

Mirrors REST `DELETE /api/v1/holidays`. A date that is not configured is `NOT_FOUND`. Deleting one of the six derived TARGET2 dates keeps it out of the automatic fill for that currency until the date is added again.

#### Errors

| gRPC status | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `set_cash_limit`. |
| `NOT_FOUND` | The date is not in that currency calendar. |
| `INVALID_ARGUMENT` | currency is neither "eur" nor "gbp". |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
client.remove_holiday(currency="eur", date="2026-01-01")
```

### <a id="rpc-Restart" name="rpc-Restart"></a>`Unary` `rpc Restart`

Restart the gateway process.

**Required permission:** `restart_system`. (see [Permissions](#permissions))

#### Request

This RPC takes no request fields.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `message` | `string` | none | yes | A human-readable confirmation that the restart was accepted. |

> [!WARNING]
> Real shutdown, not a soft reset, and not the gateway’s own internal exchange reconnect (which cycles the M7 subsystems and leaves the process up). Active streams, in-flight orders and WebSocket subscribers are torn down; every `Watch*` stream ends and must be re-established against the new process. **Without a supervisor configured to restart it, the gateway stops and stays stopped.** The exit status is 75 rather than 0 on purpose: the shipped systemd unit uses `Restart=on-failure`, so a restart request comes back while `systemctl stop` (SIGTERM, exit 0) stays stopped. Database state and the persisted profile survive; export tokens do not.

None.

`RestartResponse`: sent before the process exits.

Mirrors REST `POST /api/v1/restart` and the WebSocket `restart` command. The response is sent first; the gateway then drains its transports, logs out of M7, commits every queued write (for up to 30 seconds; a write it cannot commit in that time is counted in `writes_dropped` (a trade in `trades_persist_failed`)), records the shutdown in the audit trail with the run's lost writes per stream, and exits with status **75**, so the host supervisor (systemd, Docker, …) starts a fresh process that re-reads the gateway configuration.

#### Errors

| gRPC status | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `restart_system`. |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
client.restart()
```

### <a id="rpc-RestoreTradeHistory" name="rpc-RestoreTradeHistory"></a>`Unary` `rpc RestoreTradeHistory`

Repopulate the persistent trade store from the exchange over `[now − effective_days, now]`.

**Required permission:** `restore_trade_history`. (see [Permissions](#permissions))

#### Request

This RPC takes no request fields.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `chunk_count` | `uint32` | none | yes | How many paced requests to the exchange the window was split into (0 for an empty window). Delivery is asynchronous and paced; watch the SystemState trades_received / trades_persisted counters for progress. |
| `effective_from_ms` | `int64` | Unix ms UTC | yes | The oldest instant requested, epoch milliseconds. |
| `effective_days` | `uint32` | days | yes | Days of history requested after clamping to the exchange's reach; may be less than the requested `days`. |

> [!NOTE]
> A restore is **isolated from cash correctness**: its chunks are not registered with the cash-exposure coverage gate, so it never affects order admission. The restored tape is complete: cancelled and recalled trades are included, carrying their exchange state; a granted recall (`RGRA`) or a cancellation (`CNCL`) adds no exposure, as on a live report (see [Trade states](#trade-states)). Trades only, the exchange serves no history for filled or cancelled orders. Refuses with `Unavailable` until the exchange has reported `contractStoreTimeInDays`.

`days` (`optional uint32`): days of history to restore, clamped to the exchange’s reach. Omit to restore the full reach.

`RestoreTradeHistoryResponse { uint32 chunk_count, int64 effective_from_ms, uint32 effective_days }`: the plan the restore was armed with.

Mirrors REST `POST /api/v1/restore-trade-history` and the WebSocket `restore_trade_history` command. The break-glass for the audit tape after a wiped or migrated database, or after trades roll off the cash-exposure window. `effective_days = min(days, contractStoreTimeInDays)`; an omitted `days` restores the exchange’s whole reach and a larger value is clamped. The response returns the plan at once; the trades then arrive asynchronously as the paced requests are answered, so watch `trades_received` / `trades_persisted` on `GetState` / `WatchState` for progress.

#### Errors

| gRPC status | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `restore_trade_history`. |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
plan = client.restore_trade_history(days=3)
print(plan.chunk_count, plan.effective_days)
```

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

**Refusals.** On `SubmitOrder` and `ModifyOrder` the status is `FAILED_PRECONDITION`, with a message starting `slot position limit exceeded:` or `slot window unknown:` (the WS codes `SLOT_POSITION_LIMIT_EXCEEDED` and `SLOT_WINDOW_UNKNOWN`, REST `422`). `slot_position_limit_exceeded` names the area, the slot start and end, the side (`long` or `short`), the scope (`house` or the member's short id), the position the order would reach and the limit. `slot_window_unknown` names what has no delivery window: the order's contract, an open order's contract, or a trade. A caller without `read_status`, which cannot see the House limit elsewhere, is not shown the House figures: a refusal by the House slot limit reads `slot position limit exceeded: refused by the desk slot limit, <area> <slot start> to <slot end>, <long|short> side`, and a trade that has no delivery time is not named. A refusal by the member's own slot limit keeps the member's figures. The `order_rejected` audit row carries every field either way.

### <a id="rpc-GetSlotLimit" name="rpc-GetSlotLimit"></a>`Unary` `rpc GetSlotLimit`

The slot position limit's mode and the House slot limit. Mirrors REST `GET /slot_limit` and WS `get_slot_limit`.

**Required permission:** `read_status`. (see [Permissions](#permissions))

#### Request

This RPC takes no request fields.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `mode` | `SlotLimitMode` | none | yes | `SlotLimitMode`: `SLOT_LIMIT_MODE_OFF`, `SLOT_LIMIT_MODE_OBSERVE` or `SLOT_LIMIT_MODE_REJECT`. the gateway never sends `SLOT_LIMIT_MODE_UNSPECIFIED`; a client reads it as `OFF`, the default. |
| `house_limit` | `sint64` | sub-MW (MW × 1000) | yes | The House slot limit per quarter-hour. `0` is flat-only. |

#### Errors

| gRPC status | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `read_status`. |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
resp = client.get_slot_limit()
print(slot_limit_mode_name(resp.mode), resp.house_limit, "sub-MW")
```

### <a id="rpc-SetSlotLimit" name="rpc-SetSlotLimit"></a>`Unary` `rpc SetSlotLimit`

Set the mode and the House slot limit together. Takes effect for the next order and is persisted; a mode other than `OFF` announces at once any area already locked by a trade with no delivery window. Mirrors REST `PUT /slot_limit` and WS `set_slot_limit`.

**Required permission:** `set_position_limit`. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `mode` | `SlotLimitMode` | none | Yes | `SlotLimitMode`: `SLOT_LIMIT_MODE_OFF`, `SLOT_LIMIT_MODE_OBSERVE` or `SLOT_LIMIT_MODE_REJECT`. the gateway never sends `SLOT_LIMIT_MODE_UNSPECIFIED`; a client reads it as `OFF`, the default. Required: a request that leaves the mode unset (`SLOT_LIMIT_MODE_UNSPECIFIED`) is refused with `INVALID_ARGUMENT` `mode must be 'off', 'observe' or 'reject'`, so an unset field never turns the slot limit off. |
| `house_limit` | `optional sint64` | sub-MW (MW × 1000) | Yes | The House slot limit per quarter-hour. Must be set and ≥ 0; `0` is flat-only, not off. |

#### Response

`SlotLimitResponse`, the setting as it now stands.

#### Errors

| gRPC status | Condition |
| --- | --- |
| `INVALID_ARGUMENT` | `mode must be 'off', 'observe' or 'reject'`: `SLOT_LIMIT_MODE_UNSPECIFIED` or a value outside the enum. Nothing changes. |
| `INVALID_ARGUMENT` | `house_limit is required`: `house_limit` unset. Nothing changes. |
| `INVALID_ARGUMENT` | `house_limit must be non-negative`: a negative limit. Nothing changes. |
| `PERMISSION_DENIED` | The caller does not hold `set_position_limit`. |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
client.set_slot_limit(mode="observe", house_limit=20_000)  # 20 MW per quarter-hour
```

### <a id="rpc-GetSlotPositions" name="rpc-GetSlotPositions"></a>`Unary` `rpc GetSlotPositions`

Per-slot usage of the slot position limit. The usage read takes a delivery area, a range of at most 48 hours (`[from_ms, to_ms)` in UTC epoch milliseconds, `from_ms` rounded down to the quarter-hour, the 48 hours measured from there) and an optional member. It lists every slot in the range that holds exposure in a scope the caller sees, with, per scope, `net`, `max_long`, `max_short`, the `limit` that applies and the `buy_headroom` and `sell_headroom` left before that limit refuses an order, never below 0, all sub-MW. A caller sees the House scope only with `read_status`, and a member scope only for a member assigned to it and active. The read answers in every mode, `off` included, and reads the same sums the check reads. Mirrors REST `GET /slot_positions` and WS `get_slot_positions`; the live form is [`WatchSlotPositions`](#rpc-WatchSlotPositions).

**Required permission:** Authenticated caller; results are scoped to the members assigned to the caller and active. `read_status` widens the result to the House scope. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `delivery_area` | `string` | none | Yes | The delivery area (EIC code). |
| `from_ms` / `to_ms` | `int64` | Unix ms UTC | Yes | The range `[from_ms, to_ms)`, `from_ms` rounded down to the quarter-hour, at most 48 hours long. |
| `v_member_short_id` | `optional string` | none | No | Only that member's scope. `PERMISSION_DENIED` unless the member is assigned to the caller and active. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `delivery_area` / `from_ms` / `to_ms` | `string` / `int64` | Unix ms UTC | yes | The range as covered: `from_ms` rounded down and `to_ms` rounded up to the quarter-hour. |
| `mode` | `SlotLimitMode` | none | yes | The slot limit mode. |
| `house_limit` | `optional sint64` | sub-MW | `read_status` | The House slot limit; unset for a caller without `read_status`. |
| `locked` | `bool` | none | yes | A trade or an open order in the area has no known delivery window and still locks at least one slot: its exposure may be missing from a sum here, and on a locked slot only cancels and amendments that add no quantity pass the check. An open order, or a trade whose execution time is unknown, locks every slot of the area; a trade with a known execution time locks the slots up to the end of the delivery day after the one it executed on (in GB, to 23:00 London two days after it), until then. |
| `slots` | `repeated SlotPosition` | none | yes | Every slot holding exposure in a scope the caller sees, in time order: `slot_start_ms`, `slot_end_ms` (`int64`, Unix ms UTC) and `scopes` (`repeated SlotScopePosition`). |
| `SlotScopePosition` | message | sub-MW | yes | `scope` (`house` or the member's short id), `net`, `max_long`, `max_short` (`sint64`), and `limit`, `buy_headroom`, `sell_headroom` (`optional sint64`, unset for a member with no slot limit; the headroom never below 0). An order on a member is held to its member scope and the House scope both. |
| `seq` | `uint64` | none | yes | `0` on this RPC; the stream's sequence number on `WatchSlotPositions`. |

#### Errors

| gRPC status | Condition |
| --- | --- |
| `INVALID_ARGUMENT` | `the range is at most 48 hours from from_ms rounded down to the quarter-hour`, `to_ms must be after from_ms` or `delivery_area is required`. |
| `PERMISSION_DENIED` | `v_member_short_id` names a member not assigned to the caller, or an inactive one. |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

<a id="ops-users" name="ops-users"></a>

## Users & members

### <a id="rpc-GetMe" name="rpc-GetMe"></a>`Unary` `rpc GetMe`

Return the caller's own profile, derived from the bearer token.

**Required permission:** Authenticated caller; no permission required. (see [Permissions](#permissions))

#### Request

This RPC takes no request fields.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `id` | `string` | none | yes | The caller's user id. |
| `username` | `string` | none | yes | The caller's username. |
| `permissions` | `repeated string` | none | yes | permission codes |
| `short_id` | `string` | none | yes | compact handle (U001) used in audit attribution |

`UserProfile { string id, string username, repeated string permissions, string short_id }`: `short_id` (e.g. `"U001"`) is the compact handle used to attribute the user on the audit trail.

#### Errors

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
me = client.get_me()
print(me.username, list(me.permissions))
```

### <a id="rpc-GetMyMembers" name="rpc-GetMyMembers"></a>`Unary` `rpc GetMyMembers`

List the virtual members assigned to the caller.

**Required permission:** Authenticated caller; no permission required. (see [Permissions](#permissions))

#### Request

This RPC takes no request fields.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `members` | `repeated Member` | none | yes | The virtual members assigned to the caller (see Member). |

`MemberListResponse { repeated Member members }`. Each `Member` carries `id` / `short_id` / `name` / `max_position` (`sint64`, sub-MW, the per-contract limit) / `max_slot_position` (`optional sint64`, sub-MW, the member's [slot position limit](#ops-slot-limit); unset = none, `0` = flat-only) / `active` (`bool`) / `delivery_areas` (`DeliveryAreaScope { bool all; repeated string area_ids }`, always set: `all` is every area, including one the gateway is configured for later; otherwise only `area_ids`, and an empty list permits none. A member order in any other area is refused `FAILED_PRECONDITION` with `MEMBER_AREA_NOT_ALLOWED` on every action: submit, modify, activate, deactivate, cancel. Market data is not restricted), the member's allocations `cash_limit` / `cash_limit_gbp` (`sint64` cents; `0` = no allocation), and the live cash-usage trio per pool: `eur_consumed_cents` / `eur_limit_cents` / `eur_remaining_cents` and the `gbp_*` equivalents (all `sint64` cents). `consumed` is the member's open-order + executed-trade exposure; `*_limit_cents` is the allocation as the enforced limit, no inheritance from the desk and no clamping to it, so it always equals `cash_limit`; `remaining = limit − consumed` (negative when over, a `*_limit_cents` of `0` means the member holds no allocation and no order may add exposure in that pool). Same shape and semantics as REST `GET /api/v1/members` and the WS `get_members` response.

#### Errors

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
for m in client.get_my_members().members:
    print(m.short_id, m.name, m.eur_consumed_cents, m.eur_remaining_cents)
```

### <a id="rpc-ListUsers" name="rpc-ListUsers"></a>`Unary` `rpc ListUsers`

List every user in the system.

**Required permission:** `manage_users` behind the desk-management license. (see [Permissions](#permissions))

#### Request

This RPC takes no request fields.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `users` | `repeated UserProfile` | none | yes | One entry per user (see UserProfile). |

`ListUsersResponse { repeated UserProfile users }`.

#### Errors

| gRPC status | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `manage_users` or the license does not enable desk management. |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
for u in client.list_users().users:
    print(u.id, u.username, list(u.permissions))
```

### <a id="rpc-CreateUser" name="rpc-CreateUser"></a>`Unary` `rpc CreateUser`

Create a new user with a fresh API key.

**Required permission:** `manage_users` behind the desk-management license. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `username` | `string` | none | Yes | Unique username. |
| `permissions` | `repeated string` | none | No | Permission names from the [Permissions](#permissions) chapter. Empty = no permissions. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `user` | `UserProfile` | none | yes | The created user's profile (see UserProfile). |
| `api_key` | `string` | none | optional | shown only once on creation |

> [!WARNING]
> The plaintext API key is returned **once** and stored only as a SHA-256 hash thereafter. If the caller loses it, rotate via `rotate_api_key`.

`CreateUserResponse { UserProfile user, string api_key }`: the profile (`resp.user.id`, `resp.user.username`, `resp.user.permissions`) is nested; `api_key` is the one-time plaintext value.

Permissions are applied in the same call; no separate `SetPermissions` follow-up needed (REST `POST /users` accepts the same optional `permissions` array). Permission strings are validated *before* any database write: an unknown permission returns `INVALID_ARGUMENT` and leaves no user behind.

#### Errors

| gRPC status | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `manage_users` or the license does not enable desk management. |
| `INVALID_ARGUMENT` | An unknown permission string, or an empty username; no user is created. |
| `ABORTED` | `username already exists`: the username is taken, by a current user or a deleted one. A username is never reissued. |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
resp = client.create_user(
    username="ops_oncall",
    permissions=["create_order", "modify_order", "delete_order", "toggle_trading"],
)
print("save this key now:", resp.api_key)
```

### <a id="rpc-DeleteUser" name="rpc-DeleteUser"></a>`Unary` `rpc DeleteUser`

Delete a user; every session of that user ends with it. Its permissions and member assignments are removed and it leaves [`ListUsers`](#rpc-ListUsers); every user write on its id (`DeleteUser`, `SetPermissions`, `RotateApiKey`, `SetUserMembers`) then answers `NOT_FOUND` `user not found`, and `GetUserMembers` returns an empty list, as for an unknown id. Its orders, trades and audit rows keep its attribution: its short id and username keep naming it, and neither is ever given to another user. You cannot delete yourself or the `admin` account.

**Required permission:** `manage_users` behind the desk-management license. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `user_id` | `string` | none | Yes | User id to delete. |

#### Response

Returns `google.protobuf.Empty` on success.

`google.protobuf.Empty`.

Their API key is invalidated and any active sessions are dropped.

#### Errors

| gRPC status | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `manage_users` or the license does not enable desk management. |
| `PERMISSION_DENIED` | `cannot delete the admin account`. |
| `INVALID_ARGUMENT` | `cannot delete yourself`. |
| `NOT_FOUND` | `user not found`: no user with that id, or the user is already deleted. |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
client.delete_user(user_id="42")
```

### <a id="rpc-SetPermissions" name="rpc-SetPermissions"></a>`Unary` `rpc SetPermissions`

Replace the user's permission set with the given list.

**Required permission:** `manage_users` behind the desk-management license. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `user_id` | `string` | none | Yes | Target user. |
| `permissions` | `repeated string` | none | Yes | New permission set; empty = revoke all. |

#### Response

Returns `google.protobuf.Empty` on success.

`google.protobuf.Empty`.

Replace-all semantics: pass an empty list to revoke everything. The built-in `admin` account's permissions are **immutable** (it always holds every permission); targeting it returns `PERMISSION_DENIED`.

#### Errors

| gRPC status | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `manage_users` or the license does not enable desk management. |
| `INVALID_ARGUMENT` | An unknown permission string. |
| `NOT_FOUND` | No user with that id. |
| `PERMISSION_DENIED` | The target is the built-in admin account, whose permissions are immutable. |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
client.set_permissions(user_id="42", permissions=["read_audit"])
```

### <a id="rpc-RotateApiKey" name="rpc-RotateApiKey"></a>`Unary` `rpc RotateApiKey`

Issue a fresh API key for the user; the previous key and every session of the user are invalidated immediately.

**Required permission:** `manage_users`. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `user_id` | `string` | none | Yes | Target user. On the trader tier this must be the caller's own id. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `api_key` | `string` | none | optional | the new key, shown only once |

`RotateApiKeyResponse { string api_key }`: shown once, then hashed.

`NOT_FOUND`: user id not found, *or* (trader tier) a target that is not the caller.

Not desk-gated, so a `trader`-tier license can rotate its own key. On the trader tier it is **self-only**: `user_id` must be the caller's own id; any other target (including a non-existent one) returns `NOT_FOUND` so it cannot probe for other accounts. A desk-tier `manage_users` holder may rotate any user.

#### Errors

| gRPC status | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `manage_users`. |
| `NOT_FOUND` | No user with that id. |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
resp = client.rotate_api_key(user_id="42")
print("new key:", resp.api_key)
```

### <a id="rpc-GetUserMembers" name="rpc-GetUserMembers"></a>`Unary` `rpc GetUserMembers`

List the virtual members assigned to a specific user.

**Required permission:** `manage_users` behind the desk-management license. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `user_id` | `string` | none | Yes | Target user. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `member_ids` | `repeated string` | none | yes | Member UUIDs (the `Member.id` values), NOT short_ids. Mirrors the REST `member_ids` field. |

`UserMembersResponse { repeated string member_ids }`: member UUIDs.

The returned values are member **UUIDs** (the `Member.id` field), not `VM…`-style short ids; resolve display names via `list_members`.

#### Errors

| gRPC status | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `manage_users` or the license does not enable desk management. |
| `NOT_FOUND` | No user with that id. |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
print(client.get_user_members(user_id="42").member_ids)
```

### <a id="rpc-SetUserMembers" name="rpc-SetUserMembers"></a>`Unary` `rpc SetUserMembers`

Replace the user's set of virtual-member assignments.

**Required permission:** `manage_users` behind the desk-management license. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `user_id` | `string` | none | Yes | Target user. |
| `member_ids` | `repeated string` | none | Yes | Replacement list of member UUIDs. |

#### Response

Returns `google.protobuf.Empty` on success.

`google.protobuf.Empty`.

Replace-all semantics. The list values are member **UUIDs** (`Member.id`), not `VM…`-style short ids; a short id names no member, so passing one is `NOT_FOUND` and assigns nothing.

#### Errors

| gRPC status | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `manage_users` or the license does not enable desk management. |
| `NOT_FOUND` | `user not found`: no user with that id, or the user is deleted (checked first). `member not found`: a listed member id that does not exist, or a deleted member. Nothing is written. |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
desk_a = next(m for m in client.list_members().members if m.short_id == "VM001")
client.set_user_members(user_id="42", member_ids=[desk_a.id])
```

### <a id="rpc-ListMembers" name="rpc-ListMembers"></a>`Unary` `rpc ListMembers`

List every virtual member in the system.

**Required permission:** `manage_members` behind the desk-management license. (see [Permissions](#permissions))

#### Request

This RPC takes no request fields.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `members` | `repeated Member` | none | yes | One entry per virtual member (see Member). |

`MemberListResponse { repeated Member members }`: see [`get_my_members`](#rpc-GetMyMembers) for the full `Member` field set (configured limits + live cash usage per pool).

#### Errors

| gRPC status | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `manage_members` or the license does not enable desk management. |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
for m in client.list_members().members:
    print(m.short_id, m.name, m.eur_consumed_cents, m.eur_limit_cents, m.eur_remaining_cents)
    areas = "all" if m.delivery_areas.all else list(m.delivery_areas.area_ids)
    print("  delivery areas:", areas)
```

### <a id="rpc-CreateMember" name="rpc-CreateMember"></a>`Unary` `rpc CreateMember`

Create a new virtual member.

**Delivery areas.** A member trades only in the delivery areas it is given. A member created without `delivery_areas` has none and every order under it is refused `FAILED_PRECONDITION` `MEMBER_AREA_NOT_ALLOWED`, so give it areas here or later with [PatchMember](#rpc-PatchMember): `DeliveryAreaScope{all: true}` for every area, or `DeliveryAreaScope{area_ids: [EIC, …]}` for a list taken from the gateway’s configured `epex_settings.delivery_areas` (an unconfigured id is `INVALID_ARGUMENT` naming the configured ones). Read the current areas from [ListMembers](#rpc-ListMembers). The rule covers every order action of the member, new, modify, activate, deactivate and cancel, whoever places it; House orders and market data are not restricted.

**Required permission:** `manage_members` behind the desk-management license. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `name` | `string` | none | Yes | Display name. |
| `max_position` | `sint64` | sub-MW | Yes | Per-contract position cap in sub-MW. |
| `max_slot_position` | `optional sint64` | sub-MW | No | The member's own [slot position limit](#ops-slot-limit). Unset = no member slot limit; `0` = flat-only. Negative is `INVALID_ARGUMENT` `max_slot_position must be non-negative`. |
| `cash_limit` | `sint64` | cents (currency × 100) | No | The member's allocation out of the desk's EUR cash limit, in EUR cents. Default `0`, which means **no allocation**: the member cannot add EUR exposure at all. `INVALID_ARGUMENT` when it would push the pool's allocations past the desk's House limit, or when the exchange has reported no EUR limit to allocate out of. |
| `cash_limit_gbp` | `sint64` | cents (currency × 100) | No | The member's allocation in the independent GBP pool, in GBP cents. Same rules; default `0` = no allocation. |
| `delivery_areas` | `DeliveryAreaScope` | none | No | `{ all, area_ids }`. Unset = no areas: the member can place no order until it is given some. Each id must be one of the gateway’s configured `epex_settings.delivery_areas`; duplicates collapse and the list is stored in the configuration’s order. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `id` | `string` | none | yes | The new member's UUID. |
| `short_id` | `string` | none | yes | The server-generated compact handle such as VM001, used in order tags and audit attribution. |
| `name` | `string` | none | yes | The member's display name. |
| `max_position` | `sint64` | sub-MW | yes | The per-contract limit, sub-MW. |
| `max_slot_position` | `optional sint64` | sub-MW | when set | The member's slot position limit; unset = none, `0` = flat-only. |
| `delivery_areas` | `DeliveryAreaScope` | none | yes | The areas the member may trade in, as stored: `all`, or the `area_ids` list. |
| `active` | `bool` | none | yes | Whether the member is active. |
| `cash_limit` | `sint64` | cents (currency × 100) | yes | The member's ALLOCATION out of the desk's cash limit, in the pool's cents. Per currency the allocations of all members sum to at most the desk's House limit, so a member can only ever spend its own slice. 0 = no allocation: the member cannot add exposure in that pool at all. EUR cents; 0 = no allocation |
| `cash_limit_gbp` | `sint64` | cents (currency × 100) | yes | GBP cents; 0 = no allocation |
| `eur_consumed_cents` | `sint64` | cents (currency × 100) | yes | Live cash usage (read-only projection; in each pool's cents). `consumed` is the member's open-order + executed-trade exposure; `limit` is the allocation above; `remaining = limit − consumed` (negative when over). A `*_limit` of 0 means no exposure may be added in that pool. |
| `eur_limit_cents` | `sint64` | cents (currency × 100) | yes | The member's EUR allocation, the limit its EUR exposure is measured against. |
| `eur_remaining_cents` | `sint64` | cents (currency × 100) | yes | EUR headroom left, the allocation minus consumed, negative when over. |
| `gbp_consumed_cents` | `sint64` | cents (currency × 100) | yes | The member's GBP open-order and executed-trade exposure. |
| `gbp_limit_cents` | `sint64` | cents (currency × 100) | yes | The member's GBP allocation. |
| `gbp_remaining_cents` | `sint64` | cents (currency × 100) | yes | GBP headroom left, the allocation minus consumed, negative when over. |

`Member`: the newly-created record (full field set per [`get_my_members`](#rpc-GetMyMembers)). A fresh member has no orders/trades yet, so its `*_consumed_cents` are `0` and `*_remaining_cents` equal its allocation.

> [!WARNING]
> Per currency, the allocations of **all** members sum to at most the desk's `house_cents`, inactive members included, since the exchange does not release an idle member's share either. That is what makes one member unable to spend another's allocation. Orders with no member tag draw on the remainder (`unallocated_cents` on [`get_cash_limit`](#rpc-GetCashLimit)) and nothing more.

The `short_id` is generated server-side (`VM001`, `VM002`, …) and returned in the `Member` response; it cannot be chosen by the caller.

#### Errors

| gRPC status | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `manage_members` or the license does not enable desk management. |
| `INVALID_ARGUMENT` | A missing or invalid member name. |
| `INVALID_ARGUMENT` | A `delivery_areas` id the gateway is not configured to trade (the message names it and the configured list), or `all` together with `area_ids`. Nothing is written. |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
from voltnir_sdk import DeliveryAreaScope

m = client.create_member(
    name="Trading Desk Alpha",
    max_position=10000,
    delivery_areas=DeliveryAreaScope(area_ids=["10YNL----------L", "10YBE----------2"]),
)
print(m.id)
```

### <a id="rpc-PatchMember" name="rpc-PatchMember"></a>`Unary` `rpc PatchMember`

Partial update: only fields that are explicitly set on the wire are applied.

**Required permission:** `manage_members` behind the desk-management license. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `id` | `string` | none | Yes | Target member **UUID** (`Member.id`), not the `VM…` short_id. |
| `name` | `StringValue` | none | No | New display name. |
| `max_position` | `Int64Value` | sub-MW | No | New per-contract position cap (sub-MW). |
| `max_slot_position` | `optional sint64` | sub-MW | No | Sets the member's [slot position limit](#ops-slot-limit) (`0` = flat-only). Negative is `INVALID_ARGUMENT` and changes nothing. |
| `clear_max_slot_position` | `bool` | none | No | Removes the member's slot position limit (no member slot limit). `INVALID_ARGUMENT` together with `max_slot_position`. |
| `cash_limit` | `Int64Value` | cents (currency × 100) | No | New EUR allocation in EUR cents. `0` takes the allocation away, so the member can no longer add EUR exposure; that always succeeds. Raising it is `INVALID_ARGUMENT` when the pool's allocations would then exceed the desk's House limit, the member's own current allocation is not counted against the value replacing it, so a member can always be raised into the unallocated remainder. This is the field the desk lowers when next-window collateral is insufficient. |
| `cash_limit_gbp` | `Int64Value` | cents (currency × 100) | No | New GBP allocation in GBP cents. Same rules, in the independent GBP pool. |
| `active` | `BoolValue` | none | No | Activate / deactivate the member. |
| `delivery_areas` | `DeliveryAreaScope` | none | No | Replaces the member’s delivery areas whole, same rules as on `CreateMember`; unset leaves them. The field is a message, so an empty `DeliveryAreaScope` is present and takes every area away. |

#### Response

Returns `google.protobuf.Empty` on success.

`google.protobuf.Empty`.

Uses `google.protobuf` wrapper types so unset fields skip cleanly.

#### Errors

| gRPC status | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `manage_members` or the license does not enable desk management. |
| `NOT_FOUND` | `member not found`: no member with that id, or the member is deleted. |
| `INVALID_ARGUMENT` | A `delivery_areas` id the gateway does not trade, or `all` with `area_ids`; or `delivery_areas` that would leave any of the member’s resting or pending orders outside it (`member … has N open orders in …; cancel them before removing the area`). Nothing is written. |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
from voltnir_sdk import DeliveryAreaScope

desk = next(m for m in client.list_members().members if m.short_id == "VM042")
client.patch_member(id=desk.id, active=False)
client.patch_member(id=desk.id, max_position=20000)

# Delivery areas: replaced whole; a patch without them leaves them as they are.
client.patch_member(id=desk.id, delivery_areas=DeliveryAreaScope(all=True))
client.patch_member(id=desk.id, delivery_areas=DeliveryAreaScope(area_ids=["10YNL----------L"]))
# Removing an area while the member has open orders in it is INVALID_ARGUMENT:
# "member VM042 has 1 open order in 10YBE----------2; cancel them before removing the area"
```

### <a id="rpc-DeleteMember" name="rpc-DeleteMember"></a>`Unary` `rpc DeleteMember`

Delete a member. Refused while the member has a resting or unconfirmed pending order, a non-zero executed position on a contract whose delivery has not ended, or consumed cash still counted in the current exposure window (trades executed since the last booking cut): cancel the orders, flatten the positions, and wait for the cut. A deleted member takes no order (one naming it is refused `INVALID_ARGUMENT` `v-member '…' not found`), is unassigned from every user, and leaves [`ListMembers`](#rpc-ListMembers) and every user's members; `PatchMember`, a `SetUserMembers` naming it, or a second `DeleteMember` answers `NOT_FOUND` `member not found`, as for an unknown id. Its orders and trades stay in history and keep its name, and its short id is never given to another member. Audited as `member_deleted`.

**Required permission:** `manage_members` behind the desk-management license. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `member_id` | `string` | none | Yes | Member **UUID** (`Member.id`), not the `VM…` short_id. |

#### Response

Returns `google.protobuf.Empty` on success.

`google.protobuf.Empty`.

#### Errors

| gRPC status | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `manage_members` or the license does not enable desk management. |
| `INVALID_ARGUMENT` | `member … has N open orders; cancel them before deleting the member` (one order: `has 1 open order; cancel it`): resting or unconfirmed pending orders, checked first. `member … holds a position on N contracts whose delivery has not ended: … in …; flatten them before deleting the member`: each contract named by its catalogue name or as `contract <id>`, with its delivery area; a position that nets to zero, or one on a delivered contract, does not count. `member … has consumed cash counted until the next booking cut (EUR N cents, GBP N cents); delete it after the cut`: checked last, the consumed cash the member cash check reads, per non-zero pool, in cents. Any non-zero figure, a credit included, holds the delete until the cut; a credit is named `EUR credit N cents`, never with a minus sign, and each figure is rounded up to whole cents. `consumed cash cannot be fully priced yet; retry the delete`: the gateway's carried cash sums are not fully priced at that moment (a desk-wide state, not this member's), so the figure would be short; retry. Nothing changes. |
| `NOT_FOUND` | `member not found`: no member with that id, or the member is already deleted. |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
desk = next(m for m in client.list_members().members if m.short_id == "VM042")
client.delete_member(member_id=desk.id)
```

### <a id="rpc-ListPermissions" name="rpc-ListPermissions"></a>`Unary` `rpc ListPermissions`

The catalog of assignable permissions: every permission `code` that can be granted via `set_permissions`, paired with a human-readable `description`.

**Required permission:** `manage_users`. (see [Permissions](#permissions))

#### Request

This RPC takes no request fields.

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `permissions` | `repeated PermissionInfo` | none | yes | One entry per assignable permission, its code and description (see PermissionInfo). |

None.

`ListPermissionsResponse { repeated PermissionInfo permissions }`, where `PermissionInfo { string code; string description; }`.

Mirrors REST `GET /api/v1/permissions`. Render this rather than hardcoding the list, so a new permission appears automatically. Server-defined and stable within an API version.

#### Errors

| gRPC status | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `manage_users`. |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
resp = client.list_permissions()
for p in resp.permissions:
    print(p.code, "-", p.description)
```

<a id="ops-audit" name="ops-audit"></a>

## Audit & reports

### <a id="rpc-QueryAuditOrders" name="rpc-QueryAuditOrders"></a>`Unary` `rpc QueryAuditOrders`

Page through the audit log of order events.

**Required permission:** Authenticated caller; results are scoped to the members you may see. `read_orders` widens the result. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `cursor` | `string` | none | No | `""` on the first page; pass back the previous response's `next_cursor` for subsequent pages. |
| `limit` | `uint32` | none | No | Page size. `0` (or unset) == default `50`; capped at `200`. (REST rejects an explicit `limit=0` with 400 instead, since proto3 cannot distinguish unset from 0.) |
| `date_from` / `date_to` | `string` | none | No | RFC 3339: inclusive window. `""` = unbounded. |
| `area` | `string` | none | No | EIC area filter. |
| `product` | `string` | none | No | Product filter. |
| `status` | `string` | none | No | The order state M7 reported: `ACTIVE` (`ACTI`), `INACTIVE` (`INAC`, a deleted or fully filled order) or `HIBERNATED` (`HIB`), in any case. `""` (unset) is no filter; any other value is refused with `INVALID_ARGUMENT`, naming the accepted values. `REJECTED` is not an M7 order state: a plain order the exchange refuses has no row in this history, and its refusal is on the audit trail as `order_rejected`. A refused pre-arranged order, or a remote order that failed validation, keeps its rows, with the state M7 reported and the refusal as the row’s `action` (`UREJ`, `AREJ`, `SREJ` or `SERR`). |
| `user_code` | `string` | none | No | EPEX trader/user code filter (e.g. `"TRADER1"`). Renamed from the former, mislabelled `user_id` field. |
| `v_member_short_id` | `string` | none | No | Virtual-member filter, applied inside the caller's own member scope; a member the caller may not see returns `PERMISSION_DENIED`. |
| `voltnir_user_short_id` | `string` | none | No | Submitting Voltnir user short-id filter (e.g. `"U001"`). |
| `voltnir_username` | `string` | none | No | Submitting Voltnir username-snapshot filter (e.g. `"j.doe"`). |
| `sort_order` | `string` | none | No | Page direction. `""` or `"DESC"` (the default) returns the newest rows first, `"ASC"` the oldest. Any other value is `INVALID_ARGUMENT`. Every audit rpc takes it, as do the REST and WebSocket peers. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `items` | `repeated AuditOrderItem` | none | yes | One audit-order row per entry, each serialised as a JSON object. |
| `next_cursor` | `string` | none | optional | "" == last page |

`AuditOrdersResponse { repeated AuditOrderItem items, string next_cursor }`; each `item.json` is the audit row serialised as JSON.

**Who wrote a row: `source`.** The order history records what the gateway observed. Each row's JSON carries `source`: `exchange` for a row parsed from an execution report the exchange sent, `gateway` for a row the gateway wrote because M7 no longer held the order when the gateway reconnected, so the outcome was not observed. Such a row sits above the last `revision` the gateway knew, with `order_state` inactive, `timestamp` the time the gateway noticed, and the `action` and `quantity` last known to the gateway. Read `source` before `action`. Fills are in `QueryAuditTrades` (no order-id filter: `time_basis` execution over the time the order was open, then the trades whose `buy_json` or `sell_json` leg carries the order's id as `@ordrId`). Every login re-reads the fills of the current cash-exposure window from the exchange; an older fill is there only after `RestoreTradeHistory` (permission `restore_trade_history`). Pre-arranged (OTC) orders are not closed this way. The full rule is under REST `GET /audit/orders`.

<a id="order-history-names" name="order-history-names"></a>**Coded columns are names.** Nine columns hold a value the exchange sends as a code. In every row's JSON here and every row of an orders export each one is a name wherever the code has one: where the live order stream carries the field (`side`, `order_type`, `order_state`, `action`) it is the same word the WebSocket `orders` stream sends, which for `side`, `order_type` and `order_state` is also the enum value name `WatchOrders` carries, so an order reads the same in the stream, the history and the export, except for `0`, which the history writes as `"0"` and the stream reads as `UNKNOWN`. A code with no name is written as its number in text. In practice that is `"0"`: `0` is the exchange's unset value, and a value the exchange sends that this gateway does not know is stored as `0` too, so the row cannot say which value it was. A column the exchange left out is `null` (an empty cell in a CSV export). The `status` filter takes the `order_state` names. A trade row holds no codes: its `state` and `contract_phase` are the exchange's own text (`ACTI`, `CONT`), as on the live trade stream.

| Column | Names |
| --- | --- |
| `side` | `BUY`, `SELL` |
| `order_type` | `REGULAR`, `BLOCK`, `BALANCE`, `ICEBERG`, `STOP`, `EXCHANGE_PRE_ARRANGED`, `PRIVATE` |
| `order_state` | `ACTIVE`, `INACTIVE`, `HIBERNATED`, `UNKNOWN` (a state the exchange itself reports as unknown) |
| `action` | The exchange's four-letter action: `UADD`, `UHIB`, `UMOD`, `UDEL`, `UREJ`, `AADD`, `AHIB`, `AMOD`, `ADEL`, `AREJ`, `SADD`, `SHIB`, `SMOD`, `SDEL`, `SREJ`, `FEXE`, `PEXE`, `IADD`, `SERR`, `SNAV` |
| `aggressor_indicator` | `YES`, `NO`, `UNKNOWN` |
| `validity_restriction` | `NON`, `GFS`, `GTD`, the exchange's codes; REST and WebSocket order entry take the same values in lower case |
| `order_execution_restriction` | `NON`, `AON`, `FOK`, `IOC`, the exchange's codes; REST and WebSocket order entry take the same values in lower case |
| `open_close_indicator` | `OPEN`, `CLOSE` |
| `execution_instruction_type` | `NONE`, `VALID`, `LINKED` |

Optional filters narrow the result; the returned `next_cursor` drives pagination.

#### Errors

| gRPC status | Condition |
| --- | --- |
| `INVALID_ARGUMENT` | A malformed date filter or cursor. |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

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

### <a id="rpc-QueryAuditTrades" name="rpc-QueryAuditTrades"></a>`Unary` `rpc QueryAuditTrades`

Page through the audit log of trade events.

**Required permission:** Authenticated caller; results are scoped to the members you may see. `read_orders` widens the result. (see [Permissions](#permissions))

**A trade between two of your own members.** When two virtual members of the desk trade with each other, a member-scoped caller finds the trade under either member and receives it as the row of an ordinary fill of that member's own leg: the other leg (`buy_json` or `sell_json`) `null`; `v_member_short_id`, `voltnir_user_id`, `voltnir_user_short_id`, `voltnir_username` and `delivery_area` those of the kept leg, exactly as on a fill of that leg against an outside counterparty; and `self_trade` `false`. `self_trade` is `false` for a member-scoped caller whenever it cannot see both legs, including on a trade only one half of which has arrived. Under a member scope the `delivery_area` and `voltnir_user_short_id` filters match only on a leg the caller may see, and `voltnir_username` names a current Voltnir user and matches the same way; an unknown name matches nothing. A caller holding `read_orders` (or `bypass_member_check`) receives the whole trade, whose member, Voltnir user and `delivery_area` are those of its buy leg when that leg belongs to a member, else of its sell leg, whichever half arrived last, and its filters match those. A member filter narrows even such a caller to that member's view, so the trade then reads as that member's own fill. The public trade tape is market data and is not narrowed: it carries the exchange's own self-trade flag and both legs' delivery areas under the same trade id. The desk is told of each such trade once, on the audit trail (`member_self_cross`).

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `cursor` | `string` | none | No | `""` for the first page. |
| `limit` | `uint32` | none | No | Page size. `0` (or unset) == default `50`; capped at `200`. (REST rejects an explicit `limit=0` with 400 instead, since proto3 cannot distinguish unset from 0.) |
| `date_from` / `date_to` | `string` | none | No | RFC 3339 window, applied to the axis chosen by `time_basis`. |
| `time_basis` | `string` | none | No | Which timestamp the window filters on: `""`/`delivery` (**default**, contract delivery window, **overlap** semantics: `delivery_end ≥ date_from` and `delivery_start ≤ date_to`) or `execution` (execution time). Any other value → `INVALID_ARGUMENT`. |
| `area` | `string` | none | No | EIC area filter. |
| `product` | `string` | none | No | Product filter. |
| `contract_id` | `string` | none | No | Filter to one contract by its M7 contract id, as the string the trade rows carry. An id no trade carries returns an empty page, not an error. `""` is unset (no filter). |
| `user_code` | `string` | none | No | EPEX trader/user code filter (e.g. `"TRADER1"`). Renamed from the former, mislabelled `user_id` field. |
| `v_member_short_id` | `string` | none | No | Virtual-member filter, applied inside the caller's own member scope; a member the caller may not see returns `PERMISSION_DENIED`. |
| `voltnir_user_short_id` | `string` | none | No | Submitting Voltnir user short-id filter (e.g. `"U001"`). Under a member scope it matches only on a leg the caller may see (see the note above). |
| `voltnir_username` | `string` | none | No | Submitting Voltnir username-snapshot filter (e.g. `"j.doe"`). Under a member scope it names a current user and matches only on a leg the caller may see. |
| `sort_order` | `string` | none | No | Page direction; see [`query_audit_orders`](#rpc-QueryAuditOrders). Default newest-first. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `items` | `repeated AuditTradeItem` | none | yes | One audit-trade row per entry, each serialised as a JSON object: the REST [GET /audit/trades](rest_api_v1.md#get-audit-trades) row, including the recall fields (`null` when not applicable). |
| `next_cursor` | `string` | none | yes | Cursor for the next page, empty on the last page. |

> [!NOTE]
> **Delivery (default) vs. execution.** `delivery` (the default) filters on the contract delivery period using overlap, so block / multi-period products spanning the window are still returned (settlement / exposure / REMIT view); `execution` filters on when the trade matched (transaction view). Trades recorded before delivery capture was added have `null` `delivery_start`/`delivery_end` and never match the default delivery filter; use `time_basis=execution` for those.

`AuditTradesResponse { repeated AuditTradeItem items, string next_cursor }`. Each `AuditTradeItem.json` is the same row shape as REST (now including `delivery_start` / `delivery_end`).

Same shape and semantics as `query_audit_orders` minus the `status` filter. Each item's JSON carries both the execution time (`exec_time` / `executed_at`) and the contract delivery window (`delivery_start` / `delivery_end`); `time_basis` selects which axis `date_from`/`date_to` filter on. Mirrors REST `GET /api/v1/audit/trades`.

#### Errors

| gRPC status | Condition |
| --- | --- |
| `INVALID_ARGUMENT` | A malformed date filter or cursor. |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

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

### <a id="rpc-QueryAuditPublicTrades" name="rpc-QueryAuditPublicTrades"></a>`Unary` `rpc QueryAuditPublicTrades`

Page through the stored market-wide public trade tape.

**Required permission:** `read_audit`. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `cursor` | `string` | none | No | `""` for the first page. |
| `limit` | `uint32` | none | No | Page size. `0` (or unset) == default `50`; capped at `200`. (REST rejects an explicit `limit=0` with 400 instead, since proto3 cannot distinguish unset from 0.) |
| `date_from` / `date_to` | `string` | none | No | RFC 3339 window on execution time. |
| `area` | `string` | none | No | EIC area; matches buy **or** sell delivery area. |
| `product` | `string` | none | No | Product filter. |
| `state` | `string` | none | No | Trade state (`ACTI`, `CNCL`, …). |
| `sort_order` | `string` | none | No | Page direction; see [`query_audit_orders`](#rpc-QueryAuditOrders). Default newest-first. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `items` | `repeated AuditPublicTradeItem` | none | yes | One public-trade row per entry, each serialised as a JSON object. |
| `next_cursor` | `string` | none | yes | Cursor for the next page, empty on the last page. |

`AuditPublicTradesResponse { repeated AuditPublicTradeItem items, string next_cursor }`; each `item.json` is one public trade serialised as JSON.

Populated only when the gateway is configured to persist public trades to PostgreSQL (with persistence off, or in the export-only mode, the table stays empty). Data is scoped to assigned products; pre-arranged trades are excluded; prices (`px`) are Eurocents. Mirrors the REST `GET /audit/public_trades` endpoint 1:1.

#### Errors

| gRPC status | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `read_audit`. |
| `INVALID_ARGUMENT` | A malformed date filter or cursor. |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
page = client.query_audit_public_trades(limit=100, area="10YDE-EON------1", state="ACTI")
print(len(page.items), "public trades; next_cursor:", page.next_cursor)
```

### <a id="rpc-QueryAuditEvents" name="rpc-QueryAuditEvents"></a>`Unary` `rpc QueryAuditEvents`

Page through the **compliance audit-event log**: the append-only who-did-what record of actor-driven mutations (user/permission/member/limit changes, kill-switch and self-trade toggles, every order submit / modify / cancel and the rejections, report exports, system/license lifecycle).

**Member scope.** The trail is member-scoped like [`QueryAuditOrders`](#rpc-QueryAuditOrders), after the `read_audit` gate. A caller who also holds `read_orders` or `bypass_member_check` reads every row. Any other caller reads only the rows of order actions tagged with a virtual member assigned to them: every row with no member (a user, permission, member, limit, licence or system event, a House order, a cancel-all, a `slot_limit_would_refuse` or `member_self_cross` row) is withheld, and a caller assigned to no member reads no row. A row names the member of the order it is about in `v_member_short_id` for the order actions only (`order_submitted`, `order_modified`, `order_cancelled`, `order_rejected`, `order_command_rejected`), and `null` otherwise.

**Required permission:** `read_audit`. `read_orders` or `bypass_member_check` widens the result to the whole trail; without either it is member-scoped. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `cursor` | `string` | none | No | `""` on the first page; pass back the previous response's `next_cursor`. |
| `limit` | `uint32` | none | No | Page size. `0` (or unset) == default `50`; capped at `200`. (REST rejects an explicit `limit=0` with 400 instead, since proto3 cannot distinguish unset from 0.) |
| `date_from` / `date_to` | `string` | none | No | RFC 3339: inclusive window. `""` = unbounded. |
| `action` | `string` | none | No | Action token filter, e.g. `permissions_set`, `order_submitted`, `order_modified`, `order_cancelled`, `order_rejected`, `trading_toggled`, `trade_ingest_fault_acknowledged`, `trade_ingest_fault_ack_expired`, `auth_failed`, `permission_denied`, `rate_limited`. |
| `target_type` | `string` | none | No | Target-kind filter: `user`, `member`, `profile`, `order`, `trading`, `report`, `license`, `system`. |
| `actor_short_id` | `string` | none | No | Acting user's short-id filter (e.g. `"U001"`). |
| `outcome` | `string` | none | No | Outcome filter: `ok`, `denied` (refused at the access boundary) or `error`. |
| `v_member_short_id` | `string` | none | No | Virtual-member filter, applied inside the caller's own member scope; a member the caller may not see returns `PERMISSION_DENIED`. |
| `sort_order` | `string` | none | No | Page direction; see [`query_audit_orders`](#rpc-QueryAuditOrders). Default newest-first. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `items` | `repeated AuditEventItem` | none | yes | One audit-event row per entry, each serialised as a JSON object. |
| `next_cursor` | `string` | none | yes | Cursor for the next page, empty on the last page. |

`AuditEventsResponse { repeated AuditEventItem items, string next_cursor }`; each `item.json` is the audit event serialised as JSON.

Each `item.json` carries the actor, transport, source IP, `before`/`after` snapshots, outcome, reason and `v_member_short_id`. Mirrors REST `GET /api/v1/audit/events`.

**Lifecycle rows and lost writes.** Each clean shutdown ends the trail with a `system_shutdown` row, written once every queued write has been committed or counted lost. Its `after` is `{"writes_lost": {"audit": n, "m7_errors": n, "exchange_messages": n, "public_trades": n, "orders": n, "trades": n}}`: what that run lost, per stream. When a run ends without that row (a crash, a kill, a power loss), the next start writes a `system_unclean_exit` row (target `system`, outcome `ok`) just before its own `system_startup`. Its `after` names the previous run's start (`previous_startup_ts`, `previous_startup_ts_ms`) and `last_audit_id`, the `id` of the last row that run stored; writes that run still held in memory may be missing, and how many is not known. Row ids are assigned when a row is stored, so a gap in them is not how a loss shows: these two rows and `writes_dropped` are. The `system_startup` row's `after` records the trade-ingest fault policy the run started under: `{"trade_ingest_fault": "close" | "continue", "trade_ingest_fault_ack_ttl_sec": n}`.

#### Errors

| gRPC status | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `read_audit`. |
| `PERMISSION_DENIED` | `v_member_short_id` names a member the caller may not see (message `not assigned to member`). |
| `INVALID_ARGUMENT` | A malformed date filter or cursor. |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
page = client.query_audit_events(limit=100, action="permissions_set", outcome="ok")
for item in page.items:
    print(item.json)
```

**Order actions.** Every accepted order action appends exactly one row: `order_submitted` when a placement is accepted and the exchange does not refuse it, `order_modified` when a `ModifyOrder` (modify / activate / deactivate) is acknowledged, `order_cancelled` when a `CancelOrder` is acknowledged, and `order_rejected` when the placement is refused, by the pre-trade gate before it is published, or by the exchange after it acknowledged receipt (`reason` is `position_limit_exceeded`, `slot_position_limit_exceeded`, `slot_window_unknown`, `cash_limit_exceeded`, `self_cross_blocked`, `trading_disabled`, `load_management_throttled`, `member_area_not_allowed` or `exchange_rejected`). A `member_area_not_allowed` row, written for a refused submit, modify or cancel, carries an `after` of `member` and `area`. Exactly one row per submit, whichever way it ended: an `exchange_rejected` row carries the `after` snapshot the placement was published with, plus `state: "REJECTED"` and the exchange's own words in `exchange_reason`. A slot-limit refusal (`slot_position_limit_exceeded` or `slot_window_unknown`), of a placement or of a modify or activation, carries an `after` with the refusal's own fields, because its reason alone does not say which bound was hit: `delivery_area`; then, for `slot_position_limit_exceeded`, `slot_start_ms` and `slot_end_ms` (UTC epoch milliseconds), `side` (`long` or `short`), `scope` (`house` or the member's short id), `bound_after` (sub-MW, positive long, negative short) and `limit` (sub-MW); and, for `slot_window_unknown`, one of `order_contract_id`, `open_order_contract_id` or `trade_id`, naming what has no delivery window. A caller holding none of `read_orders`, `bypass_member_check` and `read_status` is shown such a row as the refusal itself is shown to it: a `house`-scope breach without `bound_after` and `limit`, and a trade with no window without its `trade_id`. The stored row keeps them, so a `read_status` holder and a firm-wide reader read them. Every other gate refusal carries no `after` snapshot, because nothing reached the exchange. `target_id` is the `client_order_id`; `target_type` is `order`. The `before`/`after` snapshots carry `v_member_short_id`, `delivery_area`, `contract_id`, `side`, `price_cents` and `quantity_sub_mw`, the wire units the request used, plus `state` on a submit and `modify_action` on a modify. `CancelAllOrders` stays a single `order_cancel_all` row and does not fan out into a row per order, written for every outcome, because no cancel it sends writes a row of its own: `after: {"deleted": n}` on success; on a failure, outcome `error` with the failure as `reason`, plus `after: {"deleted": <acknowledged>, "targeted": <targeted>}` when a member-scoped cancel fails part-way. A failed account-wide cancel is one command with no partial outcome, so its row carries no `after`. A report export, made over REST, writes one `report_exported` row once the request is decided: outcome `ok` when it is accepted, outcome `error` when it is refused, with the refusal text, or `export_busy` when another export was generating, as `reason`.

**Slot limit in `observe`.** An order the slot position limit would refuse is admitted, and recorded as a `slot_limit_would_refuse` row (system actor, target type `order`, no target id, outcome `ok`). Identical would-refusals (same reason, delivery area, slot, scope and side) within 10 seconds are one row. Its `after` carries the refusal's fields as an `order_rejected` row of the same refusal would, plus `reason` (`slot_position_limit_exceeded` or `slot_window_unknown`), `contract_id`, `order_side` (`BUY` or `SELL`), `quantity` (sub-MW, the size the order asked for), `member` (the member's short id, or `null` for a House order), `count` (how many would-refusals the row stands for) and `window_s` (`10`). The row is written when its 10-second window closes, or at a clean shutdown if that comes first.

**Trade recalls.** A recall appends rows with target type `trade` and the exchange trade id as target. `trade_recall_requested` (by the caller) when a sent recall was not refused at its receipt, its `after` carrying `revision_no`, `state`, `receipt` (`acknowledged` or `unknown`), `correlation_id` and `parent_trade_id`. `trade_recall_refused` (outcome `error`, by the caller) once per refusal: `recall_not_possible` or `trade_changed` for the gateway's own refusals, `exchange_refused` with `m7_err_code`, `m7_error_key` and `exchange_reason` for the exchange's, before or after its receipt, and `not_processed` for a request handed back undelivered. `trade_recall_resolved` (system actor) once per trade, the first time the gateway sees it `RGRA` or `RREJ`, carrying the state, revision and the recall times and `recall_requestor` as the exchange reported them, and `first_seen_resolved`. It is written for a recall asked outside the gateway too, with no `trade_recall_requested` row before it, and for a trade first seen already decided at login, with `first_seen_resolved: true`.

**Trades between two of the desk's members.** When two virtual members of the desk trade with each other, the gateway appends one `member_self_cross` row (system actor, target type `trade`, target id the trade id) whose `after` snapshot carries `trade_id`, `contract_id`, `qty` (sub-MW), `px` (cents), `buy_member_short_id` and `sell_member_short_id`. A member-scoped reader of the trade sees only its own leg, so this row is where the desk sees the cross whole: it names no one member, so it is readable with `read_audit` by a caller who also holds `read_orders` or `bypass_member_check`, and the matching warning-level log line reaches holders of `read_logs` when the log level includes warnings; neither reaches the trade streams, contract detail or trade history of a member-scoped caller. A trade already on the trail is not recorded again, also after a restart; a failed lookup of the trail records it rather than lose it.

### <a id="rpc-QueryM7Errors" name="rpc-QueryM7Errors"></a>`Unary` `rpc QueryM7Errors`

Page through the **M7 exchange-error log**: the append-only record of M7-side faults off the AMQP line.

**Required permission:** `read_m7_errors`. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `cursor` | `string` | none | No | `""` on the first page; pass back the previous response's `next_cursor`. |
| `limit` | `uint32` | none | No | Page size. `0` (or unset) == default `50`; capped at `200`. (REST rejects an explicit `limit=0` with 400 instead, since proto3 cannot distinguish unset from 0.) |
| `date_from` / `date_to` | `string` | none | No | RFC 3339: inclusive window on receive time. `""` = unbounded. |
| `kind` | `string` | none | No | Fault-class filter: `err_resp`, `unknown_type`, `ack_uncorrelated`, `seq_gap`. |
| `category` | `string` | none | No | Error category filter: `order_entry`, `general`, `trade`, `user_right`, `limits`, `wrong_reference`, `unknown`. |
| `err_code` | `int64` | none | No | Raw numeric M7 code filter, e.g. `1149`. `0` (or unset) == no filter. |
| `sort_order` | `string` | none | No | Page direction; see [`query_audit_orders`](#rpc-QueryAuditOrders). Default newest-first. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `items` | `repeated M7ErrorItem` | none | yes | One exchange-error row per entry, each serialised as a JSON object. |
| `next_cursor` | `string` | none | yes | Cursor for the next page, empty on the last page. |

`M7ErrorsResponse { repeated M7ErrorItem items, string next_cursor }`; each `item.json` is the m7_errors row serialised as JSON.

Gated by the **dedicated `read_m7_errors`** permission (not `read_audit`). `err_resp` rows are enriched from the official EPEX SPOT M7 API documentation with a human `err_identifier` + `category`; other kinds (`unknown_type`, `ack_uncorrelated`, `seq_gap`) carry no code/category. Mirrors REST `GET /api/v1/audit/m7_errors`.

#### Errors

| gRPC status | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `read_m7_errors`. |
| `INVALID_ARGUMENT` | A malformed date filter or cursor. |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
page = client.query_m7_errors(limit=100, kind="err_resp", category="limits")
for item in page.items:
    print(item.json)
```

### <a id="rpc-ListExchangeMessages" name="rpc-ListExchangeMessages"></a>`Unary` `rpc ListExchangeMessages`

Page through the **exchange-message log**: the append-only record of what the exchange itself said, cash-limit breaches, market and delivery-area halts, member suspensions, failover notices, automated order transfers.

**Required permission:** `read_m7_errors`. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `cursor` | `string` | none | No | `""` on the first page; pass back the previous response's `next_cursor`. |
| `limit` | `uint32` | none | No | Page size. `0` (or unset) == default `50`; capped at `200`. (REST and WS reject an explicit `limit=0` instead, since proto3 cannot distinguish unset from 0.) |
| `date_from` / `date_to` | `string` | none | No | RFC 3339: inclusive window on receive time. `""` = unbounded. |
| `severity` | `string` | none | No | `urgent`, `error`, `high`, `medium`, `low`, or `unknown` for a severity the exchange has not documented. `""` = no filter. |
| `scope` | `string` | none | No | `public` (market-wide) or `private` (this member). `""` = no filter. |
| `code` | `int64` | none | No | Vendor message code filter, e.g. `158`. `0` (or unset) == no filter. |
| `sort_order` | `string` | none | No | Page direction; see [`query_audit_orders`](#rpc-QueryAuditOrders). Default newest-first. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `items` | `repeated ExchangeMessageItem` | none | yes | One exchange-message row per entry, each serialised as a JSON object. |
| `next_cursor` | `string` | none | yes | Cursor for the next page, empty on the last page. |

The messages that are never stored, the ones the exchange marks non-persistent, and the per-contract lifecycle broadcasts (codes `74`, `76` and `77`), are streamed on `watch_exchange_messages` only, so they never appear in this result.

`ListExchangeMessagesResponse { repeated ExchangeMessageItem items, string next_cursor }`; each `item.json` is the exchange_messages row serialised as JSON, carrying `id` (`null` when the message was streamed but not stored), `msg_id`, `scope`, `code`, `key`, `severity`, `text` (placeholders substituted from `vars`, with every instant inside a variable restated in UTC, RFC 3339 with `Z`; `vars` keeps the exchange's own spelling), `product`, `account_id`, `buy_area`, `sell_area`, `market_supervision` and `vars`.

The companion to `query_m7_errors`: one is what the exchange *says*, the other what goes *wrong*. Gated by the **same `read_m7_errors`** permission; **no new permission**. Mirrors REST `GET /api/v1/audit/exchange_messages` and WS `list_exchange_messages`.

#### Errors

| gRPC status | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `read_m7_errors`. |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
page = client.list_exchange_messages(limit=100, severity="error", code=158)
for item in page.items:
    print(item.json)
```

### <a id="rpc-ListSystemLog" name="rpc-ListSystemLog"></a>`Unary` `rpc ListSystemLog`

Page through the **gateway's own diagnostic log**: the running process's internal log output, captured in memory.

**Required permission:** `read_logs`. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `cursor` | `optional uint64` | none | No | Return entries whose `seq` is greater than this. Omit for the newest page; set it, `0` included, to resume from that `seq`. It carries proto3 field presence, so a present `0` resumes from seq `0` rather than reading as "unset" (matching REST omitting the query param and WS sending `null`). |
| `limit` | `uint32` | none | No | Page size. `0` (or unset) == default `50`; capped at `200`. (REST and WS reject an explicit `limit=0` instead, since proto3 cannot distinguish unset from 0.) |
| `min_level` | `string` | none | No | `error`, `warn`, `info` or `debug`; `""` = no filter. Read-side only, the gateway captures at its configured level and streams everything captured, so widening this can never leave a hole in your history. An unrecognised value is rejected with `INVALID_ARGUMENT` rather than ignored. |
| `date_from` / `date_to` | `string` | none | No | RFC 3339: inclusive window on capture time. `""` = unbounded. |

#### Response

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `items` | `repeated SystemLogItem` | none | yes | ascending by seq |
| `truncated` | `bool` | none | yes | The caller's cursor had already been evicted; this page resumes from the oldest surviving entry instead of from where the caller left off. |
| `buffer` | `SystemLogBuffer` | none | yes | The current state of the in-memory log ring, whether capture is on, its capacity and how much it holds (see SystemLogBuffer). |

> [!WARNING]
> **Not an audit record.** The buffer is a bounded in-memory ring, capped by entry count first and age second. It lives only in the running process, is **lost on every restart**, and drops its oldest entries under load. Read the `buffer` block on the response before presenting the result; anything that must survive an incident belongs in the audit log.

Entries come back **oldest-first**, and the cursor is the entry's own `seq` rather than an opaque token. The ring always holds a contiguous run of `seq` values, which is what lets the server say `truncated = true` when your resume point has been evicted instead of silently skipping the gap.

`ListSystemLogResponse { repeated SystemLogItem items, optional uint64 next_cursor, bool truncated, SystemLogBuffer buffer }`. Each `item.json` is one entry as JSON: `seq` (the cursor), `ts_ms` (capture time, Unix milliseconds), `level`, `target` (the emitting module) and `message` (truncated at 4 KiB with a visible marker). `next_cursor` carries proto3 presence: it is absent when the page is empty, so a present `0` is the real seq `0` rather than an empty-page sentinel. `truncated` is `true` when the `cursor` you passed had already been evicted, so this page resumes from the oldest surviving entry.

`SystemLogBuffer { bool enabled, string level, uint64 capacity, uint64 len, uint64 oldest_seq, int64 oldest_ts_ms, uint64 newest_seq, int64 started_at_ms, uint64 dropped, bool has_entries }`. `started_at_ms` is as far back as the buffer reaches; `dropped` counts entries already evicted by capacity or age. Check `has_entries` before trusting the `seq` and timestamp fields: proto3 cannot distinguish an unset `uint64` from `0`, and `seq` `0` is a real entry.

Not the exchange's messages (`list_exchange_messages`), not the exchange's faults (`query_m7_errors`) and not the compliance trail (`query_audit_events`). It carries file paths, database errors and module names, which is why it has its own **`read_logs`** permission rather than sharing `read_m7_errors`. Mirrors REST `GET /api/v1/system/logs` and WS `list_system_log`.

#### Errors

| gRPC status | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `read_logs`. |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
page = client.list_system_log(limit=200, min_level="warn")
if page.buffer.dropped:
    print(f"note: {page.buffer.dropped} earlier entries already evicted")
for item in page.items:
    print(item.json)
```

<a id="streaming" name="streaming"></a>

## Streaming

Every streaming RPC is **server-streaming**: the client sends one request and reads many responses until the server closes the stream or the client cancels. Cancelling a watch is cheap and immediate.

### Watch streams (`WatchContracts` / `WatchOrder` / `WatchOrders`)

- **Snapshot first.** The first event after subscribe is always `SNAPSHOT`, carrying the current full state (every matching `Contract`, one `OwnOrder`, or the full filtered list).
- **Lag recovery.** If the server falls behind, the stream recovers with a `SNAPSHOT` and continues; it doesn't tear down. Treat any post-initial `SNAPSHOT` as a "start over" signal. Recovery is coalesced: a burst of lag yields one recovery `SNAPSHOT`, not one per lost event. On `WatchOrder`, an order that reached a terminal state while the reader was behind arrives as that terminal event instead, and the stream closes (see [WatchOrder](#rpc-WatchOrder)).
- **Terminal events close the stream.** `WatchOrder` closes cleanly on `FILLED` / `CANCELLED` / `REJECTED`, so clients don't have to track lifecycle state. `FILLED` carries the final order body (real price/side/ids, `quantity == 0`, state `INACTIVE`) from the exchange's full-execution record. `CANCELLED` is every other exit from the book: M7's `INACTIVE` state does not distinguish cancellation from expiry.
- **A refused command is a `REJECTED` event.** On `WatchOrders`, a modify or cancel the exchange refuses after acknowledging receipt, and a refused `ack_only` submission, arrives as a `REJECTED` `OrdersEvent`: `orders` carries the unchanged order (do not mutate your state from it), `reason` the exchange's own words, `rejected_action` the refused action (`submit` / `modify` / `activate` / `deactivate` / `cancel`) and `err_code` its numeric code (`0` when the exchange sent none). It is emitted whether or not a caller was waiting on the outcome, so an `ack_only` caller learns of the refusal here. Unlike `WatchOrder` above, it does not close the stream.
- **Pending orders are watchable.** `WatchOrder` on a locally-submitted order that hasn't been acknowledged by M7 yet opens with a `SNAPSHOT` whose body has `state == PENDING` and `order_id == 0` (side/price/quantity/contract are the real submitted values). The M7 ack arrives as the next event with the real `order_id`, so `submit_order → watch_order` is race-free.
- **WatchContracts stays open.** A contract that leaves the market (its delivery ended, or it was deactivated) arrives as a `DELETE` naming it, or, after a lag, is absent from the fresh `SNAPSHOT`; the stream carries on with the others. It ends only when the client cancels or the server shuts down.
- **Filter semantics.** `WatchOrders` accepts `delivery_area` alone; `contract_id` requires `delivery_area`, and `contract_id` alone returns `INVALID_ARGUMENT` (same rule as `list_orders`).

**Cancel a stream** by exiting the iterator (`break`) or, in Python, calling `stream.cancel()` on the call object. Both unwind cleanly on the server side. Every watch method also accepts an optional `timeout` (overall gRPC deadline in seconds; the iterator raises `DeadlineExceeded` when it fires) for bounded consumption.

### <a id="rpc-WatchContracts" name="rpc-WatchContracts"></a>`Server-streaming` `rpc WatchContracts`

The live contract stream: the order books of the contracts you name, by area and product or by contract id. It is the one contract stream on gRPC: follow one contract, a few, or a whole product with it. It is the same stream, with the same filter, as the WebSocket `contracts` stream.

**Required permission:** Authenticated caller; no permission required. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `areas` | `repeated string` | none | Yes | EIC codes of the delivery areas. Empty matches nothing. |
| `products` | `repeated string` | none | No | Product codes, as `Contract.prod`. Without `contract_ids` it is the filter; with them it narrows them. |
| `contract_ids` | `repeated uint64` | none | No | M7 contract ids. `ContractSummary` carries an id as text; send it as a number here. |

**Which contracts.** A contract is included when its area is in `areas`, and then:

- with no `contract_ids`, when its product is in `products`;
- with `contract_ids`, when its id is one of them and, if `products` is not empty, its product is in `products` as well.

An empty `areas` matches nothing, and so does an empty `products` without `contract_ids`. Empty filters are not an error: the stream opens with an empty `SNAPSHOT` and stays open. An id that names no contract is not an error either: it is absent from the `SNAPSHOT`. Only contracts that are live and have a known delivery period are sent.

| To follow | Request |
| --- | --- |
| One contract | `areas=["10YBE----------2"], contract_ids=[2958876]` |
| A few contracts | `areas=["10YBE----------2"], contract_ids=[2958876, 2958877, 2958880]` |
| A whole product | `areas=["10YBE----------2"], products=["XBID_Quarter_Hour_Power"]` |

#### Stream messages

Server-streaming: one `ContractsEvent` message per event until the client cancels or the server shuts down.

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `type` | `EventType` | none | yes | `SNAPSHOT`, `UPSERT` or `DELETE`. |
| `contracts` | `repeated Contract` | none | yes | `SNAPSHOT`: every matching contract. `UPSERT`: exactly one. `DELETE`: empty. Each is the complete current book and metadata (see [`GetContract`](#rpc-GetContract)). |
| `area_id` | `string` | none | `DELETE` only | The area of the contract that left. |
| `contract_id` | `string` | none | `DELETE` only | The id of the contract that left. |

Treat any `SNAPSHOT` after the first as a **start-over** signal: replace your whole view with it. A contract missing from it has left the market.

The first event after subscribe is always a `SNAPSHOT`. After it, the gateway collects the changes to the matching contracts and sends them every 100 ms: one `UPSERT` per changed contract, carrying that contract as the gateway holds it at that moment. Several changes to one contract inside 100 ms arrive as one `UPSERT` with the latest book. A client that keeps up sees every change in that form, and never an older book than one it already has; each `UPSERT` of a contract carries a newer state than the last one sent for it. A write that changes nothing (a contract report at a revision already held, a reference price already held) sends nothing. A new or changed exchange reference price (`ref_px_*`) arrives as an `UPSERT`.

A contract that leaves the market (its delivery ended, or it was deactivated) arrives as a `DELETE` naming it, and only if the stream sent you that contract before; if it leaves while your client is behind, it is simply absent from the fresh `SNAPSHOT`. The stream stays open. A client that falls behind receives one fresh `SNAPSHOT` of every matching contract, however many changes it missed. Trades are not on this stream: they come from [`WatchTrades`](#rpc-WatchTrades) and [`WatchPublicTrades`](#rpc-WatchPublicTrades).

**Message size.** A `SNAPSHOT` of many contracts with deep books can pass the 4 MB receive limit a raw gRPC client has by default, and the call then fails with `RESOURCE_EXHAUSTED`. Raise the client's receive limit, or narrow the filter. The Python SDK's channel already accepts 64 MB.

#### Errors

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
from voltnir_sdk import ContractsEventType

book = {}
for event in client.watch_contracts(areas=["10YBE----------2"], contract_ids=[2958876]):
    if event.type == ContractsEventType.SNAPSHOT:
        book = {(c.area_id, c.contract_id): c for c in event.contracts}
    elif event.type == ContractsEventType.UPSERT:
        c = event.contracts[0]
        book[(c.area_id, c.contract_id)] = c
    else:
        book.pop((event.area_id, event.contract_id), None)
    for c in book.values():
        print(c.contract_id, c.last_price, c.best_bid, c.best_ask)
```

### <a id="rpc-WatchOrder" name="rpc-WatchOrder"></a>`Server-streaming` `rpc WatchOrder`

Live push stream for one specific order.

**Required permission:** Authenticated caller; results are scoped to the members you may see. `read_orders`, `bypass_member_check` widens the result. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `client_order_id` | `string` | none | Yes | UUID of the order to watch. |

#### Stream messages

Server-streaming: one `OrderEvent` message per event until the server closes the stream or the client cancels.

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `type` | `EventType` | none | yes | SNAPSHOT, UPDATE, then a terminal FILLED, CANCELLED or REJECTED that closes the stream. For an order already finished when the watch opens, the SNAPSHOT alone, then the stream closes. |
| `order` | `OwnOrder` | none | yes | The order's current state on every event (see [OwnOrder on the REST page](rest_api_v1.md#get-order)). |

**Scoping.** Member-isolated like `get_order`: an order the caller may not see returns `NotFound` at the snapshot (identical to an unknown `client_order_id`), never the body or a stream. A caller holding `read_orders`/`bypass_member_check` can watch any order.

Pending orders (locally submitted, not yet acked by M7) are watchable: the stream opens with a `SNAPSHOT` whose body has `state == PENDING` and `order_id == 0` (side/price/quantity/contract are the real submitted values). The M7 ack arrives as the next event with the real `order_id`, so `submit_order → watch_order` is race-free.

`Iterator[OrderEvent]`: `type` ∈ {`SNAPSHOT`, `UPDATE`, `FILLED`, `CANCELLED`, `REJECTED`}. `FILLED` carries the final order body (`quantity == 0`, state `INACTIVE`, real price/side/ids). `FILLED` is raised by the exchange's full-execution record. `CANCELLED` covers every other exit from the book; M7's `INACTIVE` does not distinguish cancellation from expiry.

Closes automatically on terminal events (`FILLED` / `CANCELLED` / `REJECTED`). A watch opened on an order that has already finished (state `REJECTED`, or `INACTIVE` for any reason) still opens with its `SNAPSHOT`, and the stream closes right after it: no further event will come for that order.

**Falling behind.** A reader that falls behind the stream, and every reader after the gateway refreshes its order store (it resubscribed to the exchange's order feed, wrote off an unacknowledged order, or cleared a settled contract), gets the order read again. A live order arrives as a fresh `SNAPSHOT` and the stream continues. An order that reached a terminal state in the meantime arrives as that terminal event, so it is not lost: `FILLED` for the full-execution record, `CANCELLED` for any other exit from the book, `REJECTED` for a refused order; the stream then closes. An order still pending arrives as the `PENDING` `SNAPSHOT` and stays watched until its acknowledgement or refusal. On a re-read, only an order the gateway no longer holds, or one no longer in the caller's member scope, closes the stream with no further event; reconcile that case with [GetOrder](#rpc-GetOrder).

#### Errors

| gRPC status | Condition |
| --- | --- |
| `NOT_FOUND` | No order with that client_order_id in the caller scope. |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
for event in client.watch_order(client_order_id="550e8400-e29b-41d4-a716-446655440000"):
    print(event.type, event.order.state, event.order.quantity)
```

### <a id="rpc-WatchOrders" name="rpc-WatchOrders"></a>`Server-streaming` `rpc WatchOrders`

Live push stream over the caller's order list, optionally scoped.

**Required permission:** Authenticated caller; results are scoped to the members you may see. `read_orders`, `bypass_member_check` widens the result. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `delivery_area` | `string` | none | Cond | `""` = no filter. Required if `contract_id` is set. |
| `contract_id` | `string` | none | Cond | `""` = no filter. Requires `delivery_area`. |
| `v_member_short_id` | `string` | none | No | Empty = caller's default scope. Non-empty narrows the stream to one member; `PermissionDenied` unless the caller is assigned to it or holds `read_orders`/`bypass_member_check`. |

#### Stream messages

Server-streaming: one `OrdersEvent` message per event until the server closes the stream or the client cancels.

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `type` | `EventType` | none | yes | SNAPSHOT (the full list), then per-order ADDED, MODIFIED, CANCELLED, FILLED or REJECTED. |
| `orders` | `repeated OwnOrder` | none | yes | The full order list on SNAPSHOT, otherwise the single affected order (see [OwnOrder on the REST page](rest_api_v1.md#get-order)). |
| `reason` | `string` | none | yes | Populated on a REJECTED event; empty on every other event type. |
| `rejected_action` | `string` | none | yes | The refused action on a REJECTED event: submit, modify, activate, deactivate or cancel. Empty on every other event type. |
| `err_code` | `int64` | none | yes | M7's numeric error code on a REJECTED event; 0 when the exchange sent none and on every other event type. |

> [!NOTE]
> **Filter semantics:** `delivery_area` alone is a valid filter; `contract_id` requires `delivery_area`, and `contract_id` alone returns `INVALID_ARGUMENT`. Same rule as `list_orders` and REST `GET /orders`.

**Scoping.** The snapshot and every event are narrowed to what the caller may see, exactly like `list_orders`: a caller holding `read_orders` (or `bypass_member_check`) sees the firm-wide order book; everyone else sees only their assigned members' orders, with untagged house orders withheld.

`Iterator[OrdersEvent]`: `type` ∈ {`SNAPSHOT`, `ADDED`, `MODIFIED`, `CANCELLED`, `FILLED`}. `ADDED` fires on an order's first confirmed appearance (a modify-as-delete+re-create successor stays `MODIFIED`); `orders` carries exactly one order on every non-SNAPSHOT event. `FILLED` carries the final order body (`quantity == 0`, state `INACTIVE`, real price/side/ids). `FILLED` is raised by the exchange's full-execution record. `CANCELLED` covers every other exit from the book (cancel, expiry; M7 does not distinguish them). An order's `quantity` on every event is the remaining quantity the exchange last reported for it.

First event is `SNAPSHOT` with the full filtered list; subsequent events carry one order at a time.

#### Errors

| gRPC status | Condition |
| --- | --- |
| `INVALID_ARGUMENT` | contract_id without delivery_area. |
| `PERMISSION_DENIED` | v_member_short_id names a member the caller may not read. |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
for event in client.watch_orders(delivery_area="10YBE----------2", contract_id="2958876"):
    if event.type == 0:   # SNAPSHOT
        print("snapshot:", len(event.orders), "orders")
    else:
        print(event.type, event.orders[0].client_order_id)
```

### <a id="rpc-WatchTrades" name="rpc-WatchTrades"></a>`Server-streaming` `rpc WatchTrades`

Live push stream of the caller's filled trades, the gRPC mirror of the WS `trades` subscription.

**Required permission:** Authenticated caller; results are scoped to the members you may see. `read_orders`, `bypass_member_check` widens the result. (see [Permissions](#permissions))

#### Request

This RPC takes no request fields.

#### Stream messages

Server-streaming: one `TradeEvent` message per event until the server closes the stream or the client cancels.

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `type` | `EventType` | none | yes | SNAPSHOT for the full list, or UPSERTED for one new or revised trade. |
| `trades` | `repeated OwnTrade` | none | yes | The full trade list on SNAPSHOT, otherwise the single new or revised trade (see [OwnTrade on the REST page](rest_api_v1.md#get-contract); its state and recall fields: [Trade states](#trade-states), [OwnTrade recall fields](#recall-fields)). |

`Iterator[TradeEvent]`: `type` ∈ {`SNAPSHOT`, `UPSERTED`}; `trades` carries the full list on `SNAPSHOT`, exactly one on `UPSERTED`. Each `OwnTrade` carries an `attribution` (`string`): `"full"` when the exchange's trade report parsed completely, or `"partial"` when only the trade's financial core (quantity, price, execution time, contract) could be read and per-leg attribution may be incomplete, a `partial` trade is financially final: report it, no action.

First event is `SNAPSHOT` (full current list); each execution arrives as `UPSERTED` carrying one trade. A lagged broadcast re-emits a fresh `SNAPSHOT`. **Scoping.** Member-isolated like [`watch_orders`](#rpc-WatchOrders): a caller holding `read_orders` (or `bypass_member_check`) receives every member's trades plus the untagged house-account trades; every other caller receives only the trades tagged with a virtual member assigned to them, on the snapshot, every `UPSERTED` event and every recovery snapshot. A caller with no assigned members receives an empty snapshot and no events. A trade between two virtual members of the desk reaches a member-scoped caller as the ordinary fill of its own leg: only the leg its members placed, carrying that leg's own member, member name, Voltnir user and user name exactly as a fill against an outside counterparty would, with the other leg, its member and its Voltnir user withheld; a caller holding `read_orders` (or `bypass_member_check`) sees both legs. The exchange reports such a trade in two halves; when the other member's half lands, a member-scoped caller whose view of the trade it leaves unchanged gets no `UPSERTED` event. A later change to its own view (a new state or revision) is sent. A caller holding `read_orders` receives the trade on each half.

**What the snapshot holds.** It holds the trades of the current cash-exposure window (since the most recent 16:00 booking cut on an ECC business day) and every trade on a contract whose delivery day, in its market's local time, is today or later. A trade recorded without its delivery window is kept for up to seven days after it executed. Earlier trades come from the trade history: [`QueryAuditTrades`](#rpc-QueryAuditTrades). A trade that leaves this set is not announced on the stream; it is absent from the next snapshot.

#### <a id="recall-fields" name="recall-fields"></a>OwnTrade recall fields

Every `OwnTrade`, on this stream and in `ContractDetail.trades`, carries these fields as the exchange sent them. Each is `""` until it applies. A later revision of the trade that omits one keeps the value already reported. Times are in the format the exchange sends, as `exec_time` is.

| Field | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `recall_req_time` (16) | `string` | date-time | optional | When a recall of the trade was requested. |
| `recall_granted_time` (17) | `string` | date-time | optional | When market operations granted the recall. The exchange also sets it when market operations cancel the trade. |
| `recall_rejected_time` (18) | `string` | date-time | optional | When market operations rejected the recall. |
| `latest_recall_process_time` (19) | `string` | date-time | optional | Until when market operations can process a recall request. It is a live deadline while a recall is pending (`state` `RREQ` or `RSFA`). |
| `recall_requestor` (20) | `string` | none | optional | Member id of the party that asked for the recall. The exchange sends it to the balancing group of the requesting party when that party is a member known to the exchange. |
| `parent_trade_id` (21) | `string` | none | optional | For a cross-contract trade, the id of its parent trade. The parent itself is never reported. Recalling a trade that carries a `parent_trade_id` recalls the parent and every trade with the same `parent_trade_id` at once. |
| `prearrange_type` (22) | `string` | none | optional | `OTC` for a pre-arranged trade, which cannot be recalled. `OPT` and `PNC` are deprecated exchange values. |

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

#### Errors

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

### <a id="rpc-WatchPublicTrades" name="rpc-WatchPublicTrades"></a>`Server-streaming` `rpc WatchPublicTrades`

Live public trade tape, mirror of the WS `public_trades` stream.

**Required permission:** Authenticated caller; no permission required. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `contract_ids` | `repeated uint64` | none | No | Contracts whose prints the stream carries. Filtered server-side, so prints on other contracts never reach the wire. Empty = the market-wide tape. |

#### Stream messages

Server-streaming: one `PublicTrade` message per event until the server closes the stream or the client cancels.

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `trade_id` | `string` | none | yes | The exchange trade id. |
| `contract_id` | `uint64` | none | yes | M7 contract id the trade printed on. |
| `qty` | `int64` | sub-MW (MW × 1000) | yes | sub-MW (MWh × 1000) |
| `px` | `sint64` | cents (CCY/MWh × 100) | yes | M7 price units (EUR/MWh × 100) |
| `exec_time` | `string` | RFC 3339 | yes | RFC 3339 from exchange |
| `exec_time_ms` | `int64` | Unix ms UTC | yes | parsed millis since epoch |
| `revision_no` | `int64` | none | yes | M7 revision counter for this trade record. |
| `state` | `string` | none | yes | M7 trade state; see [Trade states](#trade-states). |
| `buy_dlvry_area` | `string` | none | optional | "" == absent |
| `sell_dlvry_area` | `string` | none | optional | "" == absent |
| `self_trade` | `bool` | none | yes | True when both legs of the trade belong to this desk. |
| `remote_trade_id` | `string` | none | yes | XBID remote trade id. Set on a trade executed on a remote (XBID) contract, "" on a local trade, the exchange omits the attribute there. It is the join key onto the market-data transaction reports, which carry the same id. |

`Iterator[PublicTrade]`

No snapshot (seed history via `list_public_trades`); each message is one live `PublicTrade`. A lagged broadcast skips missed prints (re-request per-contract history to recover).

#### Errors

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

### <a id="rpc-WatchTradeTape" name="rpc-WatchTradeTape"></a>`Server-streaming` `rpc WatchTradeTape`

The public trade tape with each print's contract metadata already resolved, mirror of the WS `trade_tape` stream and built from the same rows, so a cross-product tape needs no contract lookups of its own.

**Required permission:** Authenticated caller; no permission required. (see [Permissions](#permissions))

#### Request

This RPC takes no request fields: it is the whole tape, as on WS.

#### Stream messages

Server-streaming: one `TradeTapeEvent` message per event until the server closes the stream or the client cancels.

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `type` | `EventType` | none | yes | SNAPSHOT for the recent tape, or UPSERTED for the rows of one new or revised print. |
| `rows` | `repeated TradeTapeRow` | none | yes | The rows; see the table below. |
| `sent_at_ms` | `int64` | Unix ms UTC | yes | When the gateway sent the event. |

#### Row fields (`TradeTapeRow`)

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `trade_id` | `string` | none | yes | The exchange trade id. |
| `contract_id` | `uint64` | none | yes | M7 contract id the trade printed on. |
| `area_id` | `StringValue` | none | optional | Delivery area this row is listed under. Set on every row the gateway sends. |
| `prod` | `StringValue` | none | optional | Product code (e.g. `"H"`, `"QH"`); absent while the contract is not classified under a product. |
| `name` | `StringValue` | none | optional | Contract display name. |
| `delivery_start` | `StringValue` | RFC 3339 | optional | Delivery period start. |
| `px` | `sint64` | cents (CCY/MWh × 100) | yes | Execution price. |
| `qty` | `int64` | sub-MW (MW × 1000) | yes | Executed quantity. |
| `exec_time` | `string` | RFC 3339 | yes | Execution time as the exchange sent it. |
| `exec_time_ms` | `int64` | Unix ms UTC | yes | Execution time, parsed. |
| `state` | `string` | none | yes | M7 trade state; see [Trade states](#trade-states). |

`Iterator[TradeTapeEvent]`: `type` ∈ {`SNAPSHOT`, `UPSERTED`}.

The first event is `SNAPSHOT`: the rows of up to the 200 most recent prints, **oldest first**, so you can walk them in order to derive each contract's tick direction and then reverse them for newest-first display. Every later event is `UPSERTED`, carrying the rows of one print as it arrives or as the exchange revises it (WS coalesces rows per tick; this stream sends each print as it comes). A print is listed once per delivery area it touches, so a cross-border print carries one row under its buy area and one under its sell area. A print whose contract the gateway no longer holds is left out; the raw print is still on [`WatchPublicTrades`](#rpc-WatchPublicTrades). A lagged broadcast skips the prints missed and the stream stays open, as on `WatchPublicTrades`.

#### Errors

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

### <a id="rpc-WatchPnl" name="rpc-WatchPnl"></a>`Server-streaming` `rpc WatchPnl`

Live P&L, mirror of the WS `pnl` stream. A snapshot computed at subscribe, then one message per second: the desk's P&L is computed once a second and the same snapshot goes to every subscriber on either transport, narrowed to the caller. Each message reflects every fill, mark move and delivery day passed before the second it was computed. A client that reads slowly receives the newest snapshot, not a backlog of the ones it missed.

**Required permission:** Authenticated caller; results are scoped to the members you may see. `read_pnl` widens the result. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `v_member_short_id` | `string` | none | No | Empty = caller's default scope. Non-empty narrows to one member; `PermissionDenied` unless the caller may see it (same as `get_pnl`). |

#### Stream messages

Server-streaming: one `PnlSnapshot` message per event until the server closes the stream or the client cancels.

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `per_contract` | `repeated ContractPnl` | none | yes | One entry per (area_id, contract_id) that has any trade the exchange has not reversed (any state but `RGRA` or `CNCL`). |
| `per_area_prod` | `repeated AreaProductPnl` | none | yes | Roll-up across contracts in each (area_id, product) bucket. |
| `per_vm` | `repeated VmContractPnl` | none | yes | One entry per (v_member_short_id, area_id, contract_id). |
| `per_vm_area_prod` | `repeated VmAreaProductPnl` | none | yes | Roll-up per (v_member_short_id, area_id, product). |
| `computed_at_ms` | `int64` | Unix ms UTC | yes | Unix ms UTC |
| `compute_us` | `uint32` | microseconds | yes | microseconds spent in compute() |
| `totals` | `repeated CurrencyTotal` | none | yes | One realized/unrealized total per currency, summed server-side so a client renders the venue figure without adding rows (and never adds EUR to GBP). |
| `unpriced_trades` | `uint64` | none | yes | Trades the exchange has not reversed (any state but `RGRA` or `CNCL`) left out of this snapshot because their delivery duration is not yet known, so the money could not be energy-scaled; they rejoin once the contract report heals the duration. |

`Iterator[PnlSnapshot]`: one per second.

P&L is a computed view, not an event, so this polls: an immediate `PnlSnapshot` on subscribe then a fresh one each second, scoped exactly like `get_pnl`.

#### Errors

| gRPC status | Condition |
| --- | --- |
| `PERMISSION_DENIED` | v_member_short_id names a member the caller may not read. |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

### <a id="rpc-WatchSlotPositions" name="rpc-WatchSlotPositions"></a>`Server-streaming` `rpc WatchSlotPositions`

Live usage of the [slot position limit](#ops-slot-limit), mirror of the WS `slot_positions` stream, scoped like [`GetSlotPositions`](#rpc-GetSlotPositions). Every message is the full set of slots for the range, never a delta, so a client replaces what it holds. The first message is sent at subscribe; after it, a message is sent only when something in the set changed: at most once per second from fills and orders, plus an immediate message when the slot settings or a member's slot limit change. Each message carries the mode, the House limit (with `read_status` only), the area's `locked` flag and a sequence number `seq` that rises by one with every set the shared computation publishes. A subscriber can see gaps in `seq`: a slow reader skips to the newest set, and on WS a set that shows the caller nothing new is not sent. A gap loses nothing, since every message carries the full set. Every subscriber of the same area, range and scopes shares one computation, on either transport, and a subscriber that reads slowly receives the newest set, not a backlog.

**Required permission:** Authenticated caller; results are scoped to the members assigned to the caller and active. `read_status` widens the result to the House scope. (see [Permissions](#permissions))

#### Request

`WatchSlotPositionsRequest` carries the fields of `GetSlotPositionsRequest`: `delivery_area`, `from_ms`, `to_ms` and the optional `v_member_short_id`, validated the same way. The scopes are resolved once, at subscribe.

#### Stream messages

Server-streaming: one `SlotPositionsResponse` per set, the same message `GetSlotPositions` returns, with `seq` set.

#### Errors

| gRPC status | Condition |
| --- | --- |
| `INVALID_ARGUMENT` | The request is refused as `GetSlotPositions` refuses it; no stream opens. |
| `PERMISSION_DENIED` | `v_member_short_id` names a member not assigned to the caller, or an inactive one. |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
for msg in client.watch_slot_positions(delivery_area=area, from_ms=start, to_ms=start + 24 * 3_600_000):
    print(msg.seq, len(msg.slots))  # every message is the full set
```

### <a id="rpc-WatchHub2Hub" name="rpc-WatchHub2Hub"></a>`Server-streaming` `rpc WatchHub2Hub`

Live hub-to-hub ATC capacity out of one source hub for one delivery window, mirror of the WS `watch_hub2hub` stream with the same filter, snapshot and lag rules: the live form of [`GetHub2Hub`](#rpc-GetHub2Hub). Two cases differ from WS: an unparseable window is `INVALID_ARGUMENT` here, where WS answers with an empty response and no subscription; and with hub-to-hub disabled this stream sends one snapshot and then ends, where the WS connection stays open.

**Required permission:** Authenticated caller; no permission required. (see [Permissions](#permissions))

#### Request

| Name | Type | Unit | Required | Description |
| --- | --- | --- | --- | --- |
| `delivery_area_from` | `string` | none | Yes | EIC code of the source hub. |
| `delivery_from` | `string` | RFC 3339 | Yes | Window start (inclusive on `dlvry_start`). |
| `delivery_to` | `string` | RFC 3339 | Yes | Window end (exclusive on `dlvry_start`). |

There is no destination filter (the WS command has none): every destination reachable from the source hub is sent.

#### Stream messages

Server-streaming: one `Hub2HubEvent` per event, holding exactly one of the three below in its `event` oneof.

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `snapshot` | `Hub2HubSnapshot` | none | oneof | `enabled`, `capacity_connected` and `data` (`repeated AtcEntry`), as `GetHub2HubResponse` carries them: the stored capacity for the hub and window, minus periods that ended more than an hour ago. |
| `update` | `Hub2HubUpdate` | none | oneof | One exchange update: `source_area`, `dlvry_start` and `dlvry_end` (RFC 3339) name the hub and period, and `rows` (`repeated AtcEntry`) hold one row per destination. It is the whole row for that hub and period and replaces what you hold for it, even when `rows` is empty. |
| `heartbeat` | `Hub2HubHeartbeat` | none | oneof | A change in the capacity feed's connection state: `connected` and `ts_ms` (Unix ms UTC). |

`AtcEntry` rows carry the fields and units listed on [`GetHub2Hub`](#rpc-GetHub2Hub).

`Iterator[Hub2HubEvent]`: read `event.WhichOneof("event")`.

The first event is a `snapshot`. After it come the updates whose source hub is `delivery_area_from` and whose delivery start falls in `[delivery_from, delivery_to)`, and the heartbeats. The gateway subscribes to both feeds before it builds the snapshot, so nothing landing in between is lost. A stream that falls behind the updates is sent a fresh `snapshot`: replace everything you hold with it, since the updates it missed are not replayed. With hub-to-hub disabled on the gateway the stream is one `snapshot` with `enabled` false and no data, and then it ends with OK. While the exchange's XBID side is down a stream can stay on its snapshot for a long time.

#### Errors

| gRPC status | Condition |
| --- | --- |
| `INVALID_ARGUMENT` | `delivery_from` or `delivery_to` is not RFC 3339; the message names the field (`invalid delivery_from: ...`), as on `GetHub2Hub`. No stream opens. |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

#### Example

```
for ev in client.watch_hub2hub(delivery_area_from=area, delivery_from=start, delivery_to=end):
    kind = ev.WhichOneof("event")  # "snapshot", "update" or "heartbeat"
```

### <a id="rpc-WatchState" name="rpc-WatchState"></a>`Server-streaming` `rpc WatchState`

Live runtime-health snapshot, mirror of the WS `state` stream and the streaming form of `get_state`.

**Required permission:** `read_state`. (see [Permissions](#permissions))

#### Request

This RPC takes no request fields.

#### Stream messages

Server-streaming: one `SystemState` message per event until the server closes the stream or the client cancels.

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `uptime` | `string` | none | yes | Process uptime formatted as e.g. "2h 14m 03s" (matches REST shape). |
| `operational` | `bool` | none | yes | `true` when every required subsystem is healthy. |
| `issues` | `repeated string` | none | optional | Human-readable descriptions of failing health checks. Empty when `operational` is true. |
| `admission` | `string` | none | yes | `open`, `closed` or `degraded`: whether new orders and modifies are admitted. `closed` while any order-critical issue is present, except as follows. `degraded` while the only issues are `trade_report refused` and the `cash_exposure_window not covered` it opens, and admission is open anyway because `system.trade_ingest_fault` is `continue` or an operator acknowledged the fault. Cancels are never gated. |
| `amqp_connected` | `bool` | none | yes | Whether the AMQP connection to the exchange is up. |
| `amqp_private_consumer_healthy` | `bool` | none | yes | True while the AMQP private consumer that carries your order acknowledgements and execution reports is alive. |
| `amqp_broadcast_consumer_healthy` | `bool` | none | yes | True while the AMQP broadcast consumer that carries market-state and instrument messages is alive. |
| `amqp_publisher_healthy` | `bool` | none | yes | True while the AMQP publisher that sends commands to the exchange is operational. |
| `amqp_publisher_tx_capacity` | `uint32` | none | yes | Remaining capacity of the bounded publisher_tx channel. |
| `amqp_market_active` | `bool` | none | yes | `true` when M7 has the market open for trading. |
| `amqp_broadcast_sequence_healthy` | `bool` | none | yes | `true` while the broadcast feed's per-routing-key sequence counters are contiguous. Cleared when a broadcast is lost or M7 resets its sequences, and set again only once a fresh subscription has re-established the baseline; order entry and modify are refused while it is false. |
| `ws_order_book_stream_connected` | `bool` | none | yes | Whether the WebSocket connection to the exchange's order-book stream is up. |
| `ws_order_book_sequence_healthy` | `bool` | none | yes | True while the order-book feed's sequence numbers are contiguous, false after a detected gap until it re-syncs. |
| `ws_order_book_synchronized` | `bool` | none | yes | True once the local order book has taken its initial snapshot and is tracking live deltas. |
| `ws_order_book_pong` | `int64` | Unix ms UTC | yes | Time of the last pong on the order-book connection, 0 before the first pong. A pong proves the socket, not the feed. |
| `ws_order_book_delta` | `int64` | Unix ms UTC | yes | Unix ms of the last applied delta; 0 before the first and after a reconnect. The last time market data actually arrived on this feed. |
| `ws_order_book_delta_per_hour` | `uint64` | per hour | yes | Rolling count of order-book deltas applied per hour. |
| `ws_order_book_avg_processing_time` | `string` | none | yes | Rolling-average display strings, same formatting as the REST shape (e.g. "1.2 ms"); "" until the first sample window completes. |
| `ws_order_book_avg_latency` | `string` | none | yes | Rolling-average order-book feed latency as a display string such as "1.2 ms", empty until the first sample window completes. |
| `ws_private_data_stream_connected` | `bool` | none | yes | Whether the WebSocket connection to the exchange's private-data stream (your orders and trades) is up. |
| `ws_private_data_sequence_healthy` | `bool` | none | yes | True while the private-data feed's sequence numbers are contiguous, false after a detected gap. |
| `ws_private_data_synchronized` | `bool` | none | yes | True once every part of the private-data feed’s initial order snapshot has arrived and been applied to the order store, together; false from a reconnect until then. |
| `ws_private_data_pong` | `int64` | Unix ms UTC | yes | Time of the last pong on the private-data connection, 0 before the first pong. |
| `ws_private_data_delta_per_hour` | `uint64` | per hour | yes | Rolling count of private-data messages applied per hour. |
| `ws_private_data_avg_processing_time` | `string` | none | yes | Rolling-average private-data processing time as a display string such as "1.2 ms", empty until the first sample window completes. |
| `ws_private_data_avg_latency` | `string` | none | yes | Rolling-average private-data feed latency as a display string such as "1.2 ms", empty until the first sample window completes. |
| `license` | `LicenseView` | none | yes | Mirrors the REST /state license block. The full installed license; expiry status never gates trading and never drops a connection. |
| `trades_received` | `uint64` | none | yes | Cumulative since process start. A trade-persistence loss is never silent: a failed chunk is counted here rather than swallowed. Trade rows handed to the backfill worker across every drained snapshot. |
| `trades_persisted` | `uint64` | none | yes | Trade rows the worker committed to the database. |
| `trades_persist_failed` | `uint64` | none | yes | Trade rows lost to a failed begin/insert/commit (the load-bearing count). |
| `writes_dropped` | `uint64` | none | yes | Fire-and-forget writes lost (orders, audit, M7 errors, public trades, exchange messages). The writer queues are unbounded, so nothing is shed; a lost write means a writer accepted a batch and its transaction would not commit, the database refused that row, or a shutdown could not commit it within its 30-second drain. Counted per stream on the `stream` label of `voltnir_writes_dropped_total`. It resets on restart; each clean shutdown records the run's totals per stream in its `system_shutdown` audit row. |
| `trade_reports_refused` | `uint64` | none | yes | Cumulative since start: trade capture reports refused because their financial core could not be read. Non-zero means a trade the exchange executed was missed; while the `trade_report refused` issue is present, order admission is closed until the re-asked window brings the trade in, unless the desk trades on through it (`admission` then reads `degraded`). |
| `product_parameters_loaded` | `bool` | none | yes | Whether the session's first product report has been applied, so the gateway knows the per-product decimal scale every wire integer is on. Order admission is refused (after a short login grace) until this is true. |
| `product_scale_unrepresentable` | `uint64` | none | yes | Products whose published decimal scale or quantity unit the gateway cannot denominate in its own cents-and-sub-MW store; orders on them are refused. |
| `product_scale_frames_dropped` | `uint64` | none | yes | Cumulative since start: inbound frames dropped because their product's decimal scale was unknown or unrepresentable. |
| `product_scale_orders_refused` | `uint64` | none | yes | Cumulative since start: orders refused for an unknown or unrepresentable product scale. |
| `product_scale_changes` | `uint64` | none | yes | Cumulative since start: product reports that changed a product's recorded decimal scale. |
| `contracts_awaiting_definition` | `uint64` | none | yes | Book-born contracts streaming a book but with no contract definition from the exchange yet, so they are withheld from the contracts stream and list_contracts until their delivery is known (gauge). |
| `contract_reports_broadcast` | `uint64` | none | yes | Contract definitions the exchange has broadcast to this session without being asked. |
| `last_update_pass_refused` | `bool` | none | yes | `true` when the exchange refused this login's inquiry for the trades it updated while Voltnir was not connected (`dateMeaning=LAST_UPDATE`). Voltnir then trades on the match-time inquiry alone, so a recall or cancellation resolved during that time, on a trade matched before the cash-exposure window, can still count in position, slot sums and P&L until the exchange reports the trade again. It does not close order entry. The refused question is not asked again: the next login asks only about what changed after this session last heard the exchange, so a trade reversed during the outage before this login keeps counting until the exchange reports it again or a trade-history restore brings it back. The flag clears when the gateway next connects to the exchange. |

`Iterator[SystemState]`: one per second.

Emits an immediate `SystemState` then a fresh one each second. Gated by `read_state` (`PERMISSION_DENIED` at open without it). The trading-posture aggregate is its own stream now; see [`WatchStatus`](#rpc-WatchStatus).

#### Errors

| gRPC status | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `read_state`. |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

### <a id="rpc-WatchStatus" name="rpc-WatchStatus"></a>`Server-streaming` `rpc WatchStatus`

Live caller-scoped trading-posture aggregate, mirror of the WS `status` stream and the streaming form of `get_status`.

**Required permission:** Authenticated caller; no permission required. `read_status` widens the result (desk money and licence). (see [Permissions](#permissions))

#### Request

This RPC takes no request fields.

#### Stream messages

Server-streaming: one `SystemStatus` message per event until the server closes the stream or the client cancels.

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `throttling` | `ThrottlingStatus` | none | yes | M7's reported order load-management status, plus this gateway's own client-side guard: OMT headroom left, and why order actions are being refused when they are. Base layer, always present. |
| `trading_enabled` | `bool` | none | yes | Whether trading is currently enabled (the kill switch). Base layer. |
| `operational` | `bool` | none | yes | `true` when every required subsystem is healthy (also on `SystemState`). Base layer. |
| `admission` | `string` | none | yes | Whether new orders and modifies are admitted, the same value as `SystemState.admission`. Base layer. |
| `cash_limits` | `repeated CashLimit` | none | yes | M7-reported per-currency cash/margin feed. Distinct from `cash_limit` (the Voltnir-configured order limit). Same shape as GetCashLimitsResponse. `read_status` only, empty without it. |
| `cash_limit` | `CashLimitStatus` | cents (currency × 100) | yes | The desk-wide cash-limit state: effective House limit, live consumption, and remaining headroom per currency pool with pool provenance, in cents, plus `delivery_risk_applied` and `delivery_risk_source`, as [`GetStatus`](#rpc-GetStatus) describes them. `read_status` only. |
| `license` | `LicenseView` | none | yes | The full installed license (also on `SystemState`). `read_status` only; the base-layer `license_summary` is what an expiry banner needs. |
| `license_summary` | `LicenseSummary` | none | yes | Base-layer license projection: status kind, expiry, grace-window end while in grace, and `mode`, the licence tier (`"trader"` or `"desk"`; on `"trader"` the user, member and permission management RPCs are refused with `LICENSE_DESK_REQUIRED`). Everything an expiry banner needs, none of the holder / identity / provenance the full `license` carries. Always present. |
| `m7_client_cert` | `M7ClientCert` | none | optional | The M7 client certificate, the first certificate in the file the gateway's `epex_connection.cert` setting names: `status_kind` (`valid`, `expiring_soon` from 30 days before expiry, `expired`, `not_yet_valid` or `unreadable`), `status_days` (days left, days since expiry, or days until it starts; 0 for `valid` and `unreadable`), `status_reason` (set only when unreadable: a missing file, no PEM block, no certificate, or one that does not parse) and `not_after` (RFC 3339 UTC, unset when unreadable). Read at startup and every hour. The exchange refuses the connection under an expired certificate, with no grace period; a replacement file at the same path is used on the next connection attempt, with no restart. `read_status` only, unset without it. |
| `accounts` | `repeated AccountView` | none | optional | The accounts this caller may trade for, the House when it holds `trade_global`, plus each assigned active member, each with its own position limits and cash usage. Always present (empty when the caller may trade for none). |

`Iterator[SystemStatus]`: one per second.

Emits an immediate `SystemStatus` then a fresh one each second (1 Hz poll). Open to every authenticated caller. Each frame is re-projected per caller, resolving the caller from the user cache every tick, so a member reassigned, deactivated or re-limited shows on the next frame, and a caller whose key is rotated or deleted ends the stream. Carries the base posture and the caller's own `accounts` always; the desk-wide money and full licence only with `read_status` (those fields unset otherwise).

#### Errors

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

### <a id="rpc-WatchMessages" name="rpc-WatchMessages"></a>`Server-streaming` `rpc WatchMessages`

Live system / order-rejection log, mirror of the WS `messages` stream.

**Required permission:** Authenticated caller; results are scoped to the members you may see. `read_orders`, `bypass_member_check` widens the result. (see [Permissions](#permissions))

#### Request

This RPC takes no request fields.

#### Stream messages

Server-streaming: one `MessageItem` message per event until the server closes the stream or the client cancels.

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `json` | `string` | none | yes | One system-message row serialised as a JSON object: event, order_id, contract_id, side, price, quantity, user_code, text, ts_ms. |

`Iterator[MessageItem]`: each `.json` is one message row.

Polls at 1 Hz: the current log on subscribe, then rows appended since (deduped on `ts_ms`). Each row is JSON (`MessageItem.json`) with the same shape as a `SystemMessage` row on the WS `messages` stream. An `order_executed` row is written once per side of a trade, when that side first reaches the gateway; a later state change of the trade (a recall or a cancellation), a re-delivery of a trade the gateway still holds, or a side that reaches the gateway on a trade the exchange has already reversed (`RGRA` or `CNCL` in the newest revision the gateway holds, as the login backfill can return a trade the exchange reversed while the gateway was not connected) writes none. The gateway holds every trade in the cash-exposure window and every trade on a contract delivering today or later, so an older trade brought back by `restore_trade_history`, or by the login's inquiry for the trades the exchange updated while the gateway was not connected, is written again unless the exchange has since reversed it. **Scoping.** Every order row (`order_added`, `order_modified`, `order_deleted`, `order_hibernated`, `order_executed`, `order_rejected`) belongs to the virtual member of the order or trade leg it describes, and is member-isolated like [`watch_orders`](#rpc-WatchOrders), on the first batch and every later one: a caller holding `read_orders` (or `bypass_member_check`) receives every row, the untagged house-account ones included; every other caller receives only the rows of the virtual members assigned to them. A refusal that names no member, such as an undeliverable request no order is waiting on, is a house-account row. `license_notice`, `throttling_notice` and `m7_client_cert_notice` are about the whole login and reach every caller; a caller with no assigned members receives only those three kinds. An `m7_client_cert_notice` is written when the M7 client certificate crosses 30, 14, 7 or 1 days before expiry, expires, is not yet valid, cannot be read, or is valid again after a replacement. A `slot_limit_notice` names a trade with no delivery window and the delivery area it locks for the slot position limit, once per trade per run (in `observe` and `reject`); it carries no member, so it is a house-account row. A slot-limit `order_rejected` row tagged with a member reaches that member's readers, so it reads as a caller without `read_status` is told (see `FAILED_PRECONDITION` under status codes); a house-account one keeps every figure. A trade between two virtual members of the desk logs one `order_executed` per leg, and each member receives only its own. The caller's scope is fixed when the stream opens.

#### Errors

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

### <a id="rpc-WatchAuditEvents" name="rpc-WatchAuditEvents"></a>`Server-streaming` `rpc WatchAuditEvents`

Live tail of the compliance audit log, the streaming companion to `query_audit_events`, member-scoped as it is: a caller without `read_orders` or `bypass_member_check` is sent only the rows its unfiltered `QueryAuditEvents` would page.

**Required permission:** `read_audit`. `read_orders` or `bypass_member_check` widens the result to the whole trail; without either it is member-scoped. (see [Permissions](#permissions))

#### Request

This RPC takes no request fields.

#### Stream messages

Server-streaming: one `AuditEventItem` message per event until the server closes the stream or the client cancels.

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `json` | `string` | none | yes | JSON object of one audit event: actor, transport, source_ip, action, target, before/after snapshots, outcome, reason, ts, and `v_member_short_id` (the member of the order an order action is about, `null` otherwise). |

`Iterator[AuditEventItem]`

Gated by `read_audit` (denied at open, server-side). Event-driven: each row is pushed the moment it commits (no per-stream polling). No snapshot: seed history via `query_audit_events`, then this tails rows appended after subscribe. Each `AuditEventItem.json` carries a stable per-row `id`; dedup on it against the seeded page. Filter client-side.

#### Errors

| gRPC status | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `read_audit`. |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

### <a id="rpc-WatchM7Errors" name="rpc-WatchM7Errors"></a>`Server-streaming` `rpc WatchM7Errors`

Live tail of the M7 exchange-error log, the streaming companion to `query_m7_errors`. One exchange error response can carry several errors, since the exchange refuses a request that names several orders with a single response listing each refusal. Each error is its own `err_resp` row with its own `err_code`, `err_text` and `cl_ordr_id`, and `raw_payload` holds the whole response. The refused order is told the texts of the errors that name it, joined with `;`, and their code only when they share one. An error response the gateway cannot read is a `parse_error` row carrying the raw response, and the request it answered is still reported refused.

**Required permission:** `read_m7_errors`. (see [Permissions](#permissions))

#### Request

This RPC takes no request fields.

#### Stream messages

Server-streaming: one `M7ErrorItem` message per event until the server closes the stream or the client cancels.

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `json` | `string` | none | yes | JSON object of one m7_errors row: received_at, kind, category, err_code, err_identifier, err_text, cl_ordr_id, client_correlation_id, var_list, voltnir_*, raw_payload, severity. |

`Iterator[M7ErrorItem]`

Same event-driven semantics as `watch_audit_events` (pushed on commit, no polling) but gated by `read_m7_errors`; seed via `query_m7_errors`. Each `M7ErrorItem.json` carries the stable `id` key.

#### Errors

| gRPC status | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `read_m7_errors`. |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

### <a id="rpc-WatchExchangeMessages" name="rpc-WatchExchangeMessages"></a>`Server-streaming` `rpc WatchExchangeMessages`

Live tail of the exchange's own message feed, the streaming companion to `list_exchange_messages`.

**Required permission:** `read_m7_errors`. (see [Permissions](#permissions))

#### Request

This RPC takes no request fields.

#### Stream messages

Server-streaming: one `ExchangeMessageItem` message per event until the server closes the stream or the client cancels.

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `json` | `string` | none | yes | JSON object of one exchange_messages row: id (null when the message was streamed but not stored), received_at, exchange_ts, msg_id, scope, code, key, severity, text (placeholders substituted from vars, with every instant inside a variable restated in UTC, RFC 3339 with Z; vars keeps the exchange's own spelling), product, account_id, buy_area, sell_area, market_supervision, vars. |

Gated by `read_m7_errors` (`PERMISSION_DENIED` at open without it), the same permission `list_exchange_messages` carries. The tail and the history are the same rows, so subscribing is not a way around the gate on reading them.

The stream also carries the messages that are never stored, the ones the exchange marks non-persistent, and the per-contract lifecycle broadcasts, codes `74` (`x_contract_closed`), `76` (`x_contract_closed_tsos`) and `77` (`x_contract_in_balancing_phase`), which Voltnir drops because one arrives per contract per phase and none names an order, trade or position of yours: their `id` is `null` and they cannot be re-fetched, so a client that needs them must be subscribed when they arrive.

`Iterator[ExchangeMessageItem]`

Pushed on receipt, no polling, no snapshot, seed history via `list_exchange_messages` and de-duplicate the tail on `msg_id`.

#### Errors

| gRPC status | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `read_m7_errors`. |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

### <a id="rpc-WatchSystemLog" name="rpc-WatchSystemLog"></a>`Server-streaming` `rpc WatchSystemLog`

Live tail of the gateway's own diagnostic log, the streaming companion to `list_system_log`.

**Required permission:** `read_logs`. (see [Permissions](#permissions))

#### Request

This RPC takes no request fields.

#### Stream messages

Server-streaming: one `SystemLogItem` message per event until the server closes the stream or the client cancels.

| Name | Type | Unit | Presence | Description |
| --- | --- | --- | --- | --- |
| `json` | `string` | none | yes | JSON object of one captured entry: seq (uint64, the cursor), ts_ms (capture time, Unix milliseconds), level ("error"\|"warn"\|"info"\|"debug"), target (the emitting module path) and message (the formatted line, truncated at 4 KiB with a visible marker). On the WatchSystemLog stream only, an entry with a null seq and target "voltnir.system_log" is a synthetic marker: the server generated it to say this subscriber fell behind and lost entries. It is reported in band rather than logged, because logging it would feed the stream reporting on it. |

**No level parameter, deliberately.** The gateway captures at its configured level and this stream carries everything captured. A subscriber that had narrowed the stream and later widened it would have a hole in its history it could not explain, so the filtering belongs on your side.

An item whose `seq` is `null` and whose `target` is `voltnir.system_log` is a **marker the server generated**, not a captured line: your subscription fell behind and the marker names how many entries were dropped on the way to it. Re-query `list_system_log` to fill the gap. The loss is reported in band rather than logged, because logging it would feed a new entry into the very stream that is already behind.

`Iterator[SystemLogItem]`

Pushed as each entry is captured, no polling, no snapshot, seed history via `list_system_log` and de-duplicate the tail on `seq`.

#### Errors

| gRPC status | Condition |
| --- | --- |
| `PERMISSION_DENIED` | The caller does not hold `read_logs`. |

The transport-wide statuses (`UNAUTHENTICATED`, `RESOURCE_EXHAUSTED`, `INTERNAL`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`) may also occur; see the [Error reference](#errors).

<a id="errors" name="errors"></a>

## Error reference

gRPC uses a status enum instead of HTTP codes. Voltnir's mapping is exhaustive and matches REST 1:1, which is useful when porting clients between transports.

| REST status | gRPC `StatusCode` | Trigger |
| --- | --- | --- |
| 400 | `INVALID_ARGUMENT` | Malformed input, unknown enum value, parse error |
| 401 | `UNAUTHENTICATED` | Missing / invalid bearer token |
| 403 | `PERMISSION_DENIED` | Caller lacks the required permission |
| 404 | `NOT_FOUND` | Unknown contract / order / user / member |
| 429 | `RESOURCE_EXHAUSTED` | The API key is over its per-key request bound (the per-key request bound in a the request window window, counted across REST, WS and gRPC together). The window is fixed, not sliding, so the whole allowance is available again at the next boundary; the message states the bound to back off to. Cancelling an order, cancelling all orders and *disabling* trading are never refused by the bound: every other rule in the gateway leaves the exposure-reducing route out open, and a rate limit must not be the one that closes it. Re-*enabling* trading admits exposure again, so it is ordinary traffic and is bounded like any other call. `CancelOrder`, `CancelAllOrders` and a `SetTradingAllowed` carrying `allowed: false` therefore never return `RESOURCE_EXHAUSTED`. The kill-switch exemption belongs to a caller that holds `toggle_trading`: one that does not has no switch to be locked out of, since the permission gate refuses it whichever way the bound falls, so its `SetTradingAllowed` is charged and bounded in both directions and may return `RESOURCE_EXHAUSTED` rather than `PERMISSION_DENIED` |
| 409 | `ABORTED` | State conflict, e.g. modify already in progress (see [ModifyOrder](#rpc-ModifyOrder) for how long that lock is held) |
| 409 | `ABORTED` (message prefixed `ORDER_CHANGED:`) | The order changed at the exchange before the command was applied, a fill, or another modify, moved its revision while the command was on its way, so the exchange refused it on its revision guard. Nothing was applied and the order is resting exactly as it was, one revision further on. Retry the same command: it is rebuilt on the revision the gateway now holds. Bound the retry rather than looping, a repeatedly filling order can lose the race more than once, and a cancel may find the order already gone next time. The Python SDK raises `OrderChanged`, a subclass of `Aborted`, for exactly this case |
| 409 | `ABORTED` (message prefixed `ORDER_PENDING:`) | A [ModifyOrder](#rpc-ModifyOrder) or [CancelOrder](#rpc-CancelOrder) named an order the exchange has not yet acknowledged, so there is no exchange order to act on; nothing was sent. Retry once it is acknowledged, or wait for it on `WatchOrder` / `WatchOrders`. Only a caller who may act on the order’s member gets it; anyone else gets `NOT_FOUND`. Also the status of a member-scoped [CancelAllOrders](#rpc-CancelAllOrders) left incomplete by such an order |
| 422 | `FAILED_PRECONDITION` | Per-contract limit or slot position limit exceeded, a slot window unknown, self-cross blocked, a member order outside the member’s delivery areas (`MEMBER_AREA_NOT_ALLOWED`), trading disabled (operator kill-switch), an order, activation, size increase or reprice on a contract that has reached its delivery start (`CONTRACT_IN_DELIVERY`), the M7 load-management guard refusing the action (see [GetThrottling](#rpc-GetThrottling)), or the exposure the exchange's risk parameters put on the order would push consumed cash past one of the pool's bounds, the desk's House limit, the House remainder, the member's allocation, what the exchange still has available, or no bank-holiday calendar is configured for the pool's settlement currency (`no_holiday_calendar`, the exposure window those bounds are measured over cannot be placed on ECC Business Days without one, so the pool admits no new exposure until it is entered via [SetHolidays](#rpc-SetHolidays)) or its calendar holds no date in the current or next calendar year (`stale_holiday_calendar`, the ECC Business Day closings are an annual obligation, and last year's place none of this year's boundaries). The other currency's pool is unaffected, and an order that adds no exposure still passes under any of these. The same refusal also covers a consumed-cash figure the gateway could not finish computing: it is measured short when that happens, so the check refuses rather than admitting an order against it, and the message feed carries a line saying no limit was exceeded. (see [GetCashLimit](#rpc-GetCashLimit)) |
| 404 | `NOT_FOUND` (message prefixed `TRADE_NOT_FOUND:`) | [RecallTrade](#rpc-RecallTrade): no trade, or no trade of the order, that the caller may recall |
| 409 | `ABORTED` (message prefixed `TRADE_CHANGED:`) | [RecallTrade](#rpc-RecallTrade): the trade's revision moved past the `revision_no` named; nothing was sent |
| 409 | `FAILED_PRECONDITION` (message prefixed `RECALL_REFUSED:` or `RECALL_NOT_POSSIBLE:`) | [RecallTrade](#rpc-RecallTrade): the exchange refused the recall, or the trade is not `ACTI`. The result rides in the `grpc-status-details-bin` trailer as a `google.rpc.Status` detail |
| 504 | `DEADLINE_EXCEEDED` (message prefixed `OUTCOME_UNKNOWN:`) | [RecallTrade](#rpc-RecallTrade): the exchange did not acknowledge the recall in time; it may have reached the exchange |
| 500 | `INTERNAL` | Unexpected error |
| 503 | `UNAVAILABLE` | DB unavailable, system not operational, or the exchange handed the request back undelivered (message prefixed `NOT_PROCESSED:`), the one case in which the request definitely was not processed, and therefore the only one that is safe to resubmit blind. A returned order submission may be resubmitted **with the same `client_order_id`**: the exchange never saw the key, so the gateway frees it and the resubmission replaces the record. That order is also recorded `REJECTED` with the same reason and gives back the limit headroom it was holding. The Python SDK raises `RequestNotProcessed` for exactly this case, distinct from the `OrderOutcomeUnknown` it raises for every other `Unavailable` on an order call |
| 504 | `DEADLINE_EXCEEDED` | M7 did not acknowledge within the order acknowledgement timeout (default 2s). The outcome is *unknown*, not failed, the request may still have been processed, so re-check before resubmitting |

If the client cancels, the stream stops promptly; no wasted work on a result nobody will read.

#### Python SDK exceptions

Every RPC raises a typed subclass of `VoltnirError` on failure. Catch the specific class you care about; everything inherits from the base.

| gRPC status | Exception |
| --- | --- |
| `UNAUTHENTICATED` | `Unauthenticated` |
| `PERMISSION_DENIED` | `PermissionDenied` |
| `NOT_FOUND` | `NotFound` |
| `INVALID_ARGUMENT` | `InvalidArgument` |
| `FAILED_PRECONDITION` | `FailedPrecondition` |
| `ABORTED` | `Aborted` |
| `ABORTED` prefixed `ORDER_CHANGED:` | `OrderChanged` (subclass of `Aborted`) |
| `ABORTED` prefixed `ORDER_PENDING:` | `OrderPending` (subclass of `Aborted`) |
| `UNAVAILABLE` | `Unavailable` |
| `DEADLINE_EXCEEDED` | `DeadlineExceeded` |
| `INTERNAL` | `Internal` |
| Anything else | `VoltnirError` (base) |

Each instance carries `e.code` (the `grpc.StatusCode`), `e.message` (server detail) and `e.rpc` (which RPC raised it).

Copyright © 2026 Voltnir B.V. The Voltnir gateway is proprietary software, licensed under separate terms.
