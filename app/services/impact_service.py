import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from decimal import ROUND_HALF_UP, Decimal
from time import monotonic
from typing import NamedTuple

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
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import selectinload

from app import db
from app.models import ImpactEvent, Item, ItemAppraisal, LoanRequest, Message

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
    if event.kind == ImpactEvent.KIND_LOAN:
        usd_saved = appraisal_loan_value(appraisal)
        kg_co2e_avoided = appraisal_loan_kg_co2e(appraisal)
    else:
        usd_saved = appraisal_buy_value(appraisal)
        kg_co2e_avoided = appraisal_giveaway_kg_co2e(appraisal)
    event.new_price_usd = appraisal_row.new_price_usd
    event.quantity = appraisal_row.quantity
    event.condition = appraisal_row.condition
    event.resale_demand = appraisal_row.resale_demand
    event.footprint_category = appraisal_row.footprint_category
    event.model_version = appraisal_row.model_version
    event.usd_saved = usd_saved
    event.kg_co2e_avoided = kg_co2e_avoided
    event.policy_version = __version__


def _try_fill(event: ImpactEvent, appraisal_row: ItemAppraisal) -> bool:
    """Fill the event, leaving it pending if its appraisal can't be used."""
    try:
        fill_event(event, appraisal_row)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("Could not fill impact event for item %s", appraisal_row.item_id)
        return False
    return True


def record_loan_completed(loan) -> None:
    _record_event(
        ImpactEvent.KIND_LOAN,
        loan.item,
        loan_request_id=loan.id,
        beneficiary_id=loan.borrower_id,
    )


def record_giveaway_completed(item: Item, recipient_id) -> None:
    _record_event(ImpactEvent.KIND_GIVEAWAY, item, beneficiary_id=recipient_id)


def _build_event(
    kind, item: Item, *, occurred_at, beneficiary_id, loan_request_id=None
) -> ImpactEvent:
    event = ImpactEvent(
        kind=kind,
        occurred_at=occurred_at,
        item_id=item.id,
        loan_request_id=loan_request_id,
        beneficiary_id=beneficiary_id,
        provider_id=item.owner_id,
        item_name=item.name,
        category_name=item.category.name,
    )
    if item.appraisal is not None:
        _try_fill(event, item.appraisal)
    return event


def _record_event(kind, item: Item, *, beneficiary_id, loan_request_id=None) -> None:
    """Add a ledger row in a savepoint so a failure here never blocks the completion."""
    item_id = item.id
    event = _build_event(
        kind,
        item,
        occurred_at=datetime.now(UTC),
        beneficiary_id=beneficiary_id,
        loan_request_id=loan_request_id,
    )
    # Flush the completion itself first, so its errors aren't swallowed below.
    db.session.flush()
    try:
        with db.session.begin_nested():
            db.session.add(event)
    except SQLAlchemyError:
        logger.exception("Could not record %s impact event for item %s", kind, item_id)


def fill_pending_events() -> int:
    """Fill pending events whose item now has an appraisal; return how many."""
    rows = (
        db.session.query(ImpactEvent, ItemAppraisal)
        .join(ItemAppraisal, ItemAppraisal.item_id == ImpactEvent.item_id)
        .filter(ImpactEvent.usd_saved.is_(None))
        .all()
    )
    filled = sum(_try_fill(event, appraisal_row) for event, appraisal_row in rows)
    db.session.commit()
    return filled


@dataclass
class BackfillSummary:
    loans: int = 0
    giveaways: int = 0
    filled: int = 0
    dry_run: bool = False


def _utc_noon(day: date) -> datetime:
    return datetime.combine(day, time(12), tzinfo=UTC)


def _loan_returned_times(loans) -> dict:
    """When each loan was marked returned: the time of its last loan message."""
    # pylint: disable=not-callable
    rows = (
        db.session.query(Message.loan_request_id, func.max(Message.timestamp))
        .filter(Message.loan_request_id.in_([loan.id for loan in loans]))
        .group_by(Message.loan_request_id)
        .all()
    )
    return {loan_id: timestamp.replace(tzinfo=UTC) for loan_id, timestamp in rows}


def backfill_events(dry_run: bool = False) -> BackfillSummary:
    """Create events for completed loans and claimed giveaways that have none."""
    summary = BackfillSummary(dry_run=dry_run)
    loans = (
        LoanRequest.query.filter(
            LoanRequest.status == "completed",
            ~db.session.query(ImpactEvent.id)
            .filter(ImpactEvent.loan_request_id == LoanRequest.id)
            .exists(),
        )
        .options(selectinload(LoanRequest.item).selectinload(Item.appraisal))
        .all()
    )
    giveaways = (
        Item.query.filter(
            Item.is_giveaway.is_(True),
            Item.claim_status == "claimed",
            ~db.session.query(ImpactEvent.id)
            .filter(ImpactEvent.item_id == Item.id, ImpactEvent.kind == ImpactEvent.KIND_GIVEAWAY)
            .exists(),
        )
        .options(selectinload(Item.appraisal))
        .all()
    )
    if dry_run:
        summary.loans = len(loans)
        summary.giveaways = len(giveaways)
        return summary

    now = datetime.now(UTC)
    returned_at = _loan_returned_times(loans)
    events = [
        _build_event(
            ImpactEvent.KIND_LOAN,
            loan.item,
            occurred_at=min(returned_at.get(loan.id) or _utc_noon(loan.end_date), now),
            beneficiary_id=loan.borrower_id,
            loan_request_id=loan.id,
        )
        for loan in loans
    ]
    events += [
        _build_event(
            ImpactEvent.KIND_GIVEAWAY,
            item,
            occurred_at=(item.claimed_at or item.created_at).replace(tzinfo=UTC),
            beneficiary_id=item.claimed_by_id,
        )
        for item in giveaways
    ]
    for event in events:
        # A loan or giveaway completed while this runs already has its event.
        try:
            with db.session.begin_nested():
                db.session.add(event)
        except IntegrityError:
            continue
        if event.kind == ImpactEvent.KIND_LOAN:
            summary.loans += 1
        else:
            summary.giveaways += 1
        summary.filled += event.usd_saved is not None
    db.session.commit()
    return summary


class SiteTotals(NamedTuple):
    usd: Decimal
    kg: Decimal
    event_count: int


class UserTotals(NamedTuple):
    saved_usd: Decimal
    saved_kg: Decimal
    helped_usd: Decimal
    helped_kg: Decimal


def _sums(*filters):
    # pylint: disable=not-callable,assignment-from-no-return
    usd = func.coalesce(func.sum(ImpactEvent.usd_saved), 0)
    kg = func.coalesce(func.sum(ImpactEvent.kg_co2e_avoided), 0)
    row = (
        db.session.query(usd, kg, func.count(ImpactEvent.id))
        .filter(ImpactEvent.usd_saved.isnot(None), *filters)
        .one()
    )
    return Decimal(row[0]), Decimal(row[1]), row[2]


def site_totals() -> SiteTotals:
    return SiteTotals(*_sums())


def user_totals(user_id, start=None, end=None) -> UserTotals:
    """Saved (as beneficiary) and helped-others (as provider) sums; start inclusive, end exclusive."""
    window = []
    if start is not None:
        window.append(ImpactEvent.occurred_at >= start)
    if end is not None:
        window.append(ImpactEvent.occurred_at < end)
    saved_usd, saved_kg, _ = _sums(ImpactEvent.beneficiary_id == user_id, *window)
    helped_usd, helped_kg, _ = _sums(ImpactEvent.provider_id == user_id, *window)
    return UserTotals(saved_usd, saved_kg, helped_usd, helped_kg)


LANDING_MIN_EVENTS = 10
LANDING_CACHE_SECONDS = 3600
_landing_cache: tuple[float, "LandingImpact | None"] | None = None


class LandingImpact(NamedTuple):
    usd: int
    kg: int


def _round_for_display(value: Decimal) -> int:
    """Whole numbers under 100, two significant figures above."""
    whole = int(value.to_integral_value(ROUND_HALF_UP))
    if whole < 100:
        return whole
    places = len(str(whole)) - 2
    return int(Decimal(whole).scaleb(-places).quantize(1, ROUND_HALF_UP).scaleb(places))


def landing_impact() -> LandingImpact | None:
    """Rounded site totals for the landing page, or None until there are enough events.

    Cached per process for an hour.
    """
    global _landing_cache  # pylint: disable=global-statement
    now = monotonic()
    if _landing_cache is not None and _landing_cache[0] > now:
        return _landing_cache[1]
    totals = site_totals()
    result = None
    if totals.event_count >= LANDING_MIN_EVENTS:
        result = LandingImpact(_round_for_display(totals.usd), _round_for_display(totals.kg))
    _landing_cache = (now + LANDING_CACHE_SECONDS, result)
    return result
