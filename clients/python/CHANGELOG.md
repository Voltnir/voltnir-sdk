# Changelog

Notable changes to `voltnir-grpc-py-sdk`. Versions follow
[SemVer](https://semver.org): a major bump means the order API changed shape.

## 1.0.1 — 2026-10-14

- **Basket orders.** `submit_basket` enters a list of orders as one basket and
  `cancel_basket` cancels every resting order of one basket. `basket_ref` is the
  basket's idempotency key and comes back on each `OwnOrder`.
- **Trade-report faults.** `ack_trade_ingest_fault` acknowledges a raised
  `trade_report refused` fault and reopens order admission for the gateway's
  acknowledgement TTL.
- **Members.** `delete_member` removes a member that holds no orders, position or
  counted cash; the member is kept as a soft-deleted row.
- **`watch_order`** closes after the snapshot of an order that has already
  finished, and keeps watching a pending order across a re-read.
- **Docs and proto.** The reference, the docstrings and `voltnir_api_v1.proto`
  describe the gateway as it now behaves; the vendored stubs are regenerated.

## 1.0.0 — 2026-10-09

First release. A synchronous `VoltnirClient` and an asynchronous
`AsyncVoltnirClient`, each wrapping every RPC of `voltnir.api.v1.VoltAPI`.

- **Full API coverage.** Every unary, server-streaming and `Watch*` RPC is a
  typed method on both clients, including `restore_trade_history`, which
  backfills the persistent trade store from the exchange's history (an absent
  `days` restores the whole reach; `0` is an empty no-op window).
- **Typed request fields.** Every request field is a named keyword parameter,
  the audit, export and message-log filters included, so a filter is
  discoverable and a mistyped name is rejected rather than silently dropped.
- **Units in the names.** `submit_order` / `modify_order` take `price_cents`
  and `quantity_sub_mw`, `set_cash_limit` takes `cap_cents`; a bare `price=50`
  cannot be mistaken for 50 CCY/MWh accepted as 0.50. Helpers for all four wire
  scales: `price_to_cents` / `cents_to_price`, `quantity_to_sub_mw` /
  `sub_mw_to_quantity`, `eur_to_cents` / `cents_to_eur`, `eur_to_q8` /
  `q8_to_eur` (P&L is EUR x 100_000, not cents).
- **Reconciliation.** `client_order_id` is required on `submit_order` and is
  the key recovery depends on; `OrderOutcomeUnknown` marks a call that failed
  without proving it had no effect, so a retry cannot double a position.
  `OrderChanged` marks a modify or cancel the exchange refused because the
  order's revision moved, which is safe to retry unchanged.
- **Cash limits per pool.** `get_cash_limit` / `set_cash_limit` return one
  object per pool (`eur`, `gbp`) carrying the exchange's limit and revision,
  what it still has available, the cap and the effective limit. A pool limit of
  zero means no trading in that pool; there is no unbounded mode.
- **Typed errors.** Every failure is a `VoltnirError` subclass carrying the RPC
  name and the exchange's detail, and local validation rejects a zero-quantity
  modify, a `display_qty` on a non-iceberg order and FOK/IOC without
  `VALIDITY_NON` before anything reaches the exchange.
- **Claim gauges on the status surface.** `get_status` and `watch_status`
  carry `claims_count` and `claims_qty` (sub-MW), the amendments and
  activations whose added exposure counts against the limits until the
  exchange answers them or their expiry bound passes, and `claims_held_count`
  and `claims_held_qty` for those held past the bound. Set only for a caller
  holding `read_status`.
- **Channel tuning.** HTTP/2 keepalive for long-lived `Watch*` streams and a
  64 MB message ceiling by default, with an `options=` passthrough. Abandoning
  an async stream cancels its server-side subscription.
- **Typing and generated stubs.** `py.typed`, generated `.pyi` stubs and return
  annotations on every method; a `[typing]` extra supplies `types-protobuf`.
- **Published on PyPI** as `voltnir-grpc-py-sdk`: `pip install voltnir-grpc-py-sdk`
  is the primary install path, with project metadata (homepage,
  documentation, source, changelog, mirror) for discoverability.
- **Live integration suite.** `tests/integration/` runs the whole surface
  against a real gateway on the EPEX simulator, proving each RPC end to end. It
  skips cleanly when its environment is not set, so `pytest -q` stays offline.
