# voltnir Python SDK (`voltnir_sdk`)

Python SDK for the Voltnir external gRPC API (`voltnir.api.v1`). It is the client
library for integrating with a Voltnir EPEX M7 trading gateway.

Wraps the gRPC stubs with sync **and** async client facades, bearer-token
auth, plaintext or TLS channels, and typed exceptions for every gRPC status
code Voltnir returns.

| | |
|---|---|
| Distribution name | `voltnir-grpc-py-sdk` (what you pin in `requirements.txt`) |
| Import name | `voltnir_sdk` |
| Version | `2.0.0` — also available as `voltnir_sdk.__version__` |
| Requires | Python 3.10+ |
| Changes | `CHANGELOG.md` |

## Install

Install directly from the public repository, GitHub or the Codeberg mirror:

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

    for event in client.watch_contract(area_id=first.area_id, contract_id=first.contract_id):
        print(event.type, event.contract.last_price)   # last_price is CENTS
        break
```

## Quickstart: async

Build the client **inside** the loop that will use it. `grpc.aio` binds the
channel to the running loop at construction, so a module-level or DI-container
singleton fails on first use; the SDK now refuses this at construction with
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
        async for event in c.watch_contract(area_id=first.area_id, contract_id=first.contract_id):
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
| Realized / unrealized P&L | `sint64` | **x 100 000** | `eur_to_q8` / `q8_to_eur` |

### Sending: the order path takes wire units directly

`submit_order` and `modify_order` take `price_cents` and `quantity_sub_mw` —
the same units the REST, gRPC and WebSocket docs specify, and the same units
every response carries. An algo holding its book in minor units never converts.

The parameter **names carry the unit deliberately**. A bare `price=50` reads as
50 CCY/MWh and would be silently accepted as 0.50 — legal, unrejectable, and a
100x error, because the gateway's only size guard is `quantity != 0`.
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
| `Member.cash_limit` / `eur_*_cents` / `gbp_*_cents`, `CashLimitStatus.*_cents`, `CashLimitResponse.cents` | x 100 | `cents_to_eur` |
| `Contract.best_bid` / `best_ask` | x 100 | `cents_to_price` |
| `PnlSnapshot` `avg_open_px` / `mark_px` | x 100 | `cents_to_price` |
| `GetHub2HubResponse` `atc_out` / `atc_in` | x 1 000 | `sub_mw_to_quantity` |
| **`CashLimit` (from `get_cash_limits`) — `current_limit`, `configured_limit`** | **NOT fixed. Divide by `10 ** dec_shft`** | see below |
| **`ContractPnl.realized_pnl` / `unrealized_pnl`** | **x 100 000** | **`q8_to_eur`** |

### The two traps worth naming

**P&L is not cents.** `realized_pnl` is EUR x 100 000 — the proto calls it "q8",
which here means x 10^5, *not* x 10^8. Reading it with `cents_to_eur` overstates
by 1000x, and both readings look like real money:

```python
>>> q8_to_eur(1_234_500)      # correct
Decimal('12.345')
>>> cents_to_eur(1_234_500)   # WRONG for P&L
Decimal('12345')
```

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
pip install "voltnir-grpc-py-sdk[typing]"     # adds types-protobuf
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
`contract_id=contract.contract_id` is wrong and is now a type error rather than
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
    VoltnirClient, Side, OrderOutcomeUnknown, new_client_order_id,
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
    except OrderOutcomeUnknown:
        # The order MAY be resting. Never resubmit blindly here.
        state = client.get_order(client_order_id=order_id)
        ...
```

Identify the contract with `contract_id`, or with both `product` and
`delivery_start`.

### What the SDK checks before anything is sent

These run locally, so a rejection here is always "definitely not submitted" and
costs no round trip. Several exist because the gateway does **not** catch them:

| Check | Why |
|---|---|
| `client_order_id` present | It is your reconciliation key. Required by the SDK even though the wire allows omitting it. |
| `side` is BUY or SELL | `SIDE_UNSPECIFIED` is rejected by the gateway. |
| contract identified | Either `contract_id`, or both `product` and `delivery_start`. |
| price / quantity are ints | A float means you are thinking in CCY/MWh. `int(50.07)` would be a 100x error dressed as a rounding. |
| quantity > 0 on submit **and on modify** | The gateway guards zero on submit but only checks *presence* on modify, so a zero restatement reaches M7 as a 0.0 MW order. Reachable whenever an order fills completely between your snapshot and your modify — to withdraw, use `cancel_order`. |
| `display_qty_sub_mw` only on ICEBERG | The gateway gates its iceberg checks on the order type but forwards `display_qty` ungated, so a REGULAR order carrying one reaches M7 with neither check applied. |
| ICEBERG requires `display_qty_sub_mw` | The visible peak is mandatory for the type. |
| `display_qty_sub_mw < quantity_sub_mw` | Mirrors the gateway's iceberg rule. |
| FOK / IOC require `validity_res=VALIDITY_NON` | Any other combination is rejected by the gateway, always. Note the member is `VALIDITY_NON`, not `NON` — `NON` exists only on `ExeRestriction`. |
| values fit their wire width | protobuf raises rather than wrapping (a u32 quantity does **not** silently wrap), re-typed as `OrderValidationError` with the field named. |

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

## TLS

```python
from voltnir_sdk import VoltnirClient

VoltnirClient(host="voltnir.example.com", port=3443, api_key="YOUR_API_KEY",
              tls=True, ca_cert_path="cert.pem")
```

Self-signed dev certs work; point `ca_cert_path` at the PEM Voltnir is
serving.

## Errors

Every RPC raises a typed subclass of `VoltnirError` on failure:

| gRPC status         | Exception            |
|---------------------|----------------------|
| UNAUTHENTICATED     | `Unauthenticated`    |
| PERMISSION_DENIED   | `PermissionDenied`   |
| NOT_FOUND           | `NotFound`           |
| INVALID_ARGUMENT    | `InvalidArgument`    |
| FAILED_PRECONDITION | `FailedPrecondition` |
| ABORTED             | `Aborted`            |
| UNAVAILABLE         | `Unavailable`        |
| DEADLINE_EXCEEDED   | `DeadlineExceeded`   |
| INTERNAL            | `Internal`           |
| RESOURCE_EXHAUSTED  | `ResourceExhausted`  |
| CANCELLED           | `Cancelled`          |
| *anything else*     | `VoltnirError` (base) |

```python
from voltnir_sdk import VoltnirClient, NotFound

try:
    client.get_contract(area_id="10YBE----------2", contract_id="YOUR_CONTRACT_ID")
except NotFound as e:
    print("no such contract:", e.message)
```

Two error types are deliberately **not** `VoltnirError` subclasses, because
nothing was sent when they are raised. Both are `ValueError`, so an
`except VoltnirError` written to handle exchange failures will **not** catch
them — which is the point, but it does mean you have to handle them:

- **`OrderValidationError`** — every local order check (missing
  `client_order_id`, a float in a cents field, a zero quantity, an iceberg
  problem, an FOK/IOC validity clash, an out-of-range value). This is what
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
    ...   # the exchange or gateway said no
```

### Order errors: rejected, or unknown?

On an order-mutating call the only question that matters is whether the order
might be live. The exception type answers it.

**Definitely not live at the terms you asked for** — `InvalidArgument`,
`PermissionDenied`, `FailedPrecondition`, `Unauthenticated`, `NotFound`,
`Aborted`. Safe to fix and retry.

One caveat on `Aborted` for a modify or cancel: it means *that operation* did
not take effect, **not** that the original order is gone. A rejected modify
leaves the order resting at its original price and size. Retrying is safe;
assuming you are flat is not.

**Unknown, may be live** — `OrderOutcomeUnknown`, raised for
`DEADLINE_EXCEEDED`, `UNAVAILABLE`, `INTERNAL`, `CANCELLED` and `UNKNOWN` on
`submit_order`, `modify_order`, `cancel_order`, and `cancel_all_orders`.

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
    # Only resubmit if reconciliation says it is not there. Reusing the same
    # client_order_id is rejected while the original is live, so a mistaken
    # retry cannot double your position.
```

A timed-out **cancel** is the dangerous direction: assuming it succeeded is how
a desk carries an exposure it believes is flat.

Every error also carries `request_definitely_rejected` if you would rather
branch on a flag than on a type.

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
method. A permission error on a gated stream (`watch_status`, `watch_audit_events`)
therefore surfaces at the first `for`, not at the call.

### Message size

gRPC caps received messages; the SDK raises the default to 64 MB because a
`list_contracts` on a large delivery area exceeds gRPC's own 4 MB. If you still
hit `ResourceExhausted`, raise it further:

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

Streams release their server-side subscription when you break out of the loop.
On the async client that was once a leak — abandoned subscriptions accumulated
1:1 and, against a bounded server pool, new subscribes would block with no
exception raised. Both clients now cancel on any exit path.

## Live streams & audit / M7-error queries

Beyond the order/contract surface, the clients wrap every `Watch*` live stream
and the audit / M7-error query RPCs. Streams are plain iterators (sync) /
async iterators (async); pass `timeout=` for an overall gRPC deadline.

```python
# Polled snapshots: an immediate frame, then one per second.
for snap in client.watch_pnl(timeout=30.0):
    print(snap.per_contract, snap.per_vm)
    break

# Append-only log tails (no snapshot; seed via the matching query).
for item in client.watch_messages(timeout=30.0):
    print(item.json)          # MessageItem carries a JSON row
    break

# Compliance audit + M7 exchange errors (gated by read_audit / read_m7_errors).
events = client.query_audit_events(limit=50, action="permissions_set")
errors = client.query_m7_errors(limit=50, kind="err_resp")
```

| RPC family       | Methods                                                                 |
|------------------|-------------------------------------------------------------------------|
| Order/contract   | `watch_contract`, `watch_order`, `watch_orders`                         |
| Trades / tape    | `watch_trades`, `watch_public_trades`                                   |
| Polled snapshots | `watch_pnl`, `watch_state`, `watch_status` (unary mirror: `get_status`) |
| Log tails        | `watch_messages`, `watch_audit_events`, `watch_m7_errors`               |
| Audit / M7 query | `query_audit_orders/trades/public_trades/events`, `query_m7_errors`     |

`watch_audit_events` / `watch_m7_errors` are permission-gated server-side
(`read_audit` / `read_m7_errors`), identical to their unary query RPCs.

## Verify against a live server

> `verify.py` ships in the **source distribution and the repository, not the
> wheel**. If you installed with `pip install voltnir-grpc-py-sdk` you will not
> have it; clone the repo, or `pip download --no-binary :all:` the sdist.

`verify.py` is a linear smoke runner that exercises the **full gRPC surface
(all 63 RPCs)** against a live server and prints `[PASS]/[FAIL]/[SKIP]` per
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
  change), and throwaway user + member lifecycles. CreateMember has no
  DeleteMember RPC, so this leaves a deactivated test member behind, fine on
  a sim, not for production keys.
- `--include-restart`: also exercise `Restart`, run dead last (it restarts
  the server). Off by default.
- `--tls --ca cert.pem`: connect over TLS, trusting the given CA PEM.
- `--watch-events N`: how many `WatchContract` events to receive before
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
| `test_rpcs.py` | All 63 RPCs on both clients, happy / fail / edge, derived from the service descriptor. Fails if the proto gains an RPC with no wrapper. Also asserts filter fields really cross the wire, and that the bearer credential is attached to unary *and* streaming calls. |
| `test_units_and_orders.py` | Price/quantity conversion and order construction. Pure, no server: a wrong conversion here is a wrong trade. |
| `test_error_semantics.py` | Rejected-vs-unknown classification on the order path, and the channel defaults. |
| `test_readme_samples.py` | Executes every runnable Python sample in this README. |
| `test_verify_coverage.py` | `verify.py` has a call site for all 63 RPCs, and the runner actually executes. |
| `test_generated_stubs_public_safe.py` | The vendored stubs carry no internal strings. |

Two properties are worth calling out, because both were once silently absent:

- **Requests are asserted non-empty.** proto3 does not serialize default values,
  so a test passing `quantity=0` produced a request byte-identical to one where
  the wrapper had dropped the argument. Dummy values are now non-default and the
  received message is checked to carry fields.
- **Auth is asserted.** The fake records call metadata, so changing the bearer
  prefix to lowercase (which the gateway rejects) fails the suite. It used to
  pass.

`verify.py` is the complementary live-server smoke.

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

## Migrating to 2.0

2.0 changes the order API deliberately, and in a way that **breaks loudly rather
than silently**. Old calls raise `TypeError: unexpected keyword argument` at the
call site; none of them keep working with a changed meaning.

| 1.x | 2.0 |
|---|---|
| `submit_order(price=5007, quantity=1500)` | `submit_order(price_cents=5007, quantity_sub_mw=1500)` (same units, named) |
| `submit_order(...)` without an id | `client_order_id=` is **required** (`new_client_order_id()`) |
| `modify_order(price=Int64Value(value=5100))` | `modify_order(price_cents=5100, quantity_sub_mw=...)` |
| `patch_member(active=BoolValue(value=False))` | `patch_member(active=False)` |
| `except DeadlineExceeded` around a submit | `except OrderOutcomeUnknown` (see Errors) |

Why each one changed:

- **`price` / `quantity` are renamed, not redefined.** The units are unchanged
  (cents and sub-MW, as all three transport docs specify); the names now carry
  them. `price=50` was a legal way to bid 0.50 CCY/MWh with nothing to reject
  it, and the README documented none of this. `price_cents=50` says what it is.
  Non-integer values are now refused rather than truncated.
- **`client_order_id` is required**, though the wire allows omitting it. It is
  the idempotency key that makes recovery from an ambiguous failure possible,
  and a desk should not be able to trade without one by accident.
- **Wrapper types are handled for you.** Repricing previously failed with a bare
  `TypeError` unless you imported `google.protobuf.wrappers_pb2` yourself.
- **Ambiguous failures have their own type.** `DeadlineExceeded` on a submit
  used to look like "it failed"; it never meant that.

Also new, non-breaking: generated type stubs, `__version__`, keepalive and a
64 MB message ceiling by default, and an `options=` passthrough for channel
tuning.

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
│   ├── auth.py            bearer-token metadata helper
│   ├── channel.py         channel builders: TLS, keepalive, message limits
│   ├── errors.py          VoltnirError tree + RpcError translator
│   ├── enums.py           Side, OrderType, SelfTradePolicy, ...
│   ├── py.typed           PEP 561 marker: type checkers analyse this package
│   └── _generated/        protoc output (vendored, do not hand-edit)
├── tests/                 pytest suite (in-process fake gRPC server)
└── verify.py              linear smoke runner against a live server
```
