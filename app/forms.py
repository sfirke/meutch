"""Compatibility re-export layer for domain-specific form modules.

This module exists to maintain backwards compatibility for imports that have not
yet been updated. Do NOT add new forms here — add them in the appropriate
domain module (forms_items.py, forms_loans.py, etc.) and import from there directly.
"""

from app.forms_auth import (
    ForgotPasswordForm,
    LoginForm,
    RegistrationForm,
    ResendConfirmationForm,
    ResetPasswordForm,
)
from app.forms_circles import (
    CircleCreateForm,
    CircleJoinRequestForm,
    CircleSearchForm,
    CircleUuidSearchForm,
)
from app.forms_items import (
    ChangeRecipientForm,
    ConfirmHandoffForm,
    DeleteItemForm,
    ExpressInterestForm,
    ListItemForm,
    ReleaseToAllForm,
    SelectRecipientForm,
    WithdrawInterestForm,
)
from app.forms_loans import ExtendLoanForm, LoanRequestForm
from app.forms_messaging import BulkActionForm, MessageForm
from app.forms_profile import (
    DeleteAccountForm,
    DigestSettingsForm,
    EditProfileForm,
    UpdateLocationForm,
    VacationModeForm,
)
from app.forms_requests import ItemRequestForm
from app.forms_shared import (
    DIGEST_FREQUENCY_CHOICES,
    EmptyForm,
    OptionalFileAllowed,
    OptionalURL,
)

__all__ = [
    "BulkActionForm",
    "ChangeRecipientForm",
    "CircleCreateForm",
    "CircleJoinRequestForm",
    "CircleSearchForm",
    "CircleUuidSearchForm",
    "ConfirmHandoffForm",
    "DIGEST_FREQUENCY_CHOICES",
    "DeleteAccountForm",
    "DeleteItemForm",
    "DigestSettingsForm",
    "EditProfileForm",
    "EmptyForm",
    "ExpressInterestForm",
    "ExtendLoanForm",
    "ForgotPasswordForm",
    "ItemRequestForm",
    "ListItemForm",
    "LoanRequestForm",
    "LoginForm",
    "MessageForm",
    "OptionalFileAllowed",
    "OptionalURL",
    "RegistrationForm",
    "ReleaseToAllForm",
    "ResendConfirmationForm",
    "ResetPasswordForm",
    "SelectRecipientForm",
    "UpdateLocationForm",
    "VacationModeForm",
    "WithdrawInterestForm",
]
