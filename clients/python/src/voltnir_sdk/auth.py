"""Bearer-token auth helpers for Voltnir gRPC.

The server enforces:
  - metadata key `authorization` (lowercase; gRPC normalizes HTTP/2 headers)
  - prefix `Bearer ` (capital B; lowercase `bearer` is rejected)

The SDK attaches this pair explicitly on every call rather than installing a
gRPC interceptor, which keeps the streaming wrappers simple and keeps the
credential visible at the one place it is built.
"""

from __future__ import annotations


class AuthMetadata(tuple):
    """Call metadata that keeps its credential out of `repr` and `str`.

    A plain tuple of `(key, value)` pairs, so gRPC receives exactly what it
    always did; only its printed form changes. The clients store it on the
    instance, so without this the key showed in `vars(client)`, in a debugger's
    variable view and in any log line that formats the client's state.
    """

    __slots__ = ()

    def __repr__(self) -> str:
        pairs = ", ".join(f"({key!r}, '<redacted>')" for key, _value in self)
        return f"AuthMetadata({pairs})"

    __str__ = __repr__


def auth_metadata(api_key: str) -> AuthMetadata:
    """Return the `authorization: Bearer <api_key>` metadata pair.

    Used directly when calling stub methods (`stub.GetMe(req, metadata=...)`)
    instead of installing an interceptor. Handy for one-off calls and
    keeping the streaming wrappers simple. Prints with the value redacted.
    """
    return AuthMetadata((("authorization", f"Bearer {api_key}"),))
