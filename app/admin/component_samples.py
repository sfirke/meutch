"""Made-up data for the admin components page, so every state shows without real records."""

import uuid
from types import SimpleNamespace

from flask_wtf import FlaskForm
from wtforms import BooleanField, RadioField, SelectField, StringField, TextAreaField


class SampleForm(FlaskForm):
    class Meta:
        csrf = False

    name = StringField("Item name")
    description = TextAreaField("Description")
    category = SelectField("Category", choices=[("tools", "Tools"), ("kitchen", "Kitchen")])
    missing = StringField("A field with an error")
    agree = BooleanField("Show my items to my circles")
    switch = BooleanField("Email me a weekly digest")
    kind = RadioField(
        "Do you want to borrow it or keep it?",
        choices=[("loan", "Borrow it"), ("giveaway", "Keep it")],
        default="loan",
    )


def sample_form():
    form = SampleForm(formdata=None)
    form.missing.errors = ["This field is required."]
    return form


def sample_loans():
    def loan(state, until=0, overdue=0):
        return SimpleNamespace(
            due_state=state, days_until_due=lambda: until, days_overdue=lambda: overdue
        )

    return [
        loan("due_soon", until=2),
        loan("due_today"),
        loan("overdue", overdue=1),
        loan("overdue", overdue=6),
    ]


def sample_circle(**kwargs):
    circle = SimpleNamespace(
        id=uuid.uuid4(),
        name="Maple Street Neighbors",
        description="Tools, toys and kitchen gear for the block.",
        member_count=24,
        circle_type="open",
        is_regional=False,
        image_url=None,
    )
    circle.__dict__.update(kwargs)
    return circle


def sample_web_link():
    return SimpleNamespace(
        url="https://example.com/maya", icon_class="fas fa-globe", display_name="Website"
    )
