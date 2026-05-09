"""Compatibility re-export layer for domain-specific form modules."""

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
from app.forms_messaging import MessageForm
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
