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
from .diagnostics import season as season_diagnostics, storage as storage_diagnostics  # noqa: F401
from .transforms import season as season_transforms, storage as storage_transforms  # noqa: F401
from .relationship import season as season_relationship, storage as storage_relationship  # noqa: F401
from .trend import storage as storage_trend  # noqa: F401
from .changepoint import storage as storage_changepoint  # noqa: F401
