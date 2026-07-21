"""Bearer-token auth helpers for Voltnir gRPC.

The server enforces:
  - metadata key `authorization` (lowercase; gRPC normalizes HTTP/2 headers)
  - prefix `Bearer ` (capital B; lowercase `bearer` is rejected)

The SDK attaches this pair explicitly on every call rather than installing a
gRPC interceptor, which keeps the streaming wrappers simple and keeps the
credential visible at the one place it is built.
"""

from __future__ import annotations

from collections.abc import Sequence


def auth_metadata(api_key: str) -> tuple[tuple[str, str], ...]:
    """Return the `authorization: Bearer <api_key>` metadata pair.

    Used directly when calling stub methods (`stub.GetMe(req, metadata=...)`)
    instead of installing an interceptor. Handy for one-off calls and
    keeping the streaming wrappers simple.
    """
    return (("authorization", f"Bearer {api_key}"),)
