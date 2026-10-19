# Voltnir Python SDK v1: Reference

> Auto-generated from the Voltnir API reference.

<a id="overview" name="overview"></a>

## Overview

`voltnir_sdk` is the Python client for the Voltnir gRPC API (`voltnir.api.v1.VoltAPI`). It wraps every RPC of the [gRPC reference](grpc_api_v1.md) as a typed method, on a synchronous `VoltnirClient` and an asynchronous `AsyncVoltnirClient` that are identical method for method. The report exports are not RPCs: the gateway serves a report as a file over its [REST API](rest_api_v1.md) only, and `export_orders` and `export_trades` download it from there (see [Paging and exports](#paging)).

| Package | Value |
| --- | --- |
| Distribution name | `voltnir-grpc-py-sdk` (what you pin in `requirements.txt`) |
| Import name | `voltnir_sdk` |
| Version | `1.0.1`, also available as `voltnir_sdk.__version__` |
| Python | 3.10 or later |
| Dependencies | `grpcio` 1.80 or later, `protobuf` 6.33 up to (not including) 8 |
| License | Apache-2.0 |

What the SDK adds on top of the generated stubs:

- **Method per RPC.** `SubmitOrder` is `client.submit_order(...)`. Every request field is a named keyword argument, so a misspelled filter raises `TypeError` instead of being dropped.
- **Units in the argument names.** `price_cents`, `quantity_sub_mw`, `cap_cents`. A float is refused rather than truncated.
- **Local order checks.** Mistakes the gateway would refuse, and a few it would not, are rejected before anything is sent.
- **Typed errors that answer the money question.** After a failed order call, the exception type tells you whether the order may be live.
- **Stream hygiene.** HTTP/2 keepalive for long-lived `Watch*` streams, a 64 MB message ceiling, and cancellation of the server-side subscription when you stop iterating.

This page covers how to use the SDK well. The fields of every request and response message, and each RPC's full error list, are in the [gRPC reference](grpc_api_v1.md); each method in the [method reference](#reference) links to its RPC there. Responses are the generated protobuf messages themselves, so the field names in the gRPC reference are the attribute names you read.

<a id="install" name="install"></a>

## Install

Install from the public repository, on GitHub or the Codeberg mirror. The generated stubs ship in the package, so no `protoc` is needed.

```bash
# PyPI:
pip install voltnir-grpc-py-sdk

# GitHub:
pip install "git+https://github.com/Voltnir/voltnir-sdk.git#subdirectory=clients/python"

# ...or the Codeberg mirror:
pip install "git+https://codeberg.org/Voltnir/voltnir-sdk.git#subdirectory=clients/python"

# Static type checking of responses also needs stubs for protobuf itself:
pip install types-protobuf
```

License holders can also download a versioned tarball from the customer portal and install it with `pip install ./voltnir-python-sdk-<version>`. Each tarball has a `.sha256` companion for `sha256sum -c`.

<a id="connecting" name="connecting"></a>

## Connecting

One client holds one gRPC channel. Open it once, share it across your code, and close it on shutdown. The context manager closes it on both normal and exceptional exit.

```
from voltnir_sdk import VoltnirClient

with VoltnirClient(host="localhost", port=3443, api_key="YOUR_API_KEY") as client:
    me = client.get_me()
    print(me.username, list(me.permissions))

    contracts = client.list_contracts(area_id="10YBE----------2")
    print(len(contracts.contracts), "contracts")
```

#### Constructor arguments

| Argument | Default | Meaning |
| --- | --- | --- |
| `host` | required | Gateway host name or address. |
| `port` | `3443` | The gateway's gRPC port. |
| `api_key` | required | Sent as `authorization: Bearer <key>` on every unary and streaming call. Its permissions decide what each method may do. |
| `tls` | `False` | Plaintext by default. Set `True` for any connection that leaves the host. |
| `ca_cert_path` | `None` | PEM file to trust when `tls=True`, for a private or self-signed certificate. Without it the system roots are used. |
| `timeout` | `10.0` | Default deadline in seconds for **unary** calls. Streams have no deadline by default. `None` means no deadline. |
| `options` | `None` | gRPC channel options, merged over the SDK defaults; your value wins per key. |
| `rest_url` | `None` | The gateway's REST address, for example `"https://gateway.example:3000"`; a trailing slash is fine. Only the report exports use it. An `https` URL trusts `ca_cert_path` when given, else the system roots, whatever `tls` says. Without it an export raises `ValueError` naming `rest_url`. |

#### TLS

```
client = VoltnirClient(
    host="voltnir.example.com", port=3443, api_key="YOUR_API_KEY",
    tls=True, ca_cert_path="cert.pem",
)
```

A `ca_cert_path` that does not exist, or is not a PEM certificate, raises `CaCertificateError` at construction, where the mistake is, rather than an opaque handshake failure on the first call. Putting the gateway behind your own certificate is covered in [Deployment & TLS](deployment_v1.md).

#### Per-call timeouts

Every method that calls the gateway takes a `timeout=` argument that overrides the client default for that one call, so a slow report can have more room without loosening the order path. On a stream it is an overall deadline for the whole subscription, not an idle timeout.

#### Channel options

The defaults are HTTP/2 keepalive (a ping every 30 seconds, permitted on idle connections) and a 64 MB receive ceiling in place of gRPC's 4 MB, because `list_orders` is not paginated and a busy desk's order list can exceed 4 MB. If you still hit `ResourceExhausted`, raise the ceiling:

```
client = VoltnirClient(
    host="localhost", api_key="YOUR_API_KEY",
    options=[("grpc.max_receive_message_length", 128 * 1024 * 1024)],
)
```

> [!WARNING]
> gRPC ignores unknown option names without an error or a warning. A misspelled option has no effect.

#### Closing

`close()` is idempotent. Any call on a closed client raises `ClientClosed`, which is a `VoltnirError`, so a supervisor loop that reconnects on `VoltnirError` handles it too.

<a id="async" name="async"></a>

## The async client

`AsyncVoltnirClient` takes the same constructor arguments and has the same methods. Unary methods are coroutines; streams and the exports are async iterators.

```
import asyncio
from voltnir_sdk import AsyncVoltnirClient

async def main():
    async with AsyncVoltnirClient(host="localhost", port=3443, api_key="YOUR_API_KEY") as c:
        me = await c.get_me()
        print(me.username)
        async for snap in c.watch_status():
            print(snap.trading_enabled)
            break

asyncio.run(main())
```

> [!WARNING]
> **Build the client inside the event loop that uses it.** `grpc.aio` binds the channel to the running loop at construction. Building it at module level, or in a dependency-injection container before the loop starts, raises `AsyncLoopError` at construction; using it from a different loop raises the same error. Create it in your `main()` coroutine and pass it down.

Leaving an `async for` by `break`, an exception or task cancellation cancels the server-side subscription. Against a gateway with a bounded subscription pool this matters: a subscription that is never released holds a slot.

<a id="units" name="units"></a>

## Units

Every price, size and amount on this API is a scaled integer, and there are three scales. A misread is silent, because the wrong answer is always a plausible number. Read this section before you interpret any figure.

| What | Scale | Example | Convert with |
| --- | --- | --- | --- |
| Price (currency per MWh) | x 100 (cents) | `5007` = 50.07 CCY/MWh | `price_to_cents` / `cents_to_price` |
| Quantity, position, size | x 1 000 (sub-MW) | `1500` = 1.5 MW | `quantity_to_sub_mw` / `sub_mw_to_quantity` |
| Cash limits and exposure | x 100 (cents) | `5000000` = 50 000.00 | `eur_to_cents` / `cents_to_eur` |
| Realized and unrealized P&L | x 100 000 ("q8") | `1234500` = 12.345 | `eur_to_q8` / `q8_to_eur` |

#### Sending

`submit_order` and `modify_order` take wire units directly, the same units every response carries, so a strategy that holds its book in minor units never converts. The argument names carry the unit on purpose: a bare `price=50` would read as 50 CCY/MWh and be accepted as 0.50, a legal order the gateway cannot refuse. A non-integer is rejected:

```
>>> client.submit_order(price_cents=50.07, ...)
OrderValidationError: price_cents: expected an int in wire units, got float
50.07. Prices are cents (5000 = 50.00 CCY/MWh) and sizes are sub-MW
(1000 = 1.0 MW); use voltnir_sdk.price_to_cents / quantity_to_sub_mw if you
are holding decimals.
```

#### Reading back

| Field | Scale | Read with |
| --- | --- | --- |
| `OwnOrder.price`, `OwnTrade.px`, `PublicTrade.px`, `ObEntry.price`, `Contract.last_price` / `highest_price` / `lowest_price` / `best_bid` / `best_ask` | x 100 | `cents_to_price` |
| `OwnOrder.quantity` / `initial_quantity` / `hidden_quantity` / `displayed_quantity`, `OwnTrade.qty`, `PublicTrade.qty`, `ObEntry.quantity`, `Contract.best_bid_qty` / `best_ask_qty` | x 1 000 | `sub_mw_to_quantity` |
| `ContractDetail.net_pos`, `ContractPnl.signed_position`, `Member.max_position`, `Member.max_slot_position`, `SystemStatus.order_pos_limit`, `AccountView.slot_limit`, `SlotLimitResponse.house_limit`, every figure of `SlotScopePosition`, `AtcEntry.atc_out` / `atc_in` (the rows of `GetHub2HubResponse.data`) | x 1 000 | `sub_mw_to_quantity` |
| `Member.cash_limit` and its `eur_*_cents` / `gbp_*_cents`, `CashLimitStatus.*_cents`, `CashPool.*_cents` | x 100 | `cents_to_eur` |
| `ContractPnl.avg_open_px` / `mark_px`, and the same fields on the per-member rows of `PnlSnapshot` | x 100 | `cents_to_price` |
| **`ContractPnl.realized_pnl` / `unrealized_pnl`** | **x 100 000** | **`q8_to_eur`** |
| **`CashLimit.current_limit` / `configured_limit`** (from `get_cash_limits`) | **not fixed** | divide by `10 ** dec_shft` |

#### Three traps

**P&L is not cents.** "q8" here means x 105, not x 108. Reading P&L with `cents_to_eur` overstates it 1 000 times, and both readings look like money. The scale is the same in every currency; the row's `currency` field says which pool a figure belongs to. Never add across currencies; read the per-currency `totals` the gateway already sums. P&L is energy-scaled by the contract's delivery duration, so a 15-minute fill is a quarter of its hourly `px x qty`. A trade whose duration is not yet known is left out and counted in `unpriced_trades`, never priced at a guess.

**Size is x 1 000, not x 100.** Applying the price scale to a size is a 10x error, small enough to look like a bad day rather than a bug.

**`get_cash_limits()` has no fixed scale.** It returns the exchange's own per-currency feed, where each row carries its own `dec_shft`. There is no helper because the divisor is data:

```
from decimal import Decimal

for lim in client.get_cash_limits().limits:
    amount = Decimal(lim.current_limit) / (Decimal(10) ** (lim.dec_shft or 0))
```

`SystemStatus` carries `cash_limit` (Voltnir's own state, in cents) next to `cash_limits` (the exchange's raw feed). The names differ by one letter; the scales differ by an arbitrary power of ten.

#### Conversion helpers

```
from voltnir_sdk import (
    price_to_cents, cents_to_price,          # currency per MWh
    quantity_to_sub_mw, sub_mw_to_quantity,  # MW
    eur_to_cents, cents_to_eur,              # cash limits
    eur_to_q8, q8_to_eur,                    # P&L
)

price_to_cents("50.07")      # 5007      -> pass as price_cents
quantity_to_sub_mw("1.5")    # 1500      -> pass as quantity_sub_mw
eur_to_cents("50000")        # 5000000   -> a 50 000 cash cap
q8_to_eur(1_234_500)         # Decimal('12.345')
```

The helpers use `Decimal`, never binary floats, and **refuse a value finer than the tick instead of rounding it**: `price_to_cents("50.005")` raises `UnitConversionError`. A price moved by rounding is invisible in every log. The scale constants are exported as `PRICE_SCALE`, `QUANTITY_SCALE`, `CASH_SCALE` and `PNL_SCALE`.

<a id="orders" name="orders"></a>

## Orders

Every order carries a `client_order_id` you generate. It is your idempotency key and your only way back to the order after an ambiguous failure, so store it before you send.

#### Submitting

```
from voltnir_sdk import OrderOutcomeUnknown, OrderState, Side, new_client_order_id

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
    # The order MAY be resting. Reconcile before doing anything else.
    state = client.get_order(client_order_id=order_id)
```

Identify the contract with `contract_id`, or with both `product` and `delivery_start`. Note that `contract_id` in a `list_contracts` row is a **string** while `submit_order`'s is an **int**: pass `int(contract.contract_id)`.

The gateway refuses a reused `client_order_id` while it holds the original order's record in memory, in any state. The record is not kept for ever: a gateway restart drops every record, the contract sweep about an hour after delivery ends drops a finished order's, and a resubscription to the exchange's order feed frees the keys of filled and deleted orders. A rejected order was never on the market, so a resubscription keeps its record and its key until the contract sweep, or until a restart for an order on a contract the gateway never listed, such as a refused new block order. So the refusal guards against two live orders under one key; it is not a ledger of every key used. Retry a timed-out submission under a new key once reconciliation shows the order is not there; the full rules are under [SubmitOrder](grpc_api_v1.md#rpc-SubmitOrder). `new_client_order_id()` returns a fresh UUID.

#### Hibernated orders

`entry_state="HIBE"` places an order that rests on the gateway but is not exposed to the market, so it cannot fill until you send `modify_order(client_order_id=..., action=ModifyAction.ACTIVATE)`. The default, `""` or `"ACTI"`, is live. Passing `"HIBE"` in the belief that it means "active" leaves an order that never trades.

#### Waiting for the outcome: `ack_only`

By default an order call waits for the exchange's outcome: `submit_order` returns with `state` `ACTIVE` (or another settled state), and `modify_order` / `cancel_order` return with `outcome` `CONFIRMED`. With `ack_only=True` the call returns as soon as the exchange acknowledges receipt, with `state == PENDING` or `outcome == ACKNOWLEDGED`: received, result not yet known. The same pending answer comes back when a waited call's outcome does not arrive inside the gateway's outcome window.

**An exchange refusal of a new order is not an exception.** When the exchange receives the order and refuses it, `submit_order` returns normally with `state == OrderState.REJECTED` and the exchange's text in `resp.reason`. Nothing is resting. Always check `state`: a call that did not raise is not proof the order is working. A refusal by the gateway itself, before anything reaches the exchange, raises (see [Errors and recovery](#errors)), and a refused modify or cancel also raises.

A pending response means you follow `watch_orders` (or poll `get_order`) to learn the result, including a refusal that arrives later. `outcome` is the `Outcome` enum; `CONFIRMED` is its zero value, so compare against `Outcome.ACKNOWLEDGED` rather than testing truthiness.

#### Checked before anything is sent

These checks run locally and raise `OrderValidationError`. Nothing reached the gateway, so the order definitely does not exist.

| Check | Why |
| --- | --- |
| `client_order_id` present | It is the reconciliation key. The SDK requires it although the wire allows omitting it. |
| `side` is `Side.BUY` or `Side.SELL` | Enums are plain ints, so `side=OrderType.ICEBERG` type-checks; this catches it. |
| The contract is identified | Either `contract_id`, or both `product` and `delivery_start`. |
| Price and quantity are ints | A float means the caller is thinking in currency per MWh; `int(50.07)` would be a 100x error dressed as rounding. |
| Quantity above zero, on submit **and** modify | A zero restatement is a 0.0 MW order, and the gateway refuses it on both. It is reachable from correct code when an order fills completely between your snapshot and your modify. To withdraw, cancel. `ACTIVATE` and `DEACTIVATE` restate the order as it rests, so their quantity is held only to being an int that fits its wire field. |
| `display_qty_sub_mw` only on `ICEBERG`, required there, and below the quantity | The visible peak is an iceberg concept, and the gateway refuses it on any other type: there it would describe an exposure the order does not have. |
| `FOK` / `IOC` only with `validity_res=ValidityRes.VALIDITY_NON` | Any other combination is refused by the gateway. The member is `VALIDITY_NON`; `NON` exists only on `ExeRestriction`. |
| Values fit their wire width | protobuf raises instead of wrapping; the SDK re-raises it with the field named. |

#### Repricing: a modify is a full restatement

`modify_order` is not a patch. Both `price_cents` and `quantity_sub_mw` are required, and what you pass becomes the resting order. On a partly filled order, pass the **remaining** quantity; restating the original size re-inflates an exposure you have partly closed. Reuse the order's own `client_order_id`.

```
client.modify_order(
    client_order_id=order_id,
    price_cents=5100,
    quantity_sub_mw=800,     # what is LEFT, not what you started with
)
```

`ModifyAction.ACTIVATE` and `ModifyAction.DEACTIVATE` take neither price nor quantity.

#### Cancelling everything

`cancel_all_orders()` is the per-caller kill switch. Its `deleted` count is the number of cancels the exchange acknowledged, not deletions it has confirmed. Confirm the book with `list_orders()` before you stand down. The firm-wide switch that halts all new trading is `set_trading_allowed(allowed=False)`.

<a id="errors" name="errors"></a>

## Errors and recovery

Every failed call raises a subclass of `VoltnirError` keyed on the gRPC status. Each carries `e.code` (the `grpc.StatusCode`), `e.message` (the gateway's detail) and `e.rpc` (the RPC that raised it).

| gRPC status | Exception |
| --- | --- |
| `UNAUTHENTICATED` | `Unauthenticated` |
| `PERMISSION_DENIED` | `PermissionDenied` |
| `NOT_FOUND` | `NotFound` |
| `INVALID_ARGUMENT` | `InvalidArgument` |
| `FAILED_PRECONDITION` | `FailedPrecondition` |
| `ABORTED` | `Aborted`; `OrderChanged` when the order moved under a modify or cancel |
| `UNAVAILABLE` | `Unavailable`; `RequestNotProcessed` on an order call the exchange provably never received |
| `DEADLINE_EXCEEDED` | `DeadlineExceeded` |
| `INTERNAL` | `Internal` |
| `RESOURCE_EXHAUSTED` | `ResourceExhausted` |
| `CANCELLED` | `Cancelled` |
| anything else | `VoltnirError` |

The report exports travel over REST and raise the same types from the HTTP status, plus `ExportBusy` (code `ABORTED`) for the gateway's `409` when another export is being generated (see [Exports](#paging)).

On `submit_order`, `modify_order`, `cancel_order` and `cancel_all_orders`, the ambiguous statuses (`DEADLINE_EXCEEDED`, `INTERNAL`, `CANCELLED`, `UNKNOWN` and every `UNAVAILABLE` other than `RequestNotProcessed`) raise `OrderOutcomeUnknown` instead of the table's type.

#### Raised without a request being sent

Four exceptions are **not** `VoltnirError`, because nothing was sent. An `except VoltnirError` written for exchange failures does not catch them.

| Exception | Base | Raised when |
| --- | --- | --- |
| `OrderValidationError` | `ValueError` | A local order check fails; also a bad `policy` string on `set_self_trade_policy`. |
| `UnitConversionError` | `ValueError` | A conversion helper gets a value finer than the tick or of the wrong type. |
| `CaCertificateError` | `ValueError` | `ca_cert_path` is missing or not a PEM certificate. |
| `AsyncLoopError` | `RuntimeError` | The async client is built outside a running loop or used from another one. |

```
from voltnir_sdk import OrderValidationError, VoltnirError

try:
    client.submit_order(...)
except OrderValidationError:
    ...   # a bug in the caller: nothing was sent
except VoltnirError:
    ...   # the gateway or the exchange said no, or the outcome is unknown
```

#### After an order call fails: is the order live?

On an order call the only question that matters is whether the order might be live. The exception type answers it.

| Exception | What it means | What to do |
| --- | --- | --- |
| No exception, `resp.state == OrderState.REJECTED` (`submit_order` only) | The exchange received the order and refused it. Nothing is resting. | Read `resp.reason`, fix and resubmit under a **new** `client_order_id`. |
| `InvalidArgument`, `PermissionDenied`, `FailedPrecondition`, `Unauthenticated`, `NotFound`, `Aborted` | Not applied at the terms you asked for. | Fix and retry. A refused modify or cancel leaves the original order resting as it was: the modify failed, the order did not go away. |
| `OrderChanged` (an `Aborted`) | A fill or another modify moved the order's revision while your command was in flight, and the exchange refused it. Nothing changed. | Retry the same call; the gateway rebuilds it against the new revision. Bound the retries. A cancel retried after the order filled comes back `NotFound`. |
| `RequestNotProcessed` (an `Unavailable`) | The message broker returned the request undelivered. The exchange never saw it. | Resubmit the identical request, **same `client_order_id`**: the gateway frees a key whose only record is a request the exchange never received. |
| `OrderOutcomeUnknown` | The order **may be live**. The gateway maps its own exchange-acknowledgement timeout to `DEADLINE_EXCEEDED` and keeps the order pending, and a client-side deadline looks the same on the wire. | Reconcile with `get_order(client_order_id=e.client_order_id)`. Resubmit only if the order is not there, and then under a **new** key. |

```
from voltnir_sdk import NotFound, OrderChanged, OrderOutcomeUnknown

try:
    client.cancel_order(client_order_id=order_id)
except OrderChanged:
    client.cancel_order(client_order_id=order_id)      # rebuilt on the new revision
except OrderOutcomeUnknown as e:
    try:
        found = client.get_order(client_order_id=e.client_order_id)
    except NotFound:
        found = None      # conclusive only if it stays absent: see below
    ...
```

> [!CAUTION]
> **A timed-out cancel is the dangerous direction.** Assuming it succeeded is how a desk carries an exposure it believes is flat. And treat a `NotFound` from `get_order` as conclusive only if it persists: an order still in flight reads as absent for a moment, and resubmitting on that first reading can double the position.

**An incomplete `cancel_all_orders`.** For a member-scoped caller, cancel-all sends one cancel per order. If some are not acknowledged, the error's message ends with `(cancel-all incomplete: ...)` and states how many were acknowledged and how many may still rest, whatever the error type. Calling `cancel_all_orders` again is safe, because a cancel only removes exposure; then confirm with `list_orders()`.

If you would rather branch on a flag than a type, the order methods' errors carry `request_definitely_rejected`. It is `True` only when the request had no effect on the exchange, so it is `False` for `OrderOutcomeUnknown` and for an incomplete cancel-all. It is meaningful on `submit_order`, `modify_order`, `cancel_order` and `cancel_all_orders` only: on every other method it reads `True` whatever happened, so a `DeadlineExceeded` on `set_trading_allowed` does not prove the switch was left alone.

<a id="streams" name="streams"></a>

## Live streams

The `Watch*` methods return an iterator (an async iterator on the async client). The RPC opens on the first iteration, not when you call the method, so a permission error on a gated stream surfaces at the first `for`.

#### Reset on every snapshot

`watch_orders` and `watch_trades` open with a `SNAPSHOT` event and then send deltas. If the server falls behind it sends a **fresh snapshot**. Replace your state on every snapshot; merging it as a delta accumulates phantom orders.

```
from voltnir_sdk import OrdersEventType

for event in client.watch_orders(delivery_area="10YBE----------2"):
    if event.type == OrdersEventType.SNAPSHOT:
        book = {o.client_order_id: o for o in event.orders}   # replace, never merge
    else:
        apply_delta(book, event)
```

`OrderEventType` (for `watch_order`, one order) and `OrdersEventType` (for `watch_orders`, your book) differ by one letter. Both are ints, so mixing them up runs without error; match the enum to the stream.

#### Own the resubscribe loop

The SDK does not reconnect for you, because only your code knows whether a gap in the feed means "carry on" or "flatten and stop".

```
import time
from voltnir_sdk import VoltnirError

while not shutting_down:
    try:
        for event in client.watch_orders(delivery_area="10YBE----------2"):
            handle(event)
    except VoltnirError as e:
        log.warning("orders stream dropped: %s; resubscribing", e)
        time.sleep(1.0)
```

> [!WARNING]
> That loop is wrong for `watch_order` (singular). It ends cleanly when the order is filled, cancelled or rejected, and resubscribing to a filled order spins forever. Treat the end of a `watch_order` stream as "done".

#### Dead connections

Without keepalive, a NAT or load-balancer idle timeout can drop a quiet stream and leave the iterator blocked forever with no exception: a desk that stops receiving fills cannot tell that from a quiet market. The SDK's default keepalive turns that silence into an error, but detection takes about 60 seconds and does not get shorter if you lower the keepalive intervals. Plan for a blind window of about a minute.

#### Kinds of stream

| Kind | Methods | How it starts |
| --- | --- | --- |
| Snapshot then deltas | `watch_contracts`, `watch_orders`, `watch_trades` | A `SNAPSHOT` event, then changes; a new snapshot resets state. |
| One order to its end | `watch_order` | Ends by itself at a terminal state. |
| Polled snapshots | `watch_pnl`, `watch_state`, `watch_status` | A full frame at once, then one each second. |
| Message log | `watch_messages` | The rows the gateway's rolling log holds, at once, then each row appended after. |
| Log tails | `watch_audit_events`, `watch_m7_errors`, `watch_exchange_messages`, `watch_system_log` | No snapshot: only rows that arrive after you subscribe. Seed from the matching query. |
| Public tape | `watch_public_trades` | Each `PublicTrade` as it prints. |

`watch_exchange_messages` also carries the messages the exchange marks non-persistent, which are never stored: the `id` key in their `item.json` is `null` and they cannot be fetched later, so a client that needs them must be subscribed when they arrive. Each item is one JSON object in `item.json`; deduplicate on its `msg_id` key when you join the tail with `list_exchange_messages`.

<a id="paging" name="paging"></a>

## Paging and exports

The audit queries, `query_m7_errors` and `list_exchange_messages` return one page per call. Pass the response's `next_cursor` back as `cursor` until it is empty. There is no total count.

```
cursor = None
while True:
    page = client.query_audit_trades(
        date_from="2026-09-01T00:00:00Z", date_to="2026-09-02T00:00:00Z",
        time_basis="execution", cursor=cursor, limit=200,
    )
    for item in page.items:
        handle(item)
    if not page.next_cursor:
        break
    cursor = page.next_cursor
```

On the audit queries a `limit` of `None` (or `0`) is the default page size of 50, capped at 200, and pages come newest first unless you pass `sort_order="ASC"`.

> [!NOTE]
> **`query_audit_trades` windows on delivery time by default.** A `date_from` / `date_to` window selects trades whose contract delivery overlaps it and orders the page by delivery start, so a trade executed a minute ago can land on a later page. Pass `time_basis="execution"` to window on execution time instead.

`list_system_log` pages differently: its `cursor` is an integer, and the response's `next_cursor` is absent (test with `page.HasField("next_cursor")`) when there is no further page. A present `0` is a real position.

#### Exports

`export_orders`, `export_trades` and `export_audit` go over the gateway's [REST export](rest_api_v1.md#post-export-orders), not gRPC, so the client needs `rest_url`. The SDK requests the report, polls until the gateway has built it (0.25 seconds apart at first, backing off to 2 seconds), then yields the file as `bytes` in chunks of up to 64 KiB as they arrive. Write each chunk in order. `format` is `"json"` or `"csv"`; the time range argument is `from_`, because `from` is a Python keyword. One export covers at most 31 days plus one hour (745 hours between `from_` and `to`, so a whole calendar month fits even in local time across the October clock change), and the gateway builds one export at a time for all its users, queueing none. `export_orders` and `export_trades` take the filters of `query_audit_orders` and `query_audit_trades` (`area`, `product`, `user_code`, `v_member_short_id`, `voltnir_user_short_id`, `voltnir_username`, plus `status` for orders and `time_basis` for trades), so a report holds the rows that query pages for the same window and filters; `time_basis` `"execution"` bounds trades by execution time instead of delivery overlap. `export_audit` exports the compliance audit trail through [its REST export](rest_api_v1.md#post-export-events): it takes the `query_audit_events` filters (`action`, `target_type`, `actor_short_id`, `outcome`, `v_member_short_id`, each an exact match), yields the rows that query pages to the same caller for the same window, oldest first, so it is member-scoped as that query is, and needs `read_audit` as well as `export_reports`. A `before` or `after` snapshot is a JSON value in a JSON file and its JSON text in one CSV cell.

```
client = VoltnirClient(
    host="gateway.example", port=3443, api_key="YOUR_API_KEY",
    rest_url="https://gateway.example:3000",
)
with open("trades.csv", "wb") as f:
    for chunk in client.export_trades(
        format="csv",
        from_="2026-09-01T00:00:00Z", to="2026-09-02T00:00:00Z",
    ):
        f.write(chunk)
```

Nothing is sent until you start iterating. `timeout=` bounds the whole export from then on, request, polling and download included, and raises `DeadlineExceeded`: each socket read is cut to what is left of it, and a chunk is handed over as soon as bytes arrive, so a slow trickle cannot outlast it. Without it the export takes as long as the gateway needs, but one read that receives nothing for 30 seconds still raises `DeadlineExceeded`. The gateway's refusals arrive in its own words: `400` as `InvalidArgument`, `401` `Unauthenticated`, `403` `PermissionDenied`, `404` `NotFound`, `409` (another export is being generated: nothing was started, retry once it is done) `ExportBusy`, `429` (the per-key request bound) `ResourceExhausted`, a failed export (`500`) `Internal`, and any other status the base `VoltnirError` naming it. A connection failure, or a download that ends short of the size the gateway stated, raises `Unavailable`.

Every export request carries your API key, so the SDK never follows a redirect: a `3xx` raises `VoltnirError` naming the status. Point `rest_url` at the gateway itself.

<a id="enums" name="enums"></a>

## Enums and messages

The enums are the generated protobuf enums re-exported from `voltnir_sdk`. Their members are plain ints and pass straight into any method.

| Enum | Used by |
| --- | --- |
| `Side` | `submit_order(side=...)`: `BUY`, `SELL` |
| `OrderType` | `submit_order(order_type=...)`, default `REGULAR`; `ICEBERG` needs `display_qty_sub_mw` |
| `ExeRestriction` | `submit_order(exe_restriction=...)`, default `NON`; `FOK`, `IOC` |
| `ValidityRes` | `validity_res`: default `GFS` on `submit_order`; on `modify_order` left unset unless you pass it; `VALIDITY_NON` for FOK and IOC |
| `Outcome` | The `outcome` of `modify_order` / `cancel_order`: `CONFIRMED` (the zero value), `ACKNOWLEDGED` |
| `ModifyAction` | `modify_order(action=...)`: `MODIFY` (default), `ACTIVATE`, `DEACTIVATE` |
| `OrderState` | The `state` of an order in responses and events |
| `ContractState`, `MarkSource` | Contract state; the price source behind a P&L mark |
| `DeliveryRiskSource` | Where the delivery-risk flag in `get_status().cash_limit` came from |
| `AreaClass`, `AreaNameSource` | An area's class and the source of its name in `get_area_table()` |
| `ProductScaleClass` | Whether a product's decimal scale is usable, on `get_system_info().products` |
| `SelfTradePolicy` | The policy in `SelfTradePolicyResponse`. `set_self_trade_policy` takes the string `"observe"` or `"reject"`. |
| `ContractsEventType`, `OrderEventType`, `OrdersEventType`, `TradeEventType`, `TradeTapeEventType` | The `type` of events on `watch_contracts`, `watch_order`, `watch_orders`, `watch_trades` and `watch_trade_tape` |

Two request messages you build yourself: `Holiday`, for `set_holidays`, and `DeliveryAreaScope`, for a member's delivery areas on `create_member` and `patch_member`:

```
from voltnir_sdk import DeliveryAreaScope, Holiday

client.set_holidays(currency="eur", holidays=[
    Holiday(date="2026-12-25", label="Christmas Day"),
    Holiday(date="2026-12-26", label="Boxing Day"),
])
client.create_member(name="Intraday NL", max_position=10_000,
                     delivery_areas=DeliveryAreaScope(area_ids=["10YNL----------L"]))
client.patch_member(id=member_id, delivery_areas=DeliveryAreaScope(all=True))
```

Responses are protobuf messages. On a message field, test presence with `msg.HasField("name")` rather than truthiness: an unset scalar reads as its zero value. `get_order` is the common case, where exactly one of `confirmed` and `pending` is set.

### <a id="trade-states" name="trade-states"></a>Trade states and recall fields

An `OwnTrade` (from `watch_trades` and `get_contract`) carries its exchange `state`. A trade counts for position, cash and P&L in every state but `RGRA` and `CNCL`, including a code not listed here.

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

It also carries the exchange's recall fields, all `str`, each `""` until it applies. A later revision of the trade that omits one keeps the value already reported. The rows of `query_audit_trades` carry the same fields as JSON, `null` where not applicable.

| Field | Meaning |
| --- | --- |
| `recall_req_time` | When a recall of the trade was requested. |
| `recall_granted_time` | When market operations granted the recall. The exchange also sets it when market operations cancel the trade. |
| `recall_rejected_time` | When market operations rejected the recall. |
| `latest_recall_process_time` | Until when market operations can process a recall request. It is a live deadline while a recall is pending (`state` `RREQ` or `RSFA`). |
| `recall_requestor` | Member id of the party that asked for the recall. The exchange sends it to the balancing group of the requesting party when that party is a member known to the exchange. |
| `parent_trade_id` | For a cross-contract trade, the id of its parent trade. The parent itself is never reported. Recalling a trade that carries a `parent_trade_id` recalls the parent and every trade with the same `parent_trade_id` at once. |
| `prearrange_type` | `OTC` for a pre-arranged trade, which cannot be recalled. `OPT` and `PNC` are deprecated exchange values. |

### <a id="recall" name="recall"></a>Recalling a trade

`recall_trade(trade_id, revision_no=None)` asks the exchange to recall one trade (a mistrade); `recall_order_trades(client_order_id)` recalls every trade of an order that is still `ACTI`, sending one request per `parent_trade_id` group at once, because an order that filled in several trades needs one recall per trade inside the exchange's window. Both require `recall_trade` and return a `RecallTradeResponse`. Only a trade this gateway's exchange login placed can be recalled, for a member you may act on.

Read each result's `outcome`: `requested` (the trade moved to a recall state), `submitted` (acknowledged, the decision still to come on `watch_trades`), `refused` (the exchange refused it: `m7_err_code` and `m7_error_key`, for example 2013 `trade_execution_too_long_ago` once the exchange's 5-minute window after execution has passed), `unknown` (no acknowledgement in time: read the trade before asking again; a new recall of it is answered `not_recallable` for 60 seconds after the first was sent, unless the exchange refuses or returns it sooner), `not_recallable` (not `ACTI`, `reason` naming the state, or a recall of the same trade, or of one recalled with it, still awaiting the exchange), `cascaded` (not sent itself, recalled with the trade in `cascaded_with` whose request the exchange took; when that request failed, the trade carries its outcome instead) or `not_sent` (the exchange never received it). On the wire a single-trade recall that is not `requested` or `submitted` fails with its outcome's status and carries the result in trailing metadata; both clients return that result instead of raising. Set the call's `timeout` above the gateway's waits (about 7 s with its defaults); a client-side deadline raises `DeadlineExceeded` with no result, and the recall may have been sent, so read the trade before asking again. A request the gateway refuses outright still raises: `PermissionDenied`, `NotFound`, `InvalidArgument`, or `Aborted` when `revision_no` is behind the trade.

```
result = client.recall_trade("1500000001", revision_no=1).results[0]
if result.outcome == "refused":
    print(result.m7_err_code, result.m7_error_key, result.reason)
```

<a id="typing" name="typing"></a>

## Type checking

The package ships `py.typed`, generated `.pyi` stubs and a return annotation on every method. With the `[typing]` extra installed, mypy and pyright check both your arguments and the response fields you read.

```
error: Argument "contract_id" to "submit_order" has incompatible type "str"; expected "int"
error: "UserProfile" has no attribute "usrename"; maybe "username"?
```

What static checking cannot catch is the wrong enum: every enum member is an `int` at the type level, so `side=OrderType.ICEBERG` type-checks. The order path catches that at runtime before sending. Without `types-protobuf`, arguments are still checked but every response is `Any`, so a misspelled response field passes.

<a id="verify" name="verify"></a>

## Verifying a deployment

`verify.py` exercises all 73 RPCs against a live gateway and prints `[PASS]`, `[FAIL]` or `[SKIP]` per step. Run it after installing or upgrading a gateway.

```
python verify.py --host localhost --port 3443 \
    --api-key "$VOLTNIR_KEY" --area 10YBE----------2
```

It ships in the repository and the source distribution, not in the wheel. It is read-only by default; a read your key lacks the permission for reports `[SKIP]`.

| Flag | Effect |
| --- | --- |
| `--area` | Required. The EIC code of a delivery area your gateway's exchange connection carries. |
| `--mutate` | Also exercises the write surface: a hibernated order that is never exposed, set-it-straight-back round-trips on the operator settings, and throwaway users and members. The test member is deleted at the end, and a deleted member keeps its row, so its short id stays taken. Use it on a simulator, not with production keys. |
| `--include-restart` | Also calls `restart`, last. It restarts the gateway. |
| `--tls --ca cert.pem` | Connect over TLS, trusting the given CA. |
| `--rest-url URL` | The gateway's REST address. The export steps run over REST and report `[SKIP]` without it. |
| `--watch-events N` | How many `watch_contracts` events to take before cancelling (default 1). |
| `--timeout S` | Per-RPC timeout in seconds. |

With `--mutate` it also proves the recovery procedure on this page against your gateway: it forces a client-side deadline on `submit_order`, checks that the failure raises `OrderOutcomeUnknown`, that `get_order` resolves it, and that a landed order's `client_order_id` is refused on reuse. If your gateway answers faster than the probe deadline, that step reports `[SKIP]` with the reason.

<a id="reference" name="reference"></a>

## Method reference

Every method on `VoltnirClient`, grouped as in the [gRPC reference](grpc_api_v1.md). `AsyncVoltnirClient` has the same methods with the same arguments; await the unary ones and `async for` the streams.

Pass arguments by keyword; all but `cancel_all_orders`'s `timeout` are keyword-only. **Bold** arguments are required; every method also takes `timeout`, not listed. Each method name links to its RPC in the gRPC reference, which documents every request and response field, its unit and its errors; the exports link their endpoint in the REST reference instead. The permission column is the base permission; "wider with" names a permission that widens the result without being required. "(desk)" marks an operation also behind the desk-management licence. The full matrix is in [Permissions](grpc_api_v1.md#permissions).

### <a id="ref-orders" name="ref-orders"></a>Orders

| Method | Arguments | Returns | Permission | What it does |
| --- | --- | --- | --- | --- |
| <a id="m-submit_order" name="m-submit_order"></a>[`submit_order`](grpc_api_v1.md#rpc-SubmitOrder) | **client_order_id**, **side**, **delivery_area_id**, **price_cents**, **quantity_sub_mw**, contract_id, product, delivery_start, delivery_end, order_type, exe_restriction, validity_res, entry_state, display_qty_sub_mw, validity_date, pre_arranged_acct, v_member_short_id, ack_only | `SubmitOrderResponse` | `create_order`; wider with `bypass_member_check`, `trade_global` | Place a new order. Units are cents and sub-MW; `client_order_id` is required. See [Orders](#orders). |
| <a id="m-modify_order" name="m-modify_order"></a>[`modify_order`](grpc_api_v1.md#rpc-ModifyOrder) | **client_order_id**, action, price_cents, quantity_sub_mw, display_qty_sub_mw, validity_res, validity_date, v_member_short_id, ack_only | `ModifyOrderResponse` | `modify_order` | Reprice or resize (a full restatement, not a patch), or `ACTIVATE` / `DEACTIVATE` a hibernated order. |
| <a id="m-cancel_order" name="m-cancel_order"></a>[`cancel_order`](grpc_api_v1.md#rpc-CancelOrder) | **client_order_id**, ack_only | `CancelOrderResponse` | `delete_order` | Cancel one resting order. |
| <a id="m-cancel_all_orders" name="m-cancel_all_orders"></a>[`cancel_all_orders`](grpc_api_v1.md#rpc-CancelAllOrders) | none | `CancelAllOrdersResponse` | `delete_order` | Cancel every resting order the caller may act on. `deleted` counts acknowledged cancels. |
| <a id="m-submit_basket" name="m-submit_basket"></a>[`submit_basket`](grpc_api_v1.md#rpc-SubmitBasket) | **list_exec_inst**, **orders**, basket_ref | `SubmitBasketResponse` | `create_order`; wider with `bypass_member_check`, `trade_global` | Enter 1 to 100 orders as one exchange entry: `none`, `valid` or `linked`. Each order takes the `submit_order` arguments. Checked all or none before anything is sent; each order's outcome comes back in request order. |
| <a id="m-cancel_basket" name="m-cancel_basket"></a>[`cancel_basket`](grpc_api_v1.md#rpc-CancelBasket) | **basket_ref** | `CancelBasketResponse` | `delete_order` | Cancel every resting order of one basket the caller may act on, one cancel per order, each with its own result. |
| <a id="m-recall_trade" name="m-recall_trade"></a>[`recall_trade`](grpc_api_v1.md#rpc-RecallTrade) | **trade_id**, revision_no | `RecallTradeResponse` | `recall_trade`; wider with `bypass_member_check`, `trade_global` | Ask the exchange to recall one trade this gateway placed. Returns the result for every outcome; see [Recalling a trade](#recall). |
| <a id="m-recall_order_trades" name="m-recall_order_trades"></a>[`recall_order_trades`](grpc_api_v1.md#rpc-RecallTrade) | **client_order_id** | `RecallTradeResponse` | `recall_trade`; wider with `bypass_member_check`, `trade_global` | Recall every recallable trade of one order at once: one result per trade and `counts`. |
| <a id="m-get_order" name="m-get_order"></a>[`get_order`](grpc_api_v1.md#rpc-GetOrder) | **client_order_id** | `GetOrderResponse` | authenticated; wider with `read_orders` | One order by `client_order_id`: exactly one of `confirmed` / `pending` is set. The reconciliation call. |
| <a id="m-list_orders" name="m-list_orders"></a>[`list_orders`](grpc_api_v1.md#rpc-ListOrders) | delivery_area, contract_id, product, delivery_start, v_member_short_id | `ListOrdersResponse` | authenticated; wider with `read_orders` | Confirmed resting orders, optionally filtered by area, contract, product or member. |

### <a id="ref-market" name="ref-market"></a>Contracts and market data

`list_contracts` is a catalogue for finding contract ids: call it at startup or when a new delivery day appears, and do not poll it. Its rows carry no order book and no prices. One contract's order book comes from `get_contract` or `get_contract_by_delivery`. Live data comes from `watch_contracts`, the same stream as the WebSocket `contracts` stream: name an area and a product to follow the product, or an area and contract ids to follow those contracts.

| Method | Arguments | Returns | Permission | What it does |
| --- | --- | --- | --- | --- |
| <a id="m-list_contracts" name="m-list_contracts"></a>[`list_contracts`](grpc_api_v1.md#rpc-ListContracts) | **area_id** | `ListContractsResponse` | authenticated | The contract catalogue of one delivery area, sorted by delivery start: ids, product, delivery, state and trading phase, with no book and no prices. |
| <a id="m-get_contract" name="m-get_contract"></a>[`get_contract`](grpc_api_v1.md#rpc-GetContract) | **area_id**, **contract_id** | `ContractDetail` | authenticated; wider with `read_orders` | One contract with its order book and your working orders. `contract_id` is a string here. |
| <a id="m-get_contract_by_delivery" name="m-get_contract_by_delivery"></a>[`get_contract_by_delivery`](grpc_api_v1.md#rpc-GetContractByDelivery) | **area_id**, **prod**, **dlvry_start** | `ContractDetail` | authenticated; wider with `read_orders` | The same, looked up by product and delivery start. |
| <a id="m-get_hub2hub" name="m-get_hub2hub"></a>[`get_hub2hub`](grpc_api_v1.md#rpc-GetHub2Hub) | **delivery_area_from**, **delivery_from**, **delivery_to**, delivery_area_to | `GetHub2HubResponse` | authenticated | Cross-border capacity (ATC) out of one area, optionally to one neighbour. |
| <a id="m-list_public_trades" name="m-list_public_trades"></a>[`list_public_trades`](grpc_api_v1.md#rpc-ListPublicTrades) | limit, contract_id, area_id | `ListPublicTradesResponse` | authenticated | Recent public trade tape for an area or a contract. |
| <a id="m-get_area_table" name="m-get_area_table"></a>[`get_area_table`](grpc_api_v1.md#rpc-GetAreaTable) | none | `AreaTable` | authenticated | The exchange's EIC delivery-area reference table. |

### <a id="ref-system" name="ref-system"></a>System reads

| Method | Arguments | Returns | Permission | What it does |
| --- | --- | --- | --- | --- |
| <a id="m-get_state" name="m-get_state"></a>[`get_state`](grpc_api_v1.md#rpc-GetState) | none | `SystemState` | `read_state` | Runtime health: uptime, connectivity and latency telemetry. |
| <a id="m-get_status" name="m-get_status"></a>[`get_status`](grpc_api_v1.md#rpc-GetStatus) | none | `SystemStatus` | authenticated; wider with `read_status` | Trading posture scoped to the caller; desk money and licence need `read_status`. |
| <a id="m-get_throttling" name="m-get_throttling"></a>[`get_throttling`](grpc_api_v1.md#rpc-GetThrottling) | none | `ThrottlingStatus` | authenticated | The exchange's order load-management status and the gateway's own guard. |
| <a id="m-get_system_info" name="m-get_system_info"></a>[`get_system_info`](grpc_api_v1.md#rpc-GetSystemInfo) | none | `SystemInfo` | authenticated | Gateway version, exchange API version and request limits, and the product reference: each product's bounds, decimal scale and block settings (`block_order_product`, `block_maximum_hours`, `dst_block_product`, unset when unpublished). |
| <a id="m-get_pnl" name="m-get_pnl"></a>[`get_pnl`](grpc_api_v1.md#rpc-GetPnl) | v_member_short_id | `PnlSnapshot` | authenticated; wider with `read_pnl` | Derived P&L. Mixes three scales; read [Units](#units) first. |
| <a id="m-get_me" name="m-get_me"></a>[`get_me`](grpc_api_v1.md#rpc-GetMe) | none | `UserProfile` | authenticated | The caller's own user record and permissions. |
| <a id="m-get_my_members" name="m-get_my_members"></a>[`get_my_members`](grpc_api_v1.md#rpc-GetMyMembers) | none | `MemberListResponse` | authenticated | The virtual members assigned to the caller. |
| <a id="m-list_permissions" name="m-list_permissions"></a>[`list_permissions`](grpc_api_v1.md#rpc-ListPermissions) | none | `ListPermissionsResponse` | `manage_users` | The catalogue of assignable permissions. |

### <a id="ref-slot-limit" name="ref-slot-limit"></a>The slot position limit

The slot position limit caps the net MW a desk may hold in one quarter-hour of one delivery area, summing every contract that covers that quarter-hour.

An hour counts its full MW in each of its four quarter-hours, a half-hour in each of its two and a block in every quarter-hour it spans; MW is never divided by duration.

It works alongside the per-contract limit: an order must pass both, and the per-contract limit is unchanged by it.

A slot is one 15-minute delivery period, keyed by its UTC start, so the doubled hour of the October clock change is eight distinct slots.

For each slot the check reads the executed net position and the reachable bounds: `max_long` is the net plus every open buy, and `max_short` the net minus every open sell. An open buy on one contract never offsets an open sell on another. An order is refused only when, in some slot its contract covers, it pushes a bound past the limit and leaves it worse, so an order that reduces the position passes even on a desk that is over.

The House slot limit counts every order and trade on the desk. A member with its own `max_slot_position` is held to that limit as well, counting only its own orders and trades. A member with no slot limit (absent) is held to the House slot limit alone; a limit of `0` is flat-only, not off. Limits are sub-MW (MW × 1000).

Three modes: `off` (the default; the check is never run), `observe` (every order is admitted, and one that `reject` would refuse is written to the audit trail as `slot_limit_would_refuse`) and `reject` (such an order is refused before it reaches the exchange). The `slot_limit` section of `config.yml` seeds a fresh database only; after that the mode and the House slot limit are set at runtime and persisted, and each set writes a `slot_limit_set` audit row carrying the mode and the House limit before and after.

When a delivery window the check needs cannot be placed on the quarter-hour grid, the check fails closed: only cancels and amendments that add no quantity pass, and every other order is refused with `slot_window_unknown`. That is an order on a contract with no window; every order in the area while an open order's contract has none; and every order on a slot a trade with no window can deliver in, which is up to the end of the delivery day after the one the trade executed on (in GB, to 23:00 London two days after it), until then, or every slot of its area when its execution time is unknown too.

The usage read takes a delivery area, a range of at most 48 hours (`[from_ms, to_ms)` in UTC epoch milliseconds, `from_ms` rounded down to the quarter-hour, the 48 hours measured from there) and an optional member. It lists every slot in the range that holds exposure in a scope the caller sees, with, per scope, `net`, `max_long`, `max_short`, the `limit` that applies and the `buy_headroom` and `sell_headroom` left before that limit refuses an order, never below 0, all sub-MW. A caller sees the House scope only with `read_status`, and a member scope only for a member assigned to it and active. The read answers in every mode, `off` included, and reads the same sums the check reads. `watch_slot_positions` is its live form: every message is the full set of slots for the range, never a delta, so a client replaces what it holds. The first message is sent at subscribe; after it, a message is sent only when something in the set changed: at most once per second from fills and orders, plus an immediate message when the slot settings or a member's slot limit change. Each message carries the mode, the House limit (with `read_status` only), the area's `locked` flag and a sequence number `seq` that rises by one with every set the shared computation publishes. A subscriber can see gaps in `seq`: a slow reader skips to the newest set, and on WS a set that shows the caller nothing new is not sent. A gap loses nothing, since every message carries the full set. Every subscriber of the same area, range and scopes shares one computation, on either transport, and a subscriber that reads slowly receives the newest set, not a backlog.

A mode reads back as a `SlotLimitMode`; `slot_limit_mode_name` turns it into `"off"`, `"observe"` or `"reject"`, and reads `SLOT_LIMIT_MODE_UNSPECIFIED` as `"off"`, the default. `set_slot_limit` always sends the mode and the House limit it is given, and refuses any other mode name locally, before anything is sent; the gateway refuses a set that leaves either unset (`INVALID_ARGUMENT`).

**Refusals.** An order the slot limit refuses (mode `"reject"`) raises `FailedPrecondition` from `submit_order` or `modify_order`, with a message starting `slot position limit exceeded:` (`slot_position_limit_exceeded`) or `slot window unknown:` (`slot_window_unknown`). `slot_position_limit_exceeded` names the area, the slot start and end, the side (`long` or `short`), the scope (`house` or the member's short id), the position the order would reach and the limit. `slot_window_unknown` names what has no delivery window: the order's contract, an open order's contract, or a trade. A caller without `read_status`, which cannot see the House limit elsewhere, is not shown the House figures: a refusal by the House slot limit reads `slot position limit exceeded: refused by the desk slot limit, <area> <slot start> to <slot end>, <long|short> side`, and a trade that has no delivery time is not named. A refusal by the member's own slot limit keeps the member's figures. The `order_rejected` audit row carries every field either way.

`get_status` and `watch_status` carry the slot limit on every `AccountView`: `slot_mode` (a `SlotLimitMode`, the same on every account) and `slot_limit` (sub-MW; the House slot limit on the House account, set only with `read_status`, and the member's `max_slot_position` on a member account, unset when it has none).

### <a id="ref-limits" name="ref-limits"></a>Limits and controls

| Method | Arguments | Returns | Permission | What it does |
| --- | --- | --- | --- | --- |
| <a id="m-get_contract_limit" name="m-get_contract_limit"></a>[`get_contract_limit`](grpc_api_v1.md#rpc-GetContractLimit) | none | `ContractLimitResponse` | `read_status` | The per-contract net-position limit, in sub-MW. |
| <a id="m-set_contract_limit" name="m-set_contract_limit"></a>[`set_contract_limit`](grpc_api_v1.md#rpc-SetContractLimit) | **quantity** | `ContractLimitResponse` | `set_position_limit` | Set that limit. `quantity` is sub-MW (MW x 1 000). |
| <a id="m-get_cash_limit" name="m-get_cash_limit"></a>[`get_cash_limit`](grpc_api_v1.md#rpc-GetCashLimit) | none | `CashLimitResponse` | `read_status` | Both cash pools (`eur`, `gbp`): exchange limit, availability, your cap and the effective `house_cents`. |
| <a id="m-set_cash_limit" name="m-set_cash_limit"></a>[`set_cash_limit`](grpc_api_v1.md#rpc-SetCashLimit) | cap_cents, currency | `CashLimitResponse` | `set_cash_limit` | Set or clear the cap on one pool, in cents. It can only tighten the exchange's limit. |
| <a id="m-get_cash_limits" name="m-get_cash_limits"></a>[`get_cash_limits`](grpc_api_v1.md#rpc-GetCashLimits) | none | `GetCashLimitsResponse` | `read_status` | The exchange's raw per-currency cash feed. Not cents: divide by `10 ** dec_shft`. |
| <a id="m-get_holidays" name="m-get_holidays"></a>[`get_holidays`](grpc_api_v1.md#rpc-GetHolidays) | none | `HolidaysResponse` | authenticated | Both bank-holiday calendars that drive the cash-limit settlement window. |
| <a id="m-set_holidays" name="m-set_holidays"></a>[`set_holidays`](grpc_api_v1.md#rpc-SetHolidays) | **currency**, **holidays** | `HolidaysResponse` | `set_cash_limit` | Replace one currency's whole calendar with a list of `Holiday`. |
| <a id="m-add_holiday" name="m-add_holiday"></a>[`add_holiday`](grpc_api_v1.md#rpc-AddHoliday) | **currency**, **date**, label | `HolidaysResponse` | `set_cash_limit` | Add one date to a calendar. |
| <a id="m-remove_holiday" name="m-remove_holiday"></a>[`remove_holiday`](grpc_api_v1.md#rpc-RemoveHoliday) | **currency**, **date** | `HolidaysResponse` | `set_cash_limit` | Remove one date from a calendar. |
| <a id="m-get_trading_allowed" name="m-get_trading_allowed"></a>[`get_trading_allowed`](grpc_api_v1.md#rpc-GetTradingAllowed) | none | `TradingAllowedResponse` | authenticated | Whether trading is enabled. |
| <a id="m-set_trading_allowed" name="m-set_trading_allowed"></a>[`set_trading_allowed`](grpc_api_v1.md#rpc-SetTradingAllowed) | **allowed** | `TradingAllowedResponse` | `toggle_trading` | The firm-wide kill switch. `False` halts all new trading. |
| <a id="m-ack_trade_ingest_fault" name="m-ack_trade_ingest_fault"></a>[`ack_trade_ingest_fault`](grpc_api_v1.md#rpc-AckTradeIngestFault) | **reason** | `AckTradeIngestFaultResponse` | `toggle_trading` | Reopen order admission on incomplete figures while a `trade_report refused` fault is raised, for the acknowledgement TTL. |
| <a id="m-get_self_trade_policy" name="m-get_self_trade_policy"></a>[`get_self_trade_policy`](grpc_api_v1.md#rpc-GetSelfTradePolicy) | none | `SelfTradePolicyResponse` | authenticated | The self-trade prevention policy. |
| <a id="m-get_slot_limit" name="m-get_slot_limit"></a>[`get_slot_limit`](grpc_api_v1.md#rpc-GetSlotLimit) | none | `SlotLimitResponse` | `read_status` | The [slot position limit](#ref-slot-limit)'s mode and House limit; `house_limit` is sub-MW. |
| <a id="m-set_slot_limit" name="m-set_slot_limit"></a>[`set_slot_limit`](grpc_api_v1.md#rpc-SetSlotLimit) | **mode**, **house_limit** | `SlotLimitResponse` | `set_position_limit` | Set both. `mode` is `"off"`, `"observe"` or `"reject"`; anything else raises locally. `house_limit` is sub-MW per quarter-hour; `0` is flat-only, not off. |
| <a id="m-get_slot_positions" name="m-get_slot_positions"></a>[`get_slot_positions`](grpc_api_v1.md#rpc-GetSlotPositions) | **delivery_area**, **from_ms**, **to_ms**, v_member_short_id | `SlotPositionsResponse` | authenticated, member-scoped; wider with `read_status` | Per-quarter-hour usage for one area, at most 48 hours, every figure sub-MW. |
| <a id="m-set_self_trade_policy" name="m-set_self_trade_policy"></a>[`set_self_trade_policy`](grpc_api_v1.md#rpc-SetSelfTradePolicy) | **policy** | `SelfTradePolicyResponse` | `set_self_trade_policy` | Set it to `"observe"` or `"reject"`; anything else raises locally. |
| <a id="m-restart" name="m-restart"></a>[`restart`](grpc_api_v1.md#rpc-Restart) | none | `RestartResponse` | `restart_system` | Restart the gateway. Every open stream drops. |
| <a id="m-restore_trade_history" name="m-restore_trade_history"></a>[`restore_trade_history`](grpc_api_v1.md#rpc-RestoreTradeHistory) | days | `RestoreTradeHistoryResponse` | `restore_trade_history` | Backfill the trade store from the exchange's history. Omit `days` for the whole reach; `0` is an empty window. |

### <a id="ref-users" name="ref-users"></a>Users and members

| Method | Arguments | Returns | Permission | What it does |
| --- | --- | --- | --- | --- |
| <a id="m-list_users" name="m-list_users"></a>[`list_users`](grpc_api_v1.md#rpc-ListUsers) | none | `ListUsersResponse` | `manage_users` (desk) | All users and their permissions. |
| <a id="m-create_user" name="m-create_user"></a>[`create_user`](grpc_api_v1.md#rpc-CreateUser) | **username**, permissions | `CreateUserResponse` | `manage_users` (desk) | Create a user. The response carries its API key once. |
| <a id="m-delete_user" name="m-delete_user"></a>[`delete_user`](grpc_api_v1.md#rpc-DeleteUser) | **user_id** | `Empty` | `manage_users` (desk) | Delete a user. Their key stops working at once. |
| <a id="m-set_permissions" name="m-set_permissions"></a>[`set_permissions`](grpc_api_v1.md#rpc-SetPermissions) | **user_id**, **permissions** | `Empty` | `manage_users` (desk) | Replace a user's permission set; an empty list revokes everything. |
| <a id="m-rotate_api_key" name="m-rotate_api_key"></a>[`rotate_api_key`](grpc_api_v1.md#rpc-RotateApiKey) | **user_id** | `RotateApiKeyResponse` | `manage_users` | Issue a new key and invalidate the old one. The new key is returned once. |
| <a id="m-get_user_members" name="m-get_user_members"></a>[`get_user_members`](grpc_api_v1.md#rpc-GetUserMembers) | **user_id** | `UserMembersResponse` | `manage_users` (desk) | The member UUIDs assigned to a user. |
| <a id="m-set_user_members" name="m-set_user_members"></a>[`set_user_members`](grpc_api_v1.md#rpc-SetUserMembers) | **user_id**, **member_ids** | `Empty` | `manage_users` (desk) | Replace a user's member assignment. |
| <a id="m-list_members" name="m-list_members"></a>[`list_members`](grpc_api_v1.md#rpc-ListMembers) | none | `MemberListResponse` | `manage_members` (desk) | All virtual members with their limits and live cash usage. |
| <a id="m-create_member" name="m-create_member"></a>[`create_member`](grpc_api_v1.md#rpc-CreateMember) | **name**, **max_position**, cash_limit, cash_limit_gbp, max_slot_position, delivery_areas | `Member` | `manage_members` (desk) | Create a virtual member. `max_position` (the per-contract limit) and `max_slot_position` (the member's slot limit; `None` = none, `0` = flat-only) are sub-MW, the cash limits are cents. `delivery_areas` is a `DeliveryAreaScope`; `None` creates the member with no areas, so it can place no order until it is given some. |
| <a id="m-patch_member" name="m-patch_member"></a>[`patch_member`](grpc_api_v1.md#rpc-PatchMember) | **id**, name, max_position, active, cash_limit_cents, cash_limit_gbp_cents, max_slot_position, clear_max_slot_position, delivery_areas | `Empty` | `manage_members` (desk) | Update a member. Only the arguments you pass are sent. `max_slot_position` sets the member's slot limit and `clear_max_slot_position=True` removes it; both at once raises locally. `delivery_areas` replaces the member's areas whole; `InvalidArgument` when it would leave any of the member's open orders outside it. |
| <a id="m-delete_member" name="m-delete_member"></a>[`delete_member`](grpc_api_v1.md#rpc-DeleteMember) | **member_id** | `Empty` | `manage_members` (desk) | Delete a member. `InvalidArgument`, and nothing changes, while it has an open order, a position on a contract whose delivery has not ended, or consumed cash counted until the next booking cut (a charge or a credit), and while the gateway's cash sums cannot be fully priced. Its users are unassigned from it; its orders and trades keep its name, and its `short_id` is never reissued. |

### <a id="ref-audit" name="ref-audit"></a>Audit, logs and exports

| Method | Arguments | Returns | Permission | What it does |
| --- | --- | --- | --- | --- |
| <a id="m-query_audit_orders" name="m-query_audit_orders"></a>[`query_audit_orders`](grpc_api_v1.md#rpc-QueryAuditOrders) | cursor, limit, date_from, date_to, area, product, status, user_code, v_member_short_id, voltnir_user_short_id, voltnir_username, sort_order | `AuditOrdersResponse` | authenticated, member-scoped; wider with `read_orders` | Order history, one page per call. Member-scoped. |
| <a id="m-query_audit_trades" name="m-query_audit_trades"></a>[`query_audit_trades`](grpc_api_v1.md#rpc-QueryAuditTrades) | cursor, limit, date_from, date_to, area, product, user_code, v_member_short_id, time_basis, voltnir_user_short_id, voltnir_username, sort_order, contract_id | `AuditTradesResponse` | authenticated, member-scoped; wider with `read_orders` | Trade history, one page per call. The date window is on delivery time unless `time_basis` says otherwise. `contract_id`: Filter to one contract by its M7 contract id, as the string the trade rows carry. An id no trade carries returns an empty page, not an error. `None` or `""` is no filter. |
| <a id="m-query_audit_public_trades" name="m-query_audit_public_trades"></a>[`query_audit_public_trades`](grpc_api_v1.md#rpc-QueryAuditPublicTrades) | cursor, limit, date_from, date_to, area, product, state, sort_order | `AuditPublicTradesResponse` | `read_audit` | Public-trade history. |
| <a id="m-query_audit_events" name="m-query_audit_events"></a>[`query_audit_events`](grpc_api_v1.md#rpc-QueryAuditEvents) | cursor, limit, date_from, date_to, action, target_type, actor_short_id, outcome, sort_order, v_member_short_id | `AuditEventsResponse` | `read_audit`; wider with `read_orders` | The compliance audit trail, member-scoped: without `read_orders` or `bypass_member_check` only the order rows of your own members. A `system_shutdown` row's `after.writes_lost` holds what that run lost per stream; a `system_unclean_exit` row marks a previous run that ended without one, so writes it held may be missing (see [the audit events reference](rest_api_v1.md#get-audit-events)). |
| <a id="m-query_m7_errors" name="m-query_m7_errors"></a>[`query_m7_errors`](grpc_api_v1.md#rpc-QueryM7Errors) | cursor, limit, date_from, date_to, kind, category, err_code, sort_order | `M7ErrorsResponse` | `read_m7_errors` | The persisted exchange-error log. |
| <a id="m-list_exchange_messages" name="m-list_exchange_messages"></a>[`list_exchange_messages`](grpc_api_v1.md#rpc-ListExchangeMessages) | cursor, limit, date_from, date_to, severity, scope, code, sort_order | `ListExchangeMessagesResponse` | `read_m7_errors` | What the exchange said: breaches, halts, suspensions, failover notices. |
| <a id="m-list_system_log" name="m-list_system_log"></a>[`list_system_log`](grpc_api_v1.md#rpc-ListSystemLog) | cursor, limit, min_level, date_from, date_to | `ListSystemLogResponse` | `read_logs` | The gateway's own diagnostic log. The cursor is an integer. |
| <a id="m-export_orders" name="m-export_orders"></a>[`export_orders`](rest_api_v1.md#post-export-orders) | **format**, **from_**, **to**, area, product, status, user_code, v_member_short_id, voltnir_user_short_id, voltnir_username | `Iterator[bytes]` | `export_reports`; wider with `read_orders`, `bypass_member_check` | Order-history export over REST (needs `rest_url`), yielded as `bytes` chunks of the file. See [Exports](#paging). |
| <a id="m-export_trades" name="m-export_trades"></a>[`export_trades`](rest_api_v1.md#post-export-trades) | **format**, **from_**, **to**, area, product, user_code, v_member_short_id, time_basis, voltnir_user_short_id, voltnir_username | `Iterator[bytes]` | `export_reports`; wider with `read_orders`, `bypass_member_check` | Trade-history export, the same way. |
| <a id="m-export_audit" name="m-export_audit"></a>[`export_audit`](rest_api_v1.md#post-export-events) | **format**, **from_**, **to**, action, target_type, actor_short_id, outcome, v_member_short_id | `Iterator[bytes]` | `export_reports` and `read_audit`; wider with `read_orders`, `bypass_member_check` | Audit-trail export, the same way: the rows `query_audit_events` pages, oldest first. |

### <a id="ref-streams" name="ref-streams"></a>Live streams

| Method | Arguments | Returns | Permission | What it does |
| --- | --- | --- | --- | --- |
| <a id="m-watch_contracts" name="m-watch_contracts"></a>[`watch_contracts`](grpc_api_v1.md#rpc-WatchContracts) | **areas**, products, contract_ids | `Iterator[ContractsEvent]` | authenticated | Contracts by area and product, or by id: a snapshot, then one upsert per changed contract and a delete for one that left the market. An unknown id is absent, not an error. |
| <a id="m-watch_order" name="m-watch_order"></a>[`watch_order`](grpc_api_v1.md#rpc-WatchOrder) | **client_order_id** | `Iterator[OrderEvent]` | authenticated, member-scoped; wider with `read_orders`, `bypass_member_check` | One order. Ends by itself when the order is filled, cancelled or rejected. |
| <a id="m-watch_orders" name="m-watch_orders"></a>[`watch_orders`](grpc_api_v1.md#rpc-WatchOrders) | delivery_area, contract_id, v_member_short_id | `Iterator[OrdersEvent]` | authenticated, member-scoped; wider with `read_orders`, `bypass_member_check` | Your resting orders: a `SNAPSHOT`, then deltas. |
| <a id="m-watch_trades" name="m-watch_trades"></a>[`watch_trades`](grpc_api_v1.md#rpc-WatchTrades) | none | `Iterator[TradeEvent]` | authenticated, member-scoped; wider with `read_orders`, `bypass_member_check` | Your own trades: a `SNAPSHOT`, then new trades. **What the snapshot holds.** It holds the trades of the current cash-exposure window (since the most recent 16:00 booking cut on an ECC business day) and every trade on a contract whose delivery day, in its market's local time, is today or later. A trade recorded without its delivery window is kept for up to seven days after it executed. Earlier trades come from the trade history: [`query_audit_trades`](#m-query_audit_trades). A trade that leaves this set is not announced on the stream; it is absent from the next snapshot. |
| <a id="m-watch_public_trades" name="m-watch_public_trades"></a>[`watch_public_trades`](grpc_api_v1.md#rpc-WatchPublicTrades) | contract_ids | `Iterator[PublicTrade]` | authenticated | The public tape, optionally narrowed to contract ids. |
| <a id="m-watch_trade_tape" name="m-watch_trade_tape"></a>[`watch_trade_tape`](grpc_api_v1.md#rpc-WatchTradeTape) | none | `Iterator[TradeTapeEvent]` | authenticated | The tape with each print's contract metadata resolved: a `SNAPSHOT` of up to the 200 most recent prints, oldest first, then one `UPSERTED` event per print. One row per delivery area a print touches; a print whose contract the gateway no longer holds is left out. |
| <a id="m-watch_pnl" name="m-watch_pnl"></a>[`watch_pnl`](grpc_api_v1.md#rpc-WatchPnl) | v_member_short_id | `Iterator[PnlSnapshot]` | authenticated, member-scoped; wider with `read_pnl` | A `PnlSnapshot` at once, then one per second. |
| <a id="m-watch_slot_positions" name="m-watch_slot_positions"></a>[`watch_slot_positions`](grpc_api_v1.md#rpc-WatchSlotPositions) | **delivery_area**, **from_ms**, **to_ms**, v_member_short_id | `Iterator[SlotPositionsResponse]` | authenticated, member-scoped; wider with `read_status` | Every message the full set for the range: the first at once, then one on change: at most once per second from fills and orders, plus an immediate message when the slot settings or a member's slot limit change. |
| <a id="m-watch_hub2hub" name="m-watch_hub2hub"></a>[`watch_hub2hub`](grpc_api_v1.md#rpc-WatchHub2Hub) | **delivery_area_from**, **delivery_from**, **delivery_to** | `Iterator[Hub2HubEvent]` | authenticated | Live cross-border capacity (ATC) out of one area: a `snapshot`, then `update` and `heartbeat` events; a fresh `snapshot` after falling behind. One snapshot and the end when hub-to-hub is disabled. |
| <a id="m-watch_state" name="m-watch_state"></a>[`watch_state`](grpc_api_v1.md#rpc-WatchState) | none | `Iterator[SystemState]` | `read_state` | A `SystemState` at once, then one per second. |
| <a id="m-watch_status" name="m-watch_status"></a>[`watch_status`](grpc_api_v1.md#rpc-WatchStatus) | none | `Iterator[SystemStatus]` | authenticated; wider with `read_status` | A `SystemStatus` at once, then one per second. |
| <a id="m-watch_messages" name="m-watch_messages"></a>[`watch_messages`](grpc_api_v1.md#rpc-WatchMessages) | none | `Iterator[MessageItem]` | authenticated, member-scoped; wider with `read_orders`, `bypass_member_check` | The system and order-rejection message log: the rows held at subscribe, then each new one. Order rows are your members' only; licence, throttling and M7 client certificate notices reach everyone. |
| <a id="m-watch_audit_events" name="m-watch_audit_events"></a>[`watch_audit_events`](grpc_api_v1.md#rpc-WatchAuditEvents) | none | `Iterator[AuditEventItem]` | `read_audit`; wider with `read_orders` or `bypass_member_check` | Tail of the compliance trail, member-scoped as `query_audit_events` is. No snapshot: seed with `query_audit_events`. |
| <a id="m-watch_m7_errors" name="m-watch_m7_errors"></a>[`watch_m7_errors`](grpc_api_v1.md#rpc-WatchM7Errors) | none | `Iterator[M7ErrorItem]` | `read_m7_errors` | Tail of the exchange-error log. Seed with `query_m7_errors`. |
| <a id="m-watch_exchange_messages" name="m-watch_exchange_messages"></a>[`watch_exchange_messages`](grpc_api_v1.md#rpc-WatchExchangeMessages) | none | `Iterator[ExchangeMessageItem]` | `read_m7_errors` | Tail of the exchange-message feed, including the non-persistent messages the history never holds. Deduplicate on the `msg_id` key of `item.json`. |
| <a id="m-watch_system_log" name="m-watch_system_log"></a>[`watch_system_log`](grpc_api_v1.md#rpc-WatchSystemLog) | none | `Iterator[SystemLogItem]` | `read_logs` | Tail of the gateway's diagnostic log. |

Copyright © 2026 Voltnir B.V. The Voltnir gateway is proprietary software, licensed under separate terms.
