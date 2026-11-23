"""Map the real tools/get_trading_history normalized envelope, without a client."""

from collections.abc import Mapping

from simulacre_finance import Metadata, PriceData, ValidationError
from simulacre_finance.data import frozen_array, iso_date


def history_prices(
    response: Mapping[str, object],
    *,
    board: str,
    metadata: Metadata,
) -> PriceData:
    """Map already fetched MCP share closes; currency/vintage come from caller.

    This normalizes order and filters ONE explicit board, never fills or assumes
    pagination completion. The actual MCP tool supplies a bounded history list;
    callers must fetch their desired complete window before using this adapter.
    """
    rows, security = response.get("history"), response.get("security")
    if (
        response.get("success") is not True
        or response.get("engine") != "stock"
        or response.get("market") != "shares"
        or not isinstance(security, str)
        or not security
        or not board
        or not isinstance(rows, list)
    ):
        raise ValidationError("Expected successful MCP stock/share history with explicit board")
    selected = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValidationError("MCP history must be a list of observation dictionaries")
        if row.get("BOARDID") != board:
            continue
        if row.get("SECID") != security:
            raise ValidationError("MCP observation security disagrees with response")
        try:
            selected.append((iso_date(row["TRADEDATE"]), float(row["CLOSE"])))
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise ValidationError("MCP close/date is missing or invalid") from exc
    selected.sort(key=lambda item: item[0])
    if not selected:
        raise ValidationError("No closes on the selected board")
    return PriceData(
        tuple(day for day, _ in selected),
        (security,),
        frozen_array([[close] for _, close in selected]),
        metadata,
    )
