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

Giveaways use a formal claiming system with explicit interest tracking to avoid email spam and give owners flexible recipient selection:

1. **Claim States on Item**:
   - `unclaimed` - Item is available (default for giveaways)
   - `pending_pickup` - Owner has selected a recipient, awaiting pickup
   - `claimed` - Item has been successfully given away (terminal state)

2. **Interest Expression**:
   - Users express interest via a dedicated "I Want This" button on the item detail page
   - Optional message field: "Why do you want this item?" (helps owner decide)
   - This creates a `GiveawayInterest` record, separate from general messaging
   - Users can still send messages to ask questions without joining the interest pool
   - Interest is explicit and clean - no conflation with casual inquiries

3. **Initial Recipient Selection Workflow**:
   - Owner views item detail page and sees: "🎁 This giveaway has 7 interested users"
   - Owner clicks "View & Select Recipient" to see selection page
   - Selection page shows all interested users with:
     - Name and timestamp ("requested 2 hours ago")
     - Their optional message/reason
     - Radio button to select manually
   - Owner has three selection options:
     - **Manual Selection**: Pick specific person (maybe they had best story)
     - **First Requester**: Award to earliest interested user (chronological fairness)
     - **Random**: Unbiased random selection from pool
   - Once selected, item moves to `pending_pickup` state
   - System creates single notification message to selected recipient: "You've been selected for [item name]!"
   - **No emails sent to non-selected users** - they remain in pool with status "pending owner review"

4. **Handling Fallthrough (Recipient Doesn't Pick Up)**:
   - Owner has two options from item detail page:
   
   **Option A: Direct Reassignment (No Spam)**
   - Owner clicks "Change Recipient" 
   - System shows selection page again with:
     - Previous recipient grayed out: "Previously selected, did not pick up"
     - Three reassignment options:
       - **Next in Line**: Award to next earliest requester (fair queue)
       - **Random from Remaining**: Random selection excluding previous recipient
       - **Manual Selection**: Pick specific person from remaining pool
   - System updates `claimed_by_id` to new recipient (no state change, still `pending_pickup`)
   - System sends single notification to newly selected recipient only
   - **No emails to anyone else** - they stay in pool, no false hope
   
   **Option B: Open to All (Restart)**
   - Owner clicks "Release to Everyone"
   - Item returns to `unclaimed` state and reappears in giveaway feed
   - All existing interest records remain `active` - users stay in the pool
   - **No notifications sent** - users see item reappear naturally in feed; their prior interest still stands
   - Use this when owner wants to give more time, reconsider, or try with same pool again

5. **Data Model Additions**:

   **Item model fields:**
   - `claim_status` field on Item (enum: `unclaimed`, `pending_pickup`, `claimed`)
   - `claimed_by_id` foreign key to User (nullable, set when pending_pickup or claimed)
   - `claimed_at` timestamp (nullable, set when moving to claimed state)
   
   **New GiveawayInterest model:**
   - `id` - UUID primary key
   - `item_id` - UUID FK to items (nullable=False)
   - `user_id` - UUID FK to users (nullable=False, ondelete='CASCADE')
   - `created_at` - DateTime (for chronological ordering)
   - `message` - Text (nullable, optional "why I want this" message)
   - `status` - String(20) (values: `active`, `selected`, `passed_over`)
   - Unique constraint on (item_id, user_id) - one interest per user per item

**Available Flag Synchronization**: The existing `Item.available` flag will be automatically synchronized with `claim_status` for giveaway items:
   - When `claim_status` changes to `pending_pickup` or `claimed`, set `available = False`
   - When `claim_status` changes to `unclaimed`, set `available = True`
   - This synchronization will be implemented in the model using SQLAlchemy events or in the route handlers that change claim status
   - For regular loan items, `available` continues to work as before (toggled when loans are approved/returned)
   - This ensures giveaways don't appear in item lists once claimed, consistent with the existing loan behavior

6. **UI Elements**:
   
   **Item detail page (non-owner, giveaway is unclaimed):**
   - Prominent "I Want This!" button
   - Optional text field: "Why do you want this item?" (helps owner decide)
   - If user already expressed interest: "✓ You've expressed interest. Owner will contact you if selected."
   - Message form still available below for questions separate from claiming
   
   **Item detail page (owner view, has interested users):**
   - Badge: "🎁 This giveaway has 7 interested users"
   - Button: "View & Select Recipient" (when unclaimed)
   - Badge: "⏳ Pending pickup by [username]" (when pending_pickup)
   - Buttons: "Change Recipient" | "Release to Everyone" | "Confirm Handoff Complete" (when pending)
   - Badge: "✅ Claimed" (when claimed, with timestamp)
   
   **Recipient selection page (/item/<id>/select-recipient):**
   - List of interested users with radio buttons
   - Each shows: name, timestamp, optional message
   - Action buttons at bottom: "Select First Requester" | "Random" | "Confirm Manual Selection"
   
   **Item detail page (non-owner, giveaway is pending_pickup by someone else):**
   - Banner: "This item has been claimed by another user. You'll be notified if it becomes available again."
   - Interest expression and message form disabled/hidden
### Database Migration

Will need migration to add to `item` table and create new `giveaway_interest` table:

**Item table additions:**
- `is_giveaway` (Boolean, default False, not null, with `server_default='false'`)
- `giveaway_visibility` (String(20), nullable) - values: `'default'` or `'public'`
- `claim_status` (String(20), nullable) - values: `'unclaimed'`, `'pending_pickup'`, `'claimed'`
- `claimed_by_id` (UUID FK to users.id, nullable, with `ondelete='SET NULL'`)
- `claimed_at` (DateTime, nullable) - timestamp when item moved to `claimed` state

**New giveaway_interest table:**
- `id` (UUID, primary key)
- `item_id` (UUID FK to items.id, nullable=False, with `ondelete='CASCADE'`)
- `user_id` (UUID FK to users.id, nullable=False, with `ondelete='CASCADE'`)
- `created_at` (DateTime, default=now, for chronological ordering)
- `message` (Text, nullable, optional "why I want this" message from user)
- `status` (String(20), default='active', values: `'active'`, `'selected'`, `'passed_over'`)
- Unique constraint on (item_id, user_id)

**Complete Migration Specifications**:
```python
def upgrade():
    # Create giveaway_interest table
    op.create_table(
        'giveaway_interest',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('item_id', UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.ForeignKeyConstraint(['item_id'], ['item.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('item_id', 'user_id', name='uq_giveaway_interest_item_user')
    )
    
    # Create indexes on giveaway_interest table
    op.create_index('ix_giveaway_interest_item_id', 'giveaway_interest', ['item_id'])
    op.create_index('ix_giveaway_interest_user_id', 'giveaway_interest', ['user_id'])
    op.create_index('ix_giveaway_interest_status', 'giveaway_interest', ['status'])
    
    # Add giveaway fields to item table
    with op.batch_alter_table('item', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_giveaway', sa.Boolean(), nullable=False, server_default='false'))
        batch_op.add_column(sa.Column('giveaway_visibility', sa.String(20), nullable=True))
        batch_op.add_column(sa.Column('claim_status', sa.String(20), nullable=True))
        batch_op.add_column(sa.Column('claimed_by_id', UUID(as_uuid=True), nullable=True))
        batch_op.add_column(sa.Column('claimed_at', sa.DateTime(), nullable=True))
        
        # Add foreign key constraint with SET NULL on delete
        batch_op.create_foreign_key(
            'fk_item_claimed_by_user',
            'users',
            ['claimed_by_id'],
            ['id'],
            ondelete='SET NULL'
        )
    
    # Create indexes on item table for query performance
    op.create_index('ix_item_is_giveaway', 'item', ['is_giveaway'])
    op.create_index('ix_item_claim_status', 'item', ['claim_status'])
    op.create_index('ix_item_claimed_by_id', 'item', ['claimed_by_id'])

def downgrade():
    # Drop indexes on item table
    op.drop_index('ix_item_claimed_by_id', table_name='item')
    op.drop_index('ix_item_claim_status', table_name='item')
    op.drop_index('ix_item_is_giveaway', table_name='item')
    
    # Remove giveaway fields from item table
    with op.batch_alter_table('item', schema=None) as batch_op:
        batch_op.drop_constraint('fk_item_claimed_by_user', type_='foreignkey')
        batch_op.drop_column('claimed_at')
        batch_op.drop_column('claimed_by_id')
        batch_op.drop_column('claim_status')
        batch_op.drop_column('giveaway_visibility')
        batch_op.drop_column('is_giveaway')
    
    # Drop indexes on giveaway_interest table
    op.drop_index('ix_giveaway_interest_status', table_name='giveaway_interest')
    op.drop_index('ix_giveaway_interest_user_id', table_name='giveaway_interest')
    op.drop_index('ix_giveaway_interest_item_id', table_name='giveaway_interest')
    
    # Drop giveaway_interest table
    op.drop_table('giveaway_interest')
```

**Index Rationale**:
- `ix_item_is_giveaway`: Speeds up queries filtering giveaways vs loans (used in search, browse, feed)
- `ix_item_claim_status`: Enables fast filtering of unclaimed giveaways for the giveaway feed
- `ix_item_claimed_by_id`: Supports queries finding items claimed by a specific user (for profile views)
- `ix_giveaway_interest_item_id`: Fast lookup of all interested users for an item (recipient selection page)
- `ix_giveaway_interest_user_id`: Fast lookup of all items a user has expressed interest in (user profile)
- `ix_giveaway_interest_status`: Filter active vs selected vs passed_over interests

**ON DELETE Behaviors**:
- `item.claimed_by_id` → `SET NULL`: If user who claimed item deletes account, `claimed_by_id` becomes NULL but item remains marked as claimed (via `claim_status` and `claimed_at`), preserving data integrity
- `giveaway_interest.item_id` → `CASCADE`: If item is deleted, all interest records are automatically removed
- `giveaway_interest.user_id` → `CASCADE`: If user deletes account, all their interest records are automatically removed
            'users',
            ['claimed_by_id'],
            ['id'],
            ondelete='SET NULL'
**Routes needed for claim management:**
- `GET /item/<item_id>/select-recipient` - Owner views page with list of interested users and selection options
- `POST /item/<item_id>/express-interest` - User expresses interest in giveaway (creates GiveawayInterest record)
- `DELETE /item/<item_id>/withdraw-interest` - User withdraws their interest
- `POST /item/<item_id>/select-recipient` - Owner selects recipient (supports manual, first, or random)
  - Request body: `{"selection_method": "manual|first|random", "user_id": "<uuid>"}` (user_id only for manual)
- `POST /item/<item_id>/change-recipient` - Owner reassigns from pending_pickup (supports next, random, or manual)
  - Request body: `{"selection_method": "next|random|manual", "user_id": "<uuid>"}` (user_id only for manual)
- `POST /item/<item_id>/release-to-all` - Owner releases claim and notifies entire interest pool
- `POST /item/<item_id>/confirm-handoff` - Owner confirms successful handoff (pending_pickup → claimed)

**Validation rules:**
- Only giveaway items (`is_giveaway=True`) can have claim status set
- Only item owner can change claim status or view interested users
- Only non-owners can express interest in a giveaway
- Cannot express interest in own items or already-claimed items
- Can only select recipient from users who have active GiveawayInterest records
- `pending_pickup` → `claimed` transition sets `claimed_at` timestamp
- `pending_pickup` → `unclaimed` (via release-to-all) clears `claimed_by_id` and notifies pool
- Direct reassignment keeps `pending_pickup` status but updates `claimed_by_id`
    with op.batch_alter_table('item', schema=None) as batch_op:
        batch_op.drop_constraint('fk_item_claimed_by_user', type_='foreignkey')
        batch_op.drop_column('claimed_at')
        batch_op.drop_column('claimed_by_id')
        batch_op.drop_column('claim_status')
        batch_op.drop_column('giveaway_visibility')
        batch_op.drop_column('is_giveaway')
```

**Index Rationale**:
- `ix_item_is_giveaway`: Speeds up queries filtering giveaways vs loans (used in search, browse, feed)
- `ix_item_claim_status`: Enables fast filtering of unclaimed giveaways for the giveaway feed
- `ix_item_claimed_by_id`: Supports queries finding items claimed by a specific user (for profile views)

**ON DELETE SET NULL Behavior**:
Follows existing pattern from `b065c9d9d718` migration where user references are nullable to handle account deletion. If a user who claimed an item deletes their account, `claimed_by_id` becomes NULL but the item remains marked as claimed (via `claim_status` and `claimed_at`), preserving data integrity.

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

## Implementation Checklist

## Testing Considerations

Key test scenarios to implement:

**Interest Expression:**
1. User can express interest in unclaimed giveaway with optional message
2. User cannot express interest in own giveaway
3. User cannot express interest twice (unique constraint enforced)
4. User can withdraw interest before selection
5. Expressing interest in claimed giveaway shows appropriate error

**Recipient Selection (Initial):**
6. Owner can view list of interested users with timestamps and messages
7. Manual selection creates Message notification to selected user only
8. "First requester" selects user with earliest `created_at` timestamp
9. "Random" selection works and is deterministic in tests (seeded random)
10. Selection transitions item to `pending_pickup` and sets `claimed_by_id`
11. Non-selected users remain in pool with no notifications

**Recipient Reassignment:**
12. Owner can reassign from pending_pickup without spamming pool
13. "Next in line" selects next earliest user (excluding previous recipient)
14. "Random from remaining" excludes previous recipient
15. Reassignment updates `claimed_by_id` but keeps `pending_pickup` status
16. Only newly selected user receives notification
17. Previous recipient status updated to `passed_over` in GiveawayInterest

**Release to All:**
18. "Release to everyone" transitions to `unclaimed` and clears `claimed_by_id`
19. Existing interest pool remains `active` with no notifications sent
20. Item reappears in giveaway feed with same interested users

**Handoff Completion:**
21. Owner can confirm handoff (pending_pickup → claimed)
22. Confirmation sets `claimed_at` timestamp
23. Claimed items have `available=False` and don't appear in feeds
24. Claimed items show terminal status badge

**Data Integrity:**
25. `claimed_by_id` becomes NULL when claiming user deletes account (SET NULL)
26. GiveawayInterest records CASCADE delete when item deleted
27. GiveawayInterest records CASCADE delete when user deletes account
28. `available` flag synchronizes with `claim_status` correctly

**Search and Filtering:**
29. Search/browse with `item_type=giveaways` shows only `is_giveaway=True AND claim_status='unclaimed'`
30. Search/browse with `item_type=loans` shows only `is_giveaway=False`
31. Search/browse with `item_type=both` shows loans + unclaimed giveaways
32. Giveaway feed filters by claim_status and respects visibility (default vs public)

**Email Notifications:**
33. Interest expression does not send email (no spam)
34. Recipient selection sends single email to selected user
35. Reassignment sends single email to newly selected user
36. Release-to-all does not send notifications (users stay in pool, item reappears in feed)
37. Failed email sends are logged but don't block the operation
## Testing Considerations
Key test scenarios to implement:
1. Verify giveaway items with `claim_status='pending_pickup'` have `available=False`
2. Verify release claim notifications go to all unique previous messengers (excluding owner and previous recipient)
3. Confirm `claimed_by_id` becomes NULL when claiming user deletes their account
4. Test search/browse filters correctly distinguish loans vs unclaimed giveaways vs claimed giveaways
5. Test claim workflow state transitions (unclaimed → pending_pickup → claimed, and release claim flow)
5. Test search/browse filters correctly distinguish loans vs unclaimed giveaways vs claimed giveaways
