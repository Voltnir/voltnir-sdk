# Voltnir REST API v1: Reference

> Auto-generated from the Voltnir API reference.

## Authentication

All API endpoints require a Bearer token in the `Authorization` header. Tokens are stored as SHA-256 hashes in the database; the raw key is shown only once, at creation or rotation.

> [!NOTE]
> **Required header on every request:**
>  `Authorization: Bearer <your_api_key>`

#### Auth errors (apply to every endpoint)

| Status | Body | Condition |
| --- | --- | --- |
| 401 | `{"error": "Unauthorized"}` | Missing or invalid token |
| 403 | `{"error": "Forbidden"}` | Valid token but the user lacks the required permission for this endpoint |

> [!CAUTION]
> API keys cannot be retrieved after initial creation. If a key is lost, use [POST /users/{id}/rotate-api-key](#post-rotate-key) to issue a new one. The old key is invalidated immediately.

## Security Advisory

Voltnir is a trading gateway. Mistakes have real financial consequences. Read this section before integrating.

> [!WARNING]
> **This system connects directly to a live exchange.** Orders submitted through this API create real obligations. There is no sandbox mode. Test integrations against a dedicated non-production environment if one is available.

> [!WARNING]
> **API keys must be treated as secrets.** They are transmitted as Bearer tokens. Use HTTPS at all times. Never log or embed raw API keys in source code. Rotate keys immediately if exposure is suspected.

> [!CAUTION]
> **Permissions are enforced server-side.** A user with `create_order` but not `delete_order` cannot cancel orders, not even their own. Review permission assignments carefully before going live.

> [!CAUTION]
> **PUT /trading_allowed with `enabled: false` cancels all resting orders immediately and blocks new order traffic.** This is a kill-switch. Use it deliberately: it sends a DeleteAllOrders command to the exchange with no undo, and while disabled new orders (`POST /order`) and modifies (`PUT /order`) are rejected with `422`. Cancels (`DELETE /order`, `DELETE /orders`) stay allowed; they only reduce exposure.

> [!CAUTION]
> **POST /restart triggers a graceful shutdown.** The process exits and relies on the host supervisor (systemd, Docker, etc.) to restart it. Do not call this endpoint unless you understand the operational impact.

## Units Reference

All numeric fields use fixed-point integer encoding. No floating-point values are used anywhere in the API.

> [!NOTE]
> Convert price: divide cents by 100 to get CCY/MWh. Convert quantity/position: divide sub-MW by 1000 to get MW.

| Field | Wire type | Unit | Example value | Human-readable |
| --- | --- | --- | --- | --- |
| `price` | `i64` | Cents (CCY/MWh × 100) | `5000` | 50.00 CCY/MWh |
| `quantity` | `u32` | Sub-MW (MW × 1000) | `1000` | 1.0 MW |
| `display_qty` | `u32` | Sub-MW | `500` | 0.5 MW (iceberg visible portion) |
| `hidden_quantity` | `u32 \| null` | Sub-MW | `1500` | 1.5 MW hidden for iceberg |
| `contract_limit` | `i32` | Sub-MW | `5000` | 5.0 MW max net position per contract |
| `max_position` | `i64` | Sub-MW | `10000` | 10.0 MW member position limit |
| `cash_limit` / `cents` | `i64` | EUR cents | `10000000` | €100,000 cash limit (executed-trade + open-order exposure) |
| `{eur,gbp}_{consumed,limit,remaining}_cents` | `i64` | Pool cents | `4200000` | Per-member live cash usage (see [members list](#get-members)); `remaining = limit − consumed` |
| `net_pos` | `i64` (signed) | Sub-MW | `-1000` | −1.0 MW (net short). Executed (ACTI) trades only; open orders excluded |
| `entry_ts_ms` | `i64` | Unix ms (UTC) | `1713600000000` | 2026-04-20T10:00:00Z |
| `timestamp_ms` | `i64` | Unix ms (UTC) | `1713600000000` | 2026-04-20T10:00:00Z |
| `validity_time_ms` | `i64 \| null` | Unix ms (UTC) | `1713610800000` | 2026-04-20T13:00:00Z |
| `duration` | `string` | Decimal hours | `"1.0"` | 1-hour delivery window. M7 sends decimal hours as a string, passed through verbatim: `"0.25"`, `"0.5"`, `"1.0"`, `"2.0"`; `null` until contract metadata arrives |

## Orders

Order management: create, modify, cancel, and query your resting orders on the exchange. Orders are identified by a `client_order_id` (UUID) which you supply at submission time.

> [!NOTE]
> All order submissions flow through M7. A `201` response means the exchange accepted the order. A `422` with `"state":"REJECTED"` means M7 received it but rejected it (check the `reason` field). A `503` means the system is not connected to the exchange.

### `POST` `/api/v1/order`

_Permission: create_order_

Submit a new order to the exchange. Specify the contract either by `contract_id` or by `product` + `delivery_start`. Returns the exchange-assigned state.

#### Request Body

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `side` | `string` | Yes | `"BUY"` or `"SELL"` |
| `price` | `i64` | Yes | Cents, e.g. `5000` = 50.00 CCY/MWh |
| `quantity` | `u32` | Yes | Sub-MW, e.g. `1000` = 1.0 MW. Must be > 0. |
| `delivery_area_id` | `string` | Yes | EIC area code. Max 64 chars. |
| `contract_id` | `i64` | Cond* | M7 contract ID. Either this OR `product`+`delivery_start`. |
| `product` | `string` | Cond* | Product code (e.g. `"H"`). Used with `delivery_start`. |
| `delivery_start` | `string` | Cond* | ISO 8601 datetime. Used with `product` to look up contract. |
| `order_type` | `string` | No | Default: `"regular"`. See Order Types Guide. |
| `exe_restriction` | `string` | No | Default: `"non"`. Options: `non`, `fok`, `ioc`, `aon`. |
| `validity_res` | `string` | No | Default: `"gfs"`. Options: `gfs`, `gtd`, `non`. |
| `entry_state` | `string` | No | Default: `"active"`. Use `"hibernated"` to submit inactive. |
| `display_qty` | `u32` | Cond | Required for iceberg orders, and rejected on any other order type. Must be < `quantity`. Sub-MW. |
| `validity_date` | `string` | Cond | ISO 8601. Required when `validity_res` = `"gtd"`. |
| `pre_arranged_acct` | `string` | Cond | Required when `order_type` = `"pre_arranged"`. |
| `v_member_short_id` | `string` | No | Virtual member short ID (e.g. `"VM001"`). Tagged in M7 Txt field. Max 64 chars. |
| `client_order_id` | `string` | No | Optional idempotency key (must be a UUID). Omitted → the gateway generates one, returned in the response. Reusing one still attached to a live order is rejected (`400`). |

#### Example Request

```json
{
  "side": "BUY",
  "price": 5000,
  "quantity": 1000,
  "delivery_area_id": "10YNL----------L",
  "product": "H",
  "delivery_start": "2026-04-20T22:00:00Z",
  "order_type": "regular",
  "exe_restriction": "non",
  "validity_res": "gfs"
}
```

#### Response: 201 Created

```json
{
  "client_order_id": "550e8400-e29b-41d4-a716-446655440000",
  "state": "ACTIVE",
  "reason": null
}
```

`state` values: `PENDING`, `ACTIVE`, `INACTIVE`, `HIBERNATED`, `REJECTED`, `UNKNOWN`  
 A `422` with `"state":"REJECTED"` indicates the exchange accepted the message but rejected the order; inspect `reason`.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "delivery_area_id is required"}` | Empty `delivery_area_id` |
| 400 | `{"error": "delivery_area_id exceeds maximum length"}` | `delivery_area_id` > 64 chars |
| 400 | `{"error": "quantity must be greater than zero"}` | `quantity` = 0 |
| 400 | `{"error": "v_member_short_id exceeds maximum length"}` | `v_member_short_id` > 64 chars |
| 400 | `{"error": "display_qty is required for iceberg orders"}` | iceberg type without `display_qty` |
| 400 | `{"error": "display_qty must be less than total quantity for iceberg orders"}` | `display_qty` ≥ `quantity` |
| 400 | `{"error": "pre_arranged_acct is required for pre-arranged trades"}` | `pre_arranged` type without account |
| 400 | `{"error": "validity_date is required when validity_res is gtd"}` | GTD without `validity_date` |
| 400 | `{"error": "validity_res must be \"non\" for fok or ioc orders"}` | FOK/IOC with non-`"non"` validity |
| 400 | `{"error": "provide contract_id or both product and delivery_start"}` | No contract identifier given |
| 400 | `{"error": "client_order_id must be a valid UUID"}` | Supplied `client_order_id` is not a UUID |
| 400 | `{"error": "client_order_id '…' is already in use"}` | Supplied `client_order_id` is still attached to a live (pending or resting) order |
| 400 | `{"error": "v-member '…' not found"}` / `"v-member '…' is inactive"` / `"v-member '…' is not assigned to your account"` | `v_member_short_id` names an unknown, deactivated, or unassigned member (assignment is bypassed by `bypass_member_check`) |
| 400 | `{"error": "not permitted to trade on the global account; submit the order under a v-member"}` | No `v_member_short_id` given and the caller lacks `trade_global` |
| 403 | `{"error": "Forbidden"}` | Missing `create_order` permission |
| 404 | `{"error": "contract not found for given delivery parameters"}` | `product`+`delivery_start` lookup failed |
| 422 | `{"error": "position limit exceeded"}` | Net position would exceed the contract limit |
| 422 | `{"error": "cash limit exceeded"}` | The order's monetary value would push consumed cash above the global or per-member cash limit |
| 422 | `{"error": "SELF_CROSS_BLOCKED: ..."}` | Order would cross one of your own resting orders while `self_trade_policy` is `reject` |
| 422 | `{"error": "trading is disabled by the operator kill-switch..."}` | Trading is disabled (`PUT /trading_allowed` set `enabled:false`). Order traffic is rejected before reaching M7 |
| 422 | `{"client_order_id":…,"state":"REJECTED","reason":…}` | Exchange rejected the order |
| 503 | `{"error": "…"}` | System not connected / not operational |
| 504 | `{"error": "…"}` | M7 did not acknowledge within `system.order_ack_timeout_ms` (default 2s) |
| 500 | `{"error": "…"}` | Publish failed or internal error |

### `PUT` `/api/v1/order`

_Permission: modify_order_

Modify an existing order. Supports price/quantity changes (`modify`), hibernation (`deactivate`), and un-hibernation (`activate`). **Waits for the exchange to acknowledge receipt** before responding: `200` means M7 accepted the request, `409` means M7 rejected it (e.g. the order was concurrently filled or deleted), `504` means no acknowledgement arrived in time. The resulting order state is then delivered on the order stream.

**Member isolation.** Beyond the `modify_order` capability, the caller must be authorized to act on the *existing* order's member: assigned to it, or holding `bypass_member_check`; an untagged house order requires `trade_global`. An order outside that scope returns `404` (identical to a missing one), so a desk cannot modify or re-tag another member's order.

#### Request Body

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `client_order_id` | `string` | Yes | UUID of the order to modify |
| `modify_action` | `string` | No | Default: `"modify"`. Options: `modify`, `activate`, `deactivate` |
| `price` | `i64` | Cond | Required when `modify_action` = `"modify"`. Cents. |
| `quantity` | `u32` | Cond | Required when `modify_action` = `"modify"`, and must be greater than zero. Sub-MW. |
| `display_qty` | `u32` | No | Sub-MW. For iceberg orders. Checked only when `modify_action` = `"modify"` and `quantity` is also provided; it must then be < `quantity`. |
| `validity_res` | `string` | No | Optional change to validity restriction |
| `validity_date` | `string` | Cond | ISO 8601. Required when `validity_res` = `"gtd"`. |
| `v_member_short_id` | `string` | No | Virtual member short ID. Max 64 chars. |

#### Example Request: price/quantity modify

```json
{
  "client_order_id": "550e8400-e29b-41d4-a716-446655440000",
  "modify_action": "modify",
  "price": 5200,
  "quantity": 2000
}
```

#### Example Request: deactivate (hibernate)

```json
{
  "client_order_id": "550e8400-e29b-41d4-a716-446655440000",
  "modify_action": "deactivate"
}
```

#### Response: 200 OK

```json
{"status": "modified"}
```

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "price is required for modify action"}` | `modify` action without `price` |
| 400 | `{"error": "quantity is required for modify action"}` | `modify` action without `quantity` |
| 400 | `{"error": "display_qty must be less than quantity"}` | `modify_action` = `"modify"` with both `display_qty` and `quantity` provided and `display_qty` ≥ `quantity` |
| 400 | `{"error": "validity_date is required when validity_res is gtd"}` | GTD without `validity_date` |
| 403 | `{"error": "Forbidden"}` | Missing `modify_order` permission |
| 404 | `{"error": "order not found"}` (may carry the exchange order id) | `client_order_id` not found, or the order's member is outside the caller's scope |
| 409 | `{"error": "modify already in progress"}` | Concurrent modify attempt on same order |
| 409 | `{"error": "exchange rejected the request: ..."}` | M7 rejected the modify (e.g. the order was concurrently filled or deleted) |
| 422 | `{"error": "trading is disabled by the operator kill-switch..."}` | Trading is disabled (`PUT /trading_allowed` set `enabled:false`) |
| 422 | `{"error": "position limit exceeded"}` / `{"error": "cash limit exceeded"}` | The new quantity/price would breach the contract position limit or the cash limit (the same pre-trade checks as `POST /order`) |
| 503 | `{"error": "…"}` | System not operational |
| 504 | `{"error": "…"}` | M7 did not acknowledge within `system.order_ack_timeout_ms` (default 2s) |
| 500 | `{"error": "…"}` | Publish failed |

### `DELETE` `/api/v1/order`

_Permission: delete_order_

Cancel a single resting order. The order must be in `ACTIVE` or `HIBERNATED` state. No concurrent modify may be in progress. **Waits for the exchange to acknowledge receipt** before responding: `200` means M7 accepted the cancel, `409` means M7 rejected it (e.g. the order was concurrently filled or deleted), `504` means no acknowledgement arrived in time.

**Member isolation.** Beyond the `delete_order` capability, the caller must be authorized to act on the order's member (assigned to it, or holding `bypass_member_check`); an untagged house order requires `trade_global`. This is the same gate as order submission, and it is *not* the read grant: `read_orders` lets you see an order, not cancel it. An order you may not act on returns `404`, identical to a missing one (no existence oracle).

#### Request Body

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `client_order_id` | `string` | Yes | UUID of the order to cancel |

#### Example Request

```json
{"client_order_id": "550e8400-e29b-41d4-a716-446655440000"}
```

#### Response: 200 OK

```json
{"status": "cancelled"}
```

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 403 | `{"error": "Forbidden"}` | Missing `delete_order` permission |
| 404 | `{"error": "order not found"}` | `client_order_id` not found, or the order's member is outside the caller's scope |
| 409 | `{"error": "order is not active (state: …)"}` | Order not in ACTIVE or HIBERNATED state |
| 409 | `{"error": "modify in progress, retry after confirmation"}` | Concurrent modify is in flight |
| 409 | `{"error": "exchange rejected the request: ..."}` | M7 rejected the cancel (e.g. the order was concurrently filled or deleted) |
| 504 | `{"error": "…"}` | M7 did not acknowledge within `system.order_ack_timeout_ms` (default 2s) |
| 500 | `{"error": "…"}` | Publish failed |

Cancelling an order is **not** gated by the trading kill-switch: a cancel only reduces exposure, so it stays available even when `trading_allowed` is `false`.

### `DELETE` `/api/v1/orders`

_Permission: delete_order_

Cancel all resting orders the caller is authorized to act on. Returns the count of orders targeted at the time the command was dispatched. No request body required.

**Member isolation.** A *full-authority* caller, one holding both `bypass_member_check` (any member) and `trade_global` (the house book), cancels the whole account in a single atomic exchange command. A member-scoped caller instead cancels only the orders whose member they may act on, one per order; other desks' orders, and (without `trade_global`) the house orders, are left untouched. `read_orders` does not grant cancellation. `deleted` reflects only the orders this caller targeted.

> [!CAUTION]
> For a full-authority caller this cancels all of the account's resting orders simultaneously. It is also triggered automatically when `PUT /trading_allowed` sets `enabled: false` (an operator/system action, full authority).

#### Response: 200 OK

```json
{"deleted": 3}
```

**Waits for the exchange to acknowledge the cancel** before responding (the atomic account-wide cancel is one request → one ack; a member-scoped cancel awaits each per-order ack). `deleted` is the count of active orders this caller targeted at dispatch time.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 403 | `{"error": "Forbidden"}` | Missing `delete_order` permission |
| 409 | `{"error": "exchange rejected the request: ..."}` | M7 rejected the cancel-all |
| 504 | `{"error": "…"}` | M7 did not acknowledge within `system.order_ack_timeout_ms` (default 2s) |
| 500 | `{"error": "…"}` | Publish failed |

Cancel-all is **not** gated by the trading kill-switch; it only reduces exposure, so it stays available even when `trading_allowed` is `false`.

### `GET` `/api/v1/order`

Look up a single order by `client_order_id`. Checks the pending store first; if not found there, checks the confirmed order store. Returns different shapes depending on which store the order is in.

**Scoping.** Member-isolated, like [GET /orders](#get-orders). An order tagged with a virtual member the caller may not see (or an untagged house order, for a caller without broad read) returns `404`, **identical** to a genuinely unknown `client_order_id`. The two are indistinguishable on purpose: the endpoint cannot be used as an existence oracle for other desks' orders. A caller holding `read_orders` (or `bypass_member_check`) can look up any order.

#### Query Parameters

| Param | Type | Required | Description |
| --- | --- | --- | --- |
| `client_order_id` | `string` | Yes | UUID of the order to retrieve |

#### Response: 200 OK (pending order)

```json
{
  "client_order_id": "550e8400-e29b-41d4-a716-446655440000",
  "contract_id": 100001,
  "delivery_area": "10YNL----------L",
  "side": "BUY",
  "price": 5000,
  "quantity": 1000,
  "entry_ts_ms": 1713600000000,
  "v_member_short_id": null
}
```

#### Response: 200 OK (confirmed OwnOrder)

```json
{
  "order_id": 987654321,
  "initial_order_id": 987654321,
  "parent_order_id": null,
  "revision": 1,
  "account_id": "ACC001",
  "contract_id": 100001,
  "delivery_area": "10YNL----------L",
  "side": "BUY",
  "price": 5000,
  "quantity": 1000,
  "initial_quantity": 1000,
  "hidden_quantity": null,
  "displayed_quantity": null,
  "order_type": "REGULAR",
  "state": "ACTIVE",
  "action": "AADD",
  "client_order_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_code": "TRADER1",
  "pre_arranged": false,
  "timestamp_ms": 1713600000000,
  "validity_time_ms": null,
  "last_update_time_ms": 1713600001000,
  "text": "",
  "basket_id": null,
  "v_member_short_id": "VM003"
}
```

**Note:** `v_member_short_id` (the virtual-member tag, `null` for the default member) is recovered from the M7 `Txt` field, so a confirmed order stays attributable to its member. `client_order_id` can be `null` on re-created orders. M7 does not always echo it back when a modify is executed as delete + re-create.

**Note:** `basket_id` is the M7 numeric basket id (`u64`), `null` for standalone orders. On gRPC the same value is `uint64` with `0` as the standalone sentinel.

**state values:** `PENDING` `ACTIVE` `INACTIVE` `HIBERNATED` `REJECTED` `UNKNOWN`

**order_type values:** `REGULAR` `BLOCK` `BALANCE` `ICEBERG` `STOP` `EXCHANGE_PRE_ARRANGED` `PRIVATE` `UNKNOWN`

**action values:** `UADD` `UHIB` `UMOD` `UDEL` `UREJ` `AADD` `AHIB` `AMOD` `ADEL` `AREJ` `SADD` `SHIB` `SMOD` `SDEL` `SREJ` `FEXE` `PEXE` `IADD` `SERR` `SNAV` `UNKNOWN`

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 404 | `{"error": "order not found"}` | `client_order_id` not in pending or confirmed store |

### `GET` `/api/v1/orders`

List the caller's confirmed resting orders. Optionally filter by delivery area, contract ID, or product/delivery_start. Returns an array of OwnOrder objects.

**Scoping.** The order book is member-isolated. A caller holding `read_orders` (or `bypass_member_check`, which implies it) receives the firm-wide order book: every member's orders plus the untagged house-account orders. Every other caller receives only the orders tagged with a virtual member assigned to them; untagged house orders are **withheld**. A caller with no assigned members and no broad-read permission receives an empty list.

#### Query Parameters

| Param | Type | Required | Description |
| --- | --- | --- | --- |
| `delivery_area` | `string` | No | Filter by delivery area EIC code |
| `contract_id` | `u64` | No | Filter by contract ID (requires `delivery_area`; without it the request is rejected with 400) |
| `product` | `string` | No | Filter by product code (requires `delivery_area`; without it the request is rejected with 400) |
| `delivery_start` | `string` | No | Filter by delivery start (used with `product`) |
| `v_member_short_id` | `string` | No | Narrow the list to a single virtual member (e.g. `VM001`). Rejected with `403` unless the caller is assigned to that member or holds `read_orders`/`bypass_member_check`. |

Filter priority: (`delivery_area` + `contract_id`) > (`delivery_area` + `product` [+ `delivery_start`]) > `delivery_area` alone (all orders in that area) > all orders.

#### Errors

| Status | Body | When |
| --- | --- | --- |
| `400` | `{"error": "contract_id requires delivery_area"}` | `contract_id` passed without `delivery_area` |
| `400` | `{"error": "product requires delivery_area"}` | `product` passed without `delivery_area` |
| `403` | `{"error": "Forbidden"}` | `v_member_short_id` names a member the caller is not assigned to and has no broad-read permission for |

#### Response: 200 OK

```json
[
  {
    "order_id": 987654321,
    "contract_id": 100001,
    "delivery_area": "10YNL----------L",
    "side": "BUY",
    "price": 5000,
    "quantity": 1000,
    "state": "ACTIVE",
    "client_order_id": "550e8400-e29b-41d4-a716-446655440000",
    ...
  }
]
```

Array of OwnOrder objects, same shape as the confirmed response from [GET /order](#get-order).

## Order Types Guide

Voltnir maps its order type and restriction enums to M7 protocol values. Understanding these is essential for building correct order submission logic.

### OrderType

Sent in the `order_type` field. Default: `"regular"`.

- **`regular`**: Standard lit order. No special conditions. M7 type: O.
- **`block`**: Block order: must be fully traded in a single transaction. M7 type: B.
- **`iceberg`**: Hidden quantity. Only `display_qty` is visible in the order book. Requires `display_qty` < `quantity`. M7 type: I.
- **`balance`**: Balance order for portfolio management. M7 type: L.
- **`pre_arranged`**: Pre-arranged trade with a known counterparty. Requires `pre_arranged_acct`. M7 type: E.

> [!NOTE]
> **In the order book, `order_type` is an integer, not these strings.** The values above are what you *send* when [creating an order](#post-order). When you *read* the public order book (the `buy`/`sell` arrays on [contracts](#get-contracts)), each resting order's `order_type` is an M7 order-book integer from a smaller, read-only set (mirrors DFS180 §6.4.3 `PblcOrdrBooksResp`):
>
> | int | Order-book type | = entry type |
> | --- | --- | --- |
> | `0` | unspecified / unknown | — |
> | `1` | regular limit order (default) | `regular` (M7 `O`) |
> | `2` | user-defined block order | `block` (M7 `B`) |
> | `3` | balance order | `balance` (M7 `L`) |
> | `4` | not provided by the Shared Order Book (XBID cross-border) | — |
>
> Iceberg and pre-arranged never appear in the book: an iceberg only exposes its `display_qty`, and pre-arranged trades aren't lit.

### ExeRestriction

Sent in the `exe_restriction` field. Default: `"non"`.

- **`non`**: No execution restriction. Default behaviour. M7: NON.
- **`fok`**: Fill-or-Kill: must execute completely and immediately or be cancelled. Requires `validity_res: "non"`. M7: FOK.
- **`ioc`**: Immediate-or-Cancel: execute available portion immediately, cancel remainder. Requires `validity_res: "non"`. M7: IOC.
- **`aon`**: All-or-None: order must be completely filled or not at all. M7: AON.

> [!NOTE]
> In the order book, `order_execution_restriction` is likewise an integer: `0` = unspecified · `1` = not restricted · `2` = AON. Only AON is reported per resting order; `fok`/`ioc` are entry-time immediacy conditions, so they never rest in the book.

### ValidityRestriction

Sent in the `validity_res` field. Default: `"gfs"`.

- **`gfs`**: Good-for-Session: valid until end of trading session. Default. M7: GFS.
- **`gtd`**: Good-till-Date: valid until a specific datetime. Requires `validity_date`. M7: GTD.
- **`non`**: No validity restriction (immediate). Mandatory for FOK and IOC execution restrictions. M7: NON.

### EntryState

Sent in the `entry_state` field at order creation. Default: `"active"`.

- **`active`**: Order enters the book immediately. Default. M7: ACTI.
- **`hibernated`**: Order is registered but not yet visible in the book. Activate later with `PUT /order` using `modify_action: "activate"`. M7: HIBE.

### Member-specific orders

Use the `v_member_short_id` field to tag an order against a virtual member (e.g. `"VM001"`). This short ID is written into the M7 `Txt` field. It does not change exchange routing; it provides attribution for audit and reporting.

> [!NOTE]
> If the user does not have the `bypass_member_check` permission, the `v_member_short_id` must be from the list of members assigned to that user (see [GET /users/me/members](#get-me-members)). An order submitted *without* a `v_member_short_id` trades on the global (house) account and requires the `trade_global` permission; a caller lacking it must submit the order under a member (400 otherwise), so the member's MW and cash limits bind and the order stays attributable.

## Contracts

Query the live order book and contract metadata for delivery areas accessible to your account. Contract data is sourced from the M7 order book stream and reflects real-time market state.

> [!NOTE]
> Contract IDs are assigned by M7. Use `GET /contract/{area_id}` to discover valid IDs. The `by-delivery` endpoint provides a convenient lookup by product code and delivery start time.

> [!NOTE]
> Contracts whose delivery period has ended are removed from all contract responses and from the WebSocket feed approximately 60 minutes after their `dlvry_end`. Trades on those contracts remain queryable via the audit and history endpoints.

### `GET` `/api/v1/contract/{area_id}`

List all contracts for a delivery area, sorted by delivery start. Includes full order book snapshots (buy/sell sides) for each contract.

#### Path Parameters

| Parameter | Type | Description |
| --- | --- | --- |
| `area_id` | `string` | EIC delivery area code (e.g. `10YNL----------L`) |

#### Response: 200 OK

```json
[
  {
    "contract_id": "100001",
    "area_id": "10YNL----------L",
    "prod": "H",
    "name": "Intraday_H1",
    "long_name": "Intraday Hour 1",
    "dlvry_start": "2026-04-20T22:00:00Z",
    "dlvry_end": "2026-04-20T23:00:00Z",
    "predefined": true,
    "revision_no": 42,
    "revision_ob": 7,
    "state": "ACTI",
    "trading_phase": "CONT",
    "trading_phase_start": "2026-04-19T22:00:00Z",
    "trading_phase_end": "2026-04-20T22:00:00Z",
    "duration": "1.0",
    "last_price": 5200,
    "last_quantity": 1000,
    "last_trade_time": "2026-04-20T10:15:00Z",
    "highest_price": 5500,
    "lowest_price": 4800,
    "price_direction": 1,
    "best_bid": 5100,
    "best_bid_qty": 500,
    "best_ask": 5300,
    "best_ask_qty": 1000,
    "buy": [ ... ],
    "sell": [ ... ]
  }
]
```

`price_direction`: `1` = up, `-1` = down, `0` = unchanged.

`predefined`: `true` for a standard exchange-created contract; `false` for a **user-defined block** contract (one generated by a user-defined block order, spanning multiple base contracts). The exchange **rejects a regular limit order on a user-defined block** (M7 error 1051, `"Can't enter OPEN order for user-defined blocks"`); only block orders are accepted there. A client should not offer regular order entry on a contract with `predefined: false`. `null` means the contract's metadata has not yet arrived (treat as not-yet-orderable, not as a block).

#### Order book entries (`buy` / `sell`)

Each element of the `buy` and `sell` arrays is one order resting in the public order book, sourced from the M7 v7 order-book stream (mirrors DFS180 §6.4.3 `PblcOrdrBooksResp`):

```json
{
  "order_id": 9876543210,
  "quantity": 500,
  "price": 5100,
  "order_entry_time": "2026-04-20T10:14:55Z",
  "order_execution_restriction": 1,
  "order_type": 1
}
```

`price` is in M7 integer units (divide by the contract's price factor for display). `order_type` and `order_execution_restriction` are **integer enums**; see the [Order Types Guide](#order-types) for the full key. (The order book uses a distinct, read-only integer set, not the `POST /order` strings.) `order_entry_time` is `null` when the feed omits it; on gRPC the same absence is the `""` sentinel (proto3 has no nullable strings).

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 404 | `{"error": "area not found"}` | `area_id` not found in the order book |

### `GET` `/api/v1/contract/{area_id}/{contract_id}`

Get a single contract with its full order book, plus the account's own acknowledged and pending orders, trades, and net position for this contract and area. Unlike [GET /orders](#get-orders), the order/trade lists here are **account-wide**; they are not filtered by the caller's virtual-member assignments.

#### Path Parameters

| Parameter | Type | Description |
| --- | --- | --- |
| `area_id` | `string` | EIC delivery area code |
| `contract_id` | `i64` | M7 contract ID |

#### Response: 200 OK

```json
{
  "contract": {
    "contract_id": "100001",
    "area_id": "10YNL----------L",
    "prod": "H",
    "dlvry_start": "2026-04-20T22:00:00Z",
    "dlvry_end": "2026-04-20T23:00:00Z",
    "state": "ACTI",
    "best_bid": 5100,
    "best_ask": 5300,
    "buy": [ ... ],
    "sell": [ ... ]
  },
  "orders_acknowledged": [
    {
      "order_id": 987654321,
      "side": "BUY",
      "price": 5000,
      "quantity": 1000,
      "state": "ACTIVE",
      "client_order_id": "550e8400-e29b-41d4-a716-446655440000",
      "v_member_short_id": "VM003"
    }
  ],
  "orders_pending": [
    {
      "client_order_id": "9f1c2d34-5e6f-47a8-b9c0-1d2e3f4a5b6c",
      "contract_id": 100001,
      "delivery_area": "10YNL----------L",
      "side": "SELL",
      "price": 5400,
      "quantity": 500,
      "entry_ts_ms": 1713600002000,
      "v_member_short_id": null
    }
  ],
  "trades": [ ... ],
  "net_pos": 1000
}
```

**orders_acknowledged vs orders_pending.** `orders_acknowledged` holds orders **M7 has acknowledged**: each has an `order_id` and an order `state` (`ACTIVE`, `HIBERNATED`, `INACTIVE`, `REJECTED`). Both lists carry `v_member_short_id` (the virtual-member tag; `null` for the default member). On an acknowledged order it is recovered from the M7 `Txt` field, so an order stays attributable to its member across the submit→ack transition. `orders_pending` holds orders the gateway has **submitted but M7 has not yet acknowledged**; they have **no** `order_id` and **no** `state` field (their state is implicitly pending), and the same order shape as the pending form of [`GET /api/v1/order`](#get-order). A pending order is **never** present in `orders_acknowledged`; it moves there only once M7 acks it. To decide whether you already have an order working on this contract (and avoid re-submitting during the submit→ack window), check **both** lists. The same split is exposed on the WebSocket `orders` stream as `orders_acknowledged` + `orders_pending`, and on gRPC as `ContractDetail.orders_acknowledged` + `orders_pending`.

`net_pos` is in sub-MW (divide by 1000 for MW). Positive = net long, negative = net short. It reflects **executed (ACTI) trades only**: open and pending orders do **not** count toward it. (The order-placement position-limit check separately combines open orders + trades to bound exposure; that combined value is not exposed here; derive it client-side from `orders_acknowledged` + `orders_pending` + `trades` if needed.)

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 404 | `{"error": "contract not found"}` | No contract with this ID in this area |

### `GET` `/api/v1/contract/{area_id}/by-delivery/{prod}/{dlvry_start}`

Look up a contract by product code and delivery start time rather than by numeric contract ID. Returns the same combined response as `GET /contract/{area_id}/{contract_id}`.

#### Path Parameters

| Parameter | Type | Description |
| --- | --- | --- |
| `area_id` | `string` | EIC delivery area code |
| `prod` | `string` | Product code (e.g. `H` for hourly, `QH` for quarter-hour) |
| `dlvry_start` | `string` | URL-encoded ISO 8601 datetime (e.g. `2026-04-20T22%3A00%3A00Z`) |

#### Example Request

```
GET /api/v1/contract/10YNL----------L/by-delivery/H/2026-04-20T22%3A00%3A00Z
```

#### Response: 200 OK

Same shape as [GET /contract/{area_id}/{contract_id}](#get-contract).

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 404 | `{"error": "contract not found"}` | No contract matching product + delivery start in this area |

## Hub-to-Hub

Query cross-area capacity data between delivery hubs. This feature must be enabled in the server configuration. If disabled, the endpoint returns an empty result without error.

> [!NOTE]
> Hub-to-Hub data is only available if `epex_settings.enable_hub_2_hub = true` on the server. The response carries `enabled` (the config flag; when `false`, `data` is always empty) and `capacity_connected` (the upstream capacity-feed heartbeat) alongside `data`, mirroring the gRPC `GetHub2HubResponse` flags.

### `GET` `/api/v1/hub2hub`

Query cross-area hub-to-hub capacity for a delivery time range between two areas.

#### Query Parameters

| Param | Type | Required | Description |
| --- | --- | --- | --- |
| `delivery_area_from` | `string` | Yes | Source delivery area EIC code |
| `delivery_area_to` | `string` | No | Target delivery area EIC code (optional filter) |
| `delivery_from` | `string` | Yes | RFC 3339 datetime: start of delivery window |
| `delivery_to` | `string` | Yes | RFC 3339 datetime: end of delivery window |

#### Example Request

```
GET /api/v1/hub2hub?delivery_area_from=10YNL----------L&delivery_area_to=10YDE-VE-------2&delivery_from=2026-04-20T22%3A00%3A00Z&delivery_to=2026-04-20T23%3A00%3A00Z
```

#### Response: 200 OK

```json
{
  "enabled": true,
  "capacity_connected": true,
  "data": [
    {
      "revision_no": 42,
      "dlvry_start": "2026-04-20T22:00:00Z",
      "dlvry_end":   "2026-04-20T22:15:00Z",
      "timestmp":    "2026-04-20T21:54:30Z",
      "hub_from":    "10YDE-VE-------2",
      "connections": [
        {
          "to":              "10YNL----------L",
          "atc_in":          800,
          "atc_out":         400,
          "source_best_bid": 9450,
          "source_best_ask": 9510,
          "dest_best_bid":   9975,
          "dest_best_ask":   10025
        }
      ]
    }
  ]
}
```

#### Connection Fields

| Field | Type | Description |
| --- | --- | --- |
| `to` | `string` | Destination delivery area EIC code. |
| `atc_in` | `integer (sub-MW)` | ATC into `hub_from` from `to`. Raw signed M7 value in **sub-MW (MW × 1000)**; divide by 1000 for MW, the same scale as order/trade quantity. May be negative (M7 publishes negative ATC during congestion). *The M7 XSD does not formally annotate the ATC unit, but the feed encodes it in sub-MW like every other M7 power quantity, confirmed against the live feed.* |
| `atc_out` | `integer (sub-MW)` | ATC out of `hub_from` toward `to`. Raw signed M7 value in sub-MW (MW × 1000); divide by 1000 for MW. May be negative. |
| `source_best_bid` | `integer (CCY/MWh × 100)`, optional | Best resting bid in `hub_from` for the contract whose delivery window matches this entry. Omitted when no resting quote is available. |
| `source_best_ask` | `integer (CCY/MWh × 100)`, optional | Best resting ask in `hub_from`. Omitted when no resting quote is available. |
| `dest_best_bid` | `integer (CCY/MWh × 100)`, optional | Best resting bid in `to`. Omitted when no resting quote is available. |
| `dest_best_ask` | `integer (CCY/MWh × 100)`, optional | Best resting ask in `to`. Omitted when no resting quote is available. |

The four `*_best_bid`/`*_best_ask` fields are populated by joining the hub-to-hub feed with the live order-book best-quote state at frame-emit time. They let clients derive a per-border *implicit-spread* (e.g. `dest_best_bid − source_best_ask` for an export-direction order) without taking a separate `contracts` subscription per visible border. A value of `0` in the order book is treated as "no quote" and translated to a missing field on the wire (negative power prices are legitimate, so 0 cannot double as the absent sentinel).

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "invalid delivery_from: …"}` | `delivery_from` is not valid RFC 3339 |
| 400 | `{"error": "invalid delivery_to: …"}` | `delivery_to` is not valid RFC 3339 |

Note: the server does not validate that `delivery_from` is before `delivery_to`.

## System

Inspect system health, connection status, throttling counters, and trading controls. Several endpoints require elevated permissions.

> [!WARNING]
> **PUT /trading_allowed with `enabled: false` immediately cancels all resting orders and halts new order traffic.** Use this endpoint as a kill-switch only. It triggers a DeleteAllOrders command to M7 with no confirmation prompt, and while disabled new orders (`POST /order`) and modifies (`PUT /order`) are rejected with `422` before reaching M7. Cancels (`DELETE /order` and `DELETE /orders`) remain available: pulling an order only reduces exposure.

### `GET` `/api/v1/state`

_Permission: read_state_

Returns the full system state: connectivity health, AMQP session, WebSocket stream status, latency statistics, and an `operational` flag. The `v7_token` field is redacted from the response. Gated by `read_state` (returns `403 Forbidden` without it). (Parity note: the gRPC `GetState` RPC returns the same shape with one documented divergence: it omits the `amqp_authenticated_with` block entirely. The trading-posture aggregate (`trading_enabled`, `order_pos_limit`, throttling, cash limits, and license) lives on the separate [`GET /status`](#get-status) surface, not here.)

#### Response: 200 OK

```json
{
  "uptime": "2h 34m 12s",
  "operational": true,
  "issues": [],
  "amqp_connected": true,
  "amqp_authenticated_with": {
    "session_id": 12345,
    "user_id": 67890,
    "user_code": "TRADER1",
    "default_acct_id": "ACC001",
    "state": "ACTI",
    "mbr_id": "MBR001"
  },
  "amqp_private_consumer_healthy": true,
  "amqp_broadcast_consumer_healthy": true,
  "amqp_publisher_healthy": true,
  "amqp_publisher_tx_capacity": 100,
  "amqp_market_active": true,
  "ws_order_book_stream_connected": true,
  "ws_order_book_sequence_healthy": true,
  "ws_order_book_synchronized": true,
  "ws_order_book_pong": 1713600000000,
  "ws_order_book_delta": 15423,
  "ws_order_book_delta_per_hour": 8200,
  "ws_order_book_avg_processing_time": "45µs",
  "ws_order_book_avg_latency": "12ms",
  "ws_private_data_stream_connected": true,
  "ws_private_data_sequence_healthy": true,
  "ws_private_data_synchronized": true,
  "ws_private_data_pong": 1713600000000,
  "ws_private_data_delta_per_hour": 120,
  "ws_private_data_avg_processing_time": "22µs",
  "ws_private_data_avg_latency": "8ms",
  "license": {
    "status": { "kind": "active" },
    "license_id": "019e243d-5db9-7ea6-8965-918fdca9c47b",
    "mode": "desk",
    "environment": "prod",
    "issued_at": "2026-05-14T02:07:42Z",
    "expires_at": "2027-05-14T02:07:42Z",
    "schema_version": 2,
    "issuer": "voltnir",
    "signing_key_id": "voltnir-2026-q2",
    "holder": {
      "legal_entity": "ACME Energy B.V.",
      "portal_user_id": "019e2440-7c11-7a3e-bb02-2f8c1d4e9a55"
    },
    "epex_any": false,
    "epex_identities": [
      { "account_id": "ACME_DE", "user_id": "trader01" }
    ]
  }
}
```

`operational` = `true` only when all of the following are healthy: `amqp_broadcast_consumer_healthy`, `amqp_private_consumer_healthy`, `amqp_publisher_healthy`, `ws_order_book_synchronized`, `ws_order_book_stream_connected`, `ws_order_book_sequence_healthy`, and the exchange is active.

`license` reports the full installed license. `status.kind` is one of `active`, `expiring_soon`, `expired`, or `in_grace`; for every kind except `active` a `days` field is present (days remaining, or days elapsed since expiry). `mode` is the capability tier: `trader` (terminal + REST V1 + WS) or `desk` (adds gRPC and user/member/permission management). `issued_at`/`expires_at` are the RFC 3339 validity window. `schema_version`, `issuer`, and `signing_key_id` are the provenance of the signed file. `holder` is the entity the license is issued to (`legal_entity` + `portal_user_id`); it is `null` for a free `sim` license. `epex_any` is `true` when the license authorizes any EPEX identity (sim); otherwise `epex_identities` lists the permitted `account_id`/`user_id` pairs. License expiry is informational only; it never disables an endpoint or drops a connection. Under a `trader` license the desk-only management endpoints (`/users`, `/members`, permission assignment) return `403` with `{"error": "LICENSE_DESK_REQUIRED"}`.

`issues` lists human-readable strings describing each failing condition when `operational` is `false`.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 403 | `{"error": "Forbidden"}` | Missing `read_state` permission |

### `GET` `/api/v1/status`

_Permission: read_status_

Returns the trading-posture aggregate in one call: M7 throttling counters, the trading kill-switch and operational flags, the M7-reported cash/margin limits, the per-contract position limit, the Voltnir order cash limit (configured / consumed / remaining per currency pool), and the installed license. This is the same flat shape broadcast on the WebSocket `status` stream and returned by the gRPC `GetStatus` RPC. Gated by `read_status` (returns `403 Forbidden` without it).

#### Response: 200 OK

```json
{
  "throttling": { ... },
  "trading_enabled": true,
  "operational": true,
  "cash_limits": {
    "EUR": {
      "currency": "EUR",
      "current_limit": 1234500,
      "current_revision": 5,
      "configured_limit": 5000000,
      "dec_shft": 2,
      "lmt_id": "L1",
      "state": "ACTIVE",
      "start_date": "2026-01-01",
      "revision_no": 7
    }
  },
  "order_pos_limit": 50000,
  "cash_limit": {
    "eur_limit_cents": 10000000,
    "eur_consumed_cents": 3500000,
    "eur_remaining_cents": 6500000,
    "gbp_limit_cents": 0,
    "gbp_consumed_cents": 0,
    "gbp_remaining_cents": 0
  },
  "license": { ... }
}
```

`throttling` is the same object as [`GET /throttling`](#get-throttling); `cash_limits` the same map as [`GET /cash_limits`](#get-cash-limits) (the M7 margin feed, keyed by ISO currency); `license` the same projection as the [`GET /state`](#get-state) `license` block. `trading_enabled` mirrors [`GET /trading_allowed`](#get-trading-allowed) and `order_pos_limit` (sub-MW) mirrors [`GET /contract_limit`](#get-contract-limit).

`cash_limit` is the **Voltnir order cash limit**: configured limit, current consumption, and remaining headroom per currency pool, all in **cents** (`i64`; `remaining = limit − consumed`; an `*_limit_cents` of `0` means that pool is not enforced). Distinct from `cash_limits`, the M7-reported margin feed. The configured limits alone are queryable / settable one-shot via [`GET`](#get-cash-limit) / [`PUT /cash_limit`](#put-cash-limit); this aggregate additionally reports live consumption and remaining.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 403 | `{"error": "Forbidden"}` | Missing `read_status` permission |

### `GET` `/api/v1/throttling`

Returns the current M7 throttling status for the connected member, including short-term and long-term order message counts and limits. All fields may be null if no throttling status has been received from M7 yet.

#### Response: 200 OK

```json
{
  "mbr_id": "MBR001",
  "timestamp": "2026-04-20T10:00:00Z",
  "status": "OK",
  "short_observation_period": 100,
  "short_tolerance_period": 10,
  "short_reconnection_cool_down": 30,
  "short_omt_limit_l1": 50,
  "short_omt_limit_l2": 100,
  "short_status": "OK",
  "short_current_omt_count": 3,
  "long_observation_period": 3600,
  "long_tolerance_period": 60,
  "long_reconnection_cool_down": 300,
  "long_omt_limit_l1": 500,
  "long_omt_limit_l2": 1000,
  "long_status": "OK",
  "long_current_omt_count": 42
}
```

### `GET` `/api/v1/system_info`

Returns the M7 system-information snapshot captured when the gateway authenticates: backend version, server time zones, data-retention windows, the per-session order cap, the enabled capabilities, and the per-message-type request rate limits. Every M7-sourced scalar is null and `request_limits` is empty until the first `SystemInfoResp` arrives from M7. `voltnir_version` is the one exception: it is this gateway's own software version (from its build), always present and never null. No permission required.

#### Response: 200 OK

```json
{
  "market_id": "EPEX",
  "voltnir_version": "1.0.0",
  "backend_version": "7.21.3",
  "backend_time_zone": "CET",
  "backend_market_time_zone": "CET",
  "contract_store_time_in_days": 30,
  "trade_pool_store_time_in_hours": 168,
  "max_orders": 1000,
  "capabilities": "BLOCK,ICEBERG",
  "allowed_clearing_acct_types": "A,P",
  "request_limits": [
    { "message": "OrdrEntryReq", "duration_ms": 1000, "rate": 50 },
    { "message": "QuoteEntryReq", "duration_ms": 1000, "rate": 100 }
  ]
}
```

### `GET` `/api/v1/cash_limits`

Returns the latest cash/margin limits reported by the M7 exchange, keyed by ISO currency code. Populated from `CashLmtRprt` snapshots and updated incrementally by `CashLmtDeltaRprt` deltas. The same data is broadcast on the WebSocket status frame.

**Decimal-shift convention.** Raw integer fields are paired with `dec_shft`: human-readable amount = raw / 10dec_shft. Example: `current_limit = 1234500`, `dec_shft = 2` → 12,345.00 EUR.

#### Response: 200 OK

```json
{
  "limits": {
    "EUR": {
      "currency": "EUR",
      "current_limit": 1234500,
      "current_revision": 5,
      "configured_limit": 5000000,
      "dec_shft": 2,
      "lmt_id": "L1",
      "state": "ACTIVE",
      "start_date": "2026-01-01",
      "revision_no": 7
    }
  }
}
```

Every field past `currency` is nullable; partial M7 reports leave fields unset until both the snapshot and detail records have arrived. The map is empty (`{}`) until the first `CashLmtRprt` is received.

### `GET` `/api/v1/permissions`

Returns the catalog of assignable permissions: every permission `code` that can be granted to a user (via `PUT /users/{id}/permissions`) paired with a human-readable `description`. Clients should render this list rather than hardcoding their own copy, so a new permission appears in the UI automatically. The list is server-defined and stable within an API version. Requires the `manage_users` permission (the same permission that gates assigning them); without it the call returns `403 Forbidden`.

#### Response: 200 OK

```json
{
  "permissions": [
    { "code": "create_order", "description": "Submit new orders to the exchange." },
    { "code": "modify_order", "description": "Change the price or quantity of an existing open order." },
    { "code": "set_cash_limit", "description": "Set the House (global) cash limit and the fail-closed switch." }
  ]
}
```

`permissions` is always an array (never null), ordered canonically. The example is truncated; the live response lists every assignable permission.

### `GET` `/api/v1/pnl`

Recompute and return the caller-scoped PnL snapshot from the current trade store and order book. Stateless: every call walks the trade history through a weighted-average-cost state machine. The same shape is broadcast on the WebSocket `pnl` stream; prefer the WebSocket for live polling.

**Scoping.** P&L is member-isolated. A caller holding `read_pnl` (or `bypass_member_check`, which implies it) receives the firm-wide snapshot: every member's legs in `per_vm`/`per_vm_area_prod` plus the house-account `per_contract`/`per_area_prod` rollups. Every other caller receives only the `per_vm`/`per_vm_area_prod` rows for the virtual members assigned to them; the firm-wide `per_contract`/`per_area_prod` rollups are returned **empty** (they aggregate other desks and the house account). A caller with no assigned members and no broad-read permission receives an all-empty snapshot.

#### Query Parameters

| Param | Type | Required | Description |
| --- | --- | --- | --- |
| `v_member_short_id` | `string` | No | Narrow the snapshot to a single virtual member (e.g. `VM001`). Returns only that member's `per_vm`/`per_vm_area_prod` rows; `per_contract`/`per_area_prod` are empty. Rejected with `403` unless the caller is assigned to that member or holds `read_pnl`/`bypass_member_check`. |

**Units.** Money values are in q8 units = M7-px (EUR/MWh × 100) × sub-MW (MWh × 1000) = **EUR × 100,000**. Divide by 100,000 to render EUR. Position values are sub-MW (positive = long).

#### Response: 200 OK

```json
{
  "per_contract": [
    {
      "area_id": "10YNL----------L",
      "contract_id": 100001,
      "product": "H",
      "signed_position": 1000,
      "avg_open_px": 5000,
      "mark_px": 5200,
      "mark_source": "Mid",
      "realized_pnl": 0,
      "unrealized_pnl": 200000
    }
  ],
  "per_area_prod": [
    {
      "area_id": "10YNL----------L",
      "product": "H",
      "realized_pnl": 0,
      "unrealized_pnl": 200000
    }
  ],
  "per_vm": [],
  "per_vm_area_prod": [],
  "computed_at_ms": 1713600000000,
  "compute_us": 142
}
```

`mark_source` values: `"Mid"` (best_bid+best_ask)/2, `"Last"` last trade price, or `"None"` when no mark is available (uPnL = 0). Open / pending orders do *not* contribute; only filled `ACTI` trades count.

### `GET` `/api/v1/public_trades`

Returns up to `limit` most-recent public trades from the market-wide trade tape (`PblcTradeConfRprt`), oldest first. Sliding-window store: entries older than the configured retention window are trimmed. The same data is broadcast on the WebSocket `public_trades` stream.

#### Query Parameters

| Param | Type | Required | Description |
| --- | --- | --- | --- |
| `limit` | `usize` | No | Default 100; hard-capped at 1000. Must be > 0. |
| `contract_id` | `u64` | No | Filter to one M7 contract id. |
| `area_id` | `string` | No | Filter by EIC delivery area; matches when either the buy- or sell-side area equals this value. Max 64 chars. |

#### Response: 200 OK

```json
{
  "trades": [
    {
      "trade_id": "T-987654321",
      "contract_id": 100001,
      "qty": 1000,
      "px": 5200,
      "exec_time": "2026-04-21T10:15:00Z",
      "exec_time_ms": 1713693300000,
      "revision_no": 1,
      "state": "ACTI",
      "buy_dlvry_area": "10YNL----------L",
      "sell_dlvry_area": null,
      "self_trade": false
    }
  ]
}
```

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "limit must be greater than zero"}` | `limit=0` |
| 400 | `{"error": "area_id exceeds maximum length"}` | `area_id` > 64 chars |

### `GET` `/api/v1/contract_limit`

Returns the current per-contract position limit in sub-MW. Orders that would push the net position beyond this limit are rejected with a 422.

#### Response: 200 OK

```json
{"limit": 5000}
```

`limit` is in sub-MW. Example: `5000` = 5.0 MW maximum net position per contract.

### `PUT` `/api/v1/contract_limit`

_Permission: set_position_limit_

Update the per-contract position limit. Takes effect immediately for all subsequent order submissions. Must be non-negative. **`0` is fully supported and blocks all new position-taking**: every order that would move |net position| above the limit is rejected, so `0` is the operator kill-switch clients use as a safeguard. `0` does *not* disable the check.

#### Request Body

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `limit` | `i32` | Yes | New limit in sub-MW. Must be ≥ 0; `0` blocks all new position-taking (kill-switch). |

#### Example Request

```json
{"limit": 5000}
```

#### Response: 200 OK

```json
{"limit": 5000}
```

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "limit must be non-negative"}` | `limit` < 0 |
| 403 | `{"error": "Forbidden"}` | Missing `set_position_limit` permission |

### `GET` `/api/v1/cash_limit`

Returns the **global** (overarching-member) cash limit for both currency pools (EUR + GBP, independent). The cash limit caps the monetary value of *executed trades + open orders* (the same set the MW limit uses): an order is rejected with a 422 if its value would push consumed cash above its pool's limit. Distinct from [GET /cash_limits](#get-cash-limits) (plural), which reports the M7-supplied per-currency feed and is read-only.

#### Response: 200 OK

```json
{"cents": 10000000, "gbp_cents": 0}
```

`cents` = EUR pool, `gbp_cents` = GBP pool, both in cents (`10000000` = 100,000). `0` = that pool is not enforced. EUR and GBP are independent pools (ECC settles them separately); an order is checked only against its own currency's limit.

### `PUT` `/api/v1/cash_limit`

_Permission: set_cash_limit_

Update a global cash pool. Takes effect immediately. Must be non-negative and is expressed in cents of the target currency. `0` disables that pool's check. Every per-member cash limit is capped at the global value; a member limit can never exceed the overarching member's. EUR orders net (a resting sell credits available cash); GBP delivery areas use ECC's methodology (sell receipts ignored plus a fixed per-MWh reservation, configured server-side). EUR and GBP are independent pools; the `currency` field selects which one to set.

#### Request Body

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `cents` | `i64` | Yes | New cash limit in cents of the target currency. Must be ≥ 0; `0` disables that pool. |
| `currency` | `string` | No | `"eur"` (default) or `"gbp"`. Unknown values return 400. |

#### Example Request

```json
{"cents": 10000000, "currency": "eur"}
```

#### Response: 200 OK

```json
{"cents": 10000000, "currency": "eur"}
```

`currency` echoes the request's `currency` field verbatim; it is an empty string when the request omitted it (the EUR default still applies).

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "cents must be non-negative"}` | `cents` < 0 |
| 400 | `{"error": "unknown currency '…' (expected eur or gbp)"}` | `currency` is not `eur`, `gbp`, or omitted |
| 403 | `{"error": "Forbidden"}` | Missing `set_cash_limit` permission |

### `GET` `/api/v1/cash_fail_closed`

Returns the cash-limit **fail-closed** switch. When `true` (the default, ECC parity §3.11/§3.12) a `0`/unset cash limit means **no trading** in that pool ("set nothing = safe"). When `false` (Voltnir's historical fail-open opt-out) a `0` cash limit means *disabled*, that pool unbounded. Seeded at first boot from `cash_limit.fail_closed` in `config.yml` (an existing profile row wins on later boots); runtime-mutable thereafter.

#### Response: 200 OK

```json
{"enabled": false}
```

### `PUT` `/api/v1/cash_fail_closed`

_Permission: set_cash_limit_

Set the cash-limit fail-closed switch. Takes effect immediately for all subsequent order submissions and is persisted to the profile. Gated by `set_cash_limit` (the switch is part of the cash-limit control).

> [!WARNING]
> Enabling fail-closed makes a `0`/unset cash limit reject *all* orders adding exposure in that pool. A money-making sell (zero exposure) on an empty pool still fits: the limit caps cash *at risk*, not order count.

#### Request Body

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `enabled` | `bool` | Yes | `true` for ECC fail-closed (0 limit = no trading); `false` for disabled-on-zero (the pool is unbounded at a 0 limit) |

#### Example Request

```json
{"enabled": true}
```

#### Response: 200 OK

```json
{"enabled": true}
```

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 403 | `{"error": "Forbidden"}` | Missing `set_cash_limit` permission |

### `GET` `/api/v1/holidays`

Returns the ECC **bank-holiday calendars** used by the cash-limit exposure window, one list per settlement currency. The cash limit re-bases exposure at **16:00 (ECC timezone) each working day**; configured holidays extend the window across public holidays (a Monday holiday rolls the Friday window to Tuesday). **EUR and GBP keep independent calendars**: GB bank holidays close CHAPS, so the GBP window observes a different set than the EUR (ECC/TARGET2) window. Both pools share the same 16:00 reset; only the dates differ. Holidays are runtime-managed (no `config.yml` edit, no restart): a change is held in memory, persisted to the database, and reloaded on startup. Each entry carries an optional display `label` (ignored by the window math).

#### Response: 200 OK

```json
{
  "eur": [
    {"date": "2026-12-25", "label": "Christmas Day"},
    {"date": "2026-12-26", "label": null}
  ],
  "gbp": [
    {"date": "2026-08-31", "label": "Summer Bank Holiday"}
  ]
}
```

### `PUT` `/api/v1/holidays`

_Permission: set_cash_limit_

Replaces one currency's whole calendar with the supplied list. Takes effect immediately on the next cash check and is persisted. Gated by `set_cash_limit` (holidays are part of the cash-limit methodology). Returns both calendars after the change.

#### Request Body

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `currency` | `string` | Yes | `"eur"` or `"gbp"` (case-insensitive) |
| `holidays` | `array` | No | Full replacement list of `{"date": "YYYY-MM-DD", "label": "…"?}`. Order is irrelevant (stored sorted). Omit or pass `[]` to clear the currency's calendar. |

#### Example Request

```json
{"currency": "gbp", "holidays": [
  {"date": "2026-08-31", "label": "Summer Bank Holiday"},
  {"date": "2026-12-25"}
]}
```

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "…"}` | Unknown currency, a malformed `YYYY-MM-DD` date, or a duplicate date in the list |
| 403 | `{"error": "Forbidden"}` | Missing `set_cash_limit` permission |

### `POST` `/api/v1/holidays`

_Permission: set_cash_limit_

Adds a single date to a currency's calendar. Returns both calendars after the change.

#### Request Body

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `currency` | `string` | Yes | `"eur"` or `"gbp"` |
| `date` | `string` | Yes | `YYYY-MM-DD` |
| `label` | `string` | No | Optional display label |

#### Example Request

```json
{"currency": "eur", "date": "2026-01-01", "label": "New Year's Day"}
```

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "…"}` | Unknown currency, malformed date, or the date is already configured |
| 403 | `{"error": "Forbidden"}` | Missing `set_cash_limit` permission |

### `DELETE` `/api/v1/holidays`

_Permission: set_cash_limit_

Removes a single date from a currency's calendar. Returns both calendars after the change.

#### Request Body

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `currency` | `string` | Yes | `"eur"` or `"gbp"` |
| `date` | `string` | Yes | `YYYY-MM-DD` |

#### Example Request

```json
{"currency": "eur", "date": "2026-01-01"}
```

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "…"}` | Unknown currency or malformed date |
| 403 | `{"error": "Forbidden"}` | Missing `set_cash_limit` permission |
| 404 | `{"error": "…"}` | The date is not configured for that currency |

### `GET` `/api/v1/trading_allowed`

Returns whether order submission is currently enabled. When disabled, all order creation and modification attempts will be rejected before reaching the exchange.

#### Response: 200 OK

```json
{"enabled": true}
```

### `PUT` `/api/v1/trading_allowed`

_Permission: toggle_trading_

Enable or disable order submission. Setting `enabled: false` immediately cancels all resting orders via a DeleteAllOrders command to M7.

> [!WARNING]
> Setting `enabled: false` is a kill-switch operation. All resting orders are cancelled on the exchange immediately. This cannot be undone; you must re-submit orders after re-enabling trading.

#### Request Body

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `enabled` | `bool` | Yes | `true` to allow trading, `false` to halt and cancel all orders |

#### Example Request

```json
{"enabled": false}
```

#### Response: 200 OK

```json
{"enabled": false}
```

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 403 | `{"error": "Forbidden"}` | Missing `toggle_trading` permission |
| 409 | `{"error": "trading is force-disabled by config (system.disable_trading)…"}` | The `system.disable_trading` debug flag is set, which overrides the runtime toggle; trading cannot be changed at runtime |

### `GET` `/api/v1/self_trade_policy`

Returns the active self-trade (cross-trade) prevention policy. EPEX M7 does not prevent self-trades server-side; this is a Voltnir-side pre-trade check that looks for one of your own resting orders on the opposite side at a crossing price.

#### Response: 200 OK

```json
{"policy": "observe"}
```

`policy` is `observe` (detect + log, allow the order through) or `reject` (block the self-crossing order before it reaches M7).

### `PUT` `/api/v1/self_trade_policy`

_Permission: set_self_trade_policy_

Set the self-trade prevention policy. Takes effect immediately for all subsequent order submissions and is persisted. The `config.yml` `self_trade.policy` only seeds the default on a fresh database; this endpoint is the live control.

#### Request Body

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `policy` | `string` | Yes | `observe` or `reject`. |

#### Example Request

```json
{"policy": "reject"}
```

#### Response: 200 OK

```json
{"policy": "reject"}
```

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "policy must be 'observe' or 'reject'"}` | Unknown `policy` value |
| 403 | `{"error": "Forbidden"}` | Missing `set_self_trade_policy` permission |

When `policy` is `reject`, an order that would cross one of your own resting orders is rejected at `POST /api/v1/order` with 422 and `{"error": "SELF_CROSS_BLOCKED: ..."}`.

### `POST` `/api/v1/restart`

_Permission: restart_system_

Initiate a graceful shutdown. The process signals all internal tasks to stop, then exits. The host supervisor (systemd, Docker, etc.) is expected to restart it automatically.

> [!CAUTION]
> This endpoint terminates the Voltnir process. Ensure your deployment has a process supervisor configured to restart it. No request body is required.

#### Response: 202 Accepted

```json
{"status": "restart initiated"}
```

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 403 | `{"error": "Forbidden"}` | Missing `restart_system` permission |

## Users & Members

Manage Voltnir API credentials (users) and virtual trading members. Users hold API keys and permission sets. Members are virtual M7 sub-accounts used to tag orders for attribution.

> [!NOTE]
> **Users** are Voltnir API credentials: each has an API key, permissions, and optional member assignments.
>  **Members** are virtual M7 trading members (short IDs like `VM001`) used to tag orders in the M7 `Txt` field for sub-account attribution. Members are global; they are assigned to users to control which members that user may trade under.

> [!CAUTION]
> **Desk license required for management routes.** The user/member management surface (`/users` (list/create/delete), `/users/{id}/permissions`, `/users/{user_id}/members`, `/members`, and `/members/{id}`) requires a `desk`-tier license. Under a `trader` license these routes return 403 with `{"error": "LICENSE_DESK_REQUIRED"}` regardless of the caller's permissions. `GET /users/me`, `GET /users/me/members`, `GET /permissions`, and `POST /users/{id}/rotate-api-key` are *not* desk-gated (rotation is self-only on the trader tier).

### `GET` `/api/v1/users/me`

Returns the calling user's own profile: ID, username, short ID, and current permission set.

#### Response: 200 OK

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "username": "trader1",
  "short_id": "U002",
  "permissions": ["create_order", "delete_order"]
}
```

### `GET` `/api/v1/users/me/members`

Returns the list of virtual members assigned to the calling user. These are the only member short IDs the user may set on orders (unless they have `bypass_member_check`).

#### Response: 200 OK

```json
[
  {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "short_id": "VM001",
    "name": "Desk A",
    "max_position": 5000,
    "cash_limit": 10000000,
    "cash_limit_gbp": 0,
    "active": true,
    "eur_consumed_cents": 3500000,
    "eur_limit_cents": 10000000,
    "eur_remaining_cents": 6500000,
    "gbp_consumed_cents": 0,
    "gbp_limit_cents": 0,
    "gbp_remaining_cents": 0
  }
]
```

Member objects here carry the same shape as [GET /members](#get-members), including the live cash-usage fields (`*_consumed_cents` / `*_limit_cents` / `*_remaining_cents`). See that endpoint for the field semantics.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 503 | `{"error": "database not available"}` | Database not initialised |
| 500 | `{"error": "…"}` | Database query failed |

### `GET` `/api/v1/users`

_Permission: manage_users_

List all users in the system with their IDs, usernames, short IDs, and permission sets.

#### Response: 200 OK

```json
[
  {"id": "uuid1", "username": "admin", "short_id": "U001", "permissions": ["manage_users", "create_order"]},
  {"id": "uuid2", "username": "trader1", "short_id": "U002", "permissions": ["create_order", "delete_order"]}
]
```

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 403 | `{"error": "Forbidden"}` | Missing `manage_users` permission |

### `POST` `/api/v1/users`

_Permission: manage_users_

Create a new user. Returns the new user object including the raw API key. **The API key is shown only once**. Store it securely immediately. An optional `permissions` array grants permissions in the same call (same strings as [PUT /users/{id}/permissions](#put-user-permissions)); permission strings are validated *before* any database write, so a bad request never leaves a half-created user behind.

#### Request Body

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `username` | `string` | Yes | Must not be empty. Must be unique. |
| `permissions` | `string[]` | No | Permission names to grant on creation. Omitted or empty = no permissions. |

#### Example Request

```json
{"username": "newtrader", "permissions": ["create_order", "delete_order"]}
```

#### Response: 201 Created

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "username": "newtrader",
  "short_id": "U003",
  "permissions": ["create_order", "delete_order"],
  "api_key": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
}
```

> [!CAUTION]
> `api_key` is the raw plaintext key. It is shown **only in this response**. It cannot be retrieved again, only rotated.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "username required"}` | Empty username |
| 400 | `{"error": "unknown permissions: …"}` | A `permissions` entry is not a known permission name (no user is created) |
| 403 | `{"error": "Forbidden"}` | Missing `manage_users` permission |
| 409 | `{"error": "username already exists"}` | Username already taken |
| 503 | `{"error": "database not available"}` | Database not initialised |
| 500 | `{"error": "…"}` | Database error |

### `DELETE` `/api/v1/users/{id}`

_Permission: manage_users_

Delete a user by UUID. Cannot delete yourself or the `admin` account.

#### Response: 204 No Content

No response body.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "cannot delete yourself"}` | Target ID matches calling user's ID |
| 403 | `{"error": "Forbidden"}` | Missing `manage_users` permission |
| 403 | `{"error": "cannot delete the admin account"}` | Target username is `admin` |
| 404 | `{"error": "user not found"}` | ID not found |
| 503 | `{"error": "database not available"}` | Database not initialised |
| 500 | `{"error": "…"}` | Database error |

### `PUT` `/api/v1/users/{id}/permissions`

_Permission: manage_users_

Replace a user's full permission set. Pass an empty array to revoke all permissions. Unrecognised permission strings are rejected. The built-in `admin` account's permissions are **immutable**: it always holds every permission, and any attempt to change them is rejected with `403 Forbidden`.

#### Valid Permission Strings

`create_order` `modify_order` `delete_order` `toggle_trading` `set_position_limit` `set_cash_limit` `set_self_trade_policy`
 `manage_users` `manage_members` `read_audit` `read_m7_errors` `read_pnl` `read_orders` `read_state` `read_status` `export_reports` `restart_system` `bypass_member_check` `trade_global`

#### Request Body

```json
{"permissions": ["create_order", "delete_order", "read_audit"]}
```

#### Response: 204 No Content

No response body.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "unknown permissions: [\"bad_perm\"]"}` | Any unrecognised permission string in the array |
| 403 | `{"error": "Forbidden"}` | Missing `manage_users` permission |
| 403 | `{"error": "the admin account's permissions are immutable"}` | Target is the built-in `admin` account |
| 404 | `{"error": "user not found"}` | User ID not found |
| 503 | `{"error": "database not available"}` | Database not initialised |
| 500 | `{"error": "…"}` | Database error |

### `POST` `/api/v1/users/{id}/rotate-api-key`

_Permission: manage_users_

Generate a new API key for a user. The old key is invalidated immediately. No request body required. This endpoint is **not** desk-gated, so a `trader`-tier license can rotate its own key. On the trader tier it is **self-only**: `{id}` must be the caller's own user id; any other target (including a non-existent one) returns `404` so the endpoint cannot probe for other accounts. With a desk-tier license, a `manage_users` holder may rotate any user.

#### Response: 200 OK

```json
{"api_key": "2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae"}
```

> [!CAUTION]
> The new key is shown **only in this response**. The old key is invalidated immediately and cannot be recovered.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 403 | `{"error": "Forbidden"}` | Missing `manage_users` permission |
| 404 | `{"error": "user not found"}` | User ID not found, *or* (trader tier) a target that is not the caller |
| 503 | `{"error": "database not available"}` | Database not initialised |
| 500 | `{"error": "…"}` | Database error |

### `GET` `/api/v1/users/{user_id}/members`

_Permission: manage_users_

Returns the list of member UUIDs assigned to a specific user. Returns an array of UUID strings, not full member objects.

#### Response: 200 OK

```json
["a1b2c3d4-e5f6-7890-abcd-ef1234567890", "b2c3d4e5-f6a7-8901-bcde-f12345678901"]
```

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 403 | `{"error": "Forbidden"}` | Missing `manage_users` permission |
| 503 | `{"error": "database not available"}` | Database not initialised |
| 500 | `{"error": "…"}` | Database error |

### `PUT` `/api/v1/users/{user_id}/members`

_Permission: manage_users_

Replace the full set of member assignments for a user. Pass an empty array to remove all assignments.

#### Request Body

```json
{"member_ids": ["a1b2c3d4-e5f6-7890-abcd-ef1234567890"]}
```

#### Response: 204 No Content

No response body.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 403 | `{"error": "Forbidden"}` | Missing `manage_users` permission |
| 404 | `{"error": "user not found"}` | User ID not found |
| 503 | `{"error": "database not available"}` | Database not initialised |
| 500 | `{"error": "…"}` | Database error |

### `GET` `/api/v1/members`

_Permission: manage_members_

List all virtual members in the system. Each member carries its configured limits *and* its live cash usage: consumed, effective limit, and remaining headroom per currency pool (see the usage-fields note below).

#### Response: 200 OK

```json
[
  {"id": "uuid", "short_id": "VM001", "name": "Desk A", "max_position": 5000, "cash_limit": 10000000, "cash_limit_gbp": 0, "active": true,
   "eur_consumed_cents": 4200000, "eur_limit_cents": 10000000, "eur_remaining_cents": 5800000,
   "gbp_consumed_cents": 0, "gbp_limit_cents": 0, "gbp_remaining_cents": 0},
  {"id": "uuid", "short_id": "VM002", "name": "Desk B", "max_position": 10000, "cash_limit": 0, "cash_limit_gbp": 0, "active": true,
   "eur_consumed_cents": 0, "eur_limit_cents": 50000000, "eur_remaining_cents": 50000000,
   "gbp_consumed_cents": 0, "gbp_limit_cents": 0, "gbp_remaining_cents": 0}
]
```

**Cash-usage fields** (all in their pool's cents, `i64`): `cash_limit` / `cash_limit_gbp` are the member's configured *overrides* (`0` = none → the global limit applies), the same values `POST` / `PATCH` write. The `*_consumed_cents` / `*_limit_cents` / `*_remaining_cents` trio is the member's live usage: `consumed` is its open-order + executed-trade exposure (same set the global [`cash_limit`](#get-status) uses, scoped to this member); `*_limit_cents` is the **effective** enforced cap (the override capped at the global limit, or the inherited global when there is no override), so it need not equal `cash_limit`; and `remaining = limit − consumed` (negative when over, `0` limit = pool not enforced). These mirror the gRPC `Member` message and the WS `get_members` response.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 403 | `{"error": "Forbidden"}` | Missing `manage_members` permission |
| 503 | `{"error": "database not available"}` | Database not initialised |
| 500 | `{"error": "…"}` | Database error |

### `POST` `/api/v1/members`

_Permission: manage_members_

Create a new virtual member. The `short_id` is auto-generated (VM001, VM002, … VMA1, etc.). You cannot specify it.

#### Request Body

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `name` | `string` | Yes | Display name for the member. Must not be empty. |
| `max_position` | `i64` | No | Position limit in sub-MW. Default: `0`, which, like the global contract limit, **blocks all position-taking** for the member. Set a real limit before routing orders under it. |
| `cash_limit` | `i64` | No | Per-member cash limit in EUR cents. Default `0` (no override → the global limit applies). Always capped at the global limit. |
| `cash_limit_gbp` | `i64` | No | Per-member GBP cash limit in GBP cents. Default `0` (no override → global GBP limit applies). |

#### Example Request

```json
{"name": "Desk B", "max_position": 10000}
```

#### Response: 201 Created

```json
{
  "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
  "short_id": "VM002",
  "name": "Desk B",
  "max_position": 10000,
  "cash_limit": 0,
  "cash_limit_gbp": 0,
  "active": true,
  "eur_consumed_cents": 0,
  "eur_limit_cents": 50000000,
  "eur_remaining_cents": 50000000,
  "gbp_consumed_cents": 0,
  "gbp_limit_cents": 0,
  "gbp_remaining_cents": 0
}
```

A freshly created member has no orders or trades yet, so `*_consumed_cents` is `0` and `*_remaining_cents` equals the effective `*_limit_cents`. See the [members list](#get-members) usage-fields note for the field semantics. `PATCH` returns `204 No Content` (no body).

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "name required"}` | Empty name |
| 403 | `{"error": "Forbidden"}` | Missing `manage_members` permission |
| 503 | `{"error": "database not available"}` | Database not initialised |
| 500 | `{"error": "…"}` | Database error |

### `PATCH` `/api/v1/members/{id}`

_Permission: manage_members_

Partially update a member's name, position limit, or active status. At least one field must be provided.

#### Request Body (all fields optional, at least one required)

| Field | Type | Description |
| --- | --- | --- |
| `name` | `string` | New display name |
| `max_position` | `i64` | New position limit in sub-MW (`0` blocks all position-taking for the member) |
| `cash_limit` | `i64` | New per-member cash limit in EUR cents (`0` clears the override). This is the field the overarching member lowers when next-window collateral is insufficient. |
| `cash_limit_gbp` | `i64` | New per-member GBP cash limit in GBP cents (`0` clears the override). |
| `active` | `bool` | Enable or disable the member |

#### Example Request

```json
{"name": "Desk B Updated", "max_position": 20000, "active": false}
```

#### Response: 204 No Content

No response body.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "nothing to update"}` | All fields null, nothing to change |
| 403 | `{"error": "Forbidden"}` | Missing `manage_members` permission |
| 404 | `{"error": "member not found"}` | Member ID not found |
| 503 | `{"error": "database not available"}` | Database not initialised |
| 500 | `{"error": "…"}` | Database error |

## Audit Trail

Query and export historical order and trade data. All audit endpoints require the `read_audit` permission; export endpoints require `export_reports`.

> [!NOTE]
> Audit data is paginated using cursor-based pagination. Always use the `next_cursor` from each response to fetch the next page. `total_hint` is only present on the first page and is approximate; do not use it for loop termination logic.

### `GET` `/api/v1/audit/orders`

_Permission: read_audit_

Query paginated order audit history with optional filters for time range, area, product, status, user, and virtual member.

#### Query Parameters

| Param | Type | Required | Description |
| --- | --- | --- | --- |
| `cursor` | `string` | No | Opaque pagination token from the previous `next_cursor`. Omit for the first page. |
| `limit` | `u32` | No | Page size. Default: `50`, max: `200`. Must be > 0; an explicit `limit=0` is rejected with 400. (gRPC documents `0 == default` instead; proto3 cannot see the difference.) |
| `date_from` | `string` | No | RFC 3339 datetime: inclusive lower bound. |
| `date_to` | `string` | No | RFC 3339 datetime: inclusive upper bound. |
| `area` | `string` | No | Filter by delivery area EIC code. |
| `product` | `string` | No | Filter by product code. |
| `status` | `string` | No | Filter by order status string. |
| `user_code` | `string` | No | Filter by the EPEX trader/user code (e.g. `"TRADER1"`). Renamed from the former, mislabelled `user_id` parameter. |
| `v_member_short_id` | `string` | No | Filter by virtual member short ID. |
| `voltnir_user_short_id` | `string` | No | Filter by the submitting Voltnir user's short id (e.g. `"U001"`). |
| `voltnir_username` | `string` | No | Filter by the submitting Voltnir user's username snapshot (e.g. `"j.doe"`). |

> [!CAUTION]
> **Always paginate large datasets.** Fetching without a limit on a large audit log can cause memory exhaustion and request timeouts. Use `cursor` to iterate through pages.

#### Response: 200 OK (first page)

```json
{
  "items": [ ... ],
  "next_cursor": "1717000000000.1547",
  "total_hint": 4821
}
```

#### Response: 200 OK (last page)

```json
{
  "items": [ ... ],
  "next_cursor": null,
  "total_hint": null
}
```

`next_cursor` is `null` on the last page. `total_hint` is only present on the first page (cursor omitted); it is a count hint: use it for display only, not for iteration logic, as concurrent writes may shift it.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "invalid date '…': …"}` | `date_from` or `date_to` is not valid RFC 3339 |
| 403 | `{"error": "Forbidden"}` | Missing `read_audit` permission |
| 503 | `{"error": "database not available"}` | Database not initialised |
| 500 | `{"error": "…"}` | Database query failed |

### `GET` `/api/v1/audit/trades`

_Permission: read_audit_

Query paginated trade audit history. Same pagination as `GET /audit/orders`; the `status` filter is not available for trades. Each row carries both the **execution time** (`exec_time` / `executed_at`) and the contract **delivery window** (`delivery_start` / `delivery_end`), and you can filter the `date_from`/`date_to` window on either axis via `time_basis`.

#### Query Parameters

| Param | Type | Required | Description |
| --- | --- | --- | --- |
| `cursor` | `string` | No | Opaque pagination token from the previous `next_cursor`. |
| `limit` | `u32` | No | Default: `50`, max: `200`. Must be > 0; an explicit `limit=0` is rejected with 400. (gRPC documents `0 == default` instead; proto3 cannot see the difference.) |
| `date_from` | `string` | No | RFC 3339 datetime: inclusive lower bound, applied to the axis selected by `time_basis`. |
| `date_to` | `string` | No | RFC 3339 datetime: inclusive upper bound, applied to the axis selected by `time_basis`. |
| `time_basis` | `string` | No | Which timestamp `date_from`/`date_to` filter on: `delivery` (**default**: the contract delivery window, **overlap** semantics) or `execution` (execution time). Any other value → 400. |
| `area` | `string` | No | Filter by delivery area EIC code. |
| `product` | `string` | No | Filter by product code. |
| `user_code` | `string` | No | Filter by the EPEX trader/user code (e.g. `"TRADER1"`). Renamed from the former, mislabelled `user_id` parameter. |
| `v_member_short_id` | `string` | No | Filter by virtual member short ID. |
| `voltnir_user_short_id` | `string` | No | Filter by the submitting Voltnir user's short id (e.g. `"U001"`). |
| `voltnir_username` | `string` | No | Filter by the submitting Voltnir user's username snapshot (e.g. `"j.doe"`). |

> [!NOTE]
> **Delivery window (default) vs. execution time.** By default (`time_basis=delivery`) the date window filters on the **contract delivery period** using **overlap**: a trade is returned when its delivery window intersects `[date_from, date_to]` (i.e. `delivery_end ≥ date_from` *and* `delivery_start ≤ date_to`). That is the "what is our exposure / settlement for this delivery period" view, and what settlement / REMIT-style reporting wants. Overlap guarantees completeness for block / multi-period products that span the window. With `time_basis=execution` it instead filters on **when the trade matched** (`executed_at`), the "what did we transact in this period" (transaction-reporting) view. **Note:** trades recorded before delivery capture was added have `null` `delivery_start`/`delivery_end` and therefore never match the (default) delivery filter when a date range is given; query them with `time_basis=execution`.

#### Response: 200 OK

```json
{
  "items": [
    {
      "trade_id": "26269999001",
      "contract_id": "100123",
      "qty": 5000,
      "px": 5215,
      "state": "ACTI",
      "exec_time": "2026-04-20T13:42:07Z",
      "executed_at": "2026-04-20T13:42:07.000Z",
      "delivery_start": "2026-04-20T14:00:00Z",
      "delivery_end": "2026-04-20T15:00:00Z",
      "delivery_area": "10YNL----------L",
      "product": "Intraday_Hour_Power",
      "v_member_short_id": "VM001",
      "voltnir_user_id": "019ece6c-1a2b-4c3d-8e9f-001122334455",
      "voltnir_user_short_id": "U001",
      "voltnir_username": "j.doe"
    }
  ],
  "next_cursor": "1717000000000.892",
  "total_hint": 1203
}
```

`delivery_start` / `delivery_end` are the contract's delivery window (RFC 3339), captured at trade time; `exec_time` / `executed_at` are when the trade matched. Both are always present in the row (delivery fields are `null` only for trades recorded before this was added). Some fields omitted from this example for brevity.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "invalid date '…': …"}` | Date parameter is not valid RFC 3339 |
| 400 | `{"error": "invalid time_basis '…': expected 'execution' or 'delivery'"}` | `time_basis` is not `execution` or `delivery` |
| 403 | `{"error": "Forbidden"}` | Missing `read_audit` permission |
| 503 | `{"error": "database not available"}` | Database not initialised |
| 500 | `{"error": "…"}` | Database query failed |

### `GET` `/api/v1/audit/public_trades`

_Permission: read_audit_

Query the **saved history** of market-wide public trades (M7 `PblcTradeConfRprt`). Returns rows only when the gateway was started with `market_data.public_trades.persist: postgresql`; `false` or the export-only `parquet` backend leave the table empty, so this returns no items. Data is scoped to the products your M7 account is assigned to; pre-arranged trades are excluded. Same cursor pagination as the other audit endpoints. Prices (`px`) are Eurocents (1 EUR = 100).

> [!NOTE]
> **Saved history vs. the live feed.** This endpoint returns trades *stored in the database*, which survive restarts. How far back it reaches is set by `market_data.public_trades.retention_days`: e.g. `3` keeps roughly the last 3 days (a background cleanup deletes older rows about once an hour); `0` keeps everything forever. If you instead just want the *most recent* trades happening now (not saved history), use [GET /public_trades](#get-public-trades), the live in-memory feed.

#### Query Parameters

| Param | Type | Required | Description |
| --- | --- | --- | --- |
| `cursor` | `string` | No | Opaque pagination token from the previous `next_cursor`. Omit for the first page. |
| `limit` | `u32` | No | Page size. Default: `50`, max: `200`. Must be > 0; an explicit `limit=0` is rejected with 400. (gRPC documents `0 == default` instead; proto3 cannot see the difference.) |
| `date_from` | `string` | No | RFC 3339 datetime: inclusive lower bound on execution time. |
| `date_to` | `string` | No | RFC 3339 datetime: inclusive upper bound on execution time. |
| `area` | `string` | No | Delivery area EIC code. Matches a trade where **either** the buy or sell delivery area equals it (public trades can be cross-border). |
| `product` | `string` | No | Filter by product code (enriched from the contract at ingest). |
| `state` | `string` | No | Filter by trade state: `ACTI`, `CNCL`, `RREQ`, `RGRA`, `RREJ`, `CREQ`, `CREJ`, `RSFA`. |

#### Response: 200 OK (first page)

```json
{
  "items": [
    {
      "trade_id": "9876543210",
      "contract_id": "100123",
      "qty": 10,
      "px": 4215,
      "exec_time": "2026-06-01T10:15:00.000Z",
      "executed_at": "2026-06-01T10:15:00.000Z",
      "revision_no": 1,
      "state": "ACTI",
      "buy_dlvry_area": "10YDE-EON------1",
      "sell_dlvry_area": "10YNL----------L",
      "self_trade": false,
      "product": "Intraday_Hour_Power"
    }
  ],
  "next_cursor": "1717000000000.1547",
  "total_hint": 88210
}
```

`next_cursor` is `null` on the last page; `total_hint` is present only on the first page. The market-wide tape is high-volume, so always paginate.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "invalid date '…': …"}` | Date parameter is not valid RFC 3339 |
| 403 | `{"error": "Forbidden"}` | Missing `read_audit` permission |
| 503 | `{"error": "database not available"}` | Database not initialised |
| 500 | `{"error": "…"}` | Database query failed |

### `GET` `/api/v1/audit/events`

_Permission: read_audit_

Query the **compliance audit-event log**: the append-only, who-did-what record of actor-driven mutations. Unlike the orders/trades audit endpoints (which read the business tables), this is a dedicated event store written at every mutation site: user/permission/member changes, global & per-member limit changes, the trading kill-switch and self-trade-policy toggles, order rejections (limit/cash/self-cross/kill-switch), report exports, and system/license lifecycle events. Each row records the **actor** (id / short id / username, or a system component), the **transport** (`rest`/`ws`/`grpc`/`system`), the caller's **source IP**, `before`/`after` JSON snapshots, the `outcome`, and a `reason`. Rows are immutable and pruned after `database.audit_retention_days` (default 7; `0` = keep forever). Newest-first; same cursor pagination as the other audit endpoints.

#### Query Parameters

| Param | Type | Required | Description |
| --- | --- | --- | --- |
| `cursor` | `string` | No | Opaque pagination token from the previous `next_cursor`. Omit for the first page. |
| `limit` | `u32` | No | Page size. Default: `50`, max: `200`. An explicit `limit=0` is rejected with 400. |
| `date_from` | `string` | No | RFC 3339 datetime: inclusive lower bound on event time. |
| `date_to` | `string` | No | RFC 3339 datetime: inclusive upper bound on event time. |
| `action` | `string` | No | Filter by action token, e.g. `permissions_set`, `member_modified`, `position_limit_set`, `cash_limit_set`, `trading_toggled`, `self_trade_policy_changed`, `order_rejected`, `order_cancel_all`, `report_exported`, `system_startup`, `license_expired`. |
| `target_type` | `string` | No | Filter by target kind: `user`, `member`, `profile`, `order`, `trading`, `report`, `license`, `system`. |
| `actor_short_id` | `string` | No | Filter by the acting user's short id, e.g. `U001`. |
| `outcome` | `string` | No | Filter by outcome: `ok` or `error`. |

#### Response: 200 OK (first page)

```json
{
  "items": [
    {
      "ts": "2026-06-20T14:03:11.123Z",
      "ts_ms": 1781013791123,
      "actor_user_id": "0b8e…",
      "actor_short_id": "U001",
      "actor_username": "j.doe",
      "transport": "rest",
      "action": "permissions_set",
      "target_type": "user",
      "target_id": "3af1…",
      "before": ["read_audit"],
      "after": ["read_audit", "manage_users"],
      "outcome": "ok",
      "reason": null,
      "source_ip": "203.0.113.7"
    }
  ],
  "next_cursor": "1781013791123.4187",
  "total_hint": 1042
}
```

`next_cursor` is `null` on the last page; `total_hint` is present only on the first page. System/license events carry the component name in `actor_username` with the id columns `null` and `transport: "system"`.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "invalid date '…': …"}` | Date parameter is not valid RFC 3339 |
| 403 | `{"error": "Forbidden"}` | Missing `read_audit` permission |
| 503 | `{"error": "database not available"}` | Database not initialised |
| 500 | `{"error": "…"}` | Database query failed |

### `GET` `/api/v1/audit/m7_errors`

_Permission: read_m7_errors_

Query the **M7 exchange-error log**, the append-only record of M7-side faults observed off the AMQP line. Gated by the **dedicated `read_m7_errors` permission**, deliberately separate from `read_audit`. The primary rows are M7 business errors (`ErrResp`, `kind: "err_resp"`), each **enriched from the vendor DFS200 §4 catalog**: the raw numeric `err_code` is paired with a human `err_identifier` (e.g. `order_rejected_self_trade_protection` for `1149`) and a `category` (`order_entry`, `general`, `trade`, `user_right`, `limits`, `wrong_reference`; `unknown` for an unmapped code). Other log-only drop-points are captured too: `unknown_type`, `ack_uncorrelated`, and `seq_gap` (these carry no code/category). Rows are immutable and pruned after `database.m7_errors_retention_days` (default 7; `0` = keep forever). Newest-first; same cursor pagination as the other audit endpoints.

#### Query Parameters

| Param | Type | Required | Description |
| --- | --- | --- | --- |
| `cursor` | `string` | No | Opaque pagination token from the previous `next_cursor`. Omit for the first page. |
| `limit` | `u32` | No | Page size. Default: `50`, max: `200`. An explicit `limit=0` is rejected with 400. |
| `date_from` | `string` | No | RFC 3339 datetime: inclusive lower bound on receive time. |
| `date_to` | `string` | No | RFC 3339 datetime: inclusive upper bound on receive time. |
| `kind` | `string` | No | Filter by fault class: `err_resp`, `parse_error`, `unknown_type`, `ack_uncorrelated`, `seq_gap`. |
| `category` | `string` | No | Filter by DFS200 §4 section: `order_entry`, `general`, `trade`, `user_right`, `limits`, `wrong_reference`, `unknown`. (Set only for `kind=err_resp`.) |
| `err_code` | `i64` | No | Filter by the raw numeric M7 error code, e.g. `1149`. |

#### Response: 200 OK (first page)

```json
{
  "items": [
    {
      "received_at": "2026-06-20T14:03:11.123Z",
      "received_at_ms": 1781013791123,
      "kind": "err_resp",
      "category": "order_entry",
      "err_code": 1149,
      "err_identifier": "order_rejected_self_trade_protection",
      "err_text": "Order rejected by self-trade protection",
      "cl_ordr_id": "3af1…",
      "client_correlation_id": "0b8e…",
      "var_list": [{"id": 1, "value": "DE"}],
      "voltnir_user_id": null,
      "voltnir_short_id": null,
      "voltnir_username": null,
      "raw_payload": "{…}",
      "severity": "error"
    }
  ],
  "next_cursor": "1781013791123.4187",
  "total_hint": 37
}
```

`next_cursor` is `null` on the last page; `total_hint` is present only on the first page. The `voltnir_*` columns are populated only when the failing order's Voltnir user is resolvable; `cl_ordr_id` always correlates an `err_resp` row to the fully-attributed `orders` audit row.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "invalid date '…': …"}` | Date parameter is not valid RFC 3339 |
| 403 | `{"error": "Forbidden"}` | Missing `read_m7_errors` permission |
| 503 | `{"error": "database not available"}` | Database not initialised |
| 500 | `{"error": "…"}` | Database query failed |

### `POST` `/api/v1/audit/export/orders`

_Permission: export_reports_

Initiate an asynchronous export of order audit data. The export runs in a background task. Poll the returned `download_url` to check status and retrieve the file when ready.

#### Request Body

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `format` | `string` | Yes | `"json"` or `"csv"` |
| `from` | `string` | Yes | RFC 3339 datetime: start of range (inclusive). |
| `to` | `string` | Yes | RFC 3339 datetime: end of range. Must be after `from`. |
| `area` | `string` | No | Filter by delivery area EIC code. |
| `product` | `string` | No | Filter by product code. |

#### Example Request

```json
{
  "format": "csv",
  "from": "2026-04-01T00:00:00Z",
  "to": "2026-04-30T23:59:59Z",
  "area": "10YNL----------L"
}
```

#### Response: 202 Accepted

```json
{
  "token": "550e8400-e29b-41d4-a716-446655440000",
  "download_url": "/api/v1/audit/export/550e8400-e29b-41d4-a716-446655440000"
}
```

Poll `download_url` to check status. The export runs in a background task. Token is valid for 1 hour; tokens are lost on server restart.

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 400 | `{"error": "from: invalid ISO 8601 date"}` | `from` is not valid RFC 3339 |
| 400 | `{"error": "to: invalid ISO 8601 date"}` | `to` is not valid RFC 3339 |
| 400 | `{"error": "from must be before to"}` | `from` ≥ `to` |
| 400 | `{"error": "from is required"}` / `{"error": "to is required"}` | Missing `from` or `to` |
| 400 | `{"error": "unknown format '…', must be json or csv"}` | Invalid or missing format value |
| 403 | `{"error": "Forbidden"}` | Missing `export_reports` permission |
| 500 | `{"error": "cannot resolve output dir: …"}` | Server filesystem issue |

### `POST` `/api/v1/audit/export/trades`

_Permission: export_reports_

Initiate an asynchronous export of trade audit data. Same request body, response shape, and error conditions as [POST /audit/export/orders](#post-export-orders).

#### Request Body

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `format` | `string` | Yes | `"json"` or `"csv"` |
| `from` | `string` | Yes | RFC 3339 datetime: start of range. |
| `to` | `string` | Yes | RFC 3339 datetime: end of range. |
| `area` | `string` | No | Filter by delivery area EIC code. |
| `product` | `string` | No | Filter by product code. |

#### Example Request

```json
{
  "format": "json",
  "from": "2026-04-01T00:00:00Z",
  "to": "2026-04-30T23:59:59Z"
}
```

#### Response: 202 Accepted

```json
{
  "token": "660e9500-f3ac-52e5-b827-557766551111",
  "download_url": "/api/v1/audit/export/660e9500-f3ac-52e5-b827-557766551111"
}
```

### `GET` `/api/v1/audit/export/{token}`

Poll or download an export file by its token. Returns the binary file when ready, a 202 while still generating, or a 500 if generation failed.

> [!NOTE]
> Export tokens expire after **1 hour**. The token registry is in-memory only, so tokens are lost if the server restarts.

#### Response: 202 Accepted (export pending)

```json
{"status": "pending"}
```

#### Response: 200 OK (export ready)

Binary file download with headers:

```
Content-Type: application/json   (or text/csv)
Content-Disposition: attachment; filename="orders_2026-04-01_<token>.json"
```

#### Response: 500 (export failed)

```json
{"error": "…error message from background task…"}
```

#### Errors

| Status | Body | Condition |
| --- | --- | --- |
| 404 | `{"error": "token not found"}` | Token not found (expired, never existed, or server restarted) |
| 500 | `{"error": "…"}` | Background export task failed |
