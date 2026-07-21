# Voltnir SDK & API

Public client library and API contract for **[Voltnir](https://voltnir.io)**, a
power-trading gateway for the EPEX SPOT intraday energy market.

This repository contains everything you need to integrate against a Voltnir
gateway:

| Path | What it is |
|------|------------|
| [`clients/python/`](clients/python/) | The official **Python SDK** (`voltnir_sdk`): sync + async gRPC client. See its [README](clients/python/README.md). |
| [`proto_volt/voltnir_api_v1.proto`](proto_volt/voltnir_api_v1.proto) | The **gRPC API contract** (`voltnir.api.v1`). Generate clients in any language from this. |
| [`docs/`](docs/) | The **API reference**: REST, gRPC, and WebSocket contracts, plus the config and deployment guides. |

## Quick start (Python)

```bash
# GitHub:
pip install "git+https://github.com/Voltnir/voltnir-sdk.git#subdirectory=clients/python"

# …or the Codeberg mirror:
pip install "git+https://codeberg.org/Voltnir/voltnir-sdk.git#subdirectory=clients/python"
```

```python
from voltnir_sdk import VoltnirClient

client = VoltnirClient(host="your-gateway-host", port=3443, api_key="...")
contracts = client.list_contracts()
```

Full usage (TLS, async, streaming, error handling) is in the
[SDK README](clients/python/README.md).

## API documentation

The full reference lives in [`docs/`](docs/) and renders right here on GitHub:

- [`rest_api_v1.md`](docs/rest_api_v1.md): REST V1 endpoints
- [`grpc_api_v1.md`](docs/grpc_api_v1.md): gRPC `voltnir.api.v1` service
- [`ws_api_v1.md`](docs/ws_api_v1.md): WebSocket streaming + command protocol
- [`config_yml_dist.md`](docs/config_yml_dist.md): gateway configuration reference
- [`deployment_v1.md`](docs/deployment_v1.md): on-prem nginx / TLS reverse-proxy guide

## About this repository

This is a **read-only mirror** of the official Voltnir client SDK, API proto, and
documentation. Please don't open pull requests here; the files are published
from upstream and edits would be overwritten.

For changes, questions, access, licensing, or support, contact us at
**contact@voltnir.io** or visit **[voltnir.io](https://voltnir.io)**.
