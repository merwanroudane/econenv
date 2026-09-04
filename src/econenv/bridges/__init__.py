"""Data bridges: pandas in, engine-native out, and back again (brief §10).

Every bridge exposes the same two functions::

    push_frame(engine, name, df, **kwargs) -> ConversionReport
    pull_frame(engine, name, **kwargs)     -> DataFrame

``pandas.DataFrame`` is the canonical interchange object. The transport
underneath differs per engine — PyStata's in-memory API for Stata, COM arrays
for EViews, a typed file handshake for R — but the contract above never does, so
:mod:`econenv.transfer` can move data between *any* pair of engines without
knowing which two.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .eviews_bridge import pull_frame as pull_eviews  # noqa: F401
    from .r_bridge import pull_frame as pull_r  # noqa: F401
    from .stata_bridge import pull_frame as pull_stata  # noqa: F401

__all__ = ["eviews_bridge", "r_bridge", "stata_bridge"]
