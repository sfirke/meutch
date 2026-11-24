from decimal import Decimal

import pytest

from app import db
from app.services import impact_service
from tests.factories import ImpactEventFactory


@pytest.fixture(autouse=True)
def _fresh_cache(monkeypatch):
    monkeypatch.setattr(impact_service, "_landing_cache", None)


def _filled_events(count, usd="10.00", kg="2.0"):
    for _ in range(count):
        ImpactEventFactory(usd_saved=Decimal(usd), kg_co2e_avoided=Decimal(kg))
    db.session.commit()


@pytest.mark.parametrize(
    ("value", "expected"),
    [("0", 0), ("7.4", 7), ("99.5", 100), ("1234.56", 1200), ("98765", 99000), ("250", 250)],
)
def test_round_for_display(value, expected):
    assert impact_service._round_for_display(Decimal(value)) == expected


class TestLandingImpact:
    def test_hidden_below_threshold(self, app):
        with app.app_context():
            _filled_events(impact_service.LANDING_MIN_EVENTS - 1)
            ImpactEventFactory()  # pending events don't count toward the threshold
            db.session.commit()

            assert impact_service.landing_impact() is None

    def test_rounded_totals_at_threshold(self, app):
        with app.app_context():
            _filled_events(impact_service.LANDING_MIN_EVENTS, usd="123.40", kg="4.3")

            assert impact_service.landing_impact() == (1200, 43)

    def test_cached_until_expiry(self, app, monkeypatch):
        with app.app_context():
            clock = [1000.0]
            monkeypatch.setattr(impact_service, "monotonic", lambda: clock[0])
            assert impact_service.landing_impact() is None

            _filled_events(impact_service.LANDING_MIN_EVENTS)
            assert impact_service.landing_impact() is None

            clock[0] += impact_service.LANDING_CACHE_SECONDS + 1
            assert impact_service.landing_impact() is not None
