# Voltnir Configuration: config.yml Reference

> Auto-generated from the Voltnir API reference.

<a id="overview" name="overview"></a>

## Configuration Overview

Voltnir reads all runtime configuration from a single YAML file passed on the command line. The file is parsed once at startup; a malformed file or a missing required field is fatal: the process logs the parse error and exits before any subsystem starts.

#### How configuration is loaded

Launch the gateway with the config path on `-c`:

```
voltnir -c config.yml
```

The shipped template is `config.yml.dist`. Copy it to `config.yml` and replace every `<REPLACE_ME>` placeholder with values from your EPEX M7 onboarding pack and your `cert/` directory.

```
cp config.yml.dist config.yml
```

The file is read once, at startup. There is no in-place reload: an edit takes effect only when the gateway restarts, so change it and restart together. See the [Deployment & TLS guide](deployment_v1.md) for the restart path.

> [!NOTE]
> **Paths are relative to the working directory** voltnir is launched from. Under systemd that directory is the install root (where `config.yml` lives), so the `./cert/…` and `./voltnir.db` defaults resolve there.

#### Top-level sections

| Key | Required | Purpose |
| --- | --- | --- |
| [`epex_settings`](#epex_settings) | yes | EPEX market scope: delivery areas, products, hub-to-hub toggle. |
| [`system`](#system) | no | Connection-health thresholds; defaults to the documented values if the section is omitted. |
| [`epex_connection`](#connection) | yes | EPEX M7 TLS identity, M7 IDs, environment, and AMQP login credentials. |
| [`rest_server`](#rest_server) | no | Inbound HTTP REST server bind + enable flag; defaults to enabled on `0.0.0.0:3000` if the section is omitted. |
| [`grpc_server`](#grpc_server) | no | Inbound gRPC server; defaults to enabled on `0.0.0.0:3443` if the section is omitted. |
| [`ws_server`](#ws_server) | no | Inbound WebSocket transport (peer to REST/gRPC); defaults to enabled on `0.0.0.0:9001` if the section is omitted. |
| [`trading_terminal`](#trading_terminal) | no | Embedded terminal SPA server. Enabled by default if the section is omitted; consumes the `ws_server` transport (and binds its host). |
| [`database`](#database) | no | Audit store backend: `internal` (embedded SQLite at `./voltnir.db`, default) or `postgresql` (external server). |
| [`market_data`](#market_data) | no | High-volume capture of the public trade tape + order book frames. Each stream opts in via `persist` (`false`/`postgresql`/`parquet`). |
| [`licensing`](#licensing) | no* | License file path. **Section optional, but a valid license is required at startup.* |
| [`self_trade`](#self_trade) | no | Self-trade (cross-trade) prevention policy. Defaults to `observe`. |
| [`slot_limit`](#slot_limit) | no | Slot position limit: mode and House limit seeded on a fresh database. Defaults to `off`. |
| [`cash_limit`](#cash_limit) | no | Which delivery areas settle in ECC's GBP pool, the exposure-window timezone, and the fallback GB delivery-risk rate. Exposure itself comes from the exchange's risk parameters. |
| [`load_management`](#load_management) | no | Guards the member's order-load allowance against the exchange's rolling limits before it is reached. |
| [`system_log`](#system_log) | no | The gateway's own in-memory diagnostic log, served to clients holding `read_logs`. |
| [`logging`](#logging) | no | The stdout log's line format: text or JSON. Defaults to `text`. |

The cash limit, the risk parameters and the bank-holiday calendar are handled by the gateway from the exchange's own reports; see [What Voltnir handles automatically](#automatic) for what that leaves an operator to do.

<a id="secrets" name="secrets"></a>

## Secrets & Safety

`config.yml` holds live credentials (AMQP password, the TOTP secret, and M7 identifiers). Treat it like a secret.

> [!WARNING]
> Never commit `config.yml` to version control, and never paste its contents into tickets, chats, or external tools. Edit and share `config.yml.dist` instead; it carries only `<REPLACE_ME>` placeholders.

> [!CAUTION]
> The `totp` field is the **base32 secret**, not a generated 6-digit code. Voltnir derives the time-based code from it at login. Do not paste a code that will expire in 30 seconds.
>
>  The two credentials sit at **different layers**: the AMQP broker connection authenticates with `user_id` + `password` exactly as written, and the M7 session on top of it authenticates with the generated code. The code is **not** appended to the password.

<a id="epex_settings" name="epex_settings"></a>

## epex_settings

EPEX market scope and application-level feature flags. Required.

| Field | Type | Default | Unit | Required | Description |
| --- | --- | --- | --- | --- | --- |
| `delivery_areas` | list<string> | none | EIC | yes | EIC delivery-area codes the instance may trade in, e.g. `10YDE-RWENET---I`. |
| `products` | list<string> | none | none | yes | M7 product codes eligible for order placement, e.g. `Intraday_Hour_Power`. |
| `enable_hub_2_hub` | bool | `false` | none | no | When `true`, the hub-to-hub heartbeat monitor is active and dispatches resync requests on staleness. |

Reference data for **every** product the exchange assigns the account is inquired at login, so an assigned product you do not list here still has its parameters and contracts known and its orders and trades handled; listing a product adds its live order book and public-trade feeds.

```
epex_settings:
  delivery_areas:
    - "10YDE-RWENET---I"
  products:
    - "Intraday_Hour_Power"
  enable_hub_2_hub: false
```

<a id="system" name="system"></a>

## system

Connection-health thresholds. The whole section is optional; omit it (or leave it empty) and every threshold falls back to its default. Set any field individually to override just that one. The defaults are sensible for production; only tune them if the maintenance log shows false positives.

| Field | Type | Default | Unit | Required | Description |
| --- | --- | --- | --- | --- | --- |
| `max_ws_pong_age_ms` | int | `15000` | ms | no | Age of the last WebSocket pong before the connection is flagged unhealthy. |
| `max_ws_ob_delta_age_sec` | int | `300` | s | no | How long the order-book stream may stay connected and answering pongs while it delivers no applied delta, no snapshot frame and no `SynchronizationComplete` before the gateway reconnects it: a stuck subscription that the pong check cannot see. `0` turns the check off. Each trip doubles the threshold in force (300, 600, 1200 seconds and so on) up to an hour, and the first delta returns it to the configured value. A market with no deltas at all settles at one reconnect an hour; a market whose deltas are further apart than the configured value reconnects once per such gap. A trip reconnects the order-book stream only, alternating hosts like any reconnect. It never counts toward the stream’s failure budget and never fires the shutdown itself, and it resets the stream’s connection-failure count whatever the session’s length. The book is unsynchronised for the seconds the resubscribe takes, so order admission closes for that time, as on any order-book reconnect. As after any order-book reconnect, a resubscribe that does not synchronise within `max_wait_time_for_system_health_sec` is cycled with the rest of the exchange connection by the maintenance health timer, and that cycle restarts the backoff at the configured value. The private-data stream is not watched: it is silent whenever the desk has no orders. **Validated at startup:** a negative value, or a non-zero value not above `max_ws_pong_age_ms` (compared in milliseconds), refuses to start. The removed `max_ws_ob_delta_age_ms` key is still ignored, so an old config that carries it keeps this default. |
| `max_wait_time_for_system_health_sec` | int | `60` | s | no | Seconds the system may stay non-operational before the maintenance loop cycles the exchange tasks. Applies **once the gateway has been operational at least once** in the current connection cycle; before that, `max_startup_time_sec` applies instead. |
| `max_startup_time_sec` | int | `max(600, max_wait_time_for_system_health_sec)` | s | no | Seconds the gateway may take to become operational for the **first time** in a connection cycle. A cold start is not a degradation: it completes an AMQP login, three channel health handshakes, both v7 snapshots and the chunked cash-exposure backfill, which on a large book or a slow link legitimately takes minutes. Cutting it short discards the snapshots and restarts the identical sequence from zero, so this allowance is deliberately generous and `max_wait_time_for_system_health_sec` takes over the moment the gateway is operational. **Validated at startup:** an explicit value must be at least `max_wait_time_for_system_health_sec`, or the gateway refuses to start. When the key is omitted the default is derived as `max(600, max_wait_time_for_system_health_sec)`, so 600s on a default grace and never below the grace however it is tuned. |
| `order_ack_timeout_ms` | int | `2000` | ms | no | How long a new-order submission waits for M7 to acknowledge (order-execution report or rejection) before returning a timeout (REST `504` / gRPC `DEADLINE_EXCEEDED`). **Validated at startup:** must not exceed `3600000` (one hour); nothing about M7 makes an hour a plausible acknowledgement window, and `pending_order_reap_age_ms` is derived from this value, so a unit mix-up would buy a very long reap age silently. |
| `order_outcome_timeout_ms` | int | `3000` | ms | no | How long an order command waits for M7's **outcome** after the receipt has arrived (an execution report that confirms the resulting order, or a post-receipt rejection that refuses it) before it reports the command received but its outcome not yet known. Bounds the second of the two waits; `order_ack_timeout_ms` bounds the first. **Validated at startup:** must be at least `100`, or the gateway refuses to start; a shorter wait would expire before the exchange could answer a request it has already acknowledged. The pending reap age and the per-order modify lock both span this window as well as the receipt window. |
| `recall_outcome_wait_ms` | int | `5000` | ms | no | How long a trade recall waits, once the exchange has acknowledged it, for the trade to move to a recall state (`RREQ`, or `RSFA` for a remote trade) or for a refusal after the acknowledgement. When neither arrives in time the recall is answered `submitted` (REST `202`) and market operations’ decision follows on the trade streams. `order_ack_timeout_ms` bounds the wait before it. |
| `order_request_expiration_ms` | int | `10000` | ms | no | The AMQP `expiration` every exposure-adding request carries: a new order, a modify and an activation. M7 drops such a request not consumed within this window, and drops one its gateway consumed this long before the core would process it, so the request lands within twice the window of reaching M7's queue or not at all. That bound is what lets the gateway release the headroom of a command it never heard back from: `2 × this + 5000` ms after the publish, `20000` ms more for an order on an XBID-coupled area, and only while no report for it can have been missed. Cancels, cancel-all and deactivations do not carry it and keep M7's 45 s default. Short: a request M7 cannot process inside the window is dropped rather than executed late. Long: it still executes, late, and the headroom of an unanswered command is held longer. **Validated at startup:** must lie between `2000` and `45000` (M7's own cap), or the gateway refuses to start. |
| `pending_order_reap_age_ms` | int | `max(2 × (ack + outcome), 2 × expiration + 5000)` | ms | no | An optional upward override on how long an unanswered command holds its position and cash headroom before the gateway may release it without an answer. The release happens at the later of this age and the command's expiry bound (see `order_request_expiration_ms`), and only while no report for it can have been missed; this key can only lengthen the wait. **Validated at startup:** must be at least `5000`, at least twice `order_ack_timeout_ms + order_outcome_timeout_ms`, and at least `2 × order_request_expiration_ms + 5000`, or the gateway refuses to start. When the key is absent it is derived as the larger of the last two (`25000` with the defaults). A value over `300000` (5 minutes), set or derived, draws a startup warning naming the figure. |
| `max_requests_per_window` | int | `6000` | requests | no | The most requests one API key may make inside a `request_window_seconds` window, counted across REST, WS and gRPC together. Over the bound the request is refused (REST `429` with `{"error": "RATE_LIMITED"}`, gRPC `RESOURCE_EXHAUSTED`, WS error code `RATE_LIMITED`) and the crossing is written to the audit trail as one `rate_limited` event per window. `0` disables the bound entirely, for a deployment that rate-limits at its own reverse proxy. The default is 100 requests a second on one key, far above any terminal session, which takes live data over subscriptions rather than polling. Cancelling an order, cancelling all orders and *disabling* trading are never refused by the bound, whatever the caller's rate, so a runaway client cannot lock its own operator out of the switch that stops it; re-*enabling* trading admits exposure again and is bounded like any other call. |
| `request_window_seconds` | int | `60` | s | no | The width of that window. **Validated at startup:** must be at least `1` whenever `max_requests_per_window` is non-zero, or the gateway refuses to start. The window is fixed, not sliding: every key's counter resets on the same boundary. |
| `trusted_proxies` | list of strings | `[]` | IP or CIDR | no | Reverse proxies allowed to name the caller. Each entry is one IPv4 or IPv6 address or CIDR range. A request whose TCP peer is listed has its source, the `source_ip` on its audit rows and the key of the per-source failed-login throttle, read from `X-Forwarded-For` (on gRPC, `x-forwarded-for` metadata): every header line joined in order, read from the right, listed addresses skipped, the first address that is not listed taken. A header made only of listed addresses gives its left-most. A missing or empty header, an element that does not parse before the caller is found (elements left of it are never read), or more than 16 elements walked without an unlisted address records the peer. From an unlisted peer the header is never read, and `X-Real-IP` and `Forwarded` are never read at all. An IPv4-mapped IPv6 address matches an IPv4 entry. List only the proxy's own address (`127.0.0.1` for nginx on the same host): every listed address can write any source it likes, so a wide range lets any client inside it choose its recorded address and its throttle bucket. **Validated at startup:** an entry that is not an address or a range refuses to start, naming the entry, and so do `0.0.0.0/0`, `::/0` and any list that together covers every address. Empty (the default) reads no header and records the TCP peer. The proxy must append to the header (nginx `$proxy_add_x_forwarded_for`); see the deployment guide. |
| `reports_dir` | string | `./reports` | path | no | Directory generated audit reports are written into, and cleaned up from at startup. The gateway creates it `0700` and writes each report file `0600`, so a report (a bulk extract of the audit tape that lives for an hour) is readable only by the account the gateway runs as. Do not point this at a directory shared with anything else. A relative path resolves against the working directory. |
| `disable_trading` | bool | `false` | none | no | Debug / development hard kill-switch. When `true`, trading is force-disabled: `trade_enabled` always reports false and the runtime trading toggle (REST/gRPC/WS) is rejected with a conflict, so nothing (not the persisted profile, not the API toggle) can turn trading back on. This flag is the absolute authority. Omit it in normal operation. |
| `trade_ingest_fault` | string | `close` | none | no | What order admission does while an exchange trade report the gateway could not read holds the `trade_report refused` fault raised (a trade the exchange executed is missing from the gateway's count, so position, cash and P&L are understated). `close` refuses new orders and modifies until the fault clears, unless an operator acknowledges it (REST `POST /api/v1/trade_ingest_fault/ack`, gRPC `AckTradeIngestFault`, WS `ack_trade_ingest_fault`, permission `toggle_trading`); `continue` admits them while the fault is the only thing holding admission closed. State and status then report `admission: degraded`; cancels are never gated and nothing is flattened. While admission is `degraded` the gateway does not reconnect its exchange session over the fault, and it keeps polling the exchange's throttling status, which the load check (`load_management`) needs fresh to admit an order that adds exposure. Orders are admitted the moment admission reopens, unless the throttling report went stale while admission was closed (closed for about `load_management.max_report_age_sec` or longer, 30 s by default; the report ages from its last poll, so a slightly shorter closure can already count); then an order that adds exposure can be refused for about two seconds after admission reopens, until the first throttling poll answers. From then on orders stay admitted until the trade report is read (under `close`, until the acknowledgement runs out). Any other order-critical issue still closes admission and, past the health allowance, still makes the gateway reconnect its exchange session. The exchange still checks the member's cash limit on every order. Logged at startup and recorded on the `system_startup` audit row. **Validated at startup:** any other value refuses to start. |
| `trade_ingest_fault_ack_ttl_sec` | int | `1800` | s | no | How long one acknowledgement reopens admission under `close`. It ends early when the fault clears, a repeat restarts it, a restart drops it (it is held in memory), and it keeps running while another issue holds admission closed. **Validated at startup:** `0` refuses to start. |

```
system:
  max_ws_pong_age_ms: 15000
  max_ws_ob_delta_age_sec: 300
  max_wait_time_for_system_health_sec: 60
  max_startup_time_sec: 600
  order_ack_timeout_ms: 2000
  order_outcome_timeout_ms: 3000
  recall_outcome_wait_ms: 5000
  order_request_expiration_ms: 10000
  # pending_order_reap_age_ms: 25000
  max_requests_per_window: 6000
  request_window_seconds: 60
  trusted_proxies: []      # e.g. [127.0.0.1] behind a same-host nginx
  reports_dir: ./reports
  disable_trading: false   # debug override; omit in normal operation
  trade_ingest_fault: close
  trade_ingest_fault_ack_ttl_sec: 1800
```

<a id="connection" name="connection"></a>

## epex_connection

EPEX M7 connectivity: TLS client identity, M7 identifiers, the `environment` selector, and the AMQP login credentials. Required. See `cert/README.md` for the PEM files referenced below.

| Field | Type | Default | Unit | Required | Description |
| --- | --- | --- | --- | --- | --- |
| `cert` | string | none | path | yes | TLS client certificate PEM presented to M7. |
| `key` | string | none | path | yes | TLS private key PEM. |
| `application_id` | string | none | none | yes | M7 application identifier for this instance (onboarding pack). |
| `account_id` | string | none | none | yes | M7 account identifier used for order submission and session auth. |
| `environment` | `sim` \| `prod` | none | none | yes | EPEX environment this gateway runs in. **Selects the M7 endpoints** (host/port/virtual_host for both AMQP and WebSocket) and must be permitted by the license's `environment`; a mismatch **refuses startup**. No default; an absent value fails config parsing. |
| `user_id` | string | none | none | yes | AMQP login username. |
| `password` | string | none | none | yes | AMQP login password, used verbatim in the broker connection. The TOTP code is **not** appended to it. |
| `totp` | string | none | none | yes | Base32-encoded TOTP secret. Not a 6-digit code; a code is generated from it per connect and sent as the session login's `authVerificationCode`. |
| `extra_ca_path` | string | none | path | no | Optional PEM bundle of extra trust roots, layered **additively** on the bundled CA set + OS native store for **both** the AMQP and WebSocket dials. See the TLS-trust callout below. |

> [!NOTE]
> **Endpoints are not configured.** The AMQP and WebSocket hosts, ports, and virtual-host are fixed per EPEX environment and compiled into the binary. Selecting `environment: sim` or `environment: prod` picks the matching endpoint set. There is no host/port/virtual_host key, and no `v6`/`v7` sub-blocks; `epex_connection` carries only the TLS identity, M7 IDs, environment, and login credentials.

> [!NOTE]
> **extra_ca_path: private/corporate CA escape hatch.** The gateway's default server-trust store is the CA set baked into the binary (so it runs on minimal hosts with no system `ca-certificates`) plus whatever the OS native trust store carries. Both cover only *public* CAs. A deployment behind a corporate MitM TLS-inspection proxy, or one whose M7 chain anchors on a *private* intermediate CA, would otherwise see `UnknownIssuer` on the AMQP dial. Point `extra_ca_path` at a PEM bundle of the additional root(s) and they are trusted on both transports. Behaviour: absent means no extra roots; a **set-but-unreadable** path **refuses startup** (the error names the path); a readable file with **no CERTIFICATE blocks** logs a warning and continues on the default roots.

> [!WARNING]
> **Environment binding.** `epex_connection.environment` must match the license's `environment`: a `sim` license runs only on `sim`, a `prod` license only on `prod`, and a `sim_and_prod` license on either. A mismatch (a production license pointed at the simulator, or a simulator/eval license driving production) **refuses startup**.

```
epex_connection:
  cert: "./cert/client-cert.pem"
  key:  "./cert/client-key.pem"
  application_id: "<REPLACE_ME_APPLICATION_ID>"
  account_id:     "<REPLACE_ME_ACCOUNT_ID>"
  environment: prod
  user_id:  "<REPLACE_ME_AMQP_USER>"
  password: "<REPLACE_ME_AMQP_PASSWORD>"
  totp:     "<REPLACE_ME_TOTP_BASE32_SECRET>"
  # extra_ca_path: "./cert/corporate-ca.pem"  # optional, extra trust roots (private/corporate CA)
```

<a id="rest_server" name="rest_server"></a>

## rest_server

Inbound HTTP REST server. Optional: omit the whole section and it defaults to enabled on `0.0.0.0:3000`. See [the REST API reference](rest_api_v1.md) for the surface it serves.

| Field | Type | Default | Unit | Required | Description |
| --- | --- | --- | --- | --- | --- |
| `enable` | bool | `true` | none | no | When `false`, the REST server is not started. |
| `host` | string | `0.0.0.0` | IP | no | IP address to bind. `0.0.0.0` is all interfaces; bind to `127.0.0.1` behind a reverse proxy. |
| `port` | int | `3000` | TCP port | no | TCP port to listen on. |

```
rest_server:
  enable: true
  host:   "0.0.0.0"
  port:   3000
```

<a id="grpc_server" name="grpc_server"></a>

## grpc_server

Inbound gRPC server, plaintext HTTP/2 by default. Optional: omit the whole section and it defaults to enabled on `0.0.0.0:3443`. Behind a reverse proxy, leave `tls` unset and terminate TLS at the proxy; to terminate in-process, set the `tls` block. See [the gRPC API reference](grpc_api_v1.md) for the surface it serves.

| Field | Type | Default | Unit | Required | Description |
| --- | --- | --- | --- | --- | --- |
| `enable` | bool | `true` | none | no | When `false`, the gRPC server is not started. |
| `host` | string | `0.0.0.0` | IP | no | IP address to bind. |
| `port` | int | `3443` | TCP port | no | TCP port to listen on, chosen not to collide with the REST default 3000. |
| `tls.cert_path` | string | none | path | no | PEM server certificate chain (required if `tls` is set). Read once at startup; rotating certs needs a restart. |
| `tls.key_path` | string | none | path | no | PEM private key (required if `tls` is set). When the `tls` block is absent the server accepts plaintext HTTP/2. |

```
grpc_server:
  enable: true
  host:   "0.0.0.0"
  port:   3443
  # tls:
  #   cert_path: "./cert/grpc-server-cert.pem"
  #   key_path:  "./cert/grpc-server-key.pem"
```

<a id="ws_server" name="ws_server"></a>

## ws_server

WebSocket transport (streaming + request/response over `ws://host:port/ws/v1`), an end-user transport peer to REST and gRPC and independent of the trading terminal. Optional: omit the whole section and it defaults to enabled on `0.0.0.0:9001`. Plain WS; terminate TLS at a reverse proxy. See [the WebSocket API reference](ws_api_v1.md) for the surface it serves.

| Field | Type | Default | Unit | Required | Description |
| --- | --- | --- | --- | --- | --- |
| `enable` | bool | `true` | none | no | When `false`, the WebSocket server is not started. |
| `host` | string | `0.0.0.0` | IP | no | IP address to bind. |
| `port` | int | `9001` | TCP port | no | TCP port the live-data WebSocket feed listens on. |

```
ws_server:
  enable: true
  host:   "0.0.0.0"
  port:   9001
```

<a id="trading_terminal" name="trading_terminal"></a>

## trading_terminal

Serves the prebuilt terminal SPA embedded in the binary. Optional: omit the whole section and it defaults to enabled on port 8080. The bind host is not set here; it is the `ws_server.host` above (the SPA shares the WS interface). The SPA discovers the REST and WebSocket ports at runtime, so one binary works on any host with no rebuild.

| Field | Type | Default | Unit | Required | Description |
| --- | --- | --- | --- | --- | --- |
| `enable` | bool | `true` | none | no | When `false`, the SPA server is not started. |
| `port` | int | `8080` | TCP port | no | TCP port the embedded SPA is served on. Binds `ws_server.host`. |

```
trading_terminal:
  enable: true
  port:   8080   # binds ws_server.host
```

<a id="database" name="database"></a>

## database

Selects where orders, trades, users, and the audit trail are persisted. Optional: omit the section to use the embedded SQLite store at `./voltnir.db`. A single binary carries every driver; the backend is chosen at runtime.

| Field | Type | Default | Unit | Required | Description |
| --- | --- | --- | --- | --- | --- |
| `backend` | enum | `internal` | none | no | `internal` = embedded SQLite file store (historical default); `postgresql` = external PostgreSQL server, 16 or newer; an older server is refused at startup with an error naming the version found. |
| `path` | string | `./voltnir.db` | path | no | SQLite file path for the `internal` backend. The WAL side-files sit alongside it; back up all three together. |
| `url` | string | none | none | no | Full PostgreSQL connection URL (`postgres://user:pass@host:port/dbname`). Used verbatim; the discrete fields below are ignored when set. |
| `host` / `port` / `user` / `password` / `dbname` | mixed | `none / 5432 / voltnir / none / none` | none | no | Discrete PostgreSQL connection fields (used when `url` is absent). `password` is sensitive. For the `postgresql` backend either `url` or at least `host` + `dbname` is required, or startup fails. |
| `max_connections` | int | `4` | connections | no | Connection-pool size (both backends). |
| `audit_retention_days` | int | `0` | days | no | Days to retain compliance audit-event rows before the hourly prune task deletes them. `0` = keep forever, the default. Both backends. Negative values are rejected at startup. Every actor event is a row, so this is one of the two fast-growing tables. |
| `m7_errors_retention_days` | int | `0` | days | no | Days to retain M7 exchange-error rows before the hourly prune task deletes them. `0` = keep forever, the default. Both backends. Negative values are rejected at startup. |
| `exchange_messages_retention_days` | int | `0` | days | no | Days to retain exchange-message rows (what the exchange said: cash-limit breaches, halts, suspensions, failover notices) before the hourly prune task deletes them. `0` = keep forever, the default. Both backends. Negative values are rejected at startup. |
| `orders_retention_days` | int | `0` | days | no | Days to retain order execution reports before the hourly prune task deletes them, together with the raw exchange payload behind each one. `0` = keep forever, the default. Both backends. Negative values are rejected at startup. The window is measured on each revision's own arrival time, so an order's early revisions age out while a later one is kept. Every price move on a resting order is another row, so this is the other fast-growing table. |
| `trades_retention_days` | int | `0` | days | no | Days to retain trade capture reports, measured on each trade's execution time, before the hourly prune task deletes them together with their raw exchange payloads. `0` = keep forever, the default. Both backends. Negative values are rejected at startup. |

> [!NOTE]
> **Every window defaults to `0`: the gateway keeps every row unless you set a key.** How long to keep records is an operational choice, and both sides cost something. Keeping everything grows the disk, lengthens backups and restores, and slows some filtered history pages as the tables grow; order revisions and the audit trail grow fastest. Pruning deletes rows for good, and the record-keeping obligation is yours. If a record must outlive its window, plan where it goes before you set one. Orders, trades and the audit trail have an export: run it to separate storage on a schedule shorter than the window. `m7_errors` and `exchange_messages` have no export: keep their window at `0`, or page `GET /audit/m7_errors` and `GET /audit/exchange_messages` into your own storage before it closes. At startup the gateway logs one `INFO` line naming every table whose window is `0`, with the key that would prune it.

> [!NOTE]
> A raw exchange payload lives exactly as long as the row it is evidence for: order payloads follow `orders_retention_days` and trade payloads follow `trades_retention_days`; there is no separate payload window. The gateway never archives before it prunes. Export orders, trades and the audit trail on a schedule shorter than their windows (`POST /audit/export/{orders,trades,events}`, REST only, at most 31 days and one hour per export); an export carries the parsed rows (JSON/CSV), not the raw payload bodies. There is no export for `m7_errors` or `exchange_messages`.

> [!CAUTION]
> Switch a window on, or shorten it a long way, with trading stopped. In normal running each hourly pass removes about an hour of rows and takes a fraction of a second. The first pass after a window goes from `0` to a number, or from a year to three months, removes all the backlog at once, and so does the first start after the gateway has been stopped for weeks or after restoring an old backup. That pass runs at startup and can take minutes on a large store. On the embedded SQLite store it then hands the freed space back, which after a very large prune holds the write lock for tens of seconds, and a write that waits more than a few seconds behind it can fail. Each such loss is counted: `writes_dropped` or `trades_persist_failed` on `GET /api/v1/state`, or `voltnir_payloads_write_failed_total` on `/api/v1/metrics` for a captured exchange message, whose order or trade row is kept without it. A very large prune on SQLite also grows the write-ahead file by gigabytes until the pass ends, and the odd history read can be refused while it runs, so have that disk free first. On PostgreSQL the pass blocks no writes but is still a heavy burst of deletes and write-ahead log. Disable trading with the kill switch (`PUT /trading_allowed`, which survives the restart), stop the gateway, change the setting, start it, and enable trading again once the first pass is done: when `voltnir_db_prune_last_timestamp_seconds` on `/api/v1/metrics` changes from `0`, and on SQLite once the gateway has also logged the line beginning `db: reclaiming` (or `db: incremental vacuum failed`), which it writes when that step ends; the line is absent only when the pass freed nothing. Then check that the three counters read `0`. To hand the rest of the freed disk back at once, run `--vacuum` afterwards with the gateway stopped (see [Database care](deployment_v1.md#database-care) in the deployment guide). Lengthening a window, or leaving the windows as they are, needs no such care.

> [!NOTE]
> Omitting `database` entirely keeps the historical behaviour: the embedded SQLite store at `./voltnir.db`.

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

  # Retention (both backends; hourly prune; 0 = keep forever, the default):
  # audit_retention_days: 0
  # m7_errors_retention_days: 0
  # exchange_messages_retention_days: 0
  # orders_retention_days: 0
  # trades_retention_days: 0
```

<a id="market_data" name="market_data"></a>

## market_data

High-volume capture of the public trade tape and order book frames: two independent streams, each opting in via `persist` (`false` / `postgresql` / `parquet`) with its own retention, sharing the writer plumbing (`channel_capacity` / `batch_size`). Optional; omit the section (or leave both `persist: false`) to capture nothing. This is separate from `database` and off its parity contract: a `postgresql` stream is queryable through the audit endpoints, a `parquet` stream is export-only. On writer-channel overload rows are dropped and logged; the live feed never blocks.

| Field | Type | Default | Unit | Required | Description |
| --- | --- | --- | --- | --- | --- |
| `channel_capacity` | int | `65536` | rows | no | Bounded writer-channel depth; sized generously so bursts are absorbed before drop-on-full backpressure. |
| `batch_size` | int | `256` | rows | no | Rows accumulated per flush by the writer. |
| `public_trades.persist` | enum | `false` | none | no | `false` / `postgresql` / `parquet`. `postgresql` writes into (and is queried from) the main `database`, which must then be `backend: postgresql`; `parquet` writes export-only files on any backend. |
| `public_trades.retention_days` | int | `7` | days | no | Days to retain; an hourly task drops whole expired units, starting at startup. `0` = keep forever. |
| `public_trades.parquet` | block | none | none | no* | Parquet sink config (`path`, `rotation_secs` default 3600, `max_rows_per_file` default 1000000). *Required only when `persist: parquet`. |
| `order_book.persist` | enum | `false` | none | no | `false` / `postgresql` / `parquet`. Order book frames are never queryable through the API. |
| `order_book.retention_days` | int | `0` | days | no | Days to retain; `0` (default) = keep forever. Whole-unit drops only (Postgres daily partitions / Parquet files), never a row-by-row delete. |
| `order_book.postgres` | block | none | none | no* | Postgres connection override; else the main `database` Postgres connection is inherited (requires `database.backend: postgresql`). |
| `order_book.parquet` | block | none | none | no* | Parquet sink config (same fields as above). *Set `persist: parquet` to use it. |

> [!CAUTION]
> `public_trades.persist: postgresql` requires `database.backend: postgresql` or the gateway refuses to start; `parquet` is export-only and works on any backend. Size the writer channel for the write load and set `retention_days` to bound disk growth. Drops happen at whole-unit granularity (daily partitions or rotated files).

```bash
# market_data:
#   channel_capacity: 65536
#   batch_size: 256
#   public_trades:
#     persist: postgresql        # false | postgresql | parquet
#     retention_days: 7          # 0 = keep forever
#     # parquet:                 # required only when persist: parquet
#     #   path: "/var/lib/voltnir/public_trades"
#     #   rotation_secs: 3600
#     #   max_rows_per_file: 1000000
#   order_book:
#     persist: postgresql        # false | postgresql | parquet
#     retention_days: 0
#     # parquet:                 # required only when persist: parquet
#     #   path: "/var/lib/voltnir/orderbook"
#     #   rotation_secs: 3600
#     #   max_rows_per_file: 1000000
```

<a id="licensing" name="licensing"></a>

## licensing

License validation. The section is optional, but a valid license is required: there is no unlicensed run mode. Obtain the signed license JSON from the Voltnir customer portal.

| Field | Type | Default | Unit | Required | Description |
| --- | --- | --- | --- | --- | --- |
| `license_path` | string | `./license.json` | path | no* | Path to the portal-signed license file. *A valid license is required at startup, so this must resolve to one. |

> [!WARNING]
> **Expiry: 14-day grace, then a hard stop.** A missing `license_path`, a bad signature, an unknown signing key, or an identity mismatch **refuses startup**. An expired license keeps running for a **14-day grace period**, with escalating warnings logged and surfaced to clients; validity is re-evaluated hourly, and once the grace period lapses the license is fatal (startup is refused and a running instance shuts down). Renew the license from the customer portal before the grace period ends.

```
licensing:
  license_path: "./license.json"
```

<a id="self_trade" name="self_trade"></a>

## self_trade

Self-trade (cross-trade) prevention. EPEX M7 does not prevent self-trades server-side; it only flags them after the fact. This is a Voltnir-side pre-trade check: before an order is sent to M7, the gateway looks for one of your own resting orders on the opposite side at a crossing price and applies the configured policy. The section is optional and defaults to `observe`. This value only seeds the default on a fresh database; the active policy is runtime-mutable via `GET/PUT /api/v1/self_trade_policy` and, once the profile row exists, wins on reboot.

| Field | Type | Default | Unit | Required | Description |
| --- | --- | --- | --- | --- | --- |
| `policy` | enum | `observe` | none | no | `observe` = detect & log the self-cross but let the order through (the M7 `selfTrade` flag is still recorded). `reject` = block the aggressor before it reaches M7 (HTTP 422 / gRPC `FAILED_PRECONDITION`, reason `SELF_CROSS_BLOCKED`). |

```
self_trade:
  policy: observe
```

<a id="slot_limit" name="slot_limit"></a>

## slot_limit

The slot position limit, a second position check beside the per-contract limit. A slot is a 15-minute delivery period. A balancing group is settled on one net MW figure per slot, whichever product the MW came from, so this limit adds up every contract that covers a slot: XBID and local, hour, half-hour and quarter-hour, Base, Peak and any block, each at its full MW in every slot it covers. Contracts that follow each other in time do not add up. Open orders count on their own side only, so a buy is never offset by a sell resting on another contract. While every delivery window is known, an order that makes no bound worse is admitted. When the check needs a delivery window it cannot place (the order's own contract's, that of open orders on a contract with no known window, or that of a trade with no window), it fails closed: Voltnir cannot tell whether a new order reduces the missing exposure or adds to it, so only cancels and amendments that add no quantity (a shrink, or a reprice at the same size) pass, and every new order and activation is refused with `SLOT_WINDOW_UNKNOWN`. A missing open-order window does this for the whole delivery area, as does a trade with no window whose execution time is unknown too. A trade with no window that executed at a known time does it only on the slots its delivery can lie in, up to the end of the delivery day after the one it executed on (in GB, to 23:00 London two days after it), until then. A trade with no window announces its lock as a `slot_limit_notice` entry on the message log, once per trade per run. A cancel is never checked. The section is optional and defaults to `off`. These values only seed a fresh database; once the profile row exists it wins on reboot, so an existing installation keeps `off`. The runtime control is `PUT /api/v1/slot_limit` (WS `set_slot_limit`, gRPC `SetSlotLimit`; permission `set_position_limit`), and a member's own slot limit is `max_slot_position` on the member.

| Field | Type | Default | Unit | Required | Description |
| --- | --- | --- | --- | --- | --- |
| `mode` | enum | `off` | none | no | `off` = the check does not run. `observe` = every order is admitted; one that `reject` would refuse is written to the audit trail (`slot_limit_would_refuse`, identical ones within 10 seconds collapsed into one row with a count), counted on `/metrics` and logged. `reject` = such an order is refused (HTTP 422 / gRPC `FAILED_PRECONDITION`, reason `SLOT_POSITION_LIMIT_EXCEEDED` or `SLOT_WINDOW_UNKNOWN`). Start in `observe`. |
| `house_limit` | integer | `0` | sub-MW (1 MW = 1000) | no | The House slot limit: the most the desk's net position in any one slot may reach, long or short. `0` is flat-only. |

```
slot_limit:
  mode: off
  house_limit: 0
```

<a id="cash_limit" name="cash_limit"></a>

## cash_limit

The static methodology settings for the cash-limit risk engine. The section is optional. The cash limit caps the money at risk (open orders plus executed trades in the current window) and is enforced alongside the MW position limit: an order must pass both. Only the five keys below live in this file. The limit itself comes from the exchange, and the caps you set on top of it are runtime values: the desk-wide cap through `GET/PUT /api/v1/cash_limit`, a member's cap through the member endpoints. A `fail_closed:` key left over from an older configuration is ignored. See [What Voltnir handles automatically](#automatic) for the full picture.

| Field | Type | Default | Unit | Required | Description |
| --- | --- | --- | --- | --- | --- |
| `gbp_delivery_areas` | list<string> | `[]` | EIC | no | **Extra** delivery-area EICs that settle in ECC's GBP pool, unioned with the always-on built-in GB area (`10YGB----------A`). Empty (default) means Great Britain settles GBP and every other area settles EUR. Add an EIC here only if ECC starts settling a further zone in GBP. |
| `gbp_sell_reservation_per_mwh_cents` | int | `0` | GBP cents/MWh | no | **Fallback only**, used for a GBP delivery area the exchange has published no risk set for. Flat GBP sell-reservation rate, applied when `gbp_sell_reservation_schedule` is empty (or no scheduled rate is yet effective). `0` reserves nothing. This is ECC's GB price-independent delivery-risk parameter for continuous trading (sell only), published in whole GBP per MWh, so multiply by 100; it is a three-figure GBP/MWh number, not a single-digit one. It is the same quantity the exchange publishes as the GB risk set's sell parameter, so set it to keep the gateway protected before that report arrives. |
| `gbp_sell_reservation_schedule` | list | `[]` | none | no | **Fallback only**, same as the flat rate above. Effective-dated GBP reservation rates; each entry is `{ effective_from: "YYYY-MM-DD", rate_per_mwh_cents: N }`. A revised rate applies **at the 16:00 reset** on its `effective_from`, not from midnight, so the rate in force is the entry with the latest `effective_from` on or before the date of the *current window's* 16:00 reset (in `exposure_window_timezone`); before any is effective, the flat rate above is used. An `effective_from` that falls on a weekend or a closing day gets no reset of its own and takes hold at the first reset on or after it. |
| `exposure_window_timezone` | string | `"Europe/Amsterdam"` | IANA tz | no | IANA timezone for the exposure-window reset. ECC clears at **16:00 in this zone** each working day (a regulatory reference, not a user preference), so it defaults to `Europe/Amsterdam` (handles CET/CEST automatically). An unparseable value falls back to `Europe/Amsterdam` with a warning. |
| `max_report_age_sec` | int | `0` (off) | s | no | **Optional** hard ceiling on the age of a pool's last cash-limit report. Past it the ECC limit and the exchange's remaining amount are treated as **unknown**, which is zero, so no order may add exposure in that pool (risk-free orders and every cancel are unaffected). `0`, the default, leaves it off, and off is the supported setting: staleness is already enforced without it, by the generation of the broadcast channel each report arrived on, so a pool is refused the moment the channel carrying its reports breaks. Turning this on buys the one case that check cannot see, a channel that stays up while silently not delivering the member routing key, and costs a fail-closed refusal in any pool nothing has reported on for that long. **Nothing refreshes that age on a quiet desk**: the gateway does not poll the exchange on a timer, so a quiet stretch longer than the ceiling (a weekend included) stops that pool trading until the exchange next reports it. Setting it logs a warning saying exactly that. |
| `delivery_risk_applied` | bool | `true` | none | no | Whether the exchange charges this member the **GB delivery-risk add-on**: the GB risk set's price-independent `alpha` per MWh on GB sells, or the GBP sell-reservation fallback rate above when no risk set has arrived. The exchange charges it only to a member whose record says so, and states that record only when it changes, never on request. So this key decides until the exchange has said; once this member's own record has been seen it wins over this key, is stored in the database and keeps winning after a restart. `true`, the default, charges the add-on, so the gateway never shows more GBP headroom than the exchange would. Set `false` only when your clearing member confirms the add-on does not apply to you. With `false`, GB orders and trades are priced with the product's default risk set as the exchange publishes it, the set the exchange prices such a member's GB legs with, and the fallback rate is not charged; until that set has arrived they are priced with the GB risk set less its add-on. With `true` they are priced with the GB risk set, add-on included; that pricing has not been measured against the exchange. The status block's `cash_limit.delivery_risk_applied` and `delivery_risk_source` show what is in force. If the exchange's GBP figure shows this setting to be wrong, the gateway logs one warning per run. |

> [!NOTE]
> **The GBP sell-reservation settings are a fallback, not the methodology.** The gateway takes the GB delivery-risk add-on from the exchange's own risk set for the product, so these settings apply only while that report has not arrived, and are ignored once it has. Either way the add-on is charged only while `delivery_risk_applied` is in force; while it is not, GB legs are priced with the product's default risk set. Take the current value from ECC's published risk parameters; ECC revises it roughly monthly, so keep it current for any GB trading. It protects the desk before the risk set lands and is superseded automatically afterwards.

> [!NOTE]
> **Startup and runtime warnings, never a refusal to start.** At startup the gateway warns if `exposure_window_timezone` is not `Europe/Amsterdam`, since the 16:00 boundary would then not align with ECC's. Separately, whenever the exchange reports a GBP cash limit greater than zero and no GBP sell-reservation rate is configured, the gateway warns that GB sells will reserve nothing and understate cash at risk. Neither warning refuses startup.

> [!NOTE]
> Bank holidays for the exposure window are **not configured here**. They are runtime-managed (separate EUR and GBP calendars) via the `/api/v1/holidays` endpoint and its gRPC / WS equivalents, and the gateway fills the standard closing days in itself; see [What Voltnir handles automatically](#automatic).

```
cash_limit:
  gbp_delivery_areas: []
  gbp_sell_reservation_per_mwh_cents: 0
  gbp_sell_reservation_schedule: []
  exposure_window_timezone: "Europe/Amsterdam"
  max_report_age_sec: 0
```

<a id="load_management" name="load_management"></a>

## load_management

M7 counts every order entry, modify, activation, hibernation and deletion this member's API clients send, accepted or rejected alike, inside two rolling observation windows, a short one (10 s in EPEX's published configuration) and a long one (24 h). Each has an L1 warning threshold and an L2 hard one. The gateway counts its own order actions against M7's last reported member load and refuses order actions before the exchange would. Remaining headroom, the estimated member load and the current block reason are on `GET /throttling`, the WS status frame and gRPC `GetThrottling`.

> [!CAUTION]
> Reaching L1 broadcasts a warning and starts a tolerance clock; reaching L2, or staying at L1 for the whole tolerance, **restricts the whole member**: every API order action is rejected by the exchange until the restriction is released, and each further attempt pushes that release further out. A client that keeps retrying while restricted is disconnected and suspended, its orders are deleted, and reactivation is a phone call to EPEX Market Operations. The guard therefore refuses exposure-adding actions (new order, reprice, resize, activate) once the projected member load would reach L1 on either rule; exposure-reducing actions (delete, hibernate, delete-all) are never refused by that threshold, so a desk can always get flat; while M7 reports the member restricted, both are refused, because sending them anyway only delays the release.

| Field | Type | Default | Unit | Required | Description |
| --- | --- | --- | --- | --- | --- |
| `enabled` | bool | `true` | none | no | When `false`, the gateway counts and reports order actions but never refuses one, relying on M7's own throttling to stop it (with the order deletion and manual reactivation that can follow). Logs a warning at startup. |
| `max_report_age_sec` | int | `30` | s | no | How old the exchange's last throttling report may be before the member's load is treated as unknown. Past it, no order may add exposure until the exchange reports again; cancels and hibernations are unaffected, so the desk can always get flat. The report is the only view of what other API clients on this member have spent, so without a current one the gateway sees its own traffic alone and could be walked to the warning threshold blind. It also bounds a restriction: while the exchange still stands behind one, a restriction refuses every order action including cancels; once it no longer does, cancels come back. `0` turns the bound off. 30 s is six missed answers of an inquiry that runs every 5 s. This defaults on while `cash_limit.max_report_age_sec` defaults off, because the throttling inquiry is polled while the cash-limit one is not. |
| `reserve_omts` | int | `0` | OMTs | no | Extra order-management transactions held back below L1, on top of the one the threshold itself costs. `0` guards one order action below L1, the last load that does not raise the warning. Raise it if another API client shares this M7 member and needs room of its own. |
| `fallback_short_observation_sec` | int | `10` | s | no | Short-window width used only until the exchange's first throttling report arrives; then the exchange's own figures are used and this is ignored. |
| `fallback_short_omt_limit_l1` | int | `1000` | OMTs | no | Short-window L1 threshold used until the exchange reports (EPEX's published production configuration). |
| `fallback_long_observation_sec` | int | `86400` | s | no | Long-window width used until the exchange reports. |
| `fallback_long_omt_limit_l1` | int | `20000` | OMTs | no | Long-window L1 threshold used until the exchange reports, set to the floor of the monthly allowance so a busier desk is under-stated rather than over-stated before the real figure lands. |
| `throttling_member_action` | string | `HIBE_MBR_ORDERS` | none | no | What the exchange does with **every** order of the member, whichever client entered it, when it restricts the member; stated by the gateway on every login. `HIBE_MBR_ORDERS` hibernates them all (they stay registered but leave the book, cannot fill and hold no exposure until reactivated) and overrides every user-level action, including the one the member's other trading software asked for. `NONE_MBR_ORDERS` leaves it to each user's own action. The exchange keeps the member-level value of the last login that stated one, so another client of the member logging in later can replace it until the gateway logs in again. The trade-off of `NONE_MBR_ORDERS`: the orders of a user whose own action is `NONE_USER_ORDERS` stay live through a restriction and can fill while the exchange rejects every order action of the member's API clients, cancels included. Reactivating a hibernated order is an order action and goes through this guard; the exchange's own hibernations are not counted as load. Shown on `GET /throttling` and logged at each login. **Validated at startup:** exactly these two values, case as written; any other value, an empty one included, refuses to start and names the accepted values. |
| `throttling_user_action` | string | `HIBE_USER_ORDERS` | none | no | What the exchange does with the orders of the M7 user the gateway logs in as when it restricts the member; stated on every login. `HIBE_USER_ORDERS` hibernates them, `HIBE_BG_ORDERS` hibernates every order of the user's balancing group, and `NONE_USER_ORDERS` none, unless the member-level action hibernates them anyway. Shown on `GET /throttling` and logged at each login. **Validated at startup:** exactly these three values, case as written; any other value, an empty one included, refuses to start and names the accepted values. |

```
load_management:
  enabled: true
  max_report_age_sec: 30
  reserve_omts: 0
  fallback_short_observation_sec: 10
  fallback_short_omt_limit_l1: 1000
  fallback_long_observation_sec: 86400
  fallback_long_omt_limit_l1: 20000
  throttling_member_action: HIBE_MBR_ORDERS
  throttling_user_action: HIBE_USER_ORDERS
```

<a id="system_log" name="system_log"></a>

## system_log

The gateway's own diagnostic output, captured in memory and served to clients holding the `read_logs` permission. This is **not** an audit record: the ring lives in RAM, is bounded by entry count first and age second, is lost on every restart, and drops entries under load. The durable, rotated, restart-surviving copy is stdout, which the shipped unit file hands to journald. This is the copy a trader can see from the terminal without an SSH session. Omit the whole section to capture at `info` into a 20 000-entry, 24-hour ring.

| Field | Type | Default | Unit | Required | Description |
| --- | --- | --- | --- | --- | --- |
| `enabled` | bool | `true` | none | no | Master switch. `false` captures nothing and answers every query with an empty buffer that says so. |
| `level` | enum | `info` | none | no | Capture threshold: `off` / `error` / `warn` / `info` / `debug`. Taken from here and never from `RUST_LOG`, so the panel does not depend on an operator's environment variable. `debug` floods: the order-book context logs on every book update. |
| `capacity` | int | `20000` | entries | no | Ring capacity in entries, the hard memory bound (roughly 6 MB at 20 000). Bounding on entries first is deliberate: bounding on time alone makes the footprint a function of the error rate, which peaks exactly when the box is already unhealthy. Must be at least 1. |
| `max_age_hours` | int | `24` | hours | no | Age bound, swept hourly. `0` = no age limit (capacity still applies); a negative value is rejected at startup. |

```bash
# system_log:
#   enabled: true
#   level: info          # off | error | warn | info | debug
#   capacity: 20000
#   max_age_hours: 24
```

<a id="logging" name="logging"></a>

## logging

The shape of the gateway's stdout log, the durable copy your service manager keeps. The level is not set here: it comes from the `RUST_LOG` environment variable and is `info` when `RUST_LOG` is unset or empty. The gateway's own messages on stdout are the ones a client holding `read_logs` reads from the [system log](#system_log), so treat the two as one surface. Omit the whole section for the text format.

| Field | Type | Default | Unit | Required | Description |
| --- | --- | --- | --- | --- | --- |
| `format` | enum | `text` | none | no | Line format, fixed at startup: `text` / `json`. `json` writes one object per line with `timestamp` (RFC 3339 UTC, milliseconds), `level`, `target`, `message`, `fields` (every other field of the event, numbers and booleans as JSON numbers and booleans (a non-finite number, or an integer wider than 64 bits, as a string), `{}` when there are none) and, for an event inside a span, `spans` (root first, each with `name` and `fields`). The value is exact and lowercase; any other value refuses to start with an error naming the accepted values. Startup errors and a panic report go to stderr as plain text in either format. |

```bash
# logging:
#   format: text         # text | json
```

One `json` line, wrapped here for reading:

```json
{"timestamp":"2026-10-12T09:30:00.125Z","level":"INFO","target":"voltnir_backend::m7",
 "message":"session up","fields":{"count":3}}
```

<a id="automatic" name="automatic"></a>

## What Voltnir handles automatically

Three things a desk once tracked by hand are now driven by the exchange's own reports. This is what the gateway does for you, and what that leaves you to do.

#### Cash limits come from the exchange

The trading limit your Clearing Member sets for you at ECC arrives from M7 per settlement currency and *is* the House cash limit; there is nothing to enter in this file. Two pools, EUR and GBP, are settled separately with no netting and no FX. You can add a **cap** via `GET/PUT /api/v1/cash_limit` to trade more conservatively than ECC allows: the limit in force is `min(ECC limit, cap)`, and a cap above the ECC limit is rejected, never clamped. There is no fail-open mode: a limit of zero, including an ECC limit that has not been reported yet, means **no trading** in that pool until the exchange reports it.

#### Exposure comes from the exchange's risk parameters

How much an order or trade consumes is computed from the exchange's own **risk set** for the contract's product and delivery area: eight price-dependent `a` parameters and four price-independent `alpha` parameters, which give `a × signed price × MWh + alpha × MWh`, with the case chosen by side, price sign, and order versus trade. An open order's exposure is floored at zero (a money-making order contributes nothing, never a credit) and every figure scales with the contract's delivery duration, so a 15-minute product counts a quarter of the same MW and price hourly product. On the exchange's default risk set this means a buy at a positive price consumes its value, a trade moves the limit by its full signed value, and the risk-free order cases (a sell at a positive price, a buy at a negative price) cost nothing. A GB delivery area carries a risk set whose `alpha` sell value is ECC's GB delivery-risk parameter, which is why a GB sell also consumes limit. You do not transcribe any of these parameters: the exchange publishes them and the gateway ingests them. The GBP sell-reservation settings in `cash_limit` are only a fallback for a GBP area whose risk set has not arrived, logged once per delivery area when it is taken.

#### The bank-holiday calendar fills itself

The exposure window resets at 16:00 (`exposure_window_timezone`) on ECC Business Days, so the gateway keeps a separate EUR and GBP bank-holiday calendar. It fills the standard closing days into both calendars itself, at startup and on an hourly check, and from December it loads the coming year as well, so the turn of the year needs no action. A date you enter by hand is never overwritten, and a derived date you delete stays deleted for that currency until you add it again. A currency whose calendar is empty, or holds no date in the current or the next year, refuses every order that adds exposure until a date is present, so this is a backstop rather than a routine task. Enter a date by hand only for an ad-hoc closure outside the standard days. Holidays are managed at runtime through `/api/v1/holidays` and its gRPC / WS equivalents, not in this file.

<a id="full-example" name="full-example"></a>

## Full Template

A complete reference configuration with every section. Copy it, save as `config.yml`, and replace each `<REPLACE_ME>`.

```
epex_settings:
  delivery_areas:
    - "<REPLACE_ME_AREA_EIC>"
  products:
    - "<REPLACE_ME_PRODUCT>"
  enable_hub_2_hub: false

system:
  max_ws_pong_age_ms: 15000
  max_ws_ob_delta_age_sec: 300
  max_wait_time_for_system_health_sec: 60
  max_startup_time_sec: 600
  order_ack_timeout_ms: 2000
  order_outcome_timeout_ms: 3000
  recall_outcome_wait_ms: 5000
  order_request_expiration_ms: 10000
  # pending_order_reap_age_ms: 25000
  max_requests_per_window: 6000
  request_window_seconds: 60
  trusted_proxies: []      # e.g. [127.0.0.1] behind a same-host nginx
  reports_dir: ./reports
  disable_trading: false
  trade_ingest_fault: close
  trade_ingest_fault_ack_ttl_sec: 1800

epex_connection:
  cert: "./cert/client-cert.pem"
  key:  "./cert/client-key.pem"
  application_id: "<REPLACE_ME_APPLICATION_ID>"
  account_id:     "<REPLACE_ME_ACCOUNT_ID>"
  environment: prod
  user_id:  "<REPLACE_ME_AMQP_USER>"
  password: "<REPLACE_ME_AMQP_PASSWORD>"
  totp:     "<REPLACE_ME_TOTP_BASE32_SECRET>"
  # extra_ca_path: "./cert/corporate-ca.pem"

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
  # backend: postgresql
  # url: "postgres://voltnir:secret@db-host:5432/voltnir"
  # max_connections: 4
  # audit_retention_days: 0
  # m7_errors_retention_days: 0
  # exchange_messages_retention_days: 0
  # orders_retention_days: 0
  # trades_retention_days: 0

# market_data:
#   channel_capacity: 65536
#   batch_size: 256
#   public_trades:
#     persist: postgresql
#     retention_days: 7
#   order_book:
#     persist: postgresql
#     retention_days: 0

licensing:
  license_path: "./license.json"

self_trade:
  policy: observe

slot_limit:
  mode: off
  house_limit: 0

cash_limit:
  gbp_delivery_areas: []
  gbp_sell_reservation_per_mwh_cents: 0
  gbp_sell_reservation_schedule: []
  exposure_window_timezone: "Europe/Amsterdam"
  max_report_age_sec: 0

load_management:
  enabled: true
  max_report_age_sec: 30
  reserve_omts: 0
  fallback_short_observation_sec: 10
  fallback_short_omt_limit_l1: 1000
  fallback_long_observation_sec: 86400
  fallback_long_omt_limit_l1: 20000
  throttling_member_action: HIBE_MBR_ORDERS
  throttling_user_action: HIBE_USER_ORDERS

# system_log:
#   enabled: true
#   level: info
#   capacity: 20000
#   max_age_hours: 24

# logging:
#   format: text
```

Copyright © 2026 Voltnir B.V. The Voltnir gateway is proprietary software, licensed under separate terms.
