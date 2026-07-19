import re
from urllib.parse import urlparse

import requests as http_client
from flask import abort, flash, make_response, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import limiter
from app.forms import ContactForm
from app.main import bp as main_bp
from app.utils.email import send_contact_form_email

_CDN_HOST_RE = re.compile(r"^[a-z0-9-]+\.[a-z0-9-]+\.cdn\.digitaloceanspaces\.com$", re.IGNORECASE)


# NOTE: This proxy exists to guard against CDN cache poisoning. The DO Spaces CDN
# can cache responses without Access-Control-Allow-Origin if an image is first
# fetched via a plain <img> tag (no Origin header), causing subsequent fetch()
# calls from the crop editor to be CORS-blocked on that CDN edge node. Routing
# through the server sidesteps this even if bucket-level CORS rules are in place.
# Before removing this, verify the CDN returns Vary: Origin on image responses.
@main_bp.route("/image-proxy")
@login_required
def image_proxy():
    """Proxy a CDN-hosted item image so the crop editor can fetch it without CORS."""
    url = request.args.get("url", "")
    if not url:
        abort(400)

    parsed = urlparse(url)
    if parsed.scheme != "https" or not _CDN_HOST_RE.match(parsed.netloc):
        abort(400)

    try:
        resp = http_client.get(url, timeout=10, stream=True)
        resp.raise_for_status()
    except http_client.RequestException:
        abort(502)

    content_type = resp.headers.get("Content-Type", "image/jpeg")
    proxy_response = make_response(resp.content)
    proxy_response.headers["Content-Type"] = content_type
    proxy_response.headers["Cache-Control"] = "private, max-age=3600"
    return proxy_response


@main_bp.route("/about")
def about():
    return render_template("main/about.html")


@main_bp.route("/how-it-works")
def how_it_works():
    """Public page that explains how Meutch works for new users."""
    return render_template("main/how_it_works.html")


@main_bp.route("/privacy-policy")
def privacy_policy():
    return render_template("main/privacy_policy.html")


@main_bp.route("/terms")
def terms():
    return render_template("main/terms.html")


@main_bp.route("/contact", methods=["GET", "POST"])
@login_required
@limiter.limit("5 per hour")
def contact():
    """Contact form page for authenticated users to send messages to admins."""
    form = ContactForm()

    if form.validate_on_submit():
        success = send_contact_form_email(current_user, form.category.data, form.message.data)
        if success:
            flash("Your message has been sent to the Meutch team. Thank you!", "success")
        else:
            flash(
                "Sorry, we couldn't send your message right now. Please try again later.", "error"
            )
        return redirect(url_for("main.index"))

    return render_template("main/contact.html", form=form)
