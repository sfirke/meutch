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
   - Owner views item detail page and sees: "This giveaway has 7 interested users"
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
   - Use this when owner wants to give more time or reconsider

5. **Data Model Additions**:

   **Item model fields:**
   - `claim_status` field on Item (enum: `unclaimed`, `pending_pickup`, `claimed`)
   - `claimed_by_id` foreign key to User (nullable, set when status is `pending_pickup` or `claimed`)
   - `claimed_at` timestamp (nullable, **ONLY set when handoff is confirmed** via `pending_pickup` → `claimed` transition; remains NULL during `pending_pickup`)
   
   **New GiveawayInterest model:**
   - `id` - UUID primary key
   - `item_id` - UUID FK to items (nullable=False)
   - `user_id` - UUID FK to users (nullable=False, ondelete='CASCADE')
   - `created_at` - DateTime (for chronological ordering)
   - `message` - Text (nullable, optional "why I want this" message)
   - `status` - String(20) (values: `active`, `selected`; default='active')
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
   - Banner: "This item has been claimed by another user."
   - Interest expression and message form disabled/hidden

### Database Migration

Will need migration to add to `item` table and create new `giveaway_interest` table:

**Item table additions:**
- `is_giveaway` (Boolean, default False, not null, with `server_default='false'`)
- `giveaway_visibility` (String(20), nullable) - values: `'default'` or `'public'`
- `claim_status` (String(20), nullable) - values: `'unclaimed'`, `'pending_pickup'`, `'claimed'`
- `claimed_by_id` (UUID FK to users.id, nullable, with `ondelete='SET NULL'`)
- `claimed_at` (DateTime, nullable) - **ONLY set on handoff confirmation** (`pending_pickup` → `claimed`); NULL during selection/pending states

**New giveaway_interest table:**
- `id` (UUID, primary key)
- `item_id` (UUID FK to items.id, nullable=False, with `ondelete='CASCADE'`)
- `user_id` (UUID FK to users.id, nullable=False, with `ondelete='CASCADE'`)
- `created_at` (DateTime, default=now, for chronological ordering)
- `message` (Text, nullable, optional "why I want this" message from user)
- `status` (String(20), default='active', values: `'active'`, `'selected'`)
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
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),  # 'active' or 'selected'
        sa.ForeignKeyConstraint(['item_id'], ['item.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('item_id', 'user_id', name='uq_giveaway_interest_item_user')
    )

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

def downgrade():
    # Remove giveaway fields from item table
    with op.batch_alter_table('item', schema=None) as batch_op:
        batch_op.drop_constraint('fk_item_claimed_by_user', type_='foreignkey')
        batch_op.drop_column('claimed_at')
        batch_op.drop_column('claimed_by_id')
        batch_op.drop_column('claim_status')
        batch_op.drop_column('giveaway_visibility')
        batch_op.drop_column('is_giveaway')
    
    # Drop giveaway_interest table
    op.drop_table('giveaway_interest')
```


**ON DELETE Behaviors**:
- `item.claimed_by_id` → `SET NULL`: If user who claimed item deletes account, `claimed_by_id` becomes NULL but item remains marked as claimed (via `claim_status` and `claimed_at` timestamp), preserving data integrity
- `giveaway_interest.item_id` → `CASCADE`: If item is deleted, all interest records are automatically removed
- `giveaway_interest.user_id` → `CASCADE`: If user deletes account, all their interest records are automatically removed

### Routes and API Endpoints

**Routes needed for claim management:**
- `GET /item/<item_id>/select-recipient` - Owner views page with list of interested users and selection options
- `POST /item/<item_id>/express-interest` - User expresses interest in giveaway (creates GiveawayInterest record)
- `DELETE /item/<item_id>/withdraw-interest` - User withdraws their interest
- `POST /item/<item_id>/select-recipient` - Owner selects recipient (supports manual, first, or random)
  - Request body: `{"selection_method": "manual|first|random", "user_id": "<uuid>"}` (user_id only for manual)
- `POST /item/<item_id>/change-recipient` - Owner reassigns from pending_pickup (supports next, random, or manual)
  - Request body: `{"selection_method": "next|random|manual", "user_id": "<uuid>"}` (user_id only for manual)
- `POST /item/<item_id>/release-to-all` - Owner releases claim back to unclaimed (no notifications sent)
- `POST /item/<item_id>/confirm-handoff` - Owner confirms successful handoff (pending_pickup → claimed)

**Validation rules:**
- Only giveaway items (`is_giveaway=True`) can have claim status set
- Only item owner can change claim status or view interested users
- Cannot express interest in own items or items in `claimed` status
- Cannot express interest twice in same item (unique constraint enforced)
- Can only select recipient from users who have active GiveawayInterest records
- **`pending_pickup` → `claimed` transition sets `claimed_at` to current timestamp**
- `pending_pickup` → `unclaimed` (via release-to-all) clears `claimed_by_id` and keeps `claimed_at` as NULL
- Direct reassignment (change-recipient) keeps `pending_pickup` status, updates `claimed_by_id`, and keeps `claimed_at` as NULL

**State transitions:**
```
unclaimed ──[owner selects recipient]──> pending_pickup ──[owner confirms handoff]──> claimed
    ^                                          │
    └───────────[owner releases claim]─────────┘
```

### Search/Filter Logic

When filtering by item type:
- `loans`: `is_giveaway = False`
- `giveaways`: `is_giveaway = True AND claim_status = 'unclaimed'`
- `both`: All available items (loans + unclaimed giveaways)

## Implementation Checklist

This feature is broken down into **4 sequential PRs** for incremental review and deployment. Each PR is independently deployable and delivers meaningful value.

---

## PR #1: Database Schema & Basic Models (Foundation)

**Goal:** Establish database foundation without UI/behavior changes. All new columns are nullable or have safe defaults, so existing features remain unaffected.

**Estimated Size:** ~150-200 lines of code

### Phase 1: Database Foundation
- [ ] **Migration: Add giveaway fields to Item model**
  - [ ] Create migration file with complete specifications (see "Complete Migration Specifications" above)
  - [ ] Add `is_giveaway` boolean column (default False, not null)
  - [ ] Add `giveaway_visibility` string column (nullable)
  - [ ] Add `claim_status` string column (nullable, values: unclaimed/pending_pickup/claimed)
  - [ ] Add `claimed_by_id` UUID FK column (nullable, ondelete='SET NULL')
  - [ ] Add `claimed_at` datetime column (nullable, only set on handoff confirmation)
  - [ ] Run migration: `flask db migrate -m "Add giveaway fields to Item model"`
  - [ ] Review auto-generated migration file, adjust if needed
  - [ ] Apply migration: `flask db upgrade`
  - [ ] Verify columns exist: `psql $DATABASE_URL -c "\d item"`

- [ ] **Migration: Create GiveawayInterest model**
  - [ ] Create `giveaway_interest` table with id, item_id, user_id, created_at, message, status
  - [ ] Add CASCADE foreign keys for item_id and user_id
  - [ ] Add unique constraint on (item_id, user_id)
  - [ ] Run migration: `flask db migrate -m "Create GiveawayInterest table"`
  - [ ] Apply migration: `flask db upgrade`
  - [ ] Verify table exists: `psql $DATABASE_URL -c "\d giveaway_interest"`

- [ ] **Model: Add GiveawayInterest to app/models.py**
  - [ ] Define GiveawayInterest class with all columns
  - [ ] Add relationship to Item model: `giveaway_interests = db.relationship('GiveawayInterest', ...)`
  - [ ] Add relationship to User model: `giveaway_interests = db.relationship('GiveawayInterest', ...)`
  - [ ] Add `__repr__` method for debugging

- [ ] **Model: Update Item model**
  - [ ] Add `is_giveaway`, `giveaway_visibility`, `claim_status`, `claimed_by_id`, `claimed_at` columns
  - [ ] Add `claimed_by` relationship to User
  - [ ] **Optional**: Add SQLAlchemy event listener or property setter to sync `available` flag with `claim_status`
  - [ ] Document `claimed_at` behavior in docstring: "Only set when handoff confirmed (pending_pickup → claimed)"

- [ ] **Write unit tests for models**
  - [ ] Test GiveawayInterest creation and unique constraint
  - [ ] Test Item giveaway fields and relationships
  - [ ] Test CASCADE delete behaviors (item deletion, user deletion)
  - [ ] Test SET NULL behavior for claimed_by_id
  - [ ] Test `claimed_at` is NULL during pending_pickup, set only on claimed
  - [ ] Run tests: `./run_tests.sh -u`

---

## PR #2: Item Creation, Giveaway Feed & Search Filtering

**Goal:** Users can create and browse giveaways. Provides complete vertical slice: create → list → browse → search. No claiming logic yet, but users can message owners using existing functionality.

**Estimated Size:** ~400-500 lines of code

### Phase 2: Item Creation & Basic Forms
- [ ] **Forms: Add giveaway fields to ItemForm in app/forms.py**
  - [ ] Add `is_giveaway` BooleanField with label "This is a giveaway (free item)"
  - [ ] Add `giveaway_visibility` RadioField with choices: ('default', 'Circles only'), ('public', 'Public')
  - [ ] Add custom validator: require giveaway_visibility when is_giveaway=True
  - [ ] Add unit tests for form validation

- [ ] **Template: Update list_item.html**
  - [ ] Add checkbox for is_giveaway with helpful description
  - [ ] Add conditional radio buttons for giveaway_visibility (shown when checkbox checked)
  - [ ] Add JavaScript to show/hide visibility options based on checkbox state
  - [ ] Style as user-friendly with clear labels

- [ ] **Routes: Update list_item() in app/main/routes.py**
  - [ ] Handle is_giveaway and giveaway_visibility from form
  - [ ] Set claim_status='unclaimed' when is_giveaway=True
  - [ ] Save new item with giveaway fields
  - [ ] Test manually: create giveaway item through web UI

- [ ] **Routes: Update edit_item() in app/main/routes.py**
  - [ ] Allow editing is_giveaway and giveaway_visibility
  - [ ] Prevent changing is_giveaway if item has active GiveawayInterest records
  - [ ] Test manually: edit existing item to/from giveaway status

- [ ] **Write integration tests for item creation/editing**
  - [ ] Test creating giveaway with visibility options
  - [ ] Test editing giveaway fields
  - [ ] Test validation (giveaway requires visibility)
  - [ ] Run tests: `./run_tests.sh -i`

### Phase 3: Giveaway Feed & Display
- [ ] **Template: Create item_card.html partial (if not exists)**
  - [ ] Extract item card HTML into reusable partial
  - [ ] Add "FREE" badge for giveaways (conditional on is_giveaway)
  - [ ] Show claim_status badge if item is pending_pickup or claimed

- [ ] **Template: Create giveaways.html**
  - [ ] Create feed page with sort controls (distance, date)
  - [ ] Add optional distance filter (within X miles)
  - [ ] Use pagination (same as search/browse)
  - [ ] Show only unclaimed giveaways respecting visibility rules

- [ ] **Routes: Add /giveaways route in app/main/routes.py**
  - [ ] Query items where is_giveaway=True AND claim_status='unclaimed' (or NULL for legacy items)
  - [ ] Apply circle visibility filtering (default vs public)
  - [ ] Implement distance-based sorting (use existing geocoding utils)
  - [ ] Implement date sorting (created_at DESC)
  - [ ] Add pagination (12 items per page)
  - [ ] Test manually: visit /giveaways and verify items appear

- [ ] **Navigation: Add "Giveaways" link to navbar**
  - [ ] Update base template to include Giveaways link in main nav
  - [ ] Style consistently with other nav links
  - [ ] Test on mobile (responsive design)

- [ ] **Write functional tests for giveaway feed**
  - [ ] Test giveaways page loads and shows unclaimed items
  - [ ] Test sorting by distance and date
  - [ ] Test visibility filtering (circles vs public)
  - [ ] Test pagination
  - [ ] Run tests: `./run_tests.sh -f`

### Phase 4: Search & Browse Filtering
- [ ] **Routes: Add item_type filter to search()**
  - [ ] Accept item_type query param (values: loans, giveaways, both; default: both)
  - [ ] Filter query based on item_type
  - [ ] Update search template with filter dropdown

- [ ] **Routes: Add item_type filter to category_items()**
  - [ ] Accept item_type query param
  - [ ] Filter by category AND item_type
  - [ ] Update category template with filter dropdown

- [ ] **Routes: Add item_type filter to tag_items()**
  - [ ] Accept item_type query param
  - [ ] Filter by tag AND item_type
  - [ ] Update tag template with filter dropdown

- [ ] **Templates: Add item_type filter UI**
  - [ ] Add dropdown to search_items.html: "Show: All | Loans | Giveaways"
  - [ ] Add dropdown to category pages
  - [ ] Add dropdown to tag pages
  - [ ] Use URL params to preserve filter across pagination

- [ ] **Write integration tests for filtering**
  - [ ] Test search with item_type=loans shows only loans
  - [ ] Test search with item_type=giveaways shows only unclaimed giveaways
  - [ ] Test search with item_type=both shows both
  - [ ] Test category/tag filtering with item_type
  - [ ] Run tests: `./run_tests.sh -i`

---

## PR #3: Interest Expression & Recipient Selection (Core Claiming Logic)

**Goal:** Complete the "happy path" claiming workflow. Users can now express interest and owners can select recipients.

**Estimated Size:** ~400-500 lines of code

### Phase 5: Interest Expression
- [ ] **Routes: POST /item/<id>/express-interest**
  - [ ] Create route to handle interest expression
  - [ ] Validate: user is logged in, item is giveaway, item is unclaimed, user is not owner
  - [ ] Create GiveawayInterest record with optional message
  - [ ] Handle unique constraint violation (already expressed interest)
  - [ ] Return success JSON or redirect to item detail

- [ ] **Routes: DELETE /item/<id>/withdraw-interest**
  - [ ] Create route to withdraw interest
  - [ ] Validate: user owns the interest record
  - [ ] Delete GiveawayInterest record
  - [ ] Return success JSON or redirect

- [ ] **Template: Update item_detail.html for non-owners**
  - [ ] Show "I Want This!" button when giveaway is unclaimed
  - [ ] Add optional textarea: "Why do you want this item?"
  - [ ] If user already expressed interest, show confirmation message
  - [ ] Add "Withdraw Interest" button if user already interested
  - [ ] Hide interest UI if giveaway is pending_pickup or claimed

- [ ] **Write integration tests for interest expression**
  - [ ] Test expressing interest creates GiveawayInterest record
  - [ ] Test cannot express interest in own item
  - [ ] Test cannot express interest twice (unique constraint)
  - [ ] Test withdrawing interest deletes record
  - [ ] Test cannot express interest in claimed item
  - [ ] Run tests: `./run_tests.sh -i`

### Phase 6: Recipient Selection (Initial)
- [ ] **Routes: GET /item/<id>/select-recipient**
  - [ ] Create route for owner to view interested users
  - [ ] Validate: user is item owner, item is giveaway, item is unclaimed
  - [ ] Query all GiveawayInterest records for item (status='active'), ordered by created_at
  - [ ] Render selection template with user list

- [ ] **Template: Create select_recipient.html**
  - [ ] Show list of interested users with name, timestamp, message
  - [ ] Add radio buttons for manual selection
  - [ ] Add action buttons: "Select First Requester" | "Random" | "Confirm Manual Selection"
  - [ ] Style as clean, easy-to-use interface

- [ ] **Routes: POST /item/<id>/select-recipient**
  - [ ] Accept selection_method (manual, first, random) and optional user_id
  - [ ] Validate: user is owner, item is unclaimed, selected user has active interest
  - [ ] Implement "first" logic: select earliest created_at
  - [ ] Implement "random" logic: random.choice from active interests
  - [ ] Implement "manual" logic: use provided user_id
  - [ ] Update item: set claim_status='pending_pickup', claimed_by_id=selected_user_id
  - [ ] Keep claimed_at as NULL (not set until handoff confirmed)
  - [ ] Set `available=False` to hide from feeds
  - [ ] Create Message notification to selected user
  - [ ] **Do not send emails to non-selected users**
  - [ ] Redirect to item detail page

- [ ] **Template: Update item_detail.html for owners**
  - [ ] Show "🎁 This giveaway has X interested users" badge when unclaimed
  - [ ] Show "View & Select Recipient" button when unclaimed and has interests
  - [ ] Show "⏳ Pending pickup by [username]" badge when pending_pickup
  - [ ] Show action buttons when pending: "Change Recipient" | "Release to Everyone" | "Confirm Handoff Complete"

- [ ] **Write integration tests for recipient selection**
  - [ ] Test owner can view interested users
  - [ ] Test "first requester" selects earliest user
  - [ ] Test "random" selection (use seeded random for determinism)
  - [ ] Test manual selection works
  - [ ] Test selection transitions to pending_pickup
  - [ ] Test claimed_by_id is set, claimed_at remains NULL
  - [ ] Test available flag becomes False
  - [ ] Test Message notification is created
  - [ ] Test non-selected users remain in pool
  - [ ] Run tests: `./run_tests.sh -i`

---

## PR #4: Reassignment, Release, and Edge Cases (Fallthrough Handling)

**Goal:** Handle all edge cases and fallthrough scenarios. Completes the claiming workflow with all state transitions.

**Estimated Size:** ~400-500 lines of code

### Phase 7: Recipient Reassignment
- [ ] **Routes: POST /item/<id>/change-recipient**
  - [ ] Accept selection_method (next, random, manual) and optional user_id
  - [ ] Validate: user is owner, item is pending_pickup
  - [ ] Get previous claimed_by_id (to exclude from next selection)
  - [ ] Implement "next" logic: select earliest created_at excluding previous recipient
  - [ ] Implement "random" logic: random.choice excluding previous recipient
  - [ ] Implement "manual" logic: use provided user_id
  - [ ] Update claimed_by_id to new recipient (keep pending_pickup status)
  - [ ] Keep claimed_at as NULL
  - [ ] Create Message notification to newly selected user only
  - [ ] **Do not notify non-selected users**
  - [ ] Redirect to item detail page

- [ ] **Template: Update select_recipient.html for reassignment**
  - [ ] Show previous recipient as grayed out: "Previously selected, did not pick up"
  - [ ] Show action buttons: "Next in Line" | "Random from Remaining" | "Confirm Manual Selection"
  - [ ] Reuse same template, just adjust button labels and logic based on claim_status

- [ ] **Write integration tests for reassignment**
  - [ ] Test "next in line" excludes previous recipient
  - [ ] Test "random from remaining" excludes previous recipient
  - [ ] Test manual reassignment works
  - [ ] Test reassignment keeps pending_pickup status
  - [ ] Test claimed_at remains NULL
  - [ ] Test only new recipient gets notification
  - [ ] Test previous recipient remains in pool with active status
  - [ ] Run tests: `./run_tests.sh -i`

### Phase 8: Release to All & Handoff Confirmation
- [ ] **Routes: POST /item/<id>/release-to-all**
  - [ ] Validate: user is owner, item is pending_pickup
  - [ ] Update item: set claim_status='unclaimed', claimed_by_id=NULL
  - [ ] Keep claimed_at as NULL
  - [ ] Set `available=True` to show in feeds again
  - [ ] **Do not send any notifications** (users see item reappear naturally)
  - [ ] All existing GiveawayInterest records remain active
  - [ ] Redirect to item detail page

- [ ] **Routes: POST /item/<id>/confirm-handoff**
  - [ ] Validate: user is owner, item is pending_pickup
  - [ ] Update item: set claim_status='claimed', claimed_at=current_timestamp
  - [ ] Keep claimed_by_id unchanged
  - [ ] Set `available=False` (should already be False, but enforce)
  - [ ] Redirect to item detail page with success message

- [ ] **Template: Update item_detail.html for claimed state**
  - [ ] Show "✅ Claimed" badge when claim_status='claimed'
  - [ ] Show "Given to [username] on [date]" message using claimed_at timestamp
  - [ ] Hide all action buttons (terminal state)

- [ ] **Write integration tests**
  - [ ] Test release-to-all returns to unclaimed state
  - [ ] Test release-to-all clears claimed_by_id and keeps claimed_at as NULL
  - [ ] Test release-to-all sets available=True
  - [ ] Test release-to-all sends no notifications
  - [ ] Test confirm-handoff transitions to claimed
  - [ ] Test confirm-handoff sets claimed_at to current time
  - [ ] Test claimed items don't appear in feeds (available=False)
  - [ ] Run tests: `./run_tests.sh -i`

### Phase 9: Item Detail Page Updates
- [ ] **Template: Update item_detail.html for giveaways**
  - [ ] Hide loan request functionality when is_giveaway=True
  - [ ] Show different CTA based on claim_status:
    - unclaimed: "I Want This!" button
    - pending_pickup (non-owner): "This item has been claimed by another user"
    - claimed: "✅ Claimed on [date]"
  - [ ] Keep message form available for questions (separate from interest expression)
  - [ ] Show owner controls when user is owner

- [ ] **Write functional tests for item detail page**
  - [ ] Test giveaway shows correct UI for unclaimed state
  - [ ] Test giveaway shows correct UI for pending_pickup state
  - [ ] Test giveaway shows correct UI for claimed state
  - [ ] Test owner sees management controls
  - [ ] Test non-owner sees interest expression controls
  - [ ] Run tests: `./run_tests.sh -f`

### Phase 10: Data Integrity & Edge Cases
- [ ] **Model: Add available flag synchronization**
  - [ ] Implement automatic available flag sync in Item model or route handlers
  - [ ] When claim_status changes to pending_pickup or claimed, set available=False
  - [ ] When claim_status changes to unclaimed, set available=True
  - [ ] Test synchronization in unit tests

- [ ] **Routes: Add validation helpers**
  - [ ] Create decorator or helper to validate giveaway operations
  - [ ] Ensure only owners can manage claim status
  - [ ] Ensure only giveaways can have claim status operations
  - [ ] Ensure proper state transitions

- [ ] **Write data integrity tests**
  - [ ] Test claimed_by_id becomes NULL when user deletes account (SET NULL)
  - [ ] Test GiveawayInterest CASCADE deletes when item deleted
  - [ ] Test GiveawayInterest CASCADE deletes when user deleted
  - [ ] Test available flag synchronizes with claim_status
  - [ ] Test cannot transition from claimed back to other states
  - [ ] Run tests: `./run_tests.sh -u`

### Phase 11: Email Notifications (Optional - Can be separate PR #5)
- [ ] **Email: Create templates**
  - [ ] Create email template for "You've been selected for [item name]!"
  - [ ] Include item details, owner contact info, pickup instructions
  - [ ] Add link to item detail page

- [ ] **Email: Integrate with recipient selection**
  - [ ] Send email when recipient selected (initial selection)
  - [ ] Send email when recipient changed (reassignment)
  - [ ] **Do not send email on interest expression**
  - [ ] **Do not send email on release-to-all**
  - [ ] Log email failures but don't block operations

- [ ] **Write email tests**
  - [ ] Test email sent on recipient selection
  - [ ] Test email sent on reassignment
  - [ ] Test no email sent on interest expression
  - [ ] Test no email sent on release-to-all
  - [ ] Test email failure doesn't block operation
  - [ ] Run tests: `./run_tests.sh -i`

### Phase 12: Polish & Documentation (Optional - Can be separate PR #5 or #6)
- [ ] **UI Polish**
  - [ ] Add icons and badges for giveaways across site
  - [ ] Ensure responsive design on mobile
  - [ ] Add helpful tooltips and descriptions
  - [ ] Test accessibility (keyboard navigation, screen readers)

- [ ] **Documentation**
  - [ ] Update README with giveaways feature description
  - [ ] Document new routes in API docs (if applicable)
  - [ ] Add inline code comments for complex logic

- [ ] **Final Testing**
  - [ ] Run full test suite: `./run_tests.sh -c`
  - [ ] Manual end-to-end testing of complete workflows:
    - Create giveaway → express interest → select recipient → confirm handoff
    - Create giveaway → express interest → select recipient → reassign → confirm
    - Create giveaway → express interest → select recipient → release to all → reselect
  - [ ] Test all edge cases manually
  - [ ] Verify no regressions in loan functionality

### Phase 13: Deployment Preparation (Done during each PR merge)
- [ ] **Database Migration Review**
  - [ ] Review all migration files for production safety
  - [ ] Test migration on staging database
  - [ ] Document rollback procedures

- [ ] **Production Checklist**
  - [ ] Backup database before deploying
  - [ ] Run migrations: `flask db upgrade`
  - [ ] Monitor for errors post-deployment
  - [ ] Test critical workflows in production

---

## PR Summary

### PR #1: Database Schema & Basic Models
- **Phases:** 1
- **Files Changed:** `app/models.py`, `migrations/versions/xxx_add_giveaways.py`, `tests/unit/test_models.py`
- **Deliverable:** Database foundation with no UI changes
- **Risks:** Low (new columns are nullable/have defaults)

### PR #2: Item Creation, Giveaway Feed & Search Filtering  
- **Phases:** 2, 3, 4
- **Files Changed:** `app/forms.py`, `app/main/routes.py`, `app/templates/main/list_item.html`, `app/templates/main/giveaways.html`, `app/templates/main/item_card.html`, `app/templates/base.html`, search/category/tag templates, integration/functional tests
- **Deliverable:** Users can create and browse giveaways
- **Risks:** Low (no claiming logic, uses existing messaging)

### PR #3: Interest Expression & Recipient Selection
- **Phases:** 5, 6, 9 (partial)
- **Files Changed:** `app/main/routes.py` (new routes), `app/templates/main/item_detail.html`, `app/templates/main/select_recipient.html`, integration tests
- **Deliverable:** Complete "happy path" claiming workflow
- **Risks:** Medium (new claiming logic, but well-tested)

### PR #4: Reassignment, Release, and Edge Cases
- **Phases:** 7, 8, 9 (completion), 10
- **Files Changed:** `app/main/routes.py` (additional routes), `app/templates/main/item_detail.html`, `app/templates/main/select_recipient.html`, integration/unit tests
- **Deliverable:** Robust claiming with fallthrough handling
- **Risks:** Low (enhancements to existing claiming logic)

### PR #5: Email Notifications, Polish & Deployment
- **Phases:** 11, 12, 13
- **Files Changed:** Email templates, notification logic, documentation, deployment checklist
- **Deliverable:** Email notifications to selected recipients, UI polish, documentation, production validation
- **Risks:** Low (notifications integrate with existing email system)
- **Status:** **Required for feature completion**

---


**Progress Tracking:**
- **PR #1** (Database Foundation): 0/4 major tasks
- **PR #2** (Item Creation & Feed): 0/13 major tasks
- **PR #3** (Core Claiming): 0/9 major tasks
- **PR #4** (Edge Cases): 0/10 major tasks
- **PR #5** (Notifications, Polish & Deployment): 0/9 major tasks

**Total: 0/45 tasks complete**


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
17. Previous recipient remains in pool with `active` status (no status change needed)

**Release to All:**
18. "Release to everyone" transitions to `unclaimed` and clears `claimed_by_id`
19. Existing interest pool remains `active` with no notifications sent
20. Item reappears in giveaway feed with same interested users

**Handoff Completion:**
21. Owner can confirm handoff (pending_pickup → claimed)
22. Confirmation sets `claimed_at` to current timestamp (not set during pending_pickup)
24. Claimed items have `available=False` and don't appear in feeds
25. Claimed items show terminal status badge with claimed_at date

**Data Integrity:**
25. `claimed_by_id` becomes NULL when claiming user deletes account (SET NULL)
26. `claim_status` and `claimed_at` remain intact when claiming user deletes account (preserves history)
27. GiveawayInterest records CASCADE delete when item deleted
28. GiveawayInterest records CASCADE delete when user deletes account
29. `available` flag synchronizes with `claim_status` correctly

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
