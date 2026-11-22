import hashlib
from datetime import UTC, datetime

from item_appraiser import Appraisal, AppraisalError, Condition, Confidence, Impact, ResaleDemand


class StubAppraiser:
    """Appraiser protocol stand-in that makes no API calls."""

    def __init__(self, fail_for=()):
        self.fail_for = set(fail_for)
        self.appraised_names = []

    def fingerprint(self, listing):
        text = "|".join([listing.name, listing.description, *listing.image_urls])
        return hashlib.sha256(text.encode()).hexdigest()

    def appraise(self, listing):
        if listing.name in self.fail_for:
            raise AppraisalError(f"cannot appraise {listing.name}")
        self.appraised_names.append(listing.name)
        return Appraisal(
            new_price_usd=100.0,
            condition=Condition.USED,
            resale_demand=ResaleDemand.TYPICAL,
            confidence=Confidence.MEDIUM,
            assumption="Stub estimate.",
            model_version="stub/p1",
            estimated_at=datetime.now(UTC),
            footprint_category=None,
            impacts=frozenset({Impact.MONEY}),
            fingerprint=self.fingerprint(listing),
        )

    def estimate_cost(self, listings):
        return 0.003 * len(list(listings))
