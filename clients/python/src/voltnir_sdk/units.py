"""Exact conversion between human trading units and Voltnir wire units.

READ THIS BEFORE INTERPRETING ANY NUMBER FROM THIS API. Every monetary and
size value on the wire is a scaled integer, there are three different scales,
and a misread is silent: the wrong answer is always a plausible number.

    what                     wire type   scale        helper
    price (CCY/MWh)          sint64      x 100        price_to_cents / cents_to_price
    quantity, position       uint32      x 1_000      quantity_to_sub_mw / sub_mw_to_quantity
    cash limits, exposure    sint64      x 100        eur_to_cents / cents_to_eur
    realized/unrealized P&L  sint64      x 100_000    eur_to_q8 / q8_to_eur

The order path does NOT use these helpers. `submit_order` takes `price_cents`
and `quantity_sub_mw` directly, because that is what all three transports
document and what every response carries, so an algo holding its book in minor
units never converts. These helpers are for code that genuinely works in
decimals: dashboards, reports, spreadsheet imports, and anything a human reads.

Why this matters more than it looks:

- **A 100x price error is legal.** `price_cents=50` means 0.50 CCY/MWh. The
  gateway's only size guard is `quantity != 0`, so nothing rejects a price two
  orders of magnitude off. The parameter names carry the unit for exactly this
  reason.
- **P&L is not cents.** `ContractPnl.realized_pnl` is EUR x 100_000. Read as
  cents it is 1000x too large, and 1_234_500 reads as either 12,345.00 EUR or
  12.345 EUR with equal plausibility. Use `q8_to_eur`, never `cents_to_eur`.
- **Position and size are x 1000, not x 100.** `signed_position`,
  `max_position`, `order_pos_limit` and every quantity are sub-MW. Applying the
  price scale to a size is a 10x error, which is small enough to look like a
  bad day rather than a bug.

Conversion goes through `Decimal`, never binary float arithmetic: `0.1 + 0.2`
is not `0.3` in float, and a price landing a cent from where the trader meant
it is a real loss on a large clip. Floats are accepted and converted via
`repr()`, which round-trips to the shortest decimal reproducing the float, so
`50.07` becomes exactly `Decimal("50.07")`.

Values that are not an exact multiple of the tick are **rejected, not
rounded**. Silently moving a price or a size is the class of "helpful"
behaviour that loses money without appearing in any log.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

__all__ = [
    "PRICE_SCALE",
    "QUANTITY_SCALE",
    "CASH_SCALE",
    "PNL_SCALE",
    "UnitConversionError",
    "price_to_cents",
    "cents_to_price",
    "quantity_to_sub_mw",
    "sub_mw_to_quantity",
    "eur_to_cents",
    "cents_to_eur",
    "eur_to_q8",
    "q8_to_eur",
]

# ── four named scales, three distinct multipliers ───────────────────────────
#
# Four constants, because four different KINDS of value are scaled; three
# distinct values, because price and cash happen to share x 100 today.
# Confusing them is the most expensive mistake available to a user of this SDK:
#
#     price        x 100       CCY/MWh -> cents
#     quantity     x 1_000     MW      -> sub-MW
#     cash         x 100       EUR     -> cents
#     P&L          x 100_000   EUR     -> q8
#
# Reading `realized_pnl` as cents rather than q8 is a 1000x error, and it reads
# as a plausible number either way: a P&L of 1_234_500 is 12,345.00 EUR if you
# treat it as cents and 12.345 EUR if you treat it correctly. Nothing about the
# integer tells you which.
#
# `price` and `cash` share a multiplier but are deliberately separate constants
# and separate functions. They feed different fields, and a future divergence
# (a currency with different minor units, a rescaled price feed) must not
# silently corrupt the other. Do not "simplify" them into one.

#: Wire cents per one CCY/MWh. Used by order `price_cents`.
PRICE_SCALE = 100

#: Wire sub-MW per one MW. Used by order `quantity_sub_mw` and every position.
QUANTITY_SCALE = 1000

#: Wire cents per one EUR/GBP. Used by cash limits and member cash fields.
CASH_SCALE = 100

#: Wire q8 units per one EUR. Used by realized/unrealized P&L ONLY.
#: Note the name is historical: "q8" here means x 100_000, not x 10^8.
PNL_SCALE = 100_000

Number = Decimal | int | float | str


class UnitConversionError(ValueError):
    """A value could not be converted to wire units without losing precision.

    Deliberately a `ValueError` and NOT a `VoltnirError`: nothing was sent. This
    is a bug in the calling code, caught before any RPC is attempted, and it
    should not be swallowed by an `except VoltnirError` written to handle
    exchange failures.
    """


def _to_decimal(value: Number, *, field: str) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        # bool is an int subclass; a boolean price is always a mistake.
        raise UnitConversionError(f"{field}: expected a number, got bool {value!r}")
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        # repr() gives the shortest string that round-trips the float, so
        # Decimal(repr(50.07)) is exactly 50.07 rather than the binary
        # approximation 50.06999999999999317878973...
        return Decimal(repr(value))
    if isinstance(value, str):
        try:
            return Decimal(value)
        except InvalidOperation as exc:
            raise UnitConversionError(
                f"{field}: {value!r} is not a valid decimal number"
            ) from exc
    raise UnitConversionError(
        f"{field}: expected Decimal, int, float or str, got {type(value).__name__}"
    )


def _scale_exact(value: Number, scale: int, *, field: str, unit: str) -> int:
    dec = _to_decimal(value, field=field)

    if not dec.is_finite():
        raise UnitConversionError(f"{field}: {value!r} is not a finite number")

    scaled = dec * scale
    if scaled != scaled.to_integral_value():
        tick = Decimal(1) / Decimal(scale)
        raise UnitConversionError(
            f"{field}: {dec} {unit} is not an exact multiple of the {tick} {unit} "
            f"tick (it would need {scaled} wire units). Round it yourself, "
            f"deliberately: the SDK will not silently move a price or a size."
        )
    return int(scaled)


def _wire_int(value, *, field: str) -> int:
    """Guard the OUTBOUND (wire -> human) helpers.

    These take a value that came off the wire, so it should already be an int.
    Passing anything else means the caller has confused directions, and the
    silent results are bad in both obvious cases:

        cents_to_price(True)        -> Decimal('0.01')   bool is an int subclass
        sub_mw_to_quantity(1500.7)  -> Decimal('1.5007000000000000454747...')

    The first renders a boolean as a price. The second puts binary float noise
    straight into a report, which is exactly what the Decimal discipline on the
    inbound path exists to prevent.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise UnitConversionError(
            f"{field}: expected an int from the wire, got "
            f"{type(value).__name__} {value!r}. These helpers convert wire "
            f"integers to decimals; to go the other way use price_to_cents / "
            f"quantity_to_sub_mw / eur_to_cents / eur_to_q8."
        )
    return value


def price_to_cents(value: Number, *, field: str = "price_eur_per_mwh") -> int:
    """CCY/MWh -> wire cents. Negative prices are legal on power markets.

    >>> price_to_cents(Decimal("50.07"))
    5007
    >>> price_to_cents(-12.5)
    -1250
    """
    return _scale_exact(value, PRICE_SCALE, field=field, unit="CCY/MWh")


def cents_to_price(cents: int) -> Decimal:
    """Wire cents -> CCY/MWh, exactly.

    >>> cents_to_price(5007)
    Decimal('50.07')
    """
    return Decimal(_wire_int(cents, field="cents")) / Decimal(PRICE_SCALE)


def quantity_to_sub_mw(value: Number, *, field: str = "quantity_mw") -> int:
    """MW -> wire sub-MW. Must be positive; the gateway rejects a zero size.

    >>> quantity_to_sub_mw(Decimal("1.5"))
    1500
    """
    sub_mw = _scale_exact(value, QUANTITY_SCALE, field=field, unit="MW")
    if sub_mw < 0:
        raise UnitConversionError(
            f"{field}: negative size {value!r}. Direction is the `side` "
            f"argument (BUY / SELL), not the sign of the quantity."
        )
    return sub_mw


def sub_mw_to_quantity(sub_mw: int) -> Decimal:
    """Wire sub-MW -> MW, exactly.

    >>> sub_mw_to_quantity(1500)
    Decimal('1.5')
    """
    return Decimal(_wire_int(sub_mw, field="sub_mw")) / Decimal(QUANTITY_SCALE)


def eur_to_cents(value: Number, *, field: str = "amount_eur") -> int:
    """EUR (or GBP) -> wire cents, for CASH limits, not prices.

    Separate from `price_to_cents` on purpose. Same multiplier today, different
    field and different meaning: this one feeds `set_cash_limit(cents=...)`,
    `create_member(cash_limit=...)` and `patch_member(cash_limit_cents=...)`,
    where the value is an absolute money amount rather than a rate per MWh.

    >>> eur_to_cents("50000")     # a 50,000 EUR limit
    5000000
    """
    return _scale_exact(value, CASH_SCALE, field=field, unit="EUR")


def cents_to_eur(cents: int) -> Decimal:
    """Wire cents -> EUR, exactly. For cash limits and member cash fields.

    Applies to `Member.cash_limit`, `Member.eur_*_cents`,
    `CashLimitStatus.*_cents`, and `CashLimitResponse.cents`.

    >>> cents_to_eur(5000000)
    Decimal('50000')
    """
    return Decimal(_wire_int(cents, field="cents")) / Decimal(CASH_SCALE)


def eur_to_q8(value: Number, *, field: str = "amount_eur") -> int:
    """EUR -> wire q8 units (EUR x 100_000). P&L only.

    >>> eur_to_q8("12.345")
    1234500
    """
    return _scale_exact(value, PNL_SCALE, field=field, unit="EUR")


def q8_to_eur(q8: int) -> Decimal:
    """Wire q8 units -> EUR, exactly. For `realized_pnl` / `unrealized_pnl`.

    THIS IS NOT CENTS. `ContractPnl.realized_pnl` is EUR x 100_000, so reading
    it with `cents_to_eur` overstates P&L by 1000x, and the wrong answer looks
    entirely plausible:

    >>> q8_to_eur(1234500)      # correct
    Decimal('12.345')
    >>> cents_to_eur(1234500)   # WRONG for P&L: reads as 12,345.00 EUR
    Decimal('12345')

    Nothing in the integer itself distinguishes the two, which is why this
    helper exists rather than a comment telling you to divide.
    """
    return Decimal(_wire_int(q8, field="q8")) / Decimal(PNL_SCALE)
