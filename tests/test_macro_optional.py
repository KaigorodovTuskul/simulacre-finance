"""Core imports must keep working without pandas, HTTPX or XML extras."""

import subprocess
import sys


def test_core_and_macro_class_imports_do_not_require_optional_dependencies():
    code = """
import sys
from importlib.abc import MetaPathFinder
class BlockExtras(MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'pandas', 'httpx', 'defusedxml'}:
            raise ImportError('optional dependency blocked by test')
sys.meta_path.insert(0, BlockExtras())
from simulacre_finance import CBR, FRED, MOEXMacro, WorldBank, simple_accrual_factor
assert simple_accrual_factor(.1, 365) == 1.1
assert not {'pandas', 'httpx', 'defusedxml'} & sys.modules.keys()
from simulacre_finance.macro._common import pandas
from simulacre_finance import DataUnavailableError
try:
    pandas()
except DataUnavailableError as exc:
    assert '[macro]' in str(exc)
else:
    raise AssertionError('Missing-extra message required')
"""
    subprocess.run([sys.executable, "-c", code], check=True, capture_output=True, text=True)
