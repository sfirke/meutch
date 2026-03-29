from datetime import datetime, UTC, timedelta
from unittest.mock import patch

from app import db
from app.cli import check_digest_sends_logic, _to_utc, _digest_cadence_boundary_utc
from app.models import User
from tests.factories import UserFactory


class TestCliDigestScheduler:
    def test_digest_scheduler_prefers_tz_over_digest_timezone(self, app):
        with app.app_context():
            app.config['DIGEST_TIMEZONE'] = 'UTC'
            now_utc = datetime(2026, 3, 15, 5, 0, tzinfo=UTC)

            with patch.dict('os.environ', {'TZ': 'America/New_York'}, clear=False):
                boundary = _digest_cadence_boundary_utc(User.DIGEST_FREQUENCY_DAILY, now_utc)

            assert boundary == datetime(2026, 3, 15, 4, 0, tzinfo=UTC)

    def test_digest_scheduler_falls_back_to_digest_timezone_when_tz_invalid(self, app):
        with app.app_context():
            app.config['DIGEST_TIMEZONE'] = 'America/Los_Angeles'
            now_utc = datetime(2026, 3, 15, 12, 0, tzinfo=UTC)

            with patch.dict('os.environ', {'TZ': 'Invalid/Timezone'}, clear=False):
                boundary = _digest_cadence_boundary_utc(User.DIGEST_FREQUENCY_DAILY, now_utc)

            assert boundary == datetime(2026, 3, 15, 7, 0, tzinfo=UTC)

    def test_digest_scheduler_sends_daily_and_weekly_and_skips_none(self, app):
        with app.app_context():
            now_utc = datetime(2026, 3, 15, 14, 0, tzinfo=UTC)

            daily_user = UserFactory(digest_frequency=User.DIGEST_FREQUENCY_DAILY)
            weekly_user = UserFactory(digest_frequency=User.DIGEST_FREQUENCY_WEEKLY)
            none_user = UserFactory(digest_frequency=User.DIGEST_FREQUENCY_NONE)
            db.session.commit()

            with patch('app.utils.home_feed.build_digest_payload', return_value={'events': [{'event_type': 'request'}]}), \
                 patch('app.utils.email.send_digest_email', return_value=True) as send_mock:
                stats = check_digest_sends_logic(now_utc=now_utc)

            db.session.refresh(daily_user)
            db.session.refresh(weekly_user)
            db.session.refresh(none_user)

            assert send_mock.call_count == 2
            assert stats['sent'] == 2
            assert stats['skipped'] == 1
            assert stats['by_cadence'][User.DIGEST_FREQUENCY_DAILY]['sent'] == 1
            assert stats['by_cadence'][User.DIGEST_FREQUENCY_WEEKLY]['sent'] == 1
            assert stats['by_cadence'][User.DIGEST_FREQUENCY_NONE]['skipped'] == 1
            assert daily_user.digest_last_sent_at is not None
            assert weekly_user.digest_last_sent_at is not None
            assert none_user.digest_last_sent_at is None

    def test_digest_scheduler_skips_email_when_no_matching_activity(self, app):
        with app.app_context():
            now_utc = datetime(2026, 3, 15, 14, 0, tzinfo=UTC)

            daily_user = UserFactory(digest_frequency=User.DIGEST_FREQUENCY_DAILY)
            weekly_user = UserFactory(digest_frequency=User.DIGEST_FREQUENCY_WEEKLY)
            db.session.commit()

            with patch('app.utils.home_feed.build_digest_payload', return_value={'events': []}), \
                 patch('app.utils.email.send_digest_email', return_value=True) as send_mock:
                stats = check_digest_sends_logic(now_utc=now_utc)

            db.session.refresh(daily_user)
            db.session.refresh(weekly_user)

            assert send_mock.call_count == 0
            assert stats['sent'] == 0
            assert stats['skipped'] == 2
            assert stats['by_cadence'][User.DIGEST_FREQUENCY_DAILY]['skipped'] == 1
            assert stats['by_cadence'][User.DIGEST_FREQUENCY_WEEKLY]['skipped'] == 1
            assert daily_user.digest_last_sent_at is None
            assert weekly_user.digest_last_sent_at is None

    def test_digest_scheduler_weekly_only_sends_on_sunday(self, app):
        with app.app_context():
            monday_utc = datetime(2026, 3, 16, 14, 0, tzinfo=UTC)
            weekly_user = UserFactory(digest_frequency=User.DIGEST_FREQUENCY_WEEKLY)
            db.session.commit()

            with patch('app.utils.home_feed.build_digest_payload', return_value={'events': [{'event_type': 'request'}]}), \
                 patch('app.utils.email.send_digest_email', return_value=True) as send_mock:
                stats = check_digest_sends_logic(now_utc=monday_utc)

            db.session.refresh(weekly_user)

            assert send_mock.call_count == 0
            assert stats['sent'] == 0
            assert stats['by_cadence'][User.DIGEST_FREQUENCY_WEEKLY]['skipped'] == 1
            assert weekly_user.digest_last_sent_at is None

    def test_digest_scheduler_skips_when_already_sent_in_current_period(self, app):
        with app.app_context():
            sunday_utc = datetime(2026, 3, 15, 14, 0, tzinfo=UTC)

            daily_user = UserFactory(
                digest_frequency=User.DIGEST_FREQUENCY_DAILY,
                digest_last_sent_at=sunday_utc - timedelta(hours=1),
            )
            weekly_user = UserFactory(
                digest_frequency=User.DIGEST_FREQUENCY_WEEKLY,
                digest_last_sent_at=sunday_utc - timedelta(hours=2),
            )
            db.session.commit()

            with patch('app.utils.home_feed.build_digest_payload', return_value={'events': [{'event_type': 'request'}]}), \
                 patch('app.utils.email.send_digest_email', return_value=True) as send_mock:
                stats = check_digest_sends_logic(now_utc=sunday_utc)

            assert send_mock.call_count == 0
            assert stats['sent'] == 0
            assert stats['skipped'] == 2
            assert stats['by_cadence'][User.DIGEST_FREQUENCY_DAILY]['skipped'] == 1
            assert stats['by_cadence'][User.DIGEST_FREQUENCY_WEEKLY]['skipped'] == 1

    def test_digest_scheduler_continues_after_user_send_failure(self, app):
        with app.app_context():
            sunday_utc = datetime(2026, 3, 15, 14, 0, tzinfo=UTC)

            daily_ok = UserFactory(email='daily_ok@example.com', digest_frequency=User.DIGEST_FREQUENCY_DAILY)
            weekly_fail = UserFactory(email='weekly_fail@example.com', digest_frequency=User.DIGEST_FREQUENCY_WEEKLY)
            daily_ok_2 = UserFactory(email='daily_ok_2@example.com', digest_frequency=User.DIGEST_FREQUENCY_DAILY)
            db.session.commit()

            def send_side_effect(user, _payload):
                return user.email != 'weekly_fail@example.com'

            with patch('app.utils.home_feed.build_digest_payload', return_value={'events': [{'event_type': 'request'}]}), \
                 patch('app.utils.email.send_digest_email', side_effect=send_side_effect) as send_mock:
                stats = check_digest_sends_logic(now_utc=sunday_utc)

            db.session.refresh(daily_ok)
            db.session.refresh(weekly_fail)
            db.session.refresh(daily_ok_2)

            assert send_mock.call_count == 3
            assert stats['sent'] == 2
            assert len(stats['errors']) == 1
            assert stats['by_cadence'][User.DIGEST_FREQUENCY_WEEKLY]['errors'] == 1
            assert daily_ok.digest_last_sent_at is not None
            assert daily_ok_2.digest_last_sent_at is not None
            assert weekly_fail.digest_last_sent_at is None

    def test_digest_scheduler_force_send_bypasses_cadence_window_checks(self, app):
        with app.app_context():
            monday_utc = datetime(2026, 3, 16, 14, 0, tzinfo=UTC)

            daily_user = UserFactory(
                digest_frequency=User.DIGEST_FREQUENCY_DAILY,
                digest_last_sent_at=monday_utc - timedelta(hours=1),
            )
            weekly_user = UserFactory(
                digest_frequency=User.DIGEST_FREQUENCY_WEEKLY,
                digest_last_sent_at=monday_utc - timedelta(days=1),
            )
            none_user = UserFactory(digest_frequency=User.DIGEST_FREQUENCY_NONE)
            db.session.commit()

            with patch('app.utils.home_feed.build_digest_payload', return_value={'events': [{'event_type': 'request'}]}), \
                 patch('app.utils.email.send_digest_email', return_value=True) as send_mock:
                stats = check_digest_sends_logic(now_utc=monday_utc, force_send=True)

            db.session.refresh(daily_user)
            db.session.refresh(weekly_user)
            db.session.refresh(none_user)

            assert send_mock.call_count == 2
            assert stats['sent'] == 2
            assert stats['by_cadence'][User.DIGEST_FREQUENCY_DAILY]['sent'] == 1
            assert stats['by_cadence'][User.DIGEST_FREQUENCY_WEEKLY]['sent'] == 1
            assert stats['by_cadence'][User.DIGEST_FREQUENCY_NONE]['skipped'] == 1
            assert _to_utc(daily_user.digest_last_sent_at) == monday_utc
            assert _to_utc(weekly_user.digest_last_sent_at) == monday_utc
            assert none_user.digest_last_sent_at is None
