from unittest.mock import patch

from app import db
from app.models import ItemAppraisal
from tests.factories import ItemFactory
from tests.helpers_impact import StubAppraiser


def _invoke(app, *args):
    with patch("app.services.impact_service.build_appraiser", return_value=StubAppraiser()):
        return app.test_cli_runner().invoke(args=["impact", "appraise", *args])


class TestImpactAppraiseCommand:
    def test_appraises_items(self, app):
        with app.app_context():
            ItemFactory.create_batch(2)
            db.session.commit()

            result = _invoke(app)

            assert result.exit_code == 0, result.output
            assert "Appraised: 2" in result.output
            assert ItemAppraisal.query.count() == 2

    def test_dry_run_writes_nothing(self, app):
        with app.app_context():
            ItemFactory.create_batch(2)
            db.session.commit()

            result = _invoke(app, "--dry-run", "--limit", "1")

            assert result.exit_code == 0, result.output
            assert "1 item(s) would be appraised" in result.output
            assert ItemAppraisal.query.count() == 0
