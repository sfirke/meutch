"""Unit tests for loan reminder functionality including ExtendLoanForm and LoanRequest helper methods."""
import pytest
from datetime import date, timedelta
from app.forms import ExtendLoanForm
from app.models import LoanRequest
from tests.factories import UserFactory, ItemFactory, LoanRequestFactory


class TestExtendLoanForm:
    """Test ExtendLoanForm validation."""
    
    def test_form_validates_with_valid_future_date(self, app):
        """Test that form validates when new_end_date is in the future and after current date."""
        with app.app_context():
            current_end_date = date.today() + timedelta(days=5)
            form = ExtendLoanForm(
                current_end_date=current_end_date,
                data={
                    'new_end_date': date.today() + timedelta(days=10),
                    'message': 'Extending the loan period'
                }
            )
            assert form.validate() is True
    
    def test_form_fails_when_new_date_in_past(self, app):
        """Test that form fails validation when new_end_date is in the past."""
        with app.app_context():
            current_end_date = date.today() + timedelta(days=5)
            form = ExtendLoanForm(
                current_end_date=current_end_date,
                data={
                    'new_end_date': date.today() - timedelta(days=1),
                    'message': ''
                }
            )
            assert form.validate() is False
            assert 'new_end_date' in form.errors
            assert any('past' in error.lower() for error in form.errors['new_end_date'])
    
    def test_form_message_is_optional(self, app):
        """Test that message field is optional."""
        with app.app_context():
            current_end_date = date.today() + timedelta(days=5)
            form = ExtendLoanForm(
                current_end_date=current_end_date,
                data={
                    'new_end_date': date.today() + timedelta(days=10),
                    'message': ''
                }
            )
            assert form.validate() is True
    
    def test_form_accepts_reasonable_message(self, app):
        """Test that form accepts messages with reasonable length."""
        with app.app_context():
            current_end_date = date.today() + timedelta(days=5)
            form = ExtendLoanForm(
                current_end_date=current_end_date,
                data={
                    'new_end_date': date.today() + timedelta(days=10),
                    'message': 'A' * 500  # Well under the limit
                }
            )
            assert form.validate() is True


class TestLoanRequestHelperMethods:
    """Test LoanRequest model helper methods for due date calculations."""
    
    def test_days_until_due_future(self, app):
        """Test days_until_due returns positive number for future due dates."""
        with app.app_context():
            user = UserFactory()
            item = ItemFactory(owner=user)
            loan = LoanRequestFactory(
                item=item,
                borrower=user,
                start_date=date.today(),
                end_date=date.today() + timedelta(days=5),
                status='approved'
            )
            
            assert loan.days_until_due() == 5
    
    def test_days_until_due_today(self, app):
        """Test days_until_due returns 0 for today's due date."""
        with app.app_context():
            user = UserFactory()
            item = ItemFactory(owner=user)
            loan = LoanRequestFactory(
                item=item,
                borrower=user,
                start_date=date.today() - timedelta(days=5),
                end_date=date.today(),
                status='approved'
            )
            
            assert loan.days_until_due() == 0
    
    def test_is_due_soon_returns_true_when_due_today(self, app):
        """Test is_due_soon returns True for loans due today."""
        with app.app_context():
            user = UserFactory()
            item = ItemFactory(owner=user)
            loan = LoanRequestFactory(
                item=item,
                borrower=user,
                start_date=date.today() - timedelta(days=5),
                end_date=date.today(),
                status='approved'
            )
            
            assert loan.is_due_soon() is True
    
    def test_days_until_due_past(self, app):
        """Test days_until_due returns negative number for past due dates."""
        with app.app_context():
            user = UserFactory()
            item = ItemFactory(owner=user)
            loan = LoanRequestFactory(
                item=item,
                borrower=user,
                start_date=date.today() - timedelta(days=10),
                end_date=date.today() - timedelta(days=3),
                status='approved'
            )
            
            assert loan.days_until_due() == -3
    
    def test_is_due_soon_returns_true_within_3_days(self, app):
        """Test is_due_soon returns True for loans due in 1-3 days."""
        with app.app_context():
            user = UserFactory()
            item = ItemFactory(owner=user)
            
            # Test 1 day
            loan1 = LoanRequestFactory(
                item=item,
                borrower=user,
                start_date=date.today(),
                end_date=date.today() + timedelta(days=1),
                status='approved'
            )
            assert loan1.is_due_soon() is True
            
            # Test 3 days
            loan2 = LoanRequestFactory(
                item=item,
                borrower=user,
                start_date=date.today(),
                end_date=date.today() + timedelta(days=3),
                status='approved'
            )
            assert loan2.is_due_soon() is True
    
    def test_is_due_soon_returns_false_more_than_3_days(self, app):
        """Test is_due_soon returns False for loans due in more than 3 days."""
        with app.app_context():
            user = UserFactory()
            item = ItemFactory(owner=user)
            loan = LoanRequestFactory(
                item=item,
                borrower=user,
                start_date=date.today(),
                end_date=date.today() + timedelta(days=4),
                status='approved'
            )
            
            assert loan.is_due_soon() is False
    
    def test_is_due_soon_returns_false_for_overdue(self, app):
        """Test is_due_soon returns False for overdue loans."""
        with app.app_context():
            user = UserFactory()
            item = ItemFactory(owner=user)
            loan = LoanRequestFactory(
                item=item,
                borrower=user,
                start_date=date.today() - timedelta(days=10),
                end_date=date.today() - timedelta(days=1),
                status='approved'
            )
            
            assert loan.is_due_soon() is False
    
    def test_is_overdue_returns_true_for_past_due(self, app):
        """Test is_overdue returns True for loans past due date."""
        with app.app_context():
            user = UserFactory()
            item = ItemFactory(owner=user)
            loan = LoanRequestFactory(
                item=item,
                borrower=user,
                start_date=date.today() - timedelta(days=10),
                end_date=date.today() - timedelta(days=1),
                status='approved'
            )
            
            assert loan.is_overdue() is True
    
    def test_is_overdue_returns_false_for_future_due(self, app):
        """Test is_overdue returns False for loans not yet due."""
        with app.app_context():
            user = UserFactory()
            item = ItemFactory(owner=user)
            loan = LoanRequestFactory(
                item=item,
                borrower=user,
                start_date=date.today(),
                end_date=date.today() + timedelta(days=5),
                status='approved'
            )
            
            assert loan.is_overdue() is False
    
    def test_days_overdue_returns_correct_count(self, app):
        """Test days_overdue returns correct number of overdue days."""
        with app.app_context():
            user = UserFactory()
            item = ItemFactory(owner=user)
            loan = LoanRequestFactory(
                item=item,
                borrower=user,
                start_date=date.today() - timedelta(days=10),
                end_date=date.today() - timedelta(days=5),
                status='approved'
            )
            
            assert loan.days_overdue() == 5
    
    def test_days_overdue_returns_zero_when_not_overdue(self, app):
        """Test days_overdue returns 0 for loans not yet overdue."""
        with app.app_context():
            user = UserFactory()
            item = ItemFactory(owner=user)
            loan = LoanRequestFactory(
                item=item,
                borrower=user,
                start_date=date.today(),
                end_date=date.today() + timedelta(days=5),
                status='approved'
            )
            
            assert loan.days_overdue() == 0
