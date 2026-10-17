"""Post-creation reminder nudging users to share public activities outside Meutch."""

from flask import flash, render_template, url_for
from markupsafe import Markup


def flash_share_reminder(share_url, share_title, share_text, activity_noun):
    """Flash the share reminder (copy + Share button) rendered from its template."""
    html = render_template(
        "share/_share_reminder.html",
        share_url=share_url,
        share_title=share_title,
        share_text=share_text,
        activity_noun=activity_noun,
    )
    flash(Markup(html), "info")


def flash_giveaway_share_reminder(item):
    if not (item.is_giveaway and item.giveaway_visibility == "public"):
        return
    flash_share_reminder(
        url_for("share.giveaway_preview", item_id=item.id, _external=True),
        f"{item.name} (Free Giveaway)",
        f"Free giveaway on Meutch: {item.name}",
        "giveaway",
    )


def flash_request_share_reminder(item_request):
    if item_request.visibility != "public":
        return
    flash_share_reminder(
        url_for("share.request_preview", request_id=item_request.id, _external=True),
        f"{item_request.title} (Request)",
        f"Request on Meutch: {item_request.title}",
        "request",
    )
