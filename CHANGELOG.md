# Changelog

Stay up on what's happening with Meutch. Improvements are constantly pushed to the main instance at https://meutch.com - this lets you know what changed since the last time you logged in.

## July 2026

### Features
**Major**:
- Refactor messages infrastructure to create conversations, enabling archiving of messages and an overhaul of the inbox with pagination, sorting, and bulk actions to mark-read and archive:
  - Revised database schema in ([#436](https://github.com/sfirke/meutch/pull/436))
  - New inbox backend functionality in ([#438](https://github.com/sfirke/meutch/pull/438)).
  - Frontend changes to finish the work in ([#439](https://github.com/sfirke/meutch/pull/439)).

**Minor**:
- Improved the giveaway request and handoff experience - no more needing to click "I want this!", instead owners can choose from anyone who messages. Also allows for marking giveaways handed off outside of Meutch ([#445](https://github.com/sfirke/meutch/pull/445)).
- On the View Circle page, show the members 20/page instead of all at once ([#433](https://github.com/sfirke/meutch/pull/433)).

### Developer Experience
- Remove legacy `item`/`request`/`circle` kwargs from `MessageFactory`; all test call sites now use `conversation=` directly via `ConversationFactory` ([#437](https://github.com/sfirke/meutch/pull/437)).

### Bug fixes
- Streamlined email digest fulfilled/claimed rendering: unified phrasing across both resolution variants, replaced green status pills with a subtle gray "New" label for items the user hasn't seen before, kept descriptions only for first-time items, and grouped new-resolved entries before previously-seen resolutions ([#427](https://github.com/sfirke/meutch/pull/427)).
- Improve formatting of buttons, especially on mobile, for the circle admin interface as well as site admin and item detail card ([#434](https://github.com/sfirke/meutch/pull/434)).

## June 2026

### Features
**Minor**:
- Added a Privacy Policy and Terms & Conditions, linked from the site footer ([#421](https://github.com/sfirke/meutch/pull/421)).
- Community Activity now hides claimed giveaways by default and includes a filter to show them when desired ([#372](https://github.com/sfirke/meutch/issues/372)).
- Make it the default to view one's own activity in feed, add a toggle to disable if desired ([#414](https://github.com/sfirke/meutch/pull/414)).
- New members who have not joined any circles yet are now redirected into circle discovery after login, with a stronger onboarding prompt and personalized recommendations that preview what each suggested circle would unlock ([#395](https://github.com/sfirke/meutch/pull/395)).
- Introduced "regional" circles that are stand-ins for e.g., a Craigslist region. Admins promote these circles to official regional status, at which point they get pinned at the top of zero-circle onboarding recommendations ([#400](https://github.com/sfirke/meutch/pull/400)).
- Improve workflow for marking a request fulfilled, showing the button in every location where the user might want to take that action ([#431](https://github.com/sfirke/meutch/pull/431)).

### Bug fixes
- Claimed giveaways no longer show a "Borrowed" status badge in the conversation "Item Status" card — they now correctly display "Rehomed" ([#398](https://github.com/sfirke/meutch/pull/398)).
- Can no longer edit a fulfilled giveaway ([#406](https://github.com/sfirke/meutch/pull/406)).
- Clicking "View Loan" on My Activity page now takes you to the current loan, not the first time the item was loaned (affected both borrowers and lenders) ([#410](https://github.com/sfirke/meutch/pull/410)).

### API development (continued)
- Add API loan activity reads and loan actions, including active borrowing/lending views plus loan request, approve/deny, cancel, complete, and extend endpoints ([#393](https://github.com/sfirke/meutch/pull/393)).
- Add API giveaway-interest reads and giveaway actions, including owner-side interest management, express/withdraw interest, recipient select/change, release-to-all, and confirm-handoff endpoints([#405](https://github.com/sfirke/meutch/pull/405)).
- Harden the API for production with request-level throttles on auth and write endpoints, rollout controls for full-disable and read-only modes, request-id correlation headers, JSON `429`/`500` handling, and deployment guidance for shared limiter storage. ([#407](https://github.com/sfirke/meutch/pull/407)).

## May 2026

### Features

**Minor**:
- Profiles, loan-request conversations, and giveaway requester views now show the circles you have in common with the other user, with linked circle badges for quick context and an explicit empty state when a giveaway requester shares no circles with you ([#345](https://github.com/sfirke/meutch/pull/345)).
- Digest emails now surface fulfilled requests and claimed giveaways, including clear labels when an item is both created and resolved within the same digest window ([#339](https://github.com/sfirke/meutch/pull/339)).
- Admin panel now separates user management from analytics, with a new Monthly Active Users chart that tracks qualifying activity from January 2026 onward ([#342](https://github.com/sfirke/meutch/pull/342)).
- Address entry forms now use Canada-friendly "State/Province" and "Postal Code" wording, plus country dropdowns that put the United States of America and Canada first while keeping the existing geocoding flow ([#362](https://github.com/sfirke/meutch/pull/362)).
- Registration now lands on a clearer email-confirmation guidance page that explains the next step, keeps resend as a secondary action until it is needed, routes unconfirmed logins back into the same flow, and offers a start-over path for mistyped email addresses ([#390](https://github.com/sfirke/meutch/pull/390)).

### Bug fixes
- Geocoding now sends structured address components to Nominatim and retries without the postal code when that field blocks an otherwise valid street-level match ([#362](https://github.com/sfirke/meutch/pull/362)).
- Public giveaways from user without circles now appear in home feed and digest, consistent with how requests are treated ([#369](https://github.com/sfirke/meutch/pull/369)).
- Fixes to block block dual-item creation: adopt idempotency token, disable form submission button ([#377](https://github.com/sfirke/meutch/pull/377)).
- Delete item modal is no longer grayed out and untouchable when deleting an item from profile page (fixes #376) ([#377](https://github.com/sfirke/meutch/pull/377)).


### Developer Experience
- Massive refactor that split `routes.py` into many views and pushed the app logic down into a new service layer ([#352](https://github.com/sfirke/meutch/pull/352)).
- Align local pre-push linting with CI by sharing the same branch-diff `pre-commit` runner and documenting the diff-scoped command ([#339](https://github.com/sfirke/meutch/pull/339)).

### API development
- Add initial `app/api/v1` scaffolding, bootstrap JSON endpoints, and an API design document to prepare for a mobile client ([#354](https://github.com/sfirke/meutch/pull/354)).
- Extract auth, profile, location, and account-setting workflows into reusable services so the web layer and upcoming API can share the same business logic ([#355](https://github.com/sfirke/meutch/pull/355)).
- Extract shared read-side query helpers for item discovery, messaging inboxes/threads, request visibility, and circle browse/detail views so future API endpoints can reuse the web app's visibility and pagination rules ([#358](https://github.com/sfirke/meutch/pull/358)).
- Extract shared write-side logic into service layer ([#360](https://github.com/sfirke/meutch/pull/360)).
- Add the first reusable API foundation layer: structured JSON error handling, shared pagination helpers, and Marshmallow boundary schemas for upcoming read endpoints ([#361](https://github.com/sfirke/meutch/pull/361)).
- Add JWT-backed `/api/v1/auth` endpoints with access/refresh tokens, refresh rotation and revocation, current-user identity, and mobile-facing register/reset workflows ([#363](https://github.com/sfirke/meutch/pull/363)).
- Add read-only API endpoints with some minor related refactoring ([#370](https://github.com/sfirke/meutch/pull/370)).
- Add foundation for API writes ([#374](https://github.com/sfirke/meutch/pull/374)).
- Add API mutation parity for user profile/settings/location/acct deletion ([#382](https://github.com/sfirke/meutch/pull/382)).
- Add API mutation parity for requests/messages ([#384](https://github.com/sfirke/meutch/pull/384)).
- Add API mutation parity for circles, including create/edit flows, join-request actions, leave/delete behavior, and admin/member management ([#385](https://github.com/sfirke/meutch/pull/385)).
- Add API mutation parity for items, including item create/edit/delete flows, image upload/reorder/delete endpoints, and shared giveaway-versus-loan invariant enforcement ([#391](https://github.com/sfirke/meutch/pull/391)).

## Apr 2026

### Features

**Major**
- Allow users to upload up to eight images per item listed, with associated enhancements ([#316](https://github.com/sfirke/meutch/pull/316)).

**Minor**
- `share/` pages get the aesthetic and the "how/why" content from the main landing page ([#323](https://github.com/sfirke/meutch/pull/323)).
- Surface giveaway actions in the owner-recipient conversation, both for recipient assignment and handoff confirmation. Also add item deletion modal that stops pending-pickup items and active loans from being deleted ([#329](https://github.com/sfirke/meutch/pull/329)).

### Bug fixes
- Items can no longer be converted to giveaways while they still have pending or approved loan requests ([#334](https://github.com/sfirke/meutch/pull/334)).
- Giveaways can no longer be converted back into loan items once people have expressed interest, pickup is pending, or the handoff is complete ([#335](https://github.com/sfirke/meutch/pull/335)).
- Fix section stretch on request giveaway screen ([#336](https://github.com/sfirke/meutch/pull/336)).
- Hide loan extension button from pending loan, improve redirect after extending loan ([#337](https://github.com/sfirke/meutch/pull/337)).


### Developer Experience
- Seeded loan data now includes messages, `./dev-start seed` can run when alembic table is missing/hasn't been initialized yet ([#307](https://github.com/sfirke/meutch/pull/307)).
- Add shared `pre-commit` linting with `ruff` and `pylint --errors-only`, plus GitHub PR enforcement for the same hooks ([#338](https://github.com/sfirke/meutch/pull/338)).

## Mar 2026

### Features

**Major**
- Implement an activity feed for the home page, replacing Giveaways and Requests dedicated pages ([#259](https://github.com/sfirke/meutch/pull/259)).
- Overhaul user's view of own profile ([#228](https://github.com/sfirke/meutch/pull/228)).
- Improve search capabilities and combine search into the home page (now "Find") ([#251](https://github.com/sfirke/meutch/pull/251)).
- Add configurable email digest system (daily/weekly/none), including signup/profile/admin controls, digest content based on feed activity, and shared daily scheduler integration with loan reminder job ([#280](https://github.com/sfirke/meutch/pull/280)).
- Add owner-generated 30-day share links for regular items, including anonymous preview pages and token-backed borrow requests for recipients outside the owner's circles ([#294](https://github.com/sfirke/meutch/pull/294)).
- Convert unauthenticated landing page to a modern vertical long-scrolling page ([#298](https://github.com/sfirke/meutch/pull/298)).

**Minor**
- Hide pending-pickup claimed giveaways from view of users other than owner and recipient, create item-unavailable page, improve formatting of rehomed item ([#215](https://github.com/sfirke/meutch/pull/215)).
- Add search bar for own items ([#252](https://github.com/sfirke/meutch/pull/252)).
- Requests feed now defaults to an "All" view that combines public requests and shared-circle requests, keeps a "My Circles" filter, and defaults new requests to public visibility ([#255](https://github.com/sfirke/meutch/pull/255)).
- Make all text adjacent to a radio button or checkbox tappable ([#263](https://github.com/sfirke/meutch/pull/263)).
- Improve conversation view about an item (image formatting, say "pending pickup" instead of "borrowed") ([#264](https://github.com/sfirke/meutch/pull/264)).
- Fix unread message badge alignment on mobile and desktop for clarity ([#265](https://github.com/sfirke/meutch/pull/265)).
- DRY the new-user no-circle empty state across Home and Find, remove duplicate join-circle prompt on Find, and improve Circle discovery UX (default 25-mile filter, membership-first ordering after distance filter, private circles included in browse results, unlisted search moved lower, and member facepiles on circle results) ([#268](https://github.com/sfirke/meutch/pull/268)).
- Refactor circles to use `circle_type` (`open`/`closed`/`secret`) as the single behavior source, replacing legacy visibility labels (`public`/`private`/`unlisted`) ([#271](https://github.com/sfirke/meutch/pull/271)).
- Show distance (if available) to giveaways and requests on activity feed ([#275](https://github.com/sfirke/meutch/pull/275)).
- Add button to sort items on Find page by distance or date created ([#276](https://github.com/sfirke/meutch/pull/276)).
- Increase prominence of "Create" floating action button on mobile ([#296](https://github.com/sfirke/meutch/pull/296)).
- Show distances in buckets, e.g., "2-5 mi" instead of "2.4 mi" to improve user privacy ([#302](https://github.com/sfirke/meutch/pull/302)).
- Make loan activity easier to find: add "View Loan" button to item cards and item detail page, restructure My Activity tab to combine item thumbnail and name into one clear link with a dedicated "View Loan" action button that links to the conversation ([#304](https://github.com/sfirke/meutch/pull/304)).

### Bug Fixes
- Fix: submitting a borrow request without a message now correctly shows an inline validation error instead of silently doing nothing on mobile browsers ([#213](https://github.com/sfirke/meutch/pull/213)).
- Fix: users without location set now can't create public giveaways or requests ([#231](https://github.com/sfirke/meutch/pull/231)).
- Fix: pending private-circle join approvals no longer count as unread messages; circles pending badge remains the admin signal, and already-handled join requests can no longer be re-processed by another admin ([#257](https://github.com/sfirke/meutch/pull/257)).
- Fix: hide members of a closed circle from being viewable in search results ([#273](https://github.com/sfirke/meutch/pull/273)).
- Fix: consolidate digest display/change UI in the admin panel to eliminate scrollbar ([#291](https://github.com/sfirke/meutch/pull/291)).
- Fix: if no unread messages in conversation, retain focus on action buttons instead of scrolling to bottom ([#141](https://github.com/sfirke/meutch/pull/141)).
- Fix: improve formatting of image and banner in giveaay item details ([#300](https://github.com/sfirke/meutch/pull/300)).
- Fix XSS in list-item flash message ([#303](https://github.com/sfirke/meutch/pull/303)).

### Developer Experience
- Add hash-based cache-busting for CSS and JS static files so browsers always load the latest styles and scripts after a deploy ([#230](https://github.com/sfirke/meutch/pull/230)).

## Feb 2026

### Features

**Major**
- Implement user requests ([#192](https://github.com/sfirke/meutch/pull/192))
- Add "vacation mode" toggle to user profile ([#147](https://github.com/sfirke/meutch/pull/147)). When enabled, it hides user's items from being discovered (existing loans persist).
- Photo processing improvements: rotate, crop, zoom for uploaded photos; shared `notifications.js` for re-usable toast behavior ([#164](https://github.com/sfirke/meutch/pull/164)).
- Add shareable links for public giveaways, requests, and circles (both public and private) with rich link previews for social media and SMS, including entity images and metadata. ([#196](https://github.com/sfirke/meutch/pull/196)).

**Minor**
- Show the full image for an item (letterboxing as needed) by changing CSS attributes. Images are no longer arbitrarily cropped ([#171](https://github.com/sfirke/meutch/pull/171))
- Add Open Graph and Twitter Card meta tags for link preview support ([#144](https://github.com/sfirke/meutch/pull/144)) — Link previews now include title, description, and image for better sharing on social and SMS.
- Add drag & drop support for image uploads ([#143](https://github.com/sfirke/meutch/pull/143)) — Desktop users can drag images onto upload fields; accessibility and validation included.
- Add mobile keyboard auto-capitalization for item title fields ([#163](https://github.com/sfirke/meutch/pull/163)).
- Add opt-in "Remember this device for 30 days" at login with explicit secure cookie/session policy defaults for better sign-in persistence.

### Fixes
- The admin panel no longer freezes on page load - there had been an infinite JavaScript loop ([#170](https://github.com/sfirke/meutch/pull/170))
- Speed up creation of seed data by caching hashed passwords ([#167](https://github.com/sfirke/meutch/pull/167)).
- Edit item form submit button now says "Save" instead of "List Item" for better clarity on the edit action.
- Making a claim request on a giveaway now triggers a email message and in-app notification to the item owner. Circle join requests + the decision reply messages now appear as in-app messages in addition to emails ([#205](https://github.com/sfirke/meutch/pull/205)).
- Item detail images now keep their full height on mobile instead of being constrained to a cropped-looking 300px frame([#221](https://github.com/sfirke/meutch/pull/221)).
- Add a custom 404 page ([#218](https://github.com/sfirke/meutch/pull/218)) and CSRFError handler([#220](https://github.com/sfirke/meutch/pull/220)).
- No longer include original filename on images ([#219](https://github.com/sfirke/meutch/pull/219)).
- After registration, users are redirected to the email-confirmation guidance page instead of the login page (since unconfirmed accounts cannot sign in yet). A `?next=` URL present at registration is saved and restored after email confirmation, so users who follow a share link and register are returned to that page once they log in.([#232](https://github.com/sfirke/meutch/pull/232), [#240](https://github.com/sfirke/meutch/pull/240)).
- Make giveaway cards easier to distinguish from loans by using a diagonal FREE ribbon in feed/search item cards ([#223](https://github.com/sfirke/meutch/pull/223)).

### Developer Experience
- Add manual testing overrides for scheduled email job (`flask check-loan-reminders`) so developers can repeatedly test digest and loan reminder email flows without waiting for natural cadence windows.
- Create separate dev (sample data) vs. test databases so they stop stepping on each others' toes ([#206](https://github.com/sfirke/meutch/pull/206)).

## Jan 2026

- Giveaways feature (grouped work across multiple PRs): core features and recipient selection, UI & timezone handling, notification emails, and homepage showcasing ([#124](https://github.com/sfirke/meutch/pull/124), [#126](https://github.com/sfirke/meutch/pull/126), [#135](https://github.com/sfirke/meutch/pull/135), [#138](https://github.com/sfirke/meutch/pull/138), [#139](https://github.com/sfirke/meutch/pull/139)) — Full giveaway workflow, recipient management, timezone handling, and homepage display of public giveaways.
- Footer navigation improvements: better wording and links ("How it Works") ([#152](https://github.com/sfirke/meutch/pull/152)).
- Add PR size labeler GitHub Action to help reviewers quickly see PR size ([#153](https://github.com/sfirke/meutch/pull/153)).
- Speed up tests via session-scoped fixtures and cleanup improvements ([#134](https://github.com/sfirke/meutch/pull/134)).
- Remove deprecated `search_circles` route ([#131](https://github.com/sfirke/meutch/pull/131)).
- Fix: users should not be able to browse another user's item list from their profile ([#133](https://github.com/sfirke/meutch/pull/133)).
- Fix: category field retained when editing items ([#130](https://github.com/sfirke/meutch/pull/130)).
- Fix URL in `README.md` ([#122](https://github.com/sfirke/meutch/pull/122)).
