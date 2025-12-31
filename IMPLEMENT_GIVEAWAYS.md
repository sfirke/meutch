# Plan: Giveaways Feature for Meutch Lending App

Adding the ability for users to list items as giveaways (one-time transfers instead of loans), with configurable visibility (circles-only or public), a dedicated giveaway feed with distance/date sorting, and integrated filtering across search and browse pages.

## Steps

1. **Add giveaway fields to Item model** in `app/models.py`: Add `is_giveaway` boolean (default False), `giveaway_visibility` enum field (`default` or `public`, nullable - only required when `is_giveaway=True`), and create a database migration.

2. **Update item creation/editing form** in `app/forms.py`: Add checkbox for `is_giveaway` and radio buttons for `giveaway_visibility`; add form validation to require visibility selection when giveaway is checked. Update `app/templates/main/list_item.html` with conditional UI.

3. **Modify item routes** in `app/main/routes.py`: Update `list_item()` and edit routes to save giveaway fields; create new `/giveaways` route with pagination, distance/date sorting, and optional distance filtering.

4. **Update search and browse routes** in `app/main/routes.py`: Add `item_type` query parameter (values: `loans`, `giveaways`, `both`) to `search()`, `category_items()`, and `tag_items()` routes; default to `both`.

5. **Create giveaway feed template and update existing templates**: Create new `giveaways.html` template with sort/filter controls; update `app/templates/search_items.html`, category, and tag templates with item type filter dropdown; update `app/templates/main/item_card.html` to show "Free" badge for giveaways.

6. **Update item detail page** in `app/templates/main/item_detail.html`: Hide loan request functionality for giveaways; show "Contact to claim" or similar messaging-focused CTA instead.

7. **Add navbar link**: Add "Giveaways" link to the main navigation bar for easy discovery.

## Claiming Workflow Design

### Formal Claim Status

Giveaways will have a formal claiming system integrated with messaging:

1. **Claim States on Item**:
   - `unclaimed` - Item is available (default for giveaways)
   - `pending_pickup` - Owner has selected a recipient, awaiting pickup
   - `claimed` - Item has been successfully given away (terminal state)

2. **Workflow**:
   - Users message the owner about a giveaway item
   - Owner reviews messages and selects a recipient from a conversation thread
   - Owner clicks "Mark as Claimed" in the messaging thread, selecting that user
   - Item moves to `pending_pickup` state
   - Other conversation threads about this item show a banner: "This item has been claimed by another user. You'll be notified if it becomes available again."
   - Once pickup is confirmed, owner marks as `claimed` (terminal)

3. **Handling Fallthrough (Recipient Doesn't Pick Up)**:
   - Owner can "Release Claim" from the item detail page or messaging thread
   - Item returns to `unclaimed` state and reappears in the giveaway feed
   - All users who previously messaged about the item receive a notification: "Good news! [Item name] is available again."
   - Previous conversation threads are reactivated with a banner: "This item is available again!"

4. **Data Model Additions**:
   - `claim_status` field on Item (enum: `unclaimed`, `pending_pickup`, `claimed`)
   - `claimed_by_id` foreign key to User (nullable, set when pending_pickup or claimed)
   - `claimed_at` timestamp (nullable, set when moving to claimed state)

5. **UI Elements**:
   - In messaging thread: "Select this person as recipient" button (visible to item owner)
   - In item detail (owner view): Claim status badge, "Release Claim" button when pending
   - In item detail (non-owner view): Status indicator showing if claimed or available
   - In conversation list: Visual indicator for conversations about claimed items

### Edge Cases Addressed

| Scenario | Behavior |
|----------|----------|
| Multiple interested users | All can message; owner picks one; others see "claimed" banner |
| Selected user doesn't respond | Owner can "Release Claim" to make item available again |
| Owner wants to try different recipient | Release claim, then select from another conversation |
| Item given away successfully | Mark as `claimed`; item removed from feed; conversations archived |
| Owner changes mind about giving away | Can delete the giveaway item entirely, or convert back to loan item |

## Implementation Notes

### Visibility Field Values

- `giveaway_visibility = 'default'`: Item visible only to users in the owner's circles (same as regular loan items)
- `giveaway_visibility = 'public'`: Item visible to all users, regardless of circle membership

### Database Migration

Will need migration to add to `item` table:
- `is_giveaway` (Boolean, default False, not null)
- `giveaway_visibility` (String(20), nullable) - values: `'default'` or `'public'`
- `claim_status` (String(20), nullable) - values: `'unclaimed'`, `'pending_pickup'`, `'claimed'`
- `claimed_by_id` (UUID FK to users.id, nullable)
- `claimed_at` (DateTime, nullable) - timestamp when item moved to `claimed` state

### Pending Pickup Implementation

The `pending_pickup` state represents the period between when an owner selects a recipient and when the item is actually handed off:

**Database fields involved:**
- `claim_status = 'pending_pickup'`
- `claimed_by_id` = UUID of the selected recipient
- `claimed_at` = NULL (only set when finalized to `claimed`)

**State transitions:**
```
unclaimed ──[owner selects recipient]──> pending_pickup ──[owner confirms handoff]──> claimed
    ^                                          │
    └────────[owner releases claim]────────────┘
```

**Routes needed for claim management:**
- `POST /item/<item_id>/select-recipient` - Owner selects a user as recipient (from messaging context)
- `POST /item/<item_id>/confirm-claim` - Owner confirms successful handoff
- `POST /item/<item_id>/release-claim` - Owner releases the pending claim

**Validation rules:**
- Only giveaway items (`is_giveaway=True`) can have claim status set
- Only item owner can change claim status
- Can only select recipient from users who have messaged about this item
- Cannot select yourself as recipient
- `pending_pickup` → `claimed` transition sets `claimed_at` timestamp
- `pending_pickup` → `unclaimed` transition clears `claimed_by_id`

### Search/Filter Logic

When filtering by item type:
- `loans`: `is_giveaway = False`
- `giveaways`: `is_giveaway = True AND claim_status = 'unclaimed'`
- `both`: All available items (loans + unclaimed giveaways)
