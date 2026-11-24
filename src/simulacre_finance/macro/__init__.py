"""Optional public macro data providers; install simulacre-finance[macro]."""

from .cbr import CBR
from .fred import FRED
from .moex import MOEXMacro
from .world_bank import WorldBank

__all__ = ["CBR", "FRED", "MOEXMacro", "WorldBank"]
