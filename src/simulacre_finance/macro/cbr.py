"""Bank of Russia series via its public SOAP/XML and monetary JSON services."""

from __future__ import annotations

import re
from datetime import date
from typing import TYPE_CHECKING, Any, Literal
from xml.etree.ElementTree import ParseError

from ..exceptions import DataUnavailableError, ValidationError
from ._common import HTTPSource, frame, interval, number, observed_date

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

    import pandas as pd

_SOAP = "https://www.cbr.ru/DailyInfoWebServ/DailyInfo.asmx"
_NS = "http://web.cbr.ru/"
_DIFF = "urn:schemas-microsoft-com:xml-diffgram-v1"
_MONEY = "https://www.cbr.ru/dataservice/dataNew"


def _xml(content: bytes) -> Element:
    try:
        from defusedxml.common import DefusedXmlException
        from defusedxml.ElementTree import fromstring
    except ImportError as exc:
        raise DataUnavailableError("CBR XML access requires simulacre-finance[macro]") from exc
    try:
        return fromstring(content, forbid_dtd=True)
    except (ParseError, DefusedXmlException) as exc:
        raise DataUnavailableError("Invalid or unsafe CBR XML response") from exc


class CBR(HTTPSource):
    """Dated public CBR observations. Rates are decimal, amounts have explicit units.

    Supply an HTTPX client for a custom proxy/CA; the caller retains its ownership.
    No private Simulacre API, VPN, credentials or server-side cache is required.
    """

    def _series(
        self,
        method: str,
        date_field: str,
        fields: dict[str, tuple[str, str, float]],
        start: str | date,
        end: str | date,
        *,
        frequency: str = "daily",
    ) -> pd.DataFrame:
        first, last = interval(start, end)
        body = (
            '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
            f'<soap:Body><{method} xmlns="{_NS}">'
            f"<fromDate>{first}T00:00:00</fromDate><ToDate>{last}T00:00:00</ToDate>"
            f"</{method}></soap:Body></soap:Envelope>"
        )
        response = self._request(
            "POST",
            _SOAP,
            content=body.encode(),
            headers={"Content-Type": "text/xml; charset=utf-8", "SOAPAction": f'"{_NS}{method}"'},
        )
        root = _xml(response.content)
        result = root.find(f".//{{{_NS}}}{method}Result")
        diff = result.find(f"{{{_DIFF}}}diffgram") if result is not None else None
        if diff is None:
            raise DataUnavailableError(
                f"CBR {method}: missing result/diffgram (possibly SOAP fault)"
            )
        rows: list[dict[str, Any]] = []
        # Only data rows inside the diffgram; embedded XSD elements are not observations.
        for dataset in diff:
            if dataset.tag.startswith(f"{{{_DIFF}}}"):
                raise DataUnavailableError(
                    "CBR diffgram contains errors or historical row versions"
                )
            for item in dataset:
                raw = {child.tag.rsplit("}", 1)[-1]: child.text for child in item}
                if not raw.get(date_field):
                    raise DataUnavailableError(f"CBR {method}: missing observation date")
                day_text = raw[date_field]
                assert day_text is not None
                row: dict[str, Any] = {"date": observed_date(day_text)}
                for source, (column, _, scale) in fields.items():
                    value = raw.get(source)
                    row[column] = number(value) * scale if value is not None else None
                if all(row[column] is None for column, _, _ in fields.values()):
                    raise DataUnavailableError(f"CBR {method}: observation has no known values")
                rows.append(row)
        return frame(
            rows,
            {col: unit for col, unit, _ in fields.values()},
            source=f"{_SOAP}?op={method}",
            frequency=frequency,
            start=first,
            end=last,
        )

    def key_rate(self, start: str | date, end: str | date) -> pd.DataFrame:
        """Published daily key rate; 0.16 means 16%, no weekend filling."""
        return self._series(
            "KeyRate", "DT", {"Rate": ("rate", "decimal annual rate", 0.01)}, start, end
        )

    def ruonia(self, start: str | date, end: str | date) -> pd.DataFrame:
        """Overnight rate and transaction volume in RUB billion."""
        return self._series(
            "Ruonia",
            "D0",
            {
                "ruo": ("rate", "decimal annual rate", 0.01),
                "vol": ("volume", "RUB billion", 1),
            },
            start,
            end,
        )

    def international_reserves(
        self,
        start: str | date,
        end: str | date,
        *,
        frequency: Literal["weekly", "monthly"] = "weekly",
    ) -> pd.DataFrame:
        """Total international reserves in USD million; monthly includes components."""
        if frequency not in ("weekly", "monthly"):
            raise ValidationError("Reserves frequency must be weekly or monthly")
        fields = (
            {"val": ("reserves", "USD million", 1.0)}
            if frequency == "weekly"
            else {
                key: (col, "USD million", 1.0)
                for key, col in zip(
                    ("p1", "p2", "p3", "p4", "p5", "p6"),
                    ("reserves", "fx_reserves", "foreign_exchange", "sdr", "imf_position", "gold"),
                    strict=True,
                )
            }
        )
        return self._series(
            "mrrf7D" if frequency == "weekly" else "mrrf",
            "D0",
            fields,
            start,
            end,
            frequency=frequency,
        )

    def bank_liquidity(self, start: str | date, end: str | date) -> pd.DataFrame:
        """CBR structural deficit/surplus and balance-sheet components, RUB billion."""
        fields = {
            "StrLiDefNew": "liquidity_balance",
            "StrLiDef": "liquidity_balance_excl_corr",
            "claims": "claims",
            "liabilities": "liabilities",
            "CorrAcc": "correspondent_accounts",
            "AVGRR": "required_reserves",
            "netCBRclaims": "net_cbr_claims",
        }
        return self._series(
            "Bliquidity", "DT", {k: (v, "RUB billion", 1) for k, v in fields.items()}, start, end
        )

    def liquidity_operations(self, start: str | date, end: str | date) -> pd.DataFrame:
        """CBR liquidity provision/absorption balance, RUB billion (source sign)."""
        return self._series(
            "Saldo", "Dt", {"DEADLINEBS": ("balance", "RUB billion", 1)}, start, end
        )

    def correspondent_accounts(self, start: str | date, end: str | date) -> pd.DataFrame:
        """Credit institutions' correspondent balances at CBR, RUB million."""
        return self._series(
            "OstatDynamic",
            "DateOst",
            {
                "InRuss": ("russia", "RUB million", 1),
                "InMoscow": ("moscow", "RUB million", 1),
            },
            start,
            end,
        )

    def bank_deposits(self, start: str | date, end: str | date) -> pd.DataFrame:
        """Credit institutions' deposits at CBR, RUB million; absent components stay NaN."""
        fields = {
            "TOTAL": "total",
            "AUC_1W": "auction_1w",
            "AUC_THIN": "fine_tuning",
            "OV_P": "standing_facilities",
        }
        return self._series(
            "OstatDepoNew", "DT", {k: (v, "RUB million", 1) for k, v in fields.items()}, start, end
        )

    def exchange_rates(
        self,
        currency: str,
        start: str | date,
        end: str | date,
    ) -> pd.DataFrame:
        """Official RUB per ONE currency unit (USD/EUR/CNY or explicit CBR R-code).

        These are official rates, not exchange quotes. No implicit calendar filling.
        """
        first, last = interval(start, end)
        codes = {"USD": "R01235", "EUR": "R01239", "CNY": "R01375"}
        if not isinstance(currency, str):
            raise ValidationError("Expected USD, EUR, CNY or CBR R-code")
        code = codes.get(currency, currency)
        if not re.fullmatch(r"R\d{5}[A-Z]?", code):
            raise ValidationError("Expected USD, EUR, CNY or explicit CBR R-code")
        url = "https://www.cbr.ru/scripts/XML_dynamic.asp"
        root = _xml(
            self._request(
                "GET",
                url,
                params={
                    "date_req1": first.strftime("%d/%m/%Y"),
                    "date_req2": last.strftime("%d/%m/%Y"),
                    "VAL_NM_RQ": code,
                },
            ).content
        )
        if root.tag != "ValCurs" or root.get("ID") != code:
            raise DataUnavailableError("CBR returned an unexpected currency response")
        rows = []
        for item in root:
            if item.tag != "Record" or item.get("Id") != code:
                raise DataUnavailableError("CBR returned an unexpected currency record")
            try:
                day = date.fromisoformat("-".join(reversed(item.attrib["Date"].split("."))))
                nominal = number(item.findtext("Nominal", "").replace(",", "."))
                value = number(item.findtext("Value", "").replace(",", "."))
                if nominal <= 0 or value <= 0:
                    raise ValueError("Nonpositive currency value/nominal")
            except (KeyError, ValueError) as exc:
                raise DataUnavailableError("Invalid CBR currency record") from exc
            rows.append({"date": day, "rate": value / nominal})
        return frame(
            rows,
            {"rate": f"RUB per 1 {currency}"},
            source=url,
            frequency="daily",
            start=first,
            end=last,
        )

    def monetary_aggregates(self, start: str | date, end: str | date) -> pd.DataFrame:
        """M0/M1/M2/M2X levels and deposit structure in RUB billion, no Excel fallback."""
        first, last = interval(start, end)
        # API years describe reporting periods; January balances belong to the prior year.
        params = [
            ("categoryId", "5"),
            ("y1", str(max(1992, first.year - 1))),
            ("y2", str(last.year)),
        ]
        params.extend(("i_ids", str(i)) for i in (5, 6, 7, 8))
        try:
            payload = self._request("GET", _MONEY, params=params).json()
            if not isinstance(payload, dict) or not isinstance(payload.get("RowData"), list):
                raise ValueError("Missing RowData")
            points: dict[date, dict[str, float]] = {}
            for item in payload["RowData"]:
                day = observed_date(item["date"])
                if not first <= day <= last:
                    continue  # This API filters whole years, not exact dates.
                indicator, measure = item["indicator_id"], item["measure2_id"]
                if item["unit_id"] != 3 or item["periodicity"] != "month":
                    raise ValueError("Unexpected monetary unit/frequency")
                if indicator not in (5, 6, 7, 8):
                    continue
                if not ((indicator == 5 and measure in (None, 12)) or measure == 12):
                    continue
                key = {5: "m0", 6: "m1", 7: "m2", 8: "m2x"}[indicator]
                row = points.setdefault(day, {})
                if key in row:
                    raise ValueError("Duplicate monetary observation")
                row[key] = number(item["obs_val"])
        except (KeyError, TypeError, ValueError) as exc:
            raise DataUnavailableError("Invalid CBR monetary JSON response") from exc
        rows = []
        for day, values in points.items():
            if set(values) != {"m0", "m1", "m2", "m2x"}:
                raise DataUnavailableError("Incomplete CBR monetary aggregates for an observation")
            rows.append(
                {
                    "date": day,
                    **values,
                    "transfer_deposits": values["m1"] - values["m0"],
                    "other_ruble_deposits": values["m2"] - values["m1"],
                }
            )
        units = dict.fromkeys(
            ("m0", "m1", "m2", "m2x", "transfer_deposits", "other_ruble_deposits"), "RUB billion"
        )
        return frame(rows, units, source=_MONEY, frequency="monthly", start=first, end=last)
