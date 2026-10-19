# voltnir Python SDK (`voltnir_sdk`)

Python SDK for the Voltnir external gRPC API (`voltnir.api.v1`). It is the client
library for integrating with a [Voltnir](https://voltnir.io) gateway, which speaks the EPEX SPOT API
(the M7 intraday continuous market) on your behalf and exposes it over gRPC.

Wraps the gRPC stubs with sync **and** async client facades, bearer-token
auth, plaintext or TLS channels, and typed exceptions for every gRPC status
code Voltnir returns. The report exports are the one thing it fetches over the
gateway's REST API instead, because the gateway serves a report as a file (see
[Report exports](#report-exports-over-rest)).

| | |
|---|---|
| Distribution name | `voltnir-grpc-py-sdk` (what you pin in `requirements.txt`) |
| Import name | `voltnir_sdk` |
| Version | `1.0.1` — also available as `voltnir_sdk.__version__` |
| Requires | Python 3.10+ |
| Website | [voltnir.io](https://voltnir.io) |
| Changes | [`CHANGELOG.md`](https://github.com/Voltnir/voltnir-sdk/blob/master/clients/python/CHANGELOG.md) |
| Reference | [`docs/python_sdk_v1.md`](https://github.com/Voltnir/voltnir-sdk/blob/master/docs/python_sdk_v1.md) in the public repository; the Python SDK page in the customer portal |

## Install

From PyPI:

```bash
pip install voltnir-grpc-py-sdk
```

Or directly from the public repository, GitHub or the Codeberg mirror:

```bash
# GitHub:
pip install "git+https://github.com/Voltnir/voltnir-sdk.git#subdirectory=clients/python"

# …or the Codeberg mirror:
pip install "git+https://codeberg.org/Voltnir/voltnir-sdk.git#subdirectory=clients/python"
```

Or from a local checkout:

```bash
cd clients/python
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

The generated protobuf stubs are vendored under
`src/voltnir_sdk/_generated/`, so no `protoc` is required at install time.

To also install the codegen toolchain (only needed when the proto changes):

```bash
pip install -e '.[dev]'
```

## Quickstart: sync

```python
from voltnir_sdk import VoltnirClient, Side, OrderType

with VoltnirClient(host="localhost", port=3443, api_key="YOUR_API_KEY") as client:
    me = client.get_me()
    print(me.username, list(me.permissions))

    contracts = client.list_contracts(area_id="10YBE----------2")
    first = contracts.contracts[0]

    # Follow one contract by its id; name products instead to follow a product.
    ids = [int(first.contract_id)]
    for event in client.watch_contracts(areas=[first.area_id], contract_ids=ids):
        for contract in event.contracts:   # SNAPSHOT: every match; UPSERT: one
            print(event.type, contract.last_price)   # last_price is CENTS
        break
```

`YOUR_API_KEY` stands in for the key: load it from an environment variable or
from a file only its owner can read (mode 600), never a literal in source, since
the key carries every permission of its user and a key that leaks can only be
rotated.

Every unary call is bounded by the client's `timeout` (10 seconds unless you
pass another value to the constructor). Every method that calls the gateway
also takes its own `timeout=`, in seconds, which replaces the client value for
that one call: `client.query_audit_orders(..., timeout=60.0)` gives a slow
report room without loosening the order path. A deadline that passes raises
`DeadlineExceeded`, or `OrderOutcomeUnknown` on a call that changes an order
(see [Errors](#errors)).
Streams have no deadline unless you pass one.

## Quickstart: async

Build the client **inside** the loop that will use it. `grpc.aio` binds the
channel to the running loop at construction, so a module-level or DI-container
singleton fails on first use; the SDK refuses this at construction with
`AsyncLoopError` rather than letting it surface later as a cross-loop error.

```python
import asyncio
from voltnir_sdk import AsyncVoltnirClient

async def main():
    async with AsyncVoltnirClient(host="localhost", port=3443, api_key="YOUR_API_KEY") as c:
        me = await c.get_me()
        print(me.username)
        contracts = await c.list_contracts(area_id="10YBE----------2")
        first = contracts.contracts[0]
        ids = [int(first.contract_id)]
        async for event in c.watch_contracts(areas=[first.area_id], contract_ids=ids):
            print(event.type)
            break

asyncio.run(main())
```

## Units — read this before interpreting any number

**Every monetary and size value on this API is a scaled integer, and there are
three different scales.** A misread is silent: the wrong answer is always a
plausible number. This is the most expensive mistake available to a user of
this SDK, so it gets the longest section in this README.

| What | Wire type | Scale | Convert with |
|---|---|---|---|
| Price (CCY/MWh) | `sint64` | **x 100** | `price_to_cents` / `cents_to_price` |
| Quantity, position, size | `uint32` / `sint64` | **x 1 000** | `quantity_to_sub_mw` / `sub_mw_to_quantity` |
| Cash limits and exposure | `sint64` | **x 100** | `eur_to_cents` / `cents_to_eur` |
| Realized / unrealized P&L (q8 = currency x 100 000) | `sint64` | **x 100 000** | `eur_to_q8` / `q8_to_eur` |

### Sending: the order path takes wire units directly

`submit_order` and `modify_order` take `price_cents` and `quantity_sub_mw` —
the same units the REST, gRPC and WebSocket docs specify, and the same units
every response carries. An algo holding its book in minor units never converts.

The parameter **names carry the unit deliberately**. A bare `price=50` reads as
50 CCY/MWh and would be silently accepted as 0.50: a legal price, which no check
on the gateway or the exchange can tell from what you meant, and a 100x error.
`price_cents=50` cannot be misread. Non-integers are refused rather than
truncated:

```python
>>> client.submit_order(price_cents=50.07, ...)
OrderValidationError: price_cents: expected an int in wire units, got float
50.07. Prices are cents (5000 = 50.00 CCY/MWh) and sizes are sub-MW
(1000 = 1.0 MW); use voltnir_sdk.price_to_cents / quantity_to_sub_mw if you
are holding decimals.
```

### Reading back: which scale applies to which field

This is where the money is lost, because nothing in the integer tells you which
scale produced it.

| Field | Scale | Read with |
|---|---|---|
| `OwnOrder.price`, `OwnTrade.px`, `PublicTrade.px` | x 100 | `cents_to_price` |
| `Contract.last_price` / `highest_price` / `lowest_price`, `ObEntry.price` | x 100 | `cents_to_price` |
| `OwnOrder.quantity` / `initial_quantity` / `hidden_quantity` / `displayed_quantity` | x 1 000 | `sub_mw_to_quantity` |
| `OwnTrade.qty`, `PublicTrade.qty`, `ObEntry.quantity`, `Contract.best_bid_qty` / `best_ask_qty` | x 1 000 | `sub_mw_to_quantity` |
| `ContractDetail.net_pos`, `ContractPnl.signed_position`, `Member.max_position`, `SystemStatus.order_pos_limit` | x 1 000 | `sub_mw_to_quantity` |
| `Member.max_slot_position`, `AccountView.slot_limit`, `SlotLimitResponse.house_limit`, every `SlotScopePosition` figure (the slot position limit, MW per quarter-hour summed over every covering contract) | x 1 000 | `sub_mw_to_quantity` |
| `Member.cash_limit` / `eur_*_cents` / `gbp_*_cents`, `CashLimitStatus.*_cents`, `CashPool.*_cents` | x 100 | `cents_to_eur` |
| `Contract.best_bid` / `best_ask` | x 100 | `cents_to_price` |
| `PnlSnapshot` `avg_open_px` / `mark_px` | x 100 | `cents_to_price` |
| `GetHub2HubResponse` `atc_out` / `atc_in` | x 1 000 | `sub_mw_to_quantity` |
| **`CashLimit` (from `get_cash_limits`) — `current_limit`, `configured_limit`** | **NOT fixed. Divide by `10 ** dec_shft`** | see below |
| **`ContractPnl.realized_pnl` / `unrealized_pnl`** | **x 100 000** | **`q8_to_eur`** |

### The two traps worth naming

**P&L is not cents.** `realized_pnl` is the row's currency x 100 000 — the proto
calls it "q8", which here means x 10^5, *not* x 10^8. Reading it with
`cents_to_eur` overstates by 1000x, and both readings look like real money:

```python
>>> q8_to_eur(1_234_500)      # correct — the x 100 000 scale, whatever the currency
Decimal('12.345')
>>> cents_to_eur(1_234_500)   # WRONG for P&L
Decimal('12345')
```

The scale is the same for every currency; the row's `currency` field (`EUR` or
`GBP`) and the snapshot's per-currency `totals` tell you which pool a figure
belongs to. Never add across currencies — read `totals`, which the gateway sums
per currency. P&L money is energy-scaled by the contract's delivery duration, so
a 15-minute fill is a quarter of its hourly `px × qty`; `avg_open_px` / `mark_px`
stay bare prices. A trade whose duration is not yet known is left out of the walk
and counted in `unpriced_trades`, never priced at a guess.

**Size is x 1 000, not x 100.** Positions, limits and quantities are sub-MW.
Applying the price scale to a size is a 10x error — small enough to look like a
bad day rather than a bug.

**`get_cash_limits()` is the one thing on this page that is NOT a fixed scale.**
It returns M7's own per-currency feed, where each row carries its own
`dec_shft` and the real amount is `raw / 10 ** dec_shft`. There is no helper,
because the divisor is data rather than a constant:

```python
for lim in client.get_cash_limits().limits:
    shift = lim.dec_shft or 0
    amount = Decimal(lim.current_limit) / (Decimal(10) ** shift)
```

Do not reach for `cents_to_eur` here. The trap is sharpened by `SystemStatus`,
which carries `cash_limit` (Voltnir's own state, genuinely cents) and
`cash_limits` (M7's raw feed) as adjacent fields whose names differ by one
letter and whose scales differ by an arbitrary power of ten.

### Converting safely

```python
from voltnir_sdk import (
    price_to_cents, cents_to_price,      # CCY/MWh
    quantity_to_sub_mw, sub_mw_to_quantity,  # MW
    eur_to_cents, cents_to_eur,          # cash limits
    eur_to_q8, q8_to_eur,                # P&L
)

price_to_cents("50.07")      # 5007   -> pass as price_cents
eur_to_cents("50000")        # 5000000 -> a 50,000 EUR cash limit
q8_to_eur(1_234_500)         # Decimal('12.345') <- P&L for display
```

All of them use `Decimal`, never binary float arithmetic, and **reject a value
finer than the tick rather than rounding it**. Silently moving a price or a
size is invisible in every log, so the SDK refuses instead:

```python
>>> price_to_cents("50.005")
UnitConversionError: price_eur_per_mwh: 50.005 CCY/MWh is not an exact multiple
of the 0.01 CCY/MWh tick ...
```

`price_to_cents` and `eur_to_cents` share a multiplier today but are separate
functions on purpose: they feed different fields, and the name should match the
call site.

## Type checking: what it does and does not catch

The package ships `py.typed` and generated `.pyi` stubs, and every method has a
return annotation. For full checking you also need stubs for protobuf itself,
which does not ship its own:

```bash
pip install types-protobuf     # what the [typing] extra adds
mypy your_code.py
```

**Caught statically:**

```
error: Argument "contract_id" to "submit_order" has incompatible type "str"; expected "int"
error: "UserProfile" has no attribute "usrename"; maybe "username"?
error: "SubmitOrderResponse" has no attribute "no_such_field"
```

That first one matters more than it looks: `Contract.contract_id` is a **string**
on the wire while `submit_order`'s is an **int64**, so the natural
`contract_id=contract.contract_id` is wrong and is a type error rather than
a runtime surprise.

**NOT caught statically:** passing the wrong proto enum. `Side`, `OrderType` and
the rest are plain `int` at the type level, so `side=OrderType.ICEBERG` type-checks
fine. The SDK catches it at runtime instead, before anything is sent:

```
OrderValidationError: side must be Side.BUY or Side.SELL, got 3.
SIDE_UNSPECIFIED is rejected by the gateway.
```

Without `types-protobuf`, argument types are still checked but every response is
`Any`, so response-field typos pass. It is worth installing.

## Submitting an order

```python
from voltnir_sdk import (
    VoltnirClient, OrderOutcomeUnknown, OrderState, Side, new_client_order_id,
)

with VoltnirClient(host="localhost", port=3443, api_key="YOUR_API_KEY") as client:
    order_id = new_client_order_id()          # keep this: it is your recovery key

    try:
        resp = client.submit_order(
            client_order_id=order_id,
            side=Side.BUY,
            delivery_area_id="10YBE----------2",
            contract_id=12345,
            price_cents=5007,        # 50.07 CCY/MWh
            quantity_sub_mw=1500,    # 1.5 MW
        )
        if resp.state == OrderState.REJECTED:
            print("refused by the exchange:", resp.reason)   # nothing is resting
    except OrderOutcomeUnknown:
        # The order MAY be resting. Never resubmit blindly here.
        state = client.get_order(client_order_id=order_id)
        ...
```

**Reusing a `client_order_id`.** The gateway refuses a reused key
(`InvalidArgument`, "is already in use") while it holds the original order's
record in memory, in any state, so a retry under the same key cannot place a
second order beside a live one. The record is not kept for ever: a gateway
restart drops every record; the contract sweep, about an hour after the
contract's delivery ends, drops a finished order's; and a resubscription to the
exchange's order feed rebuilds the records from the orders still on the market,
which frees the keys of filled and deleted orders. A rejected order was never on
the market, so the rebuild keeps its record and its key until the contract
sweep, or until a restart for an order on a contract the gateway never listed,
such as a refused new block order. The refusal guards
against two live orders under one key; it is not a permanent ledger of every key
used. Retry a timed-out submission under a **new** key once reconciliation shows
the order is not there: a key written off after an unacknowledged submission
stays refused ("was reclaimed after no exchange acknowledgement; use a new id").
The one key to reuse on purpose is the one a `RequestNotProcessed` hands back.
`submit_order`'s docstring states the same rules.

Identify the contract with `contract_id`, or with both `product` and
`delivery_start`. `delivery_start` is the contract's UTC delivery start in any
RFC 3339 spelling (`2026-10-25T00:00:00Z`, `…T00:00:00.000Z` and
`…T02:00:00+02:00` name one contract). On a clock-change day the doubled hour is
two instants: on 2026-10-25, 02:00 CEST is `00:00Z` (hour `02A`) and 02:00 CET
is `01:00Z` (hour `02B`). The `A`/`B` marker exists only in contract names, so
name the hour by its UTC start. `validity_date` is an RFC 3339 instant in the
form the exchange's schema takes: an uppercase `T` and `Z`, seconds up to 59 and
an offset within ±14:00, which is forwarded unchanged; the exchange works in UTC,
so send `Z`; the exchange GUI's `02:30A` form is refused.

A **user-defined block** is one order on at least two consecutive contracts of
one product, filled all at once or not at all. Create one with `delivery_end`
beside `product` and `delivery_start`, `order_type=OrderType.BLOCK`,
`exe_restriction=ExeRestriction.AON` (or `FOK` with `VALIDITY_NON`) and no
`contract_id`. The window must start and end on the product's contract
boundaries with no contract missing between them, and be no longer than the
product's `blockMaximumHours`. The exchange creates the block's own contract on
the first order for it; until it does, the pending order carries a gateway
placeholder `contract_id` (2**50 and above). Join an existing block with its
`contract_id` and `order_type=OrderType.BLOCK`. A block with `IOC` is a market
sweep, which is not supported.

```python
from voltnir_sdk import ExeRestriction, OrderState, OrderType, Side, new_client_order_id

resp = client.submit_order(
    client_order_id=new_client_order_id(),
    side=Side.BUY,
    delivery_area_id="10YDE-EON------1",
    product="Intraday_Hour_Power",
    delivery_start="2026-10-05T10:00:00Z",
    delivery_end="2026-10-05T13:00:00Z",   # three hours, one order
    order_type=OrderType.BLOCK,
    exe_restriction=ExeRestriction.AON,
    price_cents=8000,
    quantity_sub_mw=5000,
)
if resp.state == OrderState.REJECTED:
    print(resp.err_code, resp.reason)        # the exchange's code and text
```

### What the SDK checks before anything is sent

These run locally, so a rejection here is always "definitely not submitted" and
costs no round trip. Where a row is a gateway rule, the SDK checks it first so
the error names the field before a round trip; the required `client_order_id`,
ints for wire units and wire widths are the SDK's own.

| Check | Why |
|---|---|
| `client_order_id` present | It is your reconciliation key. Required by the SDK even though the wire allows omitting it. |
| `side` is BUY or SELL | `SIDE_UNSPECIFIED` is rejected by the gateway. |
| `delivery_area_id` is 16 characters | The exchange schema fixes the area at 16 characters, the EIC code (`10YNL----------L`). The gateway refuses any other length, so a contract id typed into the field fails here, naming the field. A 16-character id that names no area you trade is refused by the exchange. |
| contract identified | Either `contract_id`, or both `product` and `delivery_start`. |
| price / quantity are ints | A float means you are thinking in CCY/MWh. `int(50.07)` would be a 100x error dressed as a rounding. |
| quantity > 0 on submit **and on a MODIFY** | A zero restatement is a 0.0 MW order, and the gateway refuses it on both. Reachable from correct code whenever an order fills completely between your snapshot and your modify; to withdraw, use `cancel_order`. `ACTIVATE` / `DEACTIVATE` restate the order as it rests, so their quantity is held only to being an int that fits its wire field. |
| `display_qty_sub_mw` only on ICEBERG | The visible peak is an iceberg concept, and the gateway refuses it on any other type: on a REGULAR order it would describe an exposure the order does not have. |
| ICEBERG requires `display_qty_sub_mw` | The visible peak is mandatory for the type. |
| `display_qty_sub_mw < quantity_sub_mw` | The gateway's iceberg rule, on submit and on a MODIFY. |
| `delivery_end` only on a block create | It creates a block, so it needs `order_type=BLOCK`, `product` and `delivery_start`, and no `contract_id` (`BLOCK_DELIVERY_END_INVALID`). |
| a block takes AON or FOK | The exchange refuses `NON` on a block (`BLOCK_RESTRICTION_NON`); `IOC` makes it a market sweep, not supported (`BLOCK_SWEEP_UNSUPPORTED`). |
| FOK / IOC require `validity_res=VALIDITY_NON` | The gateway refuses any other combination. Note the member is `VALIDITY_NON`, not `NON`: `NON` exists only on `ExeRestriction`. |
| values fit their wire width | protobuf raises rather than wrapping (a u32 quantity does **not** silently wrap), re-typed as `OrderValidationError` with the field named. |

The gateway's product checks have no local twin, because the SDK does not hold
the product catalogue: an order off its product's price band, tick, quantity
bounds or volume increment, or above the exchange's order-size limit for the
member the gateway trades as, is refused by the gateway as `InvalidArgument`
naming the bound.

All of these raise `OrderValidationError`, which is a `ValueError` and **not** a
`VoltnirError` — nothing was sent, so it must not be swallowed by an
`except VoltnirError` written to handle exchange failures.

### Repricing: a MODIFY is a full restatement

`modify_order` is **not** a patch. Both price and quantity are required and
whatever you pass becomes the resting order. To reprice a partially-filled
order, pass the **remaining** quantity — restating the original size re-inflates
an exposure you have partly closed:

```python
from voltnir_sdk import Side, new_client_order_id

order_id = new_client_order_id()
client.submit_order(
    client_order_id=order_id,
    side=Side.BUY,
    delivery_area_id="10YBE----------2",
    contract_id=12345,
    price_cents=5000,
    quantity_sub_mw=1000,
)

# ...later, reprice it. Reuse the SAME id: a fresh one targets no existing
# order, and the quantity is what is LEFT, not what you started with.
client.modify_order(
    client_order_id=order_id,
    price_cents=5100,
    quantity_sub_mw=800,
)
```

`ACTIVATE` / `DEACTIVATE` take neither price nor quantity.

### Baskets: several orders in one entry

`submit_basket` enters 1 to 100 orders as one exchange entry. Each order is a
dict of `submit_order` keyword arguments. `list_exec_inst` says how the exchange
treats the list: `"none"` processes each order on its own, `"valid"` rejects
the whole list if any order fails the exchange's entry checks, and `"linked"`
executes every order at once or deletes them all (every order
`ExeRestriction.FOK` with `ValidityRes.VALIDITY_NON`; the orders never match
each other).

```python
from voltnir_sdk import ExeRestriction, Side, ValidityRes, new_client_order_id

leg = dict(
    delivery_area_id="10YBE----------2",
    quantity_sub_mw=1000,
    exe_restriction=ExeRestriction.FOK,
    validity_res=ValidityRes.VALIDITY_NON,
)
basket_ref = new_client_order_id()
resp = client.submit_basket(
    list_exec_inst="linked",
    basket_ref=basket_ref,
    orders=[
        dict(leg, client_order_id=new_client_order_id(), side=Side.BUY,
             contract_id=12345, price_cents=5000),
        dict(leg, client_order_id=new_client_order_id(), side=Side.SELL,
             contract_id=12346, price_cents=5100),
    ],
)
for order in resp.orders:
    print(order.client_order_id, order.state, order.err_code)
```

The gateway checks every order before anything is sent and refuses the whole
basket if one fails: `BASKET_REFUSED`, whose message lists each failing order
as `[<index>] <CODE>: <text>`. A linked basket is checked on its net effect on
position and slot limits, because it fills whole or not at all. An exchange
rejection of the list, or the kill of a linked list, is each order's `state`
and `err_code`, never an exception. The exchange rejects a `valid` or `linked`
list whole, so every order of one it refuses is `REJECTED`, an order the
refusal did not name with the refusal's own `reason` and `err_code`. Each order
carries `basket_ref` on `OwnOrder`, and an order that survives a gateway
restart still carries it. Whether the orders survive is the exchange's
decision: it may delete every order of a basket when the gateway logs out, a
restart included, although on the exchange's simulator it kept them through a
restart. `cancel_basket(basket_ref)` cancels
every resting order of the basket, one cancel per order with its own result.

| Checked locally | Why |
|---|---|
| `list_exec_inst` is `none`, `valid` or `linked` | Anything else is refused by the gateway too. |
| 1 to 100 orders | The exchange takes no more than 100 in one entry (`BASKET_EMPTY`, `BASKET_TOO_LARGE`). |
| each order passes the `submit_order` checks | The message leads with the order's index, `[1] ...`. |
| no repeated `client_order_id` | `BASKET_DUPLICATE_ORDER_ID`. |
| every order of a linked basket is FOK | `BASKET_LINKED_REQUIRES_FOK`. |
| no `delivery_end` | A basket does not create a user-defined block (`BASKET_BLOCK_UNSUPPORTED`). |

## TLS

```python
from voltnir_sdk import VoltnirClient

VoltnirClient(host="voltnir.example.com", port=3443, api_key="YOUR_API_KEY",
              tls=True, ca_cert_path="cert.pem")
```

Self-signed dev certs work; point `ca_cert_path` at the PEM Voltnir is
serving. The same file is trusted for an `https` `rest_url` (see
[Report exports](#report-exports-over-rest)).

## Errors

Every RPC raises a typed subclass of `VoltnirError` on failure:

| gRPC status         | Exception            |
|---------------------|----------------------|
| UNAUTHENTICATED     | `Unauthenticated`    |
| PERMISSION_DENIED   | `PermissionDenied`   |
| NOT_FOUND           | `NotFound`           |
| INVALID_ARGUMENT    | `InvalidArgument`    |
| FAILED_PRECONDITION | `FailedPrecondition` |
| ABORTED             | `Aborted` (`OrderChanged` when the order moved under the command, `OrderPending` when the exchange has not yet acknowledged it) |
| UNAVAILABLE         | `Unavailable` (`RequestNotProcessed` on an order call the exchange never received) |
| DEADLINE_EXCEEDED   | `DeadlineExceeded`   |
| INTERNAL            | `Internal`           |
| RESOURCE_EXHAUSTED  | `ResourceExhausted`  |
| CANCELLED           | `Cancelled`          |
| *anything else*     | `VoltnirError` (base) |

The report exports travel over REST and raise the same types from the HTTP
status, plus `ExportBusy` (code `ABORTED`) when the gateway answers `409`
because another export is generating (see
[Report exports](#report-exports-over-rest)).

```python
from voltnir_sdk import VoltnirClient, NotFound

try:
    client.get_contract(area_id="10YBE----------2", contract_id="YOUR_CONTRACT_ID")
except NotFound as e:
    print("no such contract:", e.message)
```

Four error types are deliberately **not** `VoltnirError` subclasses, because
nothing was sent when they are raised. Three are `ValueError` and one a
`RuntimeError`, so an `except VoltnirError` written to handle exchange failures
will **not** catch them. That is the point, but it does mean you have to handle
them:

- **`OrderValidationError`** — every local order check (missing
  `client_order_id`, a delivery area that is not 16 characters, a float in a
  cents field, a zero quantity, an iceberg problem, an FOK/IOC validity clash,
  an out-of-range value). This is what
  `submit_order` raises on a bad argument.
- **`UnitConversionError`** — the conversion helpers, when a value is finer
  than the tick or is the wrong type.
- **`CaCertificateError`** — `ca_cert_path` is missing or is not a PEM
  certificate. Raised at construction, so a bad path fails where the mistake
  is rather than as an opaque TLS handshake error on the first call.
- **`AsyncLoopError`** — `AsyncVoltnirClient` was built outside a running event
  loop, or is being used from a different one than it was built in. A
  `RuntimeError`, since that is what the underlying failure already was.

`ClientClosed` is the exception to the pattern above: it IS a `VoltnirError`,
because a supervisor loop catching `VoltnirError` to reconnect is exactly the
right response to using a closed client.

```python
from voltnir_sdk import OrderValidationError, VoltnirError

try:
    client.submit_order(...)
except OrderValidationError as e:
    ...   # your bug: nothing was sent
except VoltnirError as e:
    ...   # not placed, or (OrderOutcomeUnknown) outcome unknown
```

A call that raises nothing is not proof the order is working: an exchange
refusal of a new order returns normally, with `state == OrderState.REJECTED`
(next section).

### Order errors: rejected, or unknown?

On an order-mutating call the only question that matters is whether the order
might be live. The response state and the exception type answer it.

**Refused by the exchange, no exception** — `submit_order` returns normally
with `state == OrderState.REJECTED` and the exchange's text in `reason` when
the exchange received the new order and refused it. Nothing is resting; fix
and resubmit under a new `client_order_id`. Always check `state`.

**Definitely not live at the terms you asked for** — `InvalidArgument`,
`PermissionDenied`, `FailedPrecondition`, `Unauthenticated`, `NotFound`,
`Aborted`. Safe to fix and retry. The gateway refuses most of these before
anything is sent; on a modify, cancel or cancel-all, `Aborted` also covers the
exchange refusing a request it received.

One caveat on `Aborted` for a modify or cancel: it means *that operation* did
not take effect, **not** that the original order is gone. A rejected modify
leaves the order resting at its original price and size. Retrying is safe;
assuming you are flat is not.

`cancel_all_orders` can fail after part of it took effect. A member-scoped
caller's cancel-all sends one cancel per order, so an error whose message ends
with `(cancel-all incomplete: ...)` follows cancels the exchange acknowledged,
whatever its type — an `Aborted` included. The message says how many of the
targeted orders' cancels the exchange acknowledged and how many may still be
resting, and the error reports `request_definitely_rejected = False` because
part of the request took effect. Calling `cancel_all_orders` again is safe,
since a cancel only removes exposure; confirm the book with `list_orders()`.

**Definitely not applied, retry as-is** — `OrderChanged`, the one `ABORTED` with
a specific answer. The exchange guards every order command with the revision it
was built on, and a fill or another modify can move that revision while your
command is on its way; the exchange then refuses the command outright. The order
is resting exactly as it was, one revision further on, and no exposure changed.
Retry the same call: the gateway rebuilds the command against the revision it
now holds, so the retry is not the request that just failed.

```python
from voltnir_sdk import OrderChanged, new_client_order_id

order_id = new_client_order_id()

try:
    client.cancel_order(client_order_id=order_id)
except OrderChanged:
    client.cancel_order(client_order_id=order_id)   # rebuilt on the new revision
```

Bound the retry rather than looping: an order filling repeatedly can lose the
race more than once, and a cancel may find the order already gone on the next
attempt, which comes back as `NotFound`. `OrderChanged` is a subclass of
`Aborted`, so an existing `except Aborted` still catches it.

**Definitely not applied, retry once acknowledged:** `OrderPending`, the
`ABORTED` a modify or cancel gets when it names an order the gateway has sent
and the exchange has not yet acknowledged (an `ack_only` submit, or one whose
outcome did not arrive in time). There is no exchange order to act on yet, so
the gateway sends nothing. The order may be resting by now; retry once it is
acknowledged, or wait for it on the order stream. On `cancel_all_orders` it
means one or more of your orders were still awaiting acknowledgement: the
message ends with the counts, and calling it again is safe. `OrderPending` is a
subclass of `Aborted`.

**Definitely not processed** — `RequestNotProcessed`, raised for the one
`UNAVAILABLE` the gateway can prove: it published the request in mandatory mode
and the message broker handed it back undelivered, which is the single negative
acknowledgement the exchange protocol offers. Nothing is on the book and there
is nothing to reconcile. Resubmit the identical request, `client_order_id`
included — the gateway frees a key whose only record is a request the exchange
never saw, so the idempotency key keeps working across the outage instead of
having to be replaced.

```python
from voltnir_sdk import RequestNotProcessed

try:
    client.submit_order(client_order_id=order_id, ...)
except RequestNotProcessed:
    client.submit_order(client_order_id=order_id, ...)   # same key, on purpose
```

`RequestNotProcessed` is a subclass of `Unavailable`, so an existing
`except Unavailable` still catches it.

**Unknown, may be live** — `OrderOutcomeUnknown`, raised for
`DEADLINE_EXCEEDED`, `INTERNAL`, `CANCELLED`, `UNKNOWN` and every other
`UNAVAILABLE` on `submit_order`, `modify_order`, `cancel_order`, and
`cancel_all_orders`.

That ambiguity is not the SDK being cautious. The gateway maps its own
post-dispatch M7 acknowledgement timeout to `DEADLINE_EXCEEDED` and keeps the
order pending, because it may well be resting — and a client-side deadline
looks identical on the wire. So:

```python
from voltnir_sdk import OrderOutcomeUnknown

try:
    client.submit_order(client_order_id=order_id, ...)
except OrderOutcomeUnknown as e:
    # e.client_order_id is carried for exactly this call.
    state = client.get_order(client_order_id=e.client_order_id)
    # Only resubmit if reconciliation says it is not there, and then under a
    # new client_order_id. "Reusing a client_order_id", under "Submitting an
    # order", says how long the gateway refuses the old one.
```

A timed-out **cancel** is the dangerous direction: assuming it succeeded is how
a desk carries an exposure it believes is flat.

The order methods' errors also carry `request_definitely_rejected` if you
would rather branch on a flag than on a type. It is `True` only when the request
had no effect on the exchange, so it is `False` for an incomplete
`cancel_all_orders` whatever the error's type. It is meaningful on
`submit_order`, `modify_order`, `cancel_order` and `cancel_all_orders` only; on
every other method it reads `True` whatever happened.

## Long-lived streams: keepalive and resubscribing

The SDK sets HTTP/2 keepalive by default (30s ping, permitted on idle
connections). Without it, a NAT table entry or load-balancer idle timeout drops
a quiet `Watch*` subscription and the iterator blocks **forever** with no
exception — a desk stops receiving fills and cannot tell that from a quiet
market.

Keepalive turns that silence into an error, but **detection takes about 60
seconds and is not tunable downward** — lowering the keepalive intervals does
not shorten it, so plan for a ~60s blind window rather than relying on the
stream to notice faster. It also does not resubscribe for you. The SDK deliberately does not auto-reconnect: only your code knows whether
a gap in the feed means "carry on" or "flatten and stop". Own the loop:

```python
import time
from voltnir_sdk import VoltnirError

while not shutting_down:
    try:
        for event in client.watch_orders(delivery_area="10YBE----------2"):
            handle(event)          # see the snapshot note below
    except VoltnirError as e:
        log.warning("orders stream dropped: %s; resubscribing", e)
        time.sleep(1.0)
```

That loop is right for `watch_orders`, `watch_trades` and the tape. It is
**wrong for `watch_order`** (singular), which ends cleanly when the order
reaches FILLED / CANCELLED / REJECTED — resubscribing there spins forever on a
filled order. Treat a `watch_order` stream end as "done".

**Reset your state on every snapshot.** `watch_orders` / `watch_trades` open
with a `SNAPSHOT` event and then send deltas, and the server re-sends a **fresh
snapshot** if it falls behind. Treating that second snapshot as a delta
accumulates phantom orders:

```python
from voltnir_sdk import OrdersEventType

if event.type == OrdersEventType.SNAPSHOT:
    book = {o.client_order_id: o for o in event.orders}   # replace, do not merge
else:
    apply_delta(book, event)
```

Streams are lazy: the RPC opens on the first iteration, not when you call the
method. A permission error on a gated stream (`watch_state`, `watch_audit_events`)
therefore surfaces at the first `for`, not at the call.

### Message size

gRPC caps received messages; the SDK raises the default to 64 MB because
`list_orders` is not paginated, and a busy desk's order list can exceed gRPC's
own 4 MB. If you still hit `ResourceExhausted`, raise it further:

```python
from voltnir_sdk import VoltnirClient

VoltnirClient(
    host="localhost", api_key="YOUR_API_KEY",
    options=[("grpc.max_receive_message_length", 128 * 1024 * 1024)],
)
```

`options` is a passthrough merged over the SDK defaults; your values win.
Note that gRPC **silently ignores unknown option names**, so a typo produces no
error, no warning and no effect.

Streams release their server-side subscription when you break out of the loop,
on both clients and on any exit path. That matters against a bounded server
pool: a subscription that is never released holds a slot, and once the pool is
full a new subscribe blocks without raising.

## Live streams & audit / M7-error queries

Beyond the order/contract surface, the clients wrap every `Watch*` live stream
and the audit / M7-error query RPCs. Streams are plain iterators (sync) /
async iterators (async); pass `timeout=` for an overall gRPC deadline.

```python
# Polled snapshots: an immediate frame, then one per second.
for snap in client.watch_pnl(timeout=30.0):
    print(snap.per_contract, snap.per_vm)
    break

# The message log: the rows the gateway holds, then each new one.
for item in client.watch_messages(timeout=30.0):
    print(item.json)          # MessageItem carries a JSON row
    break

# Compliance audit + M7 exchange errors (gated by read_audit / read_m7_errors).
events = client.query_audit_events(limit=50, action="permissions_set")
errors = client.query_m7_errors(limit=50, kind="err_resp")

# What the exchange said: breaches, halts, suspensions, failover notices.
notices = client.list_exchange_messages(limit=50, severity="error")
```

| RPC family       | Methods                                                                 |
|------------------|-------------------------------------------------------------------------|
| Order/contract   | `watch_contracts`, `watch_order`, `watch_orders`                        |
| Trades / tape    | `watch_trades`, `watch_public_trades`, `watch_trade_tape` (enriched)    |
| Capacity         | `watch_hub2hub` (unary mirror: `get_hub2hub`)                           |
| Polled snapshots | `watch_pnl`, `watch_state`, `watch_status` (unary mirror: `get_status`) |
| Message log      | `watch_messages` (the rows held at subscribe, then each new one)       |
| Log tails        | `watch_audit_events`, `watch_m7_errors`, `watch_exchange_messages`, `watch_system_log` |
| Audit / M7 query | `query_audit_orders/trades/public_trades/events`, `query_m7_errors`     |
| Exchange messages| `list_exchange_messages`, `watch_exchange_messages`                     |

`watch_audit_events` / `watch_m7_errors` are permission-gated server-side
(`read_audit` / `read_m7_errors`), identical to their unary query RPCs.
`watch_exchange_messages` carries the same `read_m7_errors` gate as its history
(`list_exchange_messages`): the tail and the history are the same rows, so
subscribing is not a way around the gate on reading them.

## Report exports (over REST)

`export_orders`, `export_trades` and `export_audit` download a report of the
order history, the trade history or the compliance audit trail as a file. The
gateway serves reports over its REST API, not gRPC, so
pass the client its REST address as `rest_url` (the gateway's REST port, 3000 by
default; a trailing slash is fine). Every other method ignores it, and an export
on a client without it raises `ValueError` naming `rest_url` before anything is
sent.

```python
from voltnir_sdk import VoltnirClient

with VoltnirClient(host="localhost", port=3443, api_key="YOUR_API_KEY",
                   rest_url="http://localhost:3000") as client:
    with open("trades.csv", "wb") as f:
        for chunk in client.export_trades(
            format="csv",
            from_="2026-09-01T00:00:00Z", to="2026-09-02T00:00:00Z",
        ):
            f.write(chunk)
```

- **What comes back.** The file itself, as `bytes` chunks of up to 64 KiB, in
  order. Write each chunk as it arrives rather than collecting them: a report of
  a busy window is large. `format` is `"json"` or `"csv"`; `from_` / `to` are
  RFC 3339 and both inclusive (`from_` because `from` is a Python keyword).
  Requires the `export_reports` permission, and the rows are the ones the
  matching audit query would serve you for the same window and filters.
- **Filters.** `export_orders` and `export_trades` take the filters of
  `query_audit_orders` and `query_audit_trades`: `area`, `product`,
  `user_code`, `v_member_short_id`, `voltnir_user_short_id` and
  `voltnir_username`, each an exact match, plus `status` on orders and
  `time_basis` on trades. `time_basis="execution"` bounds the window by
  execution time; the default, `"delivery"`, keeps a trade whose delivery
  period overlaps it. An unknown `status` or `time_basis` raises
  `InvalidArgument`, and a `v_member_short_id` outside your member scope
  raises `PermissionDenied`.
- **The audit trail.** `export_audit` takes the same `format`, `from_` and
  `to`, and the filters of `query_audit_events`: `action`, `target_type`,
  `actor_short_id`, `outcome` and `v_member_short_id`, each an exact match, so
  a value no row carries gives an empty file. The rows are the ones
  `query_audit_events` pages for the same caller, window and filters, oldest
  first, so the file is member-scoped as that read is: without `read_orders`
  or `bypass_member_check` it holds only the order rows of your assigned
  members, and a `v_member_short_id` outside your scope raises
  `PermissionDenied`. This export requires `read_audit` as well as
  `export_reports`; missing either raises `PermissionDenied`. A `before` or
  `after` snapshot is a JSON value in a JSON file, and its JSON text in one
  CSV cell.
- **Limits.** One export covers at most 31 days plus one hour: `to` may be at
  most 745 hours after `from_`, counted in the hours that really pass. The
  extra hour is the October clock change, so a whole calendar month always
  fits, even written in local time. A wider window raises `InvalidArgument`
  with the gateway's text, `export range exceeds 31 days`; export a longer
  history as several windows. The gateway also builds one export at a time, for all its
  users together, and queues none: a request made while another is generating
  raises `ExportBusy` with `an export is already running, try again later`.
  Nothing was started, so send it again once the running export is done; the
  slot frees when that report is ready or has failed, not when it is
  downloaded.
- **How it travels.** The SDK posts the request, polls until the gateway has
  built the file (0.25 s apart at first, backing off to 2 s), then streams the
  download. Nothing is sent until you start iterating. The API key goes as the
  same `Authorization: Bearer` header. An `https` `rest_url` trusts
  `ca_cert_path` when given, else the system trust store.
- **Timeouts.** `timeout=` bounds the whole export from the first iteration,
  polling and download included, and raises `DeadlineExceeded`: each socket read
  is cut to what is left of it, and a chunk is handed over as soon as bytes
  arrive, so a slow trickle cannot outlast it. Without it the export takes as
  long as the gateway needs, but a read that receives nothing for 30 s still
  raises `DeadlineExceeded`.
- **Errors.** The gateway's refusal text is the exception's `message`: `400`
  raises `InvalidArgument`, `401` `Unauthenticated`, `403` `PermissionDenied`,
  `404` `NotFound`, `409` (another export is generating) `ExportBusy`, `429`
  (the gateway's per-key request bound) `ResourceExhausted`, a failed export
  (`500`) `Internal`, and any other status the base `VoltnirError` naming it.
  A connection failure, or a download that ends short of the size the gateway
  stated, raises `Unavailable`.
- **Redirects are refused.** Every request carries your API key, so the SDK
  never follows a redirect to another address: a `3xx` raises `VoltnirError`
  naming the status. Point `rest_url` at the gateway itself.

`AsyncVoltnirClient` has the same three methods as async iterators
(`async for chunk in c.export_trades(...)`); every blocking network step runs
in a worker thread, so the event loop keeps serving other tasks.

## Restoring trade history

`restore_trade_history(days=...)` asks the exchange to resend the trade capture
reports it still serves and persists them, backfilling the store after a fresh
install or a gap. Omit `days` to restore the exchange's whole reach; `days=0` is
an explicit empty window, distinct from omitting it. Requires the
`restore_trade_history` permission. Delivery is asynchronous and paced, so the
response returns before the history lands — watch the `SystemState`
`trades_received` / `trades_persisted` counters for progress.

```python
resp = client.restore_trade_history(days=7)
print(resp.chunk_count, resp.effective_days)
```

## When a trade report cannot be read

If the gateway receives an exchange trade report it cannot read, `issues` on
`get_state()` lists `trade_report refused`: a trade the exchange executed is
missing from the gateway's count, so position, cash and P&L are understated
until the missed trade is ingested again. Treat it as a reason to stop adding
exposure and to page someone. Cancels always work.

`admission` on `get_state()` and `get_status()` (and their `watch_*` streams)
says whether new orders and modifies are admitted: `open`, `closed`, or
`degraded`. `degraded` means you are trading on incomplete figures by your own
choice: the desk configured the gateway to keep trading through the fault, or
an operator acknowledged it. The exchange still checks the member's cash limit
on every order; the gateway's own position and cash limits are measured on the
understated figures.

Under the default policy admission closes on the fault. An operator holding
`toggle_trading` can reopen it for the gateway's acknowledgement TTL (1800 s by
default); the acknowledgement ends early when the fault clears, a repeat call
restarts the TTL, and a gateway restart drops it.

While admission is `degraded` the gateway does not reconnect its exchange
session over the fault, and it keeps polling the exchange's throttling status,
which its load check needs fresh to admit an order that adds exposure. Orders
are admitted the moment admission reopens, unless the throttling report went
stale while admission was closed (closed for about the gateway's
`load_management.max_report_age_sec` or longer, 30 s by default; the report
ages from its last poll, not from the close); then an order that adds
exposure can be refused for about two seconds after admission reopens, until
the first throttling poll answers. From then on orders stay admitted until the
trade report is read or the acknowledgement runs out. Any other order-critical
issue still closes admission,
and one that outlasts the gateway's health allowance still makes it reconnect
its exchange session, with admission closed while it does; an acknowledgement
keeps counting down meanwhile. `operational` stays false throughout, so alerts
on it still fire.

```python
if "trade_report refused" in client.get_state().issues:
    resp = client.ack_trade_ingest_fault("balancing; support desk paged")
    print("admission reopened for", resp.ttl_sec, "s")
```

`ack_trade_ingest_fault` raises `Aborted` when no fault is raised, or when the
gateway's private feed is down (no trade report could arrive), and
`InvalidArgument` for an empty reason.

## Verify against a live server

> `verify.py` ships in the **source distribution and the repository, not the
> wheel**. If you installed with `pip install voltnir-grpc-py-sdk` you will not
> have it; clone the repo, or `pip download --no-binary :all:` the sdist.

`verify.py` is a linear smoke runner that exercises the **full gRPC surface
(all 73 RPCs)** against a live server and prints `[PASS]/[FAIL]/[SKIP]` per
step. Use it after starting or upgrading Voltnir to confirm the surface is
healthy.

```bash
python verify.py \
    --host localhost --port 3443 \
    --api-key "$VOLTNIR_KEY" \
    --area 10YBE----------2
```

Read-only by default: every query/getter plus first-frame/subscribe smokes
for all live streams. Permission-gated reads `[SKIP]` cleanly when the key
lacks the permission. Flags:

- `--area` (required): EIC code of a delivery area carried by your
  Voltnir's M7 connection (deployment-specific).
- `--mutate`: also exercise the write surface: a hibernated-order lifecycle
  (submit/modify/get/watch/cancel + cancel-all, never crosses), operator
  `Set*` round-trips (read the current value, set it straight back, no net
  change), and throwaway user + member lifecycles. The test member is
  deleted at the end, but a deleted member keeps its row, so its short id
  stays taken: fine on a sim, not for production keys.
- `--include-restart`: also exercise `Restart`, run dead last (it restarts
  the server). Off by default.
- `--tls --ca cert.pem`: connect over TLS, trusting the given CA PEM.
- `--rest-url URL`: the gateway's REST address. The export steps run over REST
  and `[SKIP]` without it.
- `--watch-events N`: how many `WatchContracts` events to receive before
  cancelling (default 1).
- `--timeout S`: per-RPC timeout in seconds.

Runs read-only by default; `--mutate` and `--include-restart` are opt-in
(the latter exercises the restart RPC, skipped by default so a smoke run
doesn't bounce the gateway).

### The reconciliation pass (`--mutate`)

The most valuable part of a live run, because it is the one path no fake can
verify. It forces a client-side deadline on `submit_order` and then checks the
recovery procedure this README recommends actually works against your gateway:

1. the failure raises `OrderOutcomeUnknown`, **not** `DeadlineExceeded`;
2. `get_order(client_order_id=...)` resolves it to a definitive answer;
3. if the order landed, reusing that `client_order_id` is **refused** — the
   guarantee that makes a retry after an ambiguous failure safe.

If your server answers faster than the probe deadline the pass reports `[SKIP]`
with the reason rather than a green tick, because a pass that never exercised
the path would be the most misleading possible result.

Probe orders are hibernated and priced far below anything crossable, and each
is cancelled on every exit path. A cleanup failure is reported as a FAIL with
the `client_order_id` printed and `CHECK THE BOOK`, never swallowed.

## Testing

Unit tests run against an in-process fake gRPC server (no live backend), so
they exercise the real wire path (request marshalling, status-code
translation, stream iteration) for both clients:

```bash
pip install -e '.[dev]'
pytest
```

| File | What it guards |
|---|---|
| `test_rpcs.py` | Every gRPC-wrapped RPC on both clients, happy / fail / edge, derived from the service descriptor. Fails if the proto gains an RPC with no wrapper. Also asserts filter fields really cross the wire, that the bearer credential is attached to unary *and* streaming calls, and that every method's per-call `timeout=` reaches the wire. |
| `test_rest_export.py` | The REST-backed exports on both clients against a loopback server speaking the gateway's REST export contract: the bytes, the request body, polling, streaming, every mapped status, the timeouts, TLS trust and a free event loop. |
| `test_rest_export_audit.py` | `export_audit` on both clients against the same loopback server: the audit-trail endpoint, its filters as wire fields, every mapped status naming the method, and both permissions in the docstrings. |
| `test_wrapper_field_coverage.py` | Every request field of every wrapper is a named, typed parameter on both clients (a filter is never hidden behind `**kwargs`). |
| `test_units_and_orders.py` | Price/quantity conversion and order construction. Pure, no server: a wrong conversion here is a wrong trade. |
| `test_error_semantics.py` | Rejected-vs-unknown classification on the order path, and the channel defaults. |
| `test_readme_samples.py` | Executes every runnable Python sample in this README. |
| `test_verify_coverage.py` | `verify.py` has a call site for every wrapper, and the runner actually executes. |
| `test_integration_coverage.py` | Every gRPC RPC and every REST-backed method has a happy, a fail and an edge test in the live integration suite below. |
| `test_public_enums.py` | Every proto enum a response carries is exported from `voltnir_sdk` with the proto's own values. |
| `test_docstring_accuracy.py` | Every docstring's "Requires ..." names the method's own permission, and docstrings open on their own method. |
| `test_generated_stubs_public_safe.py` | The vendored stubs carry no internal strings. |

Two properties are worth calling out, because a wire test can miss both
silently:

- **Requests are asserted non-empty.** proto3 does not serialize default values,
  so a test passing `quantity=0` would produce a request byte-identical to one
  where the wrapper had dropped the argument. Dummy values are non-default and
  the received message is checked to carry fields.
- **Auth is asserted.** The fake records call metadata, so changing the bearer
  prefix to lowercase (which the gateway rejects) fails the suite.

`verify.py` is the complementary live-server smoke.

## Running the integration suite

`tests/integration/` drives every RPC against a **real gateway on the EPEX
simulator** and proves each one end to end — happy, fail and edge — where the
offline suite can only prove wire marshalling against a fake. It needs a running
gateway, so it is skipped unless its environment is set; an ordinary `pytest`
runs the offline suite untouched.

Customers smoke a deployment with `verify.py` above. Maintainers run the
integration suite through the gateway's own runner, which boots a gateway on the
simulator, reads its admin key in process, and hands the endpoint to pytest:

```bash
cargo run --bin test_sdk -- -c <sim-config>.yml
```

The runner passes `VOLTNIR_IT_HOST`, `VOLTNIR_IT_PORT`, `VOLTNIR_IT_API_KEY`
and `VOLTNIR_IT_AREA`; set `VOLTNIR_IT_RESTART=1` to include the gateway-restart
test, off by default so a run does not bounce the gateway. The export tests
reach the gateway's REST API at `VOLTNIR_IT_REST_URL`, defaulting to
`http://<VOLTNIR_IT_HOST>:3000`. The Python
interpreter is `VOLTNIR_SDK_PYTHON`, defaulting to the SDK's own virtualenv. The
suite never places an order that can trade: every order rests hibernated and
priced far below anything crossable, and each is cancelled before its test ends.

## Regenerating stubs

When `proto_volt/voltnir_api_v1.proto` changes, run `./scripts/generate.sh`
from the SDK directory (`sdk/python/` in the source repo, `clients/python/`
in the public mirror):

```bash
./scripts/generate.sh
```

The script requires the **pinned** `grpcio-tools` (see `[project.optional-dependencies]`);
it refuses to run on any other version, because a different generator rewrites the
committed stubs wholesale and buries real contract changes in the diff. Set up a
virtualenv once:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
export PATH="$PWD/.venv/bin:$PATH"   # generate.sh resolves `python3` from PATH
```

If `python3 -m venv` fails with a message about `ensurepip` (some distributions
ship Python without it), create the environment without pip and bootstrap it:

```bash
python3 -m venv --without-pip .venv
curl -sS https://bootstrap.pypa.io/get-pip.py | .venv/bin/python
.venv/bin/python -m pip install -e '.[dev]'
```

`scripts/build-sdk-dist.sh` looks for this same `.venv` to run its exact
stub-drift check, so creating it also enables that guard.

The script locates `proto_volt/` automatically (it probes both checkout
layouts; override with `VOLTNIR_PROTO_DIR`), regenerates `_pb2.py` and
`_pb2_grpc.py`, and patches the well-known absolute-import quirk
grpcio-tools emits. Commit the regenerated files alongside your proto edit.

## Cash limits

The desk's cash limit is set by the exchange, per currency pool (`eur`, `gbp`).
`get_cash_limit` and `set_cash_limit` return one object per pool carrying the
exchange's limit and its revision, what the exchange still has available, the
cap you set, and `house_cents`, the effective limit every check uses:

```python
eur = client.get_cash_limit().eur
print(eur.house_cents, eur.breached)
```

`set_cash_limit(cap_cents=...)` sets a cap that can only tighten the exchange's
limit; a cap above it is rejected rather than clamped, so the value you set can
never loosen the exchange's control. `cap_cents=None` removes the cap;
`cap_cents=0` is a real ceiling of zero. A pool limit of zero means no trading in
that pool — there is no mode in which a cash limit means "unbounded".

## Member delivery areas

Each virtual member trades only in the delivery areas its `delivery_areas`
lists, a `DeliveryAreaScope`. `DeliveryAreaScope(all=True)` is every area,
including one the gateway is configured to trade later;
`DeliveryAreaScope(area_ids=[...])` is a list of EIC codes the gateway is
configured to trade. A member created without `delivery_areas` has none and
can place no order until it is given some:

```python
from voltnir_sdk import DeliveryAreaScope

member = client.create_member(name="Intraday NL", max_position=10_000,
                              delivery_areas=DeliveryAreaScope(area_ids=["10YNL----------L"]))
client.patch_member(id=member.id, delivery_areas=DeliveryAreaScope(all=True))
```

Every order action of the member's in another area (a new order, a modify, an
activation or deactivation, a cancel) raises `FailedPrecondition` with
`MEMBER_AREA_NOT_ALLOWED` before anything reaches the exchange, and a
member-scoped `cancel_all_orders` skips the order. Removing an area while the
member still has resting or pending orders in it raises `InvalidArgument`
naming the area and the order count, and changes nothing: cancel those orders
first. Market data is not restricted.

## Layout

(Shown as published in the mirror at `clients/python/`; in the Voltnir source
repo the same tree lives at `sdk/python/`.)

```
clients/python/
├── README.md
├── pyproject.toml
├── scripts/
│   └── generate.sh        regen vendored stubs (auto-locates proto_volt/)
├── src/voltnir_sdk/
│   ├── __init__.py        public exports + __version__
│   ├── client.py          sync VoltnirClient
│   ├── async_client.py    AsyncVoltnirClient
│   ├── units.py           exact Decimal <-> wire-unit conversion
│   ├── _orders.py         order request builders + validation (shared by both clients)
│   ├── _rest_export.py    report exports over the gateway's REST API (shared by both clients)
│   ├── auth.py            bearer-token metadata helper
│   ├── channel.py         channel builders: TLS, keepalive, message limits
│   ├── errors.py          VoltnirError tree + RpcError translator
│   ├── enums.py           Side, OrderType, SelfTradePolicy, ...
│   ├── py.typed           PEP 561 marker: type checkers analyse this package
│   └── _generated/        protoc output (vendored, do not hand-edit)
├── tests/                 pytest suite (in-process fake gRPC server)
└── verify.py              linear smoke runner against a live server
```
