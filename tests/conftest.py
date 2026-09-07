"""Shared fixtures and engine-availability gating.

Unit tests must pass on a machine with **no** R, Stata or EViews (brief §40).
Anything that needs a real engine is marked and skipped automatically, so CI can
run the whole suite with ``-m "not r and not stata and not eviews"`` and a
licensed Windows runner can run everything.
"""

from __future__ import annotations

import platform

import numpy as np
import pandas as pd
import pytest

#: Engines a test can be marked as needing. MATLAB was missing here while
#: `test_all_five_engines_agree` already asserted it took part, so that test
#: failed rather than skipped on a machine without MATLAB.
ENGINES = ("r", "stata", "eviews", "matlab")


def pytest_collection_modifyitems(config, items):
    """Skip engine tests when the engine is not usable on this machine."""
    from econenv.engines import registry

    available = set()
    for name in ENGINES:
        try:
            if registry.get(name).available:
                available.add(name)
        except Exception:
            pass

    for item in items:
        for engine in ENGINES:
            if engine in item.keywords and engine not in available:
                item.add_marker(
                    pytest.mark.skip(reason=f"{engine} is not installed on this machine")
                )
        if "windows" in item.keywords and platform.system() != "Windows":
            item.add_marker(pytest.mark.skip(reason="Windows only"))


@pytest.fixture(scope="session")
def sample_frame() -> pd.DataFrame:
    """A small, deterministic regression dataset."""
    rng = np.random.default_rng(20260904)
    n = 50
    frame = pd.DataFrame({"x1": rng.normal(size=n), "x2": rng.normal(size=n)})
    frame["y"] = 2.0 + 0.5 * frame.x1 - 0.25 * frame.x2 + rng.normal(scale=0.4, size=n)
    return frame


@pytest.fixture(scope="session")
def typed_frame() -> pd.DataFrame:
    """One column of every logical type EconEnv claims to support."""
    return pd.DataFrame(
        {
            "num": [1.5, 2.5, np.nan, 4.0],
            "whole": pd.array([1, 2, 3, 4], dtype="int64"),
            "txt": ["a", "b", "", None],
            "grp": pd.Categorical(["lo", "hi", "lo", "hi"], categories=["lo", "hi"], ordered=True),
            "when": pd.to_datetime(["2020-01-01", "2020-04-01", "2020-07-01", "2020-10-01"]),
            "flag": [True, False, True, False],
        }
    )


@pytest.fixture(scope="session")
def quarterly_frame() -> pd.DataFrame:
    """A dated frame, for the workfile/frequency paths."""
    index = pd.period_range("2000Q1", periods=12, freq="Q").to_timestamp()
    return pd.DataFrame({"y": np.arange(1.0, 13.0), "x": np.arange(12.0, 0.0, -1.0)}, index=index)


@pytest.fixture
def r_engine():
    from econenv.engines import registry

    engine = registry.get("r")
    engine.start()
    yield engine


@pytest.fixture
def stata_engine():
    from econenv.engines import registry

    engine = registry.get("stata")
    engine.start()
    yield engine


@pytest.fixture
def eviews_engine():
    from econenv.engines import registry

    engine = registry.get("eviews")
    engine.start()
    yield engine
