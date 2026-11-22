import logging
from dataclasses import dataclass

import anthropic
import openai
from flask import current_app
from item_appraiser import (
    Appraisal,
    AppraisalError,
    Appraiser,
    ClaudeAppraiser,
    DeepSeekAppraiser,
    Impact,
    Listing,
)
from item_appraiser.deepseek import BASE_URL as DEEPSEEK_BASE_URL
from sqlalchemy.orm import selectinload

from app import db
from app.models import Item, ItemAppraisal

logger = logging.getLogger(__name__)

CLIENT_TIMEOUT_SECONDS = 60


@dataclass
class AppraisalSummary:
    appraised: int = 0
    skipped: int = 0
    failed: int = 0
    pending: int = 0
    estimated_cost_usd: float = 0.0
    dry_run: bool = False


def build_appraiser() -> Appraiser:
    provider = current_app.config["IMPACT_APPRAISER_PROVIDER"]
    options = {"impacts": [Impact.MONEY, Impact.CLIMATE]}
    model = current_app.config["IMPACT_APPRAISER_MODEL"]
    if model:
        options["model"] = model

    if provider == "claude":
        client = anthropic.Anthropic(
            api_key=current_app.config["ANTHROPIC_API_KEY"], timeout=CLIENT_TIMEOUT_SECONDS
        )
        return ClaudeAppraiser(client=client, **options)
    if provider == "deepseek":
        client = openai.OpenAI(
            api_key=current_app.config["DEEPSEEK_API_KEY"],
            base_url=DEEPSEEK_BASE_URL,
            timeout=CLIENT_TIMEOUT_SECONDS,
        )
        return DeepSeekAppraiser(client=client, **options)
    raise ValueError(f"Unknown IMPACT_APPRAISER_PROVIDER: {provider!r}")


def listing_for(item: Item) -> Listing:
    return Listing(
        name=item.name,
        description=f"{item.description}\n\nCategory: {item.category.name}",
        image_urls=[image.url for image in item.images],
        item_id=str(item.id),
    )


def needs_appraisal(item: Item, appraiser: Appraiser) -> bool:
    if item.appraisal is None:
        return True
    return item.appraisal.fingerprint != appraiser.fingerprint(listing_for(item))


def appraise_item(item: Item, appraiser: Appraiser) -> ItemAppraisal:
    appraisal: Appraisal = appraiser.appraise(listing_for(item))
    row = item.appraisal or ItemAppraisal()
    item.appraisal = row
    row.update_from_appraisal(appraisal)
    return row


def appraise_pending(limit: int, appraiser: Appraiser, dry_run: bool = False) -> AppraisalSummary:
    """Appraise up to `limit` items that need it, oldest first.

    Failed attempts count toward the limit so a persistently failing item
    can't use up every run's budget.
    """
    summary = AppraisalSummary(dry_run=dry_run)
    items = (
        Item.query.options(selectinload(Item.appraisal), selectinload(Item.images))
        .order_by(Item.created_at, Item.id)
        .all()
    )

    pending = []
    for item in items:
        if len(pending) >= limit:
            break
        if needs_appraisal(item, appraiser):
            pending.append(item)
        else:
            summary.skipped += 1

    if dry_run:
        summary.pending = len(pending)
        summary.estimated_cost_usd = float(
            appraiser.estimate_cost([listing_for(item) for item in pending])
        )
        return summary

    for item in pending:
        item_id = item.id
        try:
            appraise_item(item, appraiser)
            db.session.commit()
            summary.appraised += 1
        except AppraisalError:
            db.session.rollback()
            logger.exception("Appraisal failed for item %s", item_id)
            summary.failed += 1
    return summary
