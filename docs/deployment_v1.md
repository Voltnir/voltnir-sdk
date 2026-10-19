# Voltnir Deployment & TLS: Securing an On-Prem Gateway

> Auto-generated from the Voltnir API reference.

<a id="overview" name="overview"></a>

## Overview

The Voltnir gateway is a single binary you run on your own infrastructure. It speaks **plain HTTP and WebSocket** on its listening ports; there is no in-process TLS for the REST, WebSocket, or terminal surfaces (gRPC is the one exception, see below). That is by design: on-prem operators terminate TLS at a reverse proxy they control, with their own certificate and security policy.

This guide shows the recommended, battle-tested setup: **nginx terminating TLS in front of the gateway, one certificate, the gateway bound to loopback.** It works with the gateway as shipped: no special build, no extra config beyond the bind address.

> [!WARNING]
> **Never expose the gateway's plain ports to an untrusted network.** The REST and WebSocket surfaces carry order flow and account data in clear text. Bind them to `127.0.0.1` and let the proxy be the only thing the network can reach.

<a id="requirements" name="requirements"></a>

## Requirements

Before any proxy work, get the binary starting cleanly on the host. It needs a config file, a valid license, and the M7 client identity from your EPEX onboarding.

| Item | Where | Notes |
| --- | --- | --- |
| `config.yml` | `-c` flag | Start from the shipped `config.yml.dist` template; full field reference in the [config.yml guide](config_yml_dist.md). It contains credentials; make it readable by the service user only. |
| License file | `license_path` in `config.yml` | Required. There is no unlicensed run mode. The license must permit the configured `epex_connection.environment` (`sim` / `prod`) or startup is refused. It must also be signed with a current signing key. See the upgrade note below. |
| M7 client TLS identity | `epex_connection.cert` / `epex_connection.key` | PEM certificate + private key from your EPEX onboarding pack, presented to M7. Keep the key file mode `600`. |
| Outbound network | firewall egress | The gateway dials EPEX M7 (AMQP + WebSocket) outbound over TLS. Behind a TLS-inspecting proxy or a private CA, point `epex_connection.extra_ca_path` at a PEM bundle of the extra trust roots. |

<a id="install" name="install"></a>

## Install

Put the gateway on the host, start it once to mint the admin credentials, then run it under a supervisor that owns its lifecycle.

1. Place the binary, `config.yml`, the license file and the `cert/` directory together in one install directory, and make that the process working directory.
2. Start the gateway once by hand and capture the admin API key it writes, then delete the credentials file (see First start below).
3. Install the systemd unit so a supervisor starts, stops and restarts it (see systemd unit below).

#### First start

On an empty database the gateway creates the `admin` account and writes its API key to `./VOLTNIR_CREDENTIALS.txt`, the only time the key exists in plaintext. Log in, create your own users, then delete the file.

> [!CAUTION]
> **Run from the install directory.** Relative paths (the default report directory `./reports`, the default SQLite store `./voltnir.db`, `./VOLTNIR_CREDENTIALS.txt`, and any relative `cert/` paths in `config.yml`) resolve against the process working directory. Set it explicitly in the service unit.

> [!NOTE]
> **Upgrade note: generated reports moved.** Reports used to be written into the working directory at whatever the process umask allowed. They are now written mode `0600` into `system.reports_dir` (default `./reports`, created `0700`). **Every** start also sweeps the working directory for `orders_*` / `trades_*` files and deletes them, on the first start after the upgrade that retires the world-readable reports earlier builds left there, and it keeps the two prefixes **reserved** in that directory afterwards, so do not keep a file of your own named that way beside the binary. Nothing to do by hand; if the account the gateway runs as cannot delete one of those files it stays, and it is not counted in the startup log line, so check the directory yourself after the first start on a box whose ownership has changed.

#### <a id="systemd" name="systemd"></a>systemd unit

```bash
# /etc/systemd/system/voltnir.service
[Unit]
Description=Voltnir gateway
After=network-online.target
Wants=network-online.target

[Service]
User=voltnir
WorkingDirectory=/opt/voltnir
ExecStart=/opt/voltnir/voltnir -c /opt/voltnir/config.yml
Environment=RUST_LOG=info
Environment=RUST_BACKTRACE=1
KillSignal=SIGINT
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

> [!NOTE]
> The gateway drains its subsystems on **SIGINT** (Ctrl-C) *and* on **SIGTERM**, which is what systemd, `systemctl kill` and `docker stop` send by default. Both take the same graceful path: the client transports stop accepting and finish the requests they hold, the M7 session is logged out, every queued database write is committed, and the shutdown is recorded in the audit log with what the run lost per stream. Committing the queued writes is bounded at 30 seconds; a write it cannot commit in that time is counted in `writes_dropped` (a trade in `trades_persist_failed`), never dropped silently. A stop that skips this path (SIGKILL, a crash, a power loss) leaves no shutdown row, and the next start records a `system_unclean_exit` audit row. The unit's default stop timeout (90 s) leaves room for all of it. `KillSignal=SIGINT` above is kept for continuity with existing installs; the clean shutdown no longer depends on it, so a unit that omits it stops just as cleanly.

<a id="run" name="run"></a>

## Run

Day-to-day operation: how the gateway is launched, and how a restart behaves.

#### Invocation & flags

```
voltnir -c config.yml
```

| Flag | Meaning |
| --- | --- |
| `-c`, `--config <path>` | Path to the YAML config file. Required on every invocation. |
| `--reset-admin` | Rotate the `admin` user's API key, write the new key to `./VOLTNIR_CREDENTIALS.txt`, and exit. For when the original credentials file is lost. |
| `--vacuum` | Hand the database's unused space back to the disk in one go, print its size before and after, and exit. Out of hours only: it rewrites the whole database, so stop the gateway first and run it as the service user from the install directory. It refuses, and changes nothing, while anything else has the database open: a running gateway, or on PostgreSQL any other session on that database. An autovacuum worker counts as a session too, so on PostgreSQL it can refuse while the gateway is already stopped, most likely just after a large prune; wait for the worker to finish and run it again. It connects to no exchange and binds no port. On PostgreSQL it runs `VACUUM (FULL, ANALYZE)` on each table retention prunes (orders, trades, their payload tables and the three logs); it does not reclaim space held by market-data capture. It needs free disk space while it runs: up to twice the SQLite file (part of it in the temporary directory: `SQLITE_TMPDIR` if set, else `TMPDIR`, else `/var/tmp`), or on PostgreSQL a copy of the largest table with its rebuilt indexes, plus the write-ahead log the rewrite produces. Cannot be combined with `--reset-admin`. See [Database care](#database-care) for when to run it. |

The gateway logs to stdout. The level comes from the standard `RUST_LOG` environment variable and is `info` when it is unset or empty, so a gateway started by hand, in a container or under any supervisor reports its lifecycle as well as its errors; set `RUST_LOG=warn` for less or `RUST_LOG=debug` for more. The line format is `logging.format` in `config.yml`: `text` by default, or `json` for one object per line that a log shipper can read without parsing (see the configuration reference for its fields). Startup errors and a panic report go to stderr as plain text in either format. `RUST_BACKTRACE=1`, set in the unit above, adds a backtrace to a panic report. Both variables belong to the logging library and the Rust runtime; every setting of the gateway's own lives in `config.yml`.

#### <a id="restart" name="restart"></a>Restarting the gateway, and why the exit status is 75

An operator can restart the gateway from any transport: REST `POST /api/v1/restart`, the WebSocket `restart` command, the gRPC `Restart` RPC, with the `restart_system` permission. All three run the same sequence as a termination signal: the request is recorded as a `system_restart` audit event naming the caller, the response is answered first, then the shutdown is recorded, buffered rows are flushed, the client transports drain and the M7 session is logged out. The process then **exits**, and the supervisor starts a fresh one, which is what makes an edited `config.yml` take effect. There is no in-place configuration reload.

> [!CAUTION]
> **The restart path exits with status 75, not 0, and that is deliberate.** `Restart=on-failure`, in the unit above and in the one shipped with the release, restarts the unit on a non-zero status and leaves it stopped on a clean one. The gateway needs both outcomes: `systemctl stop` sends SIGTERM and must stay stopped, while an operator restart must come back. So the signal path returns 0 and the restart path exits 75 (`EX_TEMPFAIL` from `sysexits.h`). Expect `journalctl` to log `Main process exited, code=exited, status=75` followed by the restart. That line is the restart working, not a fault. Under `Restart=always` both paths come back, and `systemctl stop` still stops the unit because systemd stops supervising a unit it was told to stop.

> [!CAUTION]
> **A gateway started without a supervisor simply stops.** Run straight from a shell, from a `tmux` pane, or under a container with no restart policy, the restart request is a shutdown: the process exits and nothing brings it back. Check for a supervisor before handing anyone the `restart_system` permission, and note that `StartLimitBurst` caps how many restarts systemd will attempt inside `StartLimitIntervalSec` before it gives up and leaves the unit failed.

<a id="m7-logout" name="m7-logout"></a>**M7 can end the process too.** When M7 logs the gateway's session out without being asked (another login on the same exchange user, a password change, or `INACTIVITY` after the connection dropped), the gateway takes the same path: it records an `m7_session_logged_out` audit event, runs the clean shutdown and exits 75, and the supervisor starts a fresh process that logs in again. `RestartSec=5s` in the shipped unit also keeps the 5 seconds M7 requires between a logout and the next login. Give the gateway an exchange user that nothing else logs in with: a second login on that user pushes the gateway out, the restarted gateway pushes the other session out, and the two keep doing so. `voltnir_m7_session_logouts_last_hour` counts these logouts across restarts, and the shipped rule `VoltnirM7SessionLoggedOut` fires above 2 an hour.

**What survives a restart:** everything in the database (orders, trades, the audit trail) and the persisted profile, so the kill switch, position limit, self-trade policy and both holiday calendars, with any derived TARGET2 date you deleted from them, come back as they were. **What does not:** every open WebSocket connection and its subscriptions, every outstanding export token, and the in-memory throttling and market-state snapshot, which is rebuilt from the exchange on the new process's first sync. Clients must reconnect, re-authenticate and re-subscribe.

> [!NOTE]
> **A restart is not the gateway's own exchange reconnect.** When an M7 subsystem gives up (the AMQP connection past its retry budget, or a health check degraded beyond its grace window) the gateway cycles the exchange tasks in place after an exponential back-off and *keeps running*: no client transport is dropped and no configuration is re-read. That is logged as `Unrecoverable error, reconnecting the exchange subsystems`. An operator restart is logged as `Operator requested a gateway restart` with the user, followed by the exit. The two are deliberately distinguishable in the journal.

<a id="topology" name="topology"></a>

## Ports and network topology

A fully-enabled gateway listens on four ports. The proxy fronts each one.

| Port | Surface | Protocol | Who connects | Config key |
| --- | --- | --- | --- | --- |
| `8080` | Trading terminal (SPA) | HTTP | Browsers | `trading_terminal.port` |
| `3000` | REST API v1 | HTTP | Browsers, ops tools | `rest_server.port` |
| `9001` | Live-data feed | WebSocket | Browsers, SDKs | `ws_server.port` |
| `3443` | gRPC API v1 | HTTP/2 | SDKs, services | `grpc_server.port` |

> [!NOTE]
> The terminal SPA (`:8080`), REST (`:3000`) and WebSocket (`:9001`) are documented here. gRPC (`:3443`) can terminate TLS *in-process*; see [the gRPC note](#grpc).

#### <a id="discovery" name="discovery"></a>How the UI finds the backend

This one fact decides the whole proxy layout, so read it before writing any nginx.

The terminal is a static single-page app served from `:8080`. At load it fetches `/config.js` from the gateway, which advertises the REST and WebSocket **ports**, not full URLs:

```
window.__VOLTNIR_CONFIG__ = {apiPort: 3000, wsPort: 9001};
```

The SPA then builds its backend URLs from **the browser's own address bar**: it takes the *hostname* you loaded the page on, the page's *scheme* (`https` → `wss`), and those advertised ports. So if a user opens `https://trading.example.com/`, the SPA will call:

```
REST  →  https://trading.example.com:3000
WS    →  wss://trading.example.com:9001
```

> [!CAUTION]
> **Consequence:** REST and WebSocket must be reachable **over TLS**, at the **same hostname**, on **the same port numbers** the gateway advertises (`3000` / `9001`). That is exactly what the per-port proxy below delivers, and why **one certificate** for that hostname covers every port (TLS certificates are bound to a host, not a port).

<a id="bind" name="bind"></a>

## 1 · Bind the gateway to loopback

Bind the gateway to `127.0.0.1`, so the proxy can own the public IP on the same port numbers and nothing but the proxy can reach the plain ports. This step is not optional: every server's `host` **defaults to `0.0.0.0`** (all interfaces), and all four servers default to enabled.

```
rest_server:
  enable: true
  host:   "127.0.0.1"
  port:   3000

ws_server:
  enable: true
  host:   "127.0.0.1"
  port:   9001

trading_terminal:
  enable: true
  port:   8080   # binds ws_server.host (127.0.0.1)
```

> [!NOTE]
> Binding to `127.0.0.1` is what lets nginx `listen` on the **public** IP using the *same* port numbers without a collision: `127.0.0.1:3000` and `203.0.113.10:3000` are different sockets. (If the proxy runs on a *separate* host, bind the gateway to the private interface that host reaches instead.)

<a id="nginx" name="nginx"></a>

## 2 · nginx per-port TLS

One `server` block per surface, each terminating TLS on the public IP and proxying to the gateway on loopback. All three share the one certificate for the hostname.

Put the TLS-hardening directives once at the `http {}` level (shown in the [full example](#full-example)), then:

```bash
# --- Terminal SPA: public 443 -> gateway 8080 ---
server {
    listen 203.0.113.10:443 ssl;
    http2 on;
    server_name trading.example.com;

    ssl_certificate     /etc/nginx/certs/trading.example.com.pem;
    ssl_certificate_key /etc/nginx/certs/trading.example.com-key.pem;

    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto https;
    }
}

# --- REST API: public 3000 -> gateway 3000 ---
server {
    listen 203.0.113.10:3000 ssl;
    http2 on;
    server_name trading.example.com;

    ssl_certificate     /etc/nginx/certs/trading.example.com.pem;
    ssl_certificate_key /etc/nginx/certs/trading.example.com-key.pem;

    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains" always;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

> [!NOTE]
> The SPA `server` block also serves `/config.js` (it proxies to `:8080` like everything else), so no special location needed. The gateway's SPA handler already serves any unknown path as the app shell, so client-side routing works through the proxy unchanged.

#### <a id="websocket" name="websocket"></a>WebSocket upgrade (port 9001)

The live-data feed is a long-lived WebSocket at `/ws/v1` (the versioned endpoint; `/` and `/v1` are accepted as transition aliases), so its block needs the HTTP/1.1 upgrade dance and a generous read timeout. Without these, nginx buffers or drops the connection. A plain `location /` covers all three paths.

```bash
# put this map once, at http {} level:
map $http_upgrade $connection_upgrade { default upgrade; '' close; }

# --- WebSocket feed: public 9001 -> gateway 9001 ---
server {
    listen 203.0.113.10:9001 ssl;
    server_name trading.example.com;

    ssl_certificate     /etc/nginx/certs/trading.example.com.pem;
    ssl_certificate_key /etc/nginx/certs/trading.example.com-key.pem;

    location / {
        proxy_pass http://127.0.0.1:9001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade    $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_set_header Host       $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 3600s;   # the feed is persistent
    }
}
```

#### <a id="grpc" name="grpc"></a>gRPC (port 3443)

gRPC is different: it is the one surface that can terminate TLS **in the gateway itself**. Set the `grpc_server.tls` block in `config.yml` and SDKs connect to `:3443` over TLS directly, with no proxy required. If you do prefer to front it, use nginx `grpc_pass` with `http2`; plain `proxy_pass` will not carry HTTP/2 trailers correctly.

```bash
# config.yml, terminating gRPC TLS in-process (simplest):
grpc_server:
  enable: true
  host:   "0.0.0.0"
  port:   3443
  tls:
    cert_path: "./cert/grpc-server-cert.pem"
    key_path:  "./cert/grpc-server-key.pem"
```

Fronted by nginx instead, with the gateway's gRPC bound to loopback and no `tls` block:

```bash
# --- gRPC: public 3443 -> gateway 3443 ---
server {
    listen 203.0.113.10:3443 ssl;
    http2 on;
    server_name trading.example.com;

    ssl_certificate     /etc/nginx/certs/trading.example.com.pem;
    ssl_certificate_key /etc/nginx/certs/trading.example.com-key.pem;

    location / {
        grpc_pass grpc://127.0.0.1:3443;
        grpc_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        grpc_read_timeout 3600s;   # Watch* streams are long-lived
    }
}
```

#### <a id="client-address" name="client-address"></a>Recording the caller's address

Every audit row records the address a request came from, and failed logins are written to the trail at most once a minute per address. Behind this proxy every connection reaches the gateway from `127.0.0.1`, so without one more setting every row reads `127.0.0.1` and the failed logins of all callers count as one source. The `X-Forwarded-For` lines above make nginx append each caller's address; list the proxy's own address in `system.trusted_proxies` so the gateway reads it:

```bash
# config.yml
system:
  trusted_proxies:
    - 127.0.0.1   # nginx on this host; use the proxy's private address if it runs elsewhere
```

> [!CAUTION]
> The gateway reads `X-Forwarded-For` only from a listed address, and believes whatever a listed address writes there. List the proxy alone, never a client network: a wide range lets any client inside it choose the address its requests are recorded under. `0.0.0.0/0` and `::/0` are refused at startup. Use `$proxy_add_x_forwarded_for` as shown, which appends; a proxy that passes the client's own header on unchanged lets the client write its own address.

<a id="database" name="database"></a>

## Database backend (internal / PostgreSQL)

The gateway persists orders, trades, users, and the audit trail to a database chosen at startup. A single binary carries both drivers, so pick one in `config.yml`; no rebuild needed.

| Backend | What it is | When to use |
| --- | --- | --- |
| `internal` | Embedded SQLite file (the default, historical behavior). Stored at `database.path` (default `./voltnir.db`), with WAL side-files alongside. | Single-node installs; nothing extra to operate. Back up the `.db` + `-wal` + `-shm` together. |
| `postgresql` | External PostgreSQL server. Schema is created automatically on first connect. | When you already run Postgres, need centralized backups/replication, or want the store off the gateway host. |

```bash
# config.yml, pointing the gateway at an external PostgreSQL:
database:
  backend: postgresql
  url: "postgres://voltnir:<password>@db-host:5432/voltnir"
  # or discrete fields: host / port / user / password / dbname
  max_connections: 4
```

> [!NOTE]
> Omit the `database` section entirely to keep the embedded SQLite store; existing deployments need no change. Full field reference is in the [config.yml guide](config_yml_dist.md) under `database`.

> [!CAUTION]
> **Postgres is a network service:** the gateway opens a TCP connection to it, so reach it over a trusted network (or TLS in the connection URL), and treat `database.password` like the rest of `config.yml`: sensitive, never committed. The gateway creates its own tables; point it at an empty database (or one it already owns).

#### <a id="database-care" name="database-care"></a>Database care

- **One gateway per database.** Two gateways on one database are not a supported set-up: they would share users, API keys and stored settings, and each would prune every row to its own retention windows.
- **PostgreSQL requirements.** Version 16 or newer (an older server is refused at startup, naming the version found). Keep `autovacuum` and `track_counts` on, as they are by default: without them the rows retention deletes are never cleaned up, and the gateway does not check. Connect directly or through a pooler in session mode, never in transaction mode (PgBouncer `pool_mode = transaction`): the schema is applied under a session-level lock.
- **Changing a retention window.** Every window defaults to `0`, keep forever. Switch a window on, or shorten it a long way, with trading stopped; see the `database` section of the [config.yml guide](config_yml_dist.md). The first start after the gateway has been stopped for weeks, or after restoring an old backup, runs the same large first pass. Lengthening a window needs no care.
- **Disk does not shrink on its own.** New rows reuse the space a prune frees. The SQLite store hands a small amount back after each hourly pass, so after a large prune the file takes weeks or months to shrink; PostgreSQL keeps the space. To get it back at once, stop the gateway and run `--vacuum` ([flags](#run)), after a one-off event such as a shortened window or an upgrade that dropped a column, not on a schedule.
- **An upgrade that adds indexes.** The first start builds them before the gateway takes writes, so it takes longer. On PostgreSQL some are built with `CREATE INDEX CONCURRENTLY`, with a log line naming each, and each build waits for every transaction open in the database: end a running `pg_dump`, a long report or an idle-in-transaction session first, and make sure no `statement_timeout` (on the server or the gateway's role) cancels a build of tens of seconds. A start cut short mid-build is recovered on the next start. Every start also waits for any index build already running in the database, yours included, so do not start the gateway during a `pg_restore` or `pg_repack`.

<a id="safety" name="safety"></a>

## Safety checklist

The "do it safe" part. Each item below has bitten someone, so treat them as required, not optional.

| Check | Why |
| --- | --- |
| Gateway bound to `127.0.0.1` (or a private interface) | The plain HTTP/WS ports must be unreachable from the network. The proxy is the only public listener. |
| Firewall blocks the gateway's plain ports | Defense in depth: even if a bind is misconfigured, the network drops it. |
| **No mixed content**: REST and WS are TLS too | A page loaded over `https` *cannot* open a plain `ws://` or call `http://`; browsers block it silently. If the SPA is HTTPS, `:3000` and `:9001` must be HTTPS/WSS. |
| HSTS enabled (`Strict-Transport-Security`) | Forces TLS on every future visit; closes the first-request downgrade window. |
| Security headers set (`X-Frame-Options`, `X-Content-Type-Options`) | Clickjacking and MIME-sniffing protection for the terminal. |
| Modern TLS only (1.2 + 1.3, strong ciphers) | See the `http {}` hardening in the full example. |
| gRPC also TLS (in-process or proxied) | The SDK surface carries the same order/account data as REST. |
| Certificate auto-renews | An expired cert takes the whole terminal down. Use certbot or your internal CA's renewal. |
| **License renewed before grace ends** | An expired license runs for a **14-day grace period**, then the gateway **refuses to start** and a running instance **shuts down**. Renew from the customer portal during the grace window; watch the license warnings on the `messages` stream. |

> [!WARNING]
> **The mixed-content rule is the most common failure.** If the terminal loads but shows no data and the browser console logs blocked `ws://` or insecure `http://` requests, you terminated TLS on the SPA port but left REST/WS plain. Terminate TLS on all three.

<a id="go-live" name="go-live"></a>

## Before real-money go-live

The gateway's pre-trade cash check is only as good as the ECC figures it is given, and every one of them defaults to a safe-but-inert value. Work through this list before pointing the gateway at a production EPEX account.

| Set | To |
| --- | --- |
| House cash limit, **EUR** and **GBP** | Nothing to enter. The trading limit your Clearing Member has set for you in the ECC Member Area arrives from M7 and *is* the House limit. ECC names the two limits `EPEX_CONTINUOUS_EUR` and `EPEX_CONTINUOUS_GBP`, so those are the names to quote if you ask your Clearing Member to check or change one; confirm both pools read the figure you expect on `GET /api/v1/cash_limit` or the terminal's Limits page once the gateway is connected. Until that first report arrives no order may add exposure. Set a **cap** only to be stricter than ECC; it can lower the limit, never raise it. |
| `cash_limit.gbp_sell_reservation_schedule` | ECC's current GB Price Independent Delivery Risk Parameter for Continuous Trading in M7 (sell only), from the ECC Risk Parameter File. The gateway takes the GB delivery-risk add-on from the exchange's own risk set for the product, so this is the **fallback** that protects the desk until that report arrives, still worth setting for any GB trading, and worth keeping current, since ECC revises the figure monthly. See the [config.yml guide](config_yml_dist.md). |
| Bank-holiday calendars, **both** currencies | The TARGET2 closing days for the year (New Year's Day, Good Friday, Easter Monday, 1 May, Christmas Day, 26 December) in the EUR *and* the GBP calendar. Both pools reset on ECC Business Days. Set via `PUT /api/v1/holidays` or the terminal's Limits page. **Normally nothing to enter:** the gateway derives the six closing days for the current year and loads them into both calendars at startup, re-checking hourly, and from December it loads the coming year as well, so the turn of the year needs no action and no order is refused while the new year's dates are being filled in and a gateway that was down over New Year catches up when it returns. Derived entries are labelled `(auto)`. **Anything you enter yourself is never overwritten** (a correction, or an ad-hoc ECC closure, always wins), so enter a date by hand whenever ECC closes on a day outside the standard six, and it will stick. **Deleting a derived date sticks too:** the deletion is remembered for that currency and the hourly check does not add the date back until you add it again, which is how a change to the TARGET2 schedule is made. ECC publishes no machine-readable calendar, so the derivation is a convenience and the refusal still stands behind it: a currency whose calendar is empty refuses every order which adds exposure (`no_holiday_calendar`). Startup judges the calendars only after filling them, so its `ERROR` names only a pool the fill could not stock (normally one whose derived dates were all deleted), with a warning when the two calendars disagree. A calendar that is populated but holds no date in the current or the next calendar year is refused too, under its own `stale_holiday_calendar`, since last year's closings place none of this year's boundaries. Entering a date for the current year lifts either refusal immediately, with no restart. |
| `cash_limit.exposure_window_timezone` | Leave it at `Europe/Amsterdam`. It is ECC's clearing timezone (CET/CEST), not a display preference; changing it moves the 16:00 booking cut away from ECC's and the gateway warns about it at startup. |

> [!CAUTION]
> **The gateway's check is a front-end risk check, not a substitute for the exchange's.** It is deliberately never looser than M7's, but a Trading Participant remains legally required to comply with its Trading Limit regardless of what any pre-trade layer accepts.

<a id="verify" name="verify"></a>

## Verify

After reloading nginx, confirm each surface is TLS and wired.

```bash
# nginx config is valid, then reload
nginx -t && systemctl reload nginx

# SPA + runtime config over TLS
curl -I  https://trading.example.com/
curl -s  https://trading.example.com/config.js
#   -> window.__VOLTNIR_CONFIG__ = {apiPort: 3000, wsPort: 9001};

# REST answers over TLS: liveness, then readiness (no token needed)
curl -s https://trading.example.com:3000/livez
#   -> {"live":true}
curl -s -w " %{http_code}\n" https://trading.example.com:3000/readyz
#   -> {"ready":true} 200 once the exchange login and streams are up,
#      {"ready":false} 503 until then

# gRPC health over in-process TLS (grpc_health_probe)
grpc_health_probe -addr trading.example.com:3443 -tls
grpc_health_probe -addr trading.example.com:3443 -tls -service voltnir.api.v1.VoltAPI

# WebSocket handshake upgrades over TLS
curl -I -N \
  -H "Connection: Upgrade" -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Version: 13" -H "Sec-WebSocket-Key: dGhlIHNhbXBsZQ==" \
  https://trading.example.com:9001/ws/v1
```

> [!NOTE]
> Then open `https://trading.example.com/` in a browser and check the devtools console: **no mixed-content or blocked-request warnings** means REST and WS resolved to TLS. The Network tab should show `/config.js` and a `wss://` connection, both `200`/`101`.

<a id="probes" name="probes"></a>

## Probes

The gateway answers two unauthenticated probes on the REST port, `GET /livez` and `GET /readyz`, and the standard gRPC health service on the gRPC port. They need no API key, write nothing to the audit trail, are not charged to any key's request bound, and disclose only live, or ready or not. The REST and gRPC references describe them in full.

| Signal | REST | gRPC service name | Use it for |
| --- | --- | --- | --- |
| Live: the process answers | `/livez` | `""` | Liveness **and** readiness checks |
| Ready: the gateway is operational | `/readyz` | `voltnir.api.v1.VoltAPI` | Monitoring and alerting only |

> [!CAUTION]
> **Do not gate traffic on readiness.** One gateway serves one M7 login, so there is no second instance to send traffic to. `/readyz` is `503` from start until the exchange login completes and during every exchange outage or maintenance window; a readiness check on it takes the gateway out of service at exactly those times, which blacks out the trading terminal and the API when the desk most needs to see state and cancel orders. Wire liveness and readiness checks to `/livez` and alert on `/readyz` (or on the `voltnir_operational` gauge).

```bash
# Kubernetes container spec. The kubelet probes the pod IP, so the REST
# server listens on the pod's interface inside the container.
livenessProbe:
  httpGet: { path: /livez, port: 3000 }
  periodSeconds: 10
  failureThreshold: 3
readinessProbe:
  httpGet: { path: /livez, port: 3000 }   # /livez, not /readyz: see above
  periodSeconds: 10
# The native grpc probe (grpc: { port: 3443 }) speaks plaintext only; with
# gRPC TLS enabled in the gateway, keep the httpGet probes above.
```

<a id="full-example" name="full-example"></a>

## Full nginx vhost

The complete file: `http {}`-level TLS hardening, the upgrade map, an HTTP→HTTPS redirect, and all three surface blocks. Swap `trading.example.com`, the public IP, and the certificate paths for yours.

```
http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;
    server_tokens off;

    # --- TLS hardening (Mozilla "intermediate") ---
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305;
    ssl_prefer_server_ciphers off;
    ssl_session_tickets off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    map $http_upgrade $connection_upgrade { default upgrade; '' close; }

    # HTTP -> HTTPS for the SPA
    server {
        listen 203.0.113.10:80;
        server_name trading.example.com;
        return 301 https://$host$request_uri;
    }

    # Terminal SPA + /config.js : 443 -> 8080
    server {
        listen 203.0.113.10:443 ssl;
        http2 on;
        server_name trading.example.com;
        ssl_certificate     /etc/nginx/certs/trading.example.com.pem;
        ssl_certificate_key /etc/nginx/certs/trading.example.com-key.pem;
        add_header Strict-Transport-Security "max-age=63072000; includeSubDomains" always;
        add_header X-Frame-Options "DENY" always;
        add_header X-Content-Type-Options "nosniff" always;
        location / {
            proxy_pass http://127.0.0.1:8080;
            proxy_set_header Host $host;
            proxy_set_header X-Forwarded-Proto https;
        }
    }

    # REST API : 3000 -> 3000
    server {
        listen 203.0.113.10:3000 ssl;
        http2 on;
        server_name trading.example.com;
        ssl_certificate     /etc/nginx/certs/trading.example.com.pem;
        ssl_certificate_key /etc/nginx/certs/trading.example.com-key.pem;
        add_header Strict-Transport-Security "max-age=63072000; includeSubDomains" always;
        location / {
            proxy_pass http://127.0.0.1:3000;
            proxy_set_header Host $host;
            proxy_set_header X-Forwarded-Proto https;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        }
    }

    # WebSocket feed : 9001 -> 9001
    server {
        listen 203.0.113.10:9001 ssl;
        server_name trading.example.com;
        ssl_certificate     /etc/nginx/certs/trading.example.com.pem;
        ssl_certificate_key /etc/nginx/certs/trading.example.com-key.pem;
        add_header Strict-Transport-Security "max-age=63072000; includeSubDomains" always;
        location / {
            proxy_pass http://127.0.0.1:9001;
            proxy_http_version 1.1;
            proxy_set_header Upgrade    $http_upgrade;
            proxy_set_header Connection $connection_upgrade;
            proxy_set_header Host       $host;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_read_timeout 3600s;
        }
    }
}
```

> [!NOTE]
> gRPC (`:3443`) is intentionally not in this file. Terminate its TLS in-process via the `grpc_server.tls` block (see the [Configuration Reference](config_yml_dist.md)), or add a fourth `server` block using `grpc_pass` with `http2 on;` and `grpc_set_header X-Forwarded-For $proxy_add_x_forwarded_for;` as shown in [gRPC](#grpc).

Copyright © 2026 Voltnir B.V. The Voltnir gateway is proprietary software, licensed under separate terms.
