# Voltnir Configuration: config.yml Reference

> Auto-generated from the Voltnir API reference.

## Configuration Overview

Voltnir reads all runtime configuration from a single YAML file passed on the command line. The file is parsed once at startup; a malformed file or a missing required field is fatal: the process logs the parse error and exits before any subsystem starts.

```
voltnir -c config.yml
```

The shipped template is `config.yml.dist`. Copy it to `config.yml` and replace every `<REPLACE_ME>` placeholder with values from your EPEX M7 onboarding pack and your `cert/` directory.

```
cp config.yml.dist config.yml
```

> [!NOTE]
> **Paths are relative to the working directory** voltnir is launched from. Under systemd that directory is the install root (where `config.yml` lives), so the `./cert/…` and `./voltnir.db` defaults resolve there.

#### Top-level sections

| Key | Required | Purpose |
| --- | --- | --- |
| `epex_settings` | yes | EPEX market scope: delivery areas, products, hub-to-hub toggle. |
| `system` | no | Connection-health thresholds; defaults to the documented values if the section is omitted. |
| `epex_connection` | yes | EPEX M7 TLS identity, M7 IDs, environment, and AMQP login credentials. |
| `rest_server` | no | Inbound HTTP REST server bind + enable flag; defaults to enabled on `0.0.0.0:3000` if the section is omitted. |
| `grpc_server` | no | Inbound gRPC server; defaults to enabled on `0.0.0.0:3443` if the section is omitted. |
| `ws_server` | no | Inbound WebSocket transport (peer to REST/gRPC); defaults to enabled on `0.0.0.0:9001` if the section is omitted. |
| `trading_terminal` | no | Embedded terminal SPA server. Enabled by default if the section is omitted; consumes the `ws_server` transport (and binds its host). |
| `database` | no | Audit store backend: `internal` (embedded SQLite at `./voltnir.db`, default) or `postgresql` (external server). |
| `market_data` | no | High-volume capture of the public trade tape + order book frames. Each stream opts in via `persist` (`false`/`postgresql`/`parquet`). |
| `licensing` | no* | License file path. **Section optional, but a valid license is required at startup.* |
| `self_trade` | no | Self-trade (cross-trade) prevention policy. Defaults to `observe`. |
| `cash_limit` | no | Cash-limit currency methodology (GBP delivery areas + per-MWh sell reservation). Defaults to EUR netting everywhere. |

## Secrets & Safety

`config.yml` holds live credentials (AMQP password, the TOTP secret, and M7 identifiers). Treat it like a secret.

> [!WARNING]
> Never commit `config.yml` to version control, and never paste its contents into tickets, chats, or external tools. Edit and share `config.yml.dist` instead; it carries only `<REPLACE_ME>` placeholders.

> [!CAUTION]
> The `totp` field is the **base32 secret**, not a generated 6-digit code. Voltnir derives the time-based code from it at login. Do not paste a code that will expire in 30 seconds.

## epex_settings

EPEX market scope and application-level feature flags. Required.

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `delivery_areas` | list<string> | yes | — | EIC delivery-area codes the instance may trade in, e.g. `10YDE-RWENET---I`. |
| `products` | list<string> | yes | — | M7 product codes eligible for order placement, e.g. `Intraday_Hour_Power`. |
| `enable_hub_2_hub` | bool | no | `false` | When `true`, the hub-to-hub heartbeat monitor is active and dispatches resync requests on staleness. |

```
epex_settings:
  delivery_areas:
    - "10YDE-RWENET---I"
  products:
    - "Intraday_Hour_Power"
  enable_hub_2_hub: false
```

## system

Connection-health thresholds. The whole section is optional; omit it (or leave it empty) and every threshold falls back to its default. Set any field individually to override just that one. The defaults are sensible for production; only tune them if the maintenance log shows false positives.

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `max_ws_pong_age_ms` | int (ms) | no | `15000` | Age of the last WebSocket pong before the connection is flagged unhealthy. Optional; defaults to 15s. |
| `max_wait_time_for_system_health_sec` | int (s) | no | `60` | Seconds the system may stay non-operational before the maintenance loop triggers a controlled shutdown. Optional; defaults to 60s. |
| `order_ack_timeout_ms` | int (ms) | no | `2000` | How long a new-order submission waits for M7 to acknowledge (order-execution report or rejection) before returning a timeout (REST `504` / gRPC `DEADLINE_EXCEEDED`). Optional; defaults to 2s. |
| `disable_trading` | bool | no | `false` | Debug / development hard kill-switch. When `true`, trading is force-disabled: `trade_enabled` always reports false and the runtime trading toggle (REST/gRPC/WS) is rejected with a conflict, so nothing (not the persisted profile, not the API toggle) can turn trading back on. This flag is the absolute authority. Optional; defaults to `false`; omit it in normal operation. |

```
system:
  max_ws_pong_age_ms: 15000
  max_wait_time_for_system_health_sec: 60
  order_ack_timeout_ms: 2000
  disable_trading: false   # debug override; omit in normal operation
```

## epex_connection

EPEX M7 connectivity: TLS client identity, M7 identifiers, the `environment` selector, and the AMQP login credentials. Required. See `cert/README.md` for the PEM files referenced below. The AMQP and WebSocket **endpoints** (host, host_alt, port, virtual_host) are **not** configured here: they are fixed per `environment` (sim/prod) and baked into the binary.

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `cert` | path | yes | — | TLS client certificate PEM presented to M7. |
| `key` | path | yes | — | TLS private key PEM. |
| `application_id` | string | yes | — | M7 application identifier for this instance (onboarding pack). |
| `account_id` | string | yes | — | M7 account identifier used for order submission and session auth. |
| `environment` | `sim` \| `prod` | yes | — | EPEX environment this gateway runs in. **Selects the M7 endpoints** (host/port/virtual_host for both AMQP and WebSocket) and must be permitted by the license's `environment`; a mismatch **refuses startup**. No default; an absent value fails config parsing. |
| `user_id` | string | yes | — | AMQP login username. |
| `password` | string | yes | — | Static component of the AMQP password; a TOTP code is appended at login. |
| `totp` | string | yes | — | Base32-encoded TOTP secret. Not a 6-digit code; the code is generated from it. |
| `extra_ca_path` | path | no | — | Optional PEM bundle of extra trust roots, layered **additively** on top of the bundled CA set + OS native store for **both** the AMQP and WebSocket dials. See the TLS-trust callout below. |

> [!NOTE]
> **Endpoints are not configured.** The AMQP and WebSocket hosts, ports, and virtual-host are fixed per EPEX environment and compiled into the binary. Selecting `environment: sim` or `environment: prod` picks the matching endpoint set. There is no host/port/virtual_host key, and no `v6`/`v7` sub-blocks; `epex_connection` carries only the TLS identity, M7 IDs, environment, and login credentials.

> [!NOTE]
> **extra_ca_path: private/corporate CA escape hatch.** The gateway's default server-trust store is the CA set baked into the binary (so it runs on minimal hosts with no system `ca-certificates`) plus whatever the OS native trust store carries. Both cover only *public* CAs. A deployment behind a corporate MitM TLS-inspection proxy, or one whose M7 chain anchors on a *private* intermediate CA, would otherwise see `UnknownIssuer` on the AMQP dial. Point `extra_ca_path` at a PEM bundle of the additional root(s) and they are trusted on both transports. Behavior: absent → no extra roots; a **set-but-unreadable** path **refuses startup** (the error names the path); a readable file with **no CERTIFICATE blocks** logs a warning and continues on the default roots.

> [!WARNING]
> **Environment binding.** `epex_connection.environment` must match the license's `environment`: a `sim` license runs only on `sim`, a `prod` license only on `prod`, and a `sim_and_prod` license on either. A mismatch (e.g. a production license pointed at the simulator, or a simulator/eval license driving production) **refuses startup**.

```
epex_connection:
  cert: "./cert/client-cert.pem"
  key:  "./cert/client-key.pem"
  application_id: "<REPLACE_ME_APPLICATION_ID>"
  account_id:     "<REPLACE_ME_ACCOUNT_ID>"
  environment: prod
  user_id:  "<REPLACE_ME_AMQP_USER>"
  password: "<REPLACE_ME_AMQP_STATIC_PASSWORD>"
  totp:     "<REPLACE_ME_TOTP_BASE32_SECRET>"
  # extra_ca_path: "./cert/corporate-ca.pem"  # optional, extra trust roots (private/corporate CA)
```

## rest_server

Inbound HTTP REST server. The whole section is optional. Omit it (or leave it empty) and the server starts on `0.0.0.0:3000`. Set any field individually to override just that one. See [the REST API reference](rest_api_v1.md) for the surface it serves.

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `enable` | bool | no | `true` | When `false`, the REST server is not started. Optional; defaults to `true`. |
| `host` | string | no | `0.0.0.0` | IP address to bind (all interfaces by default). |
| `port` | int | no | `3000` | TCP port to listen on. |

```
rest_server:
  enable: true
  host:   "0.0.0.0"
  port:   3000
```

## grpc_server

Inbound gRPC server, independent of REST. The whole section is optional: omit it (or leave it empty) and the server starts on `0.0.0.0:3443`. Set any field individually to override just that one. Plaintext HTTP/2 by default. See [the gRPC API reference](grpc_api_v1.md) for the surface it serves.

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `enable` | bool | no | `true` | When `false`, the gRPC server is not started. Optional; defaults to `true`. |
| `host` | string | no | `0.0.0.0` | IP address to bind. |
| `port` | int | no | `3443` | TCP port, chosen to not collide with the REST default 3000. |
| `tls` | object | no | *none* | Optional in-process TLS. When absent, plaintext HTTP/2 is used. |
| `tls.cert_path` | path | no | — | PEM-encoded server certificate chain (required if `tls` is present). |
| `tls.key_path` | path | no | — | PEM-encoded private key (required if `tls` is present). |

> [!NOTE]
> For production behind a reverse proxy, leave `tls` unset and terminate TLS at the proxy. To terminate TLS in-process, set the `tls` block. Both PEM files are read once at startup; there is no hot-reload, so rotating certs requires a restart.

```
grpc_server:
  enable: true
  host:   "0.0.0.0"
  port:   3443
  # tls:
  #   cert_path: "./cert/grpc-server-cert.pem"
  #   key_path:  "./cert/grpc-server-key.pem"
```

## ws_server

Inbound WebSocket transport, independent of REST and gRPC. The whole section is optional; omit it (or leave it empty) and the server starts on `0.0.0.0:9001`. Set any field individually to override just that one. An end-user transport in its own right; the trading terminal consumes it but no longer gates it. Plain WS (no TLS in-process); terminate TLS at a reverse proxy. See [the WebSocket API reference](ws_api_v1.md) for the surface it serves.

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `enable` | bool | no | `true` | When `false`, the WebSocket server is not started. Optional; defaults to `true`. |
| `host` | string | no | `0.0.0.0` | IP address to bind. |
| `port` | int | no | `9001` | TCP port the live-data WebSocket feed listens on. |

```
ws_server:
  enable: true
  host:   "0.0.0.0"
  port:   9001
```

## trading_terminal

Serves the prebuilt trading-terminal SPA (embedded in the binary). The whole section is optional. Omit it entirely and the SPA is served with `enable` defaulting to `true` on port `8080`. The bind host is not configured here: it is discovered from [`ws_server.host`](#ws_server), since the SPA shares the WebSocket transport's interface. The live-data WebSocket the SPA consumes is configured under [`ws_server`](#ws_server); the SPA discovers the REST and WebSocket ports at runtime via a generated `/config.js`, so one binary works on any host without a rebuild.

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `enable` | bool | no | `true` | When `false`, the SPA server is not started. |
| `port` | int | no | `8080` | TCP port the embedded SPA is served on. The bind host is taken from `ws_server.host`. |

> [!NOTE]
> Changing `port` (or the `ws_server` port) only needs a config edit and a restart; no SPA rebuild.

> [!CAUTION]
> **Exposing this publicly?** The SPA, REST, and WebSocket are served as plain HTTP/WS, so bind them to `127.0.0.1` and terminate TLS at a reverse proxy. See the [Deployment & TLS guide](deployment_v1.md) for the per-port nginx setup and the safety checklist.

```
trading_terminal:
  enable: true
  port:   8080
```

## database

Selects where orders, trades, users, and the audit trail are persisted. Optional: omit the section to use the embedded SQLite store at `./voltnir.db`. A single binary carries every driver; the backend is chosen at runtime.

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `backend` | enum | no | `internal` | `internal` = embedded SQLite file store (historical default); `postgresql` = external PostgreSQL server. |
| `path` | path | no | `./voltnir.db` | SQLite file path for the `internal` backend. |
| `url` | string | no | — | Full PostgreSQL connection URL (`postgres://user:pass@host:port/dbname`). Used verbatim; the discrete fields below are ignored when set. |
| `host` / `port` / `user` / `password` / `dbname` | mixed | no | `— / 5432 / voltnir / — / —` | Discrete PostgreSQL connection fields (used when `url` is absent). `password` is sensitive. For the `postgresql` backend either `url` or at least `host` + `dbname` is required, or startup fails. |
| `max_connections` | int | no | `4` | Connection-pool size (both backends). |
| `audit_retention_days` | int | no | `7` | Days to retain compliance audit-event rows before the hourly prune task deletes them. `0` = keep forever. Both backends. Negative values are rejected at startup. |
| `m7_errors_retention_days` | int | no | `7` | Days to retain M7 exchange-error rows before the hourly prune task deletes them. `0` = keep forever. Both backends. Negative values are rejected at startup. |

> [!NOTE]
> Omitting `database` entirely keeps the historical behavior: the embedded SQLite store at `./voltnir.db`.

```
database:
  # internal (SQLite), the default:
  backend: internal
  path: "./voltnir.db"

  # …or an external PostgreSQL server:
  # backend: postgresql
  # url: "postgres://voltnir:secret@db-host:5432/voltnir"
  # # or the discrete fields:
  # host: "db-host"
  # port: 5432
  # user: "voltnir"
  # password: "secret"
  # dbname: "voltnir"
  # max_connections: 4

  # Retention (both backends; hourly prune, 0 = keep forever):
  # audit_retention_days: 7
  # m7_errors_retention_days: 7
```

## market_data

High-volume market-data capture: the **public trade tape** (`public_trades`) and **order book frames** (`order_book`). Two independent streams, each opting in via `persist` (`false` / `postgresql` / `parquet`) with its own retention; both share the writer plumbing (`channel_capacity` / `batch_size`). Optional; omit the section (or leave both `persist: false`) to capture nothing; the live in-memory feeds are untouched. This is **separate** from [`database`](#database) and off its parity contract: a `postgresql` stream is queryable via the audit endpoints, while a `parquet` stream is **export-only** (rotating files on disk; the audit query returns an empty page for it). On a full writer channel rows are dropped (logged), never blocking the feed.

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `channel_capacity` | int | no | `65536` | Bounded writer-channel size, shared by both streams. Generously sized so bursts are absorbed before drop-on-full backpressure. Must be > 0 (rejected at startup). |
| `batch_size` | int | no | `256` | Rows accumulated per flush (one DB transaction or one Parquet row group), shared by both streams; or flushed on the periodic timer, whichever first. Must be > 0 (rejected at startup). |
| `public_trades.persist` | enum | no | `false` | `false` / `postgresql` / `parquet`. `postgresql` persists into (and is queried from) the main `database`, which must itself be `backend: postgresql`. `parquet` writes export-only files (audit query returns empty). |
| `public_trades.retention_days` | int | no | `7` | Days of tape to keep; an hourly task drops whole expired units. `0` = keep forever. |
| `public_trades.parquet` | block | no* | — | Parquet sink config (`path`, `rotation_secs` default `3600`, `max_rows_per_file` default `1000000`). *Required when `public_trades.persist: parquet`. |
| `order_book.persist` | enum | no | `false` | `false` / `postgresql` / `parquet`. Order book capture is **never** queryable via the API (replay/backtest export only). `postgresql` uses a `postgres` override or inherits the main `database` Postgres connection. |
| `order_book.retention_days` | int | no | `0` | Days of frames to keep; `0` = keep forever. Whole-unit drops only (Postgres daily partitions via `DETACH CONCURRENTLY` + `DROP`, or Parquet files), never a row-by-row `DELETE`. Postgres backend requires **PostgreSQL 14+**. |
| `order_book.postgres` | block | no* | — | Postgres connection override (same shape as `database`). When omitted the main `database` Postgres connection is inherited (requires `database.backend: postgresql`). *Block or inheritance required for `order_book.persist: postgresql`. |
| `order_book.parquet` | block | no* | — | Parquet sink config (same fields as above). *Required when `order_book.persist: parquet`. |

> [!NOTE]
> **Parquet is export-only.** A `parquet` stream writes rotating `part-<ts>.parquet` files (closed + atomically renamed from a `.inprogress` temp on rotation, so only complete files are ever visible). There is no read-back API; query the files with your own offline tools (DuckDB, pandas, Spark). The audit endpoints ([/audit/public_trades](rest_api_v1.md)) return an empty page for a parquet-configured tape, exactly as they do on a SQLite audit store.

> [!CAUTION]
> **These streams are high-volume.** The order book delta feed runs at hundreds of thousands of frames per hour, and the public trade tape is the full market-wide feed for your assigned products. Size the Postgres table / Parquet disk for the write load and set `retention_days` to bound disk growth. Drops happen at whole-unit granularity (daily partitions / files) so retention never stalls the writer. `public_trades.persist: postgresql` requires a PostgreSQL `database` backend (rejected at startup on `internal`); a dropped order book frame leaves a `sequence_number` gap a replay reader can detect.

```
market_data:
  # Shared writer plumbing (defaults shown):
  channel_capacity: 65536
  batch_size: 256

  # Market-wide public trade tape:
  public_trades:
    persist: postgresql        # false | postgresql | parquet
    retention_days: 7          # 0 = keep forever
    # parquet:                 # required only when persist: parquet
    #   path: "/var/lib/voltnir/public_trades"
    #   rotation_secs: 3600
    #   max_rows_per_file: 1000000

  # Order book frames (snapshots + deltas), never queryable via the API:
  order_book:
    persist: postgresql        # false | postgresql | parquet
    retention_days: 0
    # postgres:                # else inherits the main `database` Postgres conn
    #   url: "postgres://voltnir:secret@ob-host:5432/orderbook"
    # parquet:                 # required only when persist: parquet
    #   path: "/var/lib/voltnir/orderbook"
    #   rotation_secs: 3600
    #   max_rows_per_file: 1000000
```

## licensing

License validation. The section itself is optional for backwards compatibility, but a valid license **is required**; there is no unlicensed run mode. Obtain the signed license JSON from the Voltnir customer portal.

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `license_path` | path | yes* | *none* | Path to the portal-signed license file, loaded and verified on startup. **Optional in YAML, but required at runtime.* |

> [!WARNING]
> **Strict policy.** A missing `license_path`, a bad signature, an unknown signing key, or an identity mismatch **refuses startup**: the binary exits with code 1.

> [!WARNING]
> **Expiry: 14-day grace, then a hard stop.** An expired license keeps running for a **14-day grace period** (status `in_grace`), with escalating warnings logged and surfaced to clients. **Once the grace period lapses** (status `expired`) the policy turns hard: the gateway **refuses to start** (exit code 1), and a gateway that is already running **shuts down** at the next hourly license check. Renew the license from the customer portal before the grace period ends.

```
licensing:
  license_path: "./license.json"
```

## self_trade

Self-trade (cross-trade) prevention. EPEX M7 does **not** prevent self-trades server-side; it only flags them after the fact. This is a Voltnir-side pre-trade check: before an order is sent to M7, the gateway looks for one of *our own* resting orders on the opposite side at a crossing price and applies the configured policy. The section is optional and defaults to `observe`.

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `policy` | enum | no | `observe` | `observe` = detect & log the self-cross but let the order through (the M7 `selfTrade` flag is still recorded). `reject` = block the aggressor before it reaches M7 (HTTP 422 / gRPC `FAILED_PRECONDITION`, reason `SELF_CROSS_BLOCKED`). |

> [!WARNING]
> **Default only: the live value is runtime-mutable.** This config seeds the policy on a *fresh* database. The active policy is held in the `profile` table and changed at runtime via `GET/PUT /api/v1/self_trade_policy` (and the gRPC `Get/SetSelfTradePolicy` RPCs); once the row exists it wins on every reboot.

```
self_trade:
  policy: observe
```

## cash_limit

Cash-limit risk-engine settings. The cash limit caps the monetary value at risk (open orders + windowed executed trades) and is enforced alongside the MW position limit. The limit *values* are runtime-mutable (global via `GET/PUT /api/v1/cash_limit`; per-member via the member endpoints). Only the static settings below live here. The section is optional.

**Two separate pools, EUR and GBP** (ECC settles them separately: no cross-currency netting, no FX); a leg is bucketed by delivery area. For both pools an open order's exposure is floored at zero (a money-making order contributes nothing, never a credit; a negative-price sell consumes), while executed trades move the limit by their full signed value. Values scale with the contract's delivery duration (energy = MW × hours), so a 15-min product counts a quarter of the same MW/price hourly product. The pools differ only in the **sell** methodology: an **EUR** sell credits (receipt counted), while a **GBP** sell's receipt is *ignored* (ECC) and instead reserves a fixed rate per MWh. Buys consume normally in both.

> [!WARNING]
> **Default semantics.** Voltnir defaults to ECC fail-closed parity (`fail_closed: true`): a `0`/unset cash limit means **zero = no trading** in that pool (ECC Risk Management Services §3.11 EUR / §3.12 GBP), so a fresh install is guarded out of the box and a real limit must be set to trade. Set `fail_closed: false` (or flip it at runtime via `GET/PUT /api/v1/cash_fail_closed`) to opt back into Voltnir's historical fail-*open* semantics, intended for a simulator or non-ECC deployment: a `0` cash limit is then **disabled**, that pool *unbounded* with no Voltnir-side guardrail. **Migration:** this value only *seeds* a fresh profile row, so an install created under the old fail-open default keeps it until the runtime switch is flipped; upgrading never silently halts an existing deployment. At startup, when a cash limit is in force but the ECC parameters look unconfigured (GBP areas with no reservation rate, empty holiday calendar, or a non-Amsterdam timezone), the gateway logs a warning; it never refuses to start over these.

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `fail_closed` | bool | no | `true` | ECC fail-closed parity (**seed** for the runtime switch). `true` (default) is ECC §3.11/§3.12: a `0`/unset cash limit = **no trading** in that pool, so a fresh install is guarded out of the box. `false` opts into Voltnir's historical semantics: a `0` cash limit = *disabled* (pool unbounded), for a simulator or non-ECC deployment. Seeds the profile row on first boot only; the live switch is runtime-mutable via `GET/PUT /api/v1/cash_fail_closed` (and the gRPC/WS mirrors) and an existing row wins on later boots, exactly like `self_trade.policy`, so upgrading never silently halts an install created under the old fail-open default. |
| `gbp_delivery_areas` | list | no | `[]` | **Extra** delivery-area EICs that settle in GBP (ECC's GBP pool + methodology), unioned with the always-on built-in GB area (`10YGB----------A`). Empty (default) = Great Britain settles GBP, every other area settles EUR. Add an EIC here only if ECC starts settling a further zone in GBP. |
| `gbp_sell_reservation_per_mwh_cents` | i64 | no | `0` | Flat GBP sell-reservation rate, in GBP cents per MWh. Used when `gbp_sell_reservation_schedule` is empty (or no scheduled rate is yet effective). `0` reserves nothing. |
| `gbp_sell_reservation_schedule` | list | no | `[]` | Effective-dated GBP reservation rates. ECC revises the rate ~monthly, announced ~a week ahead. Each entry is `{ effective_from: "YYYY-MM-DD", rate_per_mwh_cents: N }`. The rate in force is the entry with the latest `effective_from` on or before today (in `exposure_window_timezone`); before any is effective, the flat rate above is used. |
| `exposure_window_timezone` | string | no | `"Europe/Amsterdam"` | IANA timezone for the exposure-window reset. ECC clears at **16:00 in this zone** each working day (a regulatory reference, not a user preference), so it defaults to `Europe/Amsterdam` (handles CET/CEST automatically). An unparseable value falls back to `Europe/Amsterdam` with a warning. |
| Bank holidays for the exposure window are **no longer configured here**. They are runtime-managed (separate EUR and GBP calendars) via the `/api/v1/holidays` REST endpoint (and the gRPC / WS equivalents), persisted to the database, and reloaded on restart. After upgrading, re-enter any holiday dates through that endpoint. |  |  |  |  |

> [!WARNING]
> **Confirm the GBP reservation rate with risk.** The per-MWh figure (and its effective dates) is ECC's published rate. Set it via `gbp_sell_reservation_schedule` (or the flat field) and confirm the exact value, the GBP-area list, and the currency basis before go-live.

```
cash_limit:
  fail_closed: true
  gbp_delivery_areas: []
  gbp_sell_reservation_per_mwh_cents: 0
  gbp_sell_reservation_schedule: []
  exposure_window_timezone: "Europe/Amsterdam"
```

## Full Template

A complete reference configuration with every section. Copy it, save as `config.yml`, and replace each `<REPLACE_ME>`. Optional values are shown at their defaults.

```
epex_settings:
  delivery_areas:
    - "<REPLACE_ME_AREA_EIC>"
  products:
    - "<REPLACE_ME_PRODUCT>"
  enable_hub_2_hub: false

system:
  max_ws_pong_age_ms: 15000
  max_wait_time_for_system_health_sec: 60
  order_ack_timeout_ms: 2000

epex_connection:
  cert: "./cert/client-cert.pem"
  key:  "./cert/client-key.pem"
  application_id: "<REPLACE_ME_APPLICATION_ID>"
  account_id:     "<REPLACE_ME_ACCOUNT_ID>"
  environment: prod
  user_id:  "<REPLACE_ME_AMQP_USER>"
  password: "<REPLACE_ME_AMQP_STATIC_PASSWORD>"
  totp:     "<REPLACE_ME_TOTP_BASE32_SECRET>"
  # extra_ca_path: "./cert/corporate-ca.pem"  # optional, extra trust roots (private/corporate CA)

rest_server:
  enable: true
  host:   "0.0.0.0"
  port:   3000

grpc_server:
  enable: true
  host:   "0.0.0.0"
  port:   3443
  # tls:
  #   cert_path: "./cert/grpc-server-cert.pem"
  #   key_path:  "./cert/grpc-server-key.pem"

ws_server:
  enable: true
  host:   "0.0.0.0"
  port:   9001

trading_terminal:
  enable: true
  port:   8080

database:
  backend: internal
  path: "./voltnir.db"
  # audit_retention_days: 7      # hourly prune; 0 = keep forever
  # m7_errors_retention_days: 7  # hourly prune; 0 = keep forever

# market_data:                 # optional, high-volume capture (off by default)
#   public_trades:
#     persist: postgresql      # false | postgresql | parquet
#     retention_days: 7
#   order_book:
#     persist: postgresql      # false | postgresql | parquet
#     retention_days: 0

licensing:
  license_path: "./license.json"

self_trade:
  policy: observe

cash_limit:
  fail_closed: true
  gbp_delivery_areas: []
  gbp_sell_reservation_per_mwh_cents: 0
  gbp_sell_reservation_schedule: []
  exposure_window_timezone: "Europe/Amsterdam"
```
