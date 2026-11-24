"""Public network example: install .[macro], then python examples/macro.py.

This example makes live CBR requests; it is deliberately not part of offline tests.
"""

from simulacre_finance import CBR

if __name__ == "__main__":
    cbr = CBR()
    rates = cbr.key_rate(start="2024-01-01", end="2024-12-31")
    print(rates.tail().to_string(index=False))
    print(rates.attrs["units"])

    money = cbr.monetary_aggregates("2024-01-01", "2024-12-31")
    print(money.tail().to_string(index=False))
    print(money.attrs["units"])
