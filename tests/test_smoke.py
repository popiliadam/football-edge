from __future__ import annotations

import football_edge


def test_package_exposes_version() -> None:
    assert isinstance(football_edge.__version__, str)
    assert football_edge.__version__
