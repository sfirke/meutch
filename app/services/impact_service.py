import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from flask import current_app
from item_appraiser import (
    Appraisal,
    AppraisalError,
    Appraiser,
    Impact,
    Listing,
    __version__,
)
from item_appraiser.climate import appraisal_giveaway_kg_co2e, appraisal_loan_kg_co2e
from item_appraiser.policy import appraisal_buy_value, appraisal_loan_value
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload

from app import db
from app.models import ImpactEvent, Item, ItemAppraisal

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
    # pylint: disable=import-outside-toplevel
    # Provider SDKs are heavy; load them only when the job runs.
    import anthropic
    import openai
    from item_appraiser import ClaudeAppraiser, DeepSeekAppraiser
    from item_appraiser.deepseek import BASE_URL as DEEPSEEK_BASE_URL

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


def fill_event(event: ImpactEvent, appraisal_row: ItemAppraisal) -> None:
    """Copy the appraisal inputs onto the event and compute its savings."""
    appraisal = appraisal_row.to_appraisal()
    event.new_price_usd = appraisal_row.new_price_usd
    event.quantity = appraisal_row.quantity
    event.condition = appraisal_row.condition
    event.resale_demand = appraisal_row.resale_demand
    event.footprint_category = appraisal_row.footprint_category
    event.model_version = appraisal_row.model_version
    if event.kind == ImpactEvent.KIND_LOAN:
        event.usd_saved = appraisal_loan_value(appraisal)
        event.kg_co2e_avoided = appraisal_loan_kg_co2e(appraisal)
    else:
        event.usd_saved = appraisal_buy_value(appraisal)
        event.kg_co2e_avoided = appraisal_giveaway_kg_co2e(appraisal)
    event.policy_version = __version__


def record_loan_completed(loan) -> None:
    _record_event(
        ImpactEvent.KIND_LOAN,
        loan.item,
        loan_request_id=loan.id,
        beneficiary_id=loan.borrower_id,
    )


def record_giveaway_completed(item: Item, recipient_id) -> None:
    _record_event(ImpactEvent.KIND_GIVEAWAY, item, beneficiary_id=recipient_id)


def _record_event(kind, item: Item, *, beneficiary_id, loan_request_id=None) -> None:
    """Add a ledger row in a savepoint so a failure here never blocks the completion."""
    item_id = item.id
    event = ImpactEvent(
        kind=kind,
        occurred_at=datetime.now(UTC),
        item_id=item_id,
        loan_request_id=loan_request_id,
        beneficiary_id=beneficiary_id,
        provider_id=item.owner_id,
        item_name=item.name,
        category_name=item.category.name,
    )
    if item.appraisal is not None:
        fill_event(event, item.appraisal)
    # Flush the completion itself first, so its errors aren't swallowed below.
    db.session.flush()
    try:
        with db.session.begin_nested():
            db.session.add(event)
    except SQLAlchemyError:
        logger.exception("Could not record %s impact event for item %s", kind, item_id)
