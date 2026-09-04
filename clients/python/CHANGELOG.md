# Changelog

Notable changes to `voltnir-grpc-py-sdk`. Versions follow
[SemVer](https://semver.org): a major bump means the order API changed shape.

## 2.0.0 — unreleased

**Breaking.** See "Migrating to 2.0" in `README.md` for the full table; every
change below fails loudly at the call site rather than altering the meaning of
an existing call.

### Changed
- `submit_order` / `modify_order` take `price_cents` and `quantity_sub_mw`
  instead of `price` and `quantity`. Same wire units as before; the names now
  carry them, because a bare `price=50` reads as 50 CCY/MWh and was silently
  accepted as 0.50.
- `client_order_id` is required on `submit_order`. It is the key reconciliation
  depends on after an ambiguous failure; `new_client_order_id()` generates one.
- `modify_order` and `patch_member` accept plain Python values and wrap the
  protobuf `Int64Value` / `UInt32Value` types internally. Repricing previously
  failed with a bare `TypeError` unless the caller imported
  `google.protobuf.wrappers_pb2`.
- `set_cash_limit` takes `cap_cents` instead of `cents`. The desk's cash limit
  now comes from the exchange; the value passed here is a cap that only ever
  tightens it, and one above the exchange's limit is rejected rather than
  clamped. `cap_cents=None` removes the cap; `cap_cents=0` is a real ceiling of
  zero.
- `get_cash_limit` / `set_cash_limit` return one object per pool (`eur`, `gbp`)
  carrying the exchange's limit and its revision, what the exchange still has
  available, the cap, and the effective limit every check uses — in place of the
  flat `cents` / `gbp_cents` pair.

### Added
- `list_exchange_messages` / `watch_exchange_messages`, the exchange's own
  message feed: cash-limit breaches, market and delivery-area halts, member
  suspensions, failover notices, automated order transfers. The history shares
  the `read_m7_errors` gate; the live tail is authenticated-only and also
  carries the messages the exchange does not persist.
- `OrderOutcomeUnknown`, raised when an order call fails without proving it had
  no effect. Distinguishing this from a definite rejection is what stops a
  retry doubling a position.
- `ClientClosed`, `ResourceExhausted`, `Cancelled`, `OrderValidationError`,
  `CaCertificateError`, `AsyncLoopError`.
- Unit helpers for all four wire scales: `price_to_cents` / `cents_to_price`,
  `quantity_to_sub_mw` / `sub_mw_to_quantity`, `eur_to_cents` / `cents_to_eur`,
  and `eur_to_q8` / `q8_to_eur`. P&L is EUR x 100_000, not cents.
- Channel tuning: HTTP/2 keepalive and a 64 MB message ceiling by default, with
  an `options=` passthrough. Without keepalive a quiet stream behind NAT died
  silently; gRPC's own 4 MB default failed a large `list_contracts` with no
  client-side fix.
- `py.typed`, generated `.pyi` stubs, and return annotations on every method. A
  `[typing]` extra supplies `types-protobuf`, without which responses are `Any`.
- `__version__`.

### Removed
- `get_cash_fail_closed` / `set_cash_fail_closed`. A cash limit is always
  enforced: a pool limit of zero means no trading in that pool, and there is no
  mode in which it means "unbounded".

### Fixed
- Abandoning an async stream leaked the server-side subscription, which against
  a bounded server pool eventually blocked new subscribes with no exception.
- Local validation now rejects a zero-quantity modify, a `display_qty` on a
  non-iceberg order, and FOK/IOC without `VALIDITY_NON` — each of which
  previously reached the exchange.
- Wrong-type arguments name the field, the expected wire type and the value,
  instead of surfacing protobuf's own message, which named none of them.

## 1.0.0
Initial release.
