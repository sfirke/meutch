# Changelog

Stay up on what's happening with Meutch. Improvements are constantly pushed to the main instance at https://meutch.com - this lets you know what changed since the last time you logged in.

## Mar 2026

### Features

**Major**
- Implement an activity feed for the home page ([#259](https://github.com/sfirke/meutch/pull/259)).
- Overhaul user's view of own profile ([#228](https://github.com/sfirke/meutch/pull/228)).
- Improve search capabilities and combine search into the home page (now "Find") ([#251](https://github.com/sfirke/meutch/pull/251)).
- Introduce a social-style activity homepage for logged-in users, move item discovery to a dedicated Find page, and redirect legacy Giveaways/Requests feed routes to Home ([#259](https://github.com/sfirke/meutch/pull/259)).

**Minor**
- Hide pending-pickup claimed giveaways from view of users other than owner and recipient, create item-unavailable page, improve formatting of rehomed item ([#215](https://github.com/sfirke/meutch/pull/215)).
- Add search bar for own items ([#252](https://github.com/sfirke/meutch/pull/252)).
- Requests feed now defaults to an "All" view that combines public requests and shared-circle requests, keeps a "My Circles" filter, and defaults new requests to public visibility ([#255](https://github.com/sfirke/meutch/pull/255)).
- Make all text adjacent to a radio button or checkbox tappable ([#263](https://github.com/sfirke/meutch/pull/263)).
- Improve conversation view about an item (image formatting, say "pending pickup" instead of "borrowed") ([#264](https://github.com/sfirke/meutch/pull/264)).
- Fix unread message badge alignment on mobile and desktop for clarity ([#265](https://github.com/sfirke/meutch/pull/265)).
- DRY the new-user no-circle empty state across Home and Find, remove duplicate join-circle prompt on Find, and improve Circle discovery UX (default 25-mile filter, membership-first ordering after distance filter, private circles included in browse results, unlisted search moved lower, and member facepiles on circle results) ([#268](https://github.com/sfirke/meutch/pull/268)).
- Refactor circles to use `circle_type` (`open`/`closed`/`secret`) as the single behavior source, replacing legacy visibility labels (`public`/`private`/`unlisted`) and removing `requires_approval` usage in app logic.

### Bug Fixes
- Fix: submitting a borrow request without a message now correctly shows an inline validation error instead of silently doing nothing on mobile browsers ([#213](https://github.com/sfirke/meutch/issues/213)).
- Fix: users without location set now can't create public giveaways or requests ([#231](https://github.com/sfirke/meutch/issues/231)). 
- Fix: pending private-circle join approvals no longer count as unread messages; circles pending badge remains the admin signal, and already-handled join requests can no longer be re-processed by another admin.

## Feb 2026

### Features

### Fixes


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
