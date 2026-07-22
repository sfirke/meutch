"""Contact form route for authenticated users to message the Meutch team."""

from flask import flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.forms_contact import ContactForm
from app.main import bp as main_bp
from app.utils.email import send_contact_form_email


@main_bp.route("/contact", methods=["GET", "POST"])
@login_required
def contact():
    """Render and process the contact form."""
    form = ContactForm()

    if form.validate_on_submit():
        sent = send_contact_form_email(current_user, form.category.data, form.message.data)
        if sent:
            flash(
                "Your message has been sent to the Meutch team. Thank you!",
                "success",
            )
            return redirect(url_for("main.index"))
        else:
            flash(
                "The Meutch team is currently unavailable. Please try again later.",
                "info",
            )
            return redirect(url_for("main.index"))

    return render_template("main/contact.html", form=form)
