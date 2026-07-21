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

### Added
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
