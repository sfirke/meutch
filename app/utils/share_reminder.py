"""Share link fields for public activities, plus the post-creation reminder to share them."""

from typing import NamedTuple

from flask import flash, render_template, url_for
from markupsafe import Markup


class ShareFields(NamedTuple):
    url: str
    title: str
    text: str


def giveaway_share_fields(item):
    return ShareFields(
        url_for("share.giveaway_preview", item_id=item.id, _external=True),
        f"{item.name} (Free Giveaway)",
        f"Free giveaway on Meutch: {item.name}",
    )


def request_share_fields(item_request):
    return ShareFields(
        url_for("share.request_preview", request_id=item_request.id, _external=True),
        f"{item_request.title} (Request)",
        f"Request on Meutch: {item_request.title}",
    )


def flash_share_reminder(share_fields, activity_noun, headline):
    """Flash the creation message with the share reminder (copy + Share button) folded in."""
    html = render_template(
        "share/_share_reminder.html",
        share_url=share_fields.url,
        share_title=share_fields.title,
        share_text=share_fields.text,
        activity_noun=activity_noun,
        share_headline=headline,
    )
    flash(Markup(html), "success")


def flash_item_created(item, message):
    if item.is_giveaway and item.giveaway_visibility == "public":
        headline = Markup('Giveaway "<a href="{}" class="alert-link">{}</a>" posted!').format(
            url_for("main.item_detail", item_id=item.id), item.name
        )
        flash_share_reminder(giveaway_share_fields(item), "giveaway", headline)
    else:
        flash(message, "success")


def flash_request_created(item_request):
    if item_request.visibility == "public":
        flash_share_reminder(request_share_fields(item_request), "request", "Request posted!")
    else:
        flash("Your request has been posted!", "success")
