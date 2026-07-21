# Voltnir Deployment & TLS: Securing an On-Prem Gateway

> Auto-generated from the Voltnir API reference.

## Deployment & TLS

The Voltnir gateway is a single binary you run on your own infrastructure. It speaks **plain HTTP and WebSocket** on its listening ports; there is no in-process TLS for the REST, WebSocket, or terminal surfaces (gRPC is the one exception, see below). That is by design: on-prem operators terminate TLS at a reverse proxy they control, with their own certificate and security policy.

This guide shows the recommended, battle-tested setup: **nginx terminating TLS in front of the gateway, one certificate, the gateway bound to loopback.** It works with the gateway as shipped: no special build, no extra config beyond the bind address.

> [!WARNING]
> **Never expose the gateway's plain ports to an untrusted network.** The REST and WebSocket surfaces carry order flow and account data in clear text. Bind them to `127.0.0.1` and let the proxy be the only thing the network can reach.

## Running the gateway

Before any proxy work, get the binary starting cleanly on the host. It needs a config file, a valid license, and the M7 client identity from your EPEX onboarding.

#### Prerequisites

| Item | Where | Notes |
| --- | --- | --- |
| `config.yml` | `-c` flag | Start from the shipped `config.yml.dist` template; full field reference in the [config.yml guide](config_yml_dist.md). It contains credentials; make it readable by the service user only. |
| License file | `license_path` in `config.yml` | Required. There is no unlicensed run mode. The license must permit the configured `epex_connection.environment` (`sim` / `prod`) or startup is refused. |
| M7 client TLS identity | `epex_connection.cert` / `epex_connection.key` | PEM certificate + private key from your EPEX onboarding pack, presented to M7. Keep the key file mode `600`. |
| Outbound network | firewall egress | The gateway dials EPEX M7 (AMQP + WebSocket) outbound over TLS. Behind a TLS-inspecting proxy or a private CA, point `epex_connection.extra_ca_path` at a PEM bundle of the extra trust roots. |

#### Invocation & flags

```
voltnir -c config.yml
```

| Flag | Meaning |
| --- | --- |
| `-c`, `--config <path>` | Path to the YAML config file. Required on every invocation. |
| `--generate-key` | Print a freshly generated API key and exit. Nothing is written or changed. |
| `--reset-admin` | Rotate the `admin` user's API key, write the new key to `./VOLTNIR_CREDENTIALS.txt`, and exit. For when the original credentials file is lost. |

Log verbosity comes from the standard `RUST_LOG` environment variable (e.g. `RUST_LOG=info`); set it in the service unit below. No other environment variables are read; everything else lives in `config.yml`.

#### First start

On an empty database the gateway creates the `admin` account and writes its API key to `./VOLTNIR_CREDENTIALS.txt`, the only time the key exists in plaintext. Log in, create your own users, then delete the file.

> [!CAUTION]
> **Run from the install directory.** Relative paths (the default SQLite store `./voltnir.db`, `./VOLTNIR_CREDENTIALS.txt`, and any relative `cert/` paths in `config.yml`) resolve against the process working directory. Set it explicitly in the service unit.

#### systemd unit

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
KillSignal=SIGINT
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

> [!NOTE]
> `KillSignal=SIGINT` matters: the gateway drains its subsystems on **SIGINT** (Ctrl-C). systemd's default `SIGTERM` would kill it without the graceful shutdown path.

## Port topology

A fully-enabled gateway listens on four ports. The proxy fronts each one.

| Port | Surface | Protocol | Who connects | Config key |
| --- | --- | --- | --- | --- |
| `8080` | Trading terminal (SPA) | HTTP | Browsers | `trading_terminal.port` |
| `3000` | REST API v1 | HTTP | Browsers, ops tools | `rest_server.port` |
| `9001` | Live-data feed | WebSocket | Browsers, SDKs | `ws_server.port` |
| `3443` | gRPC API v1 | HTTP/2 | SDKs, services | `grpc_server.port` |

> [!NOTE]
> The terminal SPA (`:8080`), REST (`:3000`) and WebSocket (`:9001`) are documented here. gRPC (`:3443`) can terminate TLS *in-process*; see [the gRPC note](#grpc).

## How the UI finds the backend

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
    }
}
```

> [!NOTE]
> The SPA `server` block also serves `/config.js` (it proxies to `:8080` like everything else), so no special location needed. The gateway's SPA handler already serves any unknown path as the app shell, so client-side routing works through the proxy unchanged.

#### WebSocket upgrade (port 9001)

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
        proxy_read_timeout 3600s;   # the feed is persistent
    }
}
```

#### gRPC (port 3443)

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

## Verify

After reloading nginx, confirm each surface is TLS and wired.

```bash
# nginx config is valid, then reload
nginx -t && systemctl reload nginx

# SPA + runtime config over TLS
curl -I  https://trading.example.com/
curl -s  https://trading.example.com/config.js
#   -> window.__VOLTNIR_CONFIG__ = {apiPort: 3000, wsPort: 9001};

# REST answers over TLS (401 without a token is expected and healthy)
curl -so /dev/null -w "%{http_code}\n" https://trading.example.com:3000/api/v1/state

# WebSocket handshake upgrades over TLS
curl -I -N \
  -H "Connection: Upgrade" -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Version: 13" -H "Sec-WebSocket-Key: dGhlIHNhbXBsZQ==" \
  https://trading.example.com:9001/ws/v1
```

> [!NOTE]
> Then open `https://trading.example.com/` in a browser and check the devtools console: **no mixed-content or blocked-request warnings** means REST and WS resolved to TLS. The Network tab should show `/config.js` and a `wss://` connection, both `200`/`101`.

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
            proxy_read_timeout 3600s;
        }
    }
}
```

> [!NOTE]
> gRPC (`:3443`) is intentionally not in this file. Terminate its TLS in-process via the `grpc_server.tls` block (see the [Configuration Reference](config_yml_dist.md)), or add a fourth `server` block using `grpc_pass` with `http2 on;`.
