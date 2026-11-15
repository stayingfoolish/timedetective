"""Explicit pack registration; never imported by the core."""

from .diagnostics import weather  # noqa: F401
from .transforms import monthly  # noqa: F401
from .trend import seasonal  # noqa: F401
from .robustness import comparison  # noqa: F401
from .trend import precipitation  # noqa: F401
from .diagnostics import precipitation as precipitation_diagnostics, return_levels  # noqa: F401
from .transforms import spi  # noqa: F401
from .robustness import precipitation as precipitation_robustness  # noqa: F401
from .relationship import precipitation as precipitation_relationship  # noqa: F401
