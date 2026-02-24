# Changelog

Stay up on what's happening with Meutch. Improvements are constantly pushed to the main instance at https://meutch.com - this lets you know what changed since the last time you logged in. 

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

### Fixes
- The admin panel no longer freezes on page load - there had been an infinite JavaScript loop ([#170](https://github.com/sfirke/meutch/pull/170))
- Speed up creation of seed data by caching hashed passwords ([#167](https://github.com/sfirke/meutch/pull/167)).
- Edit item form submit button now says "Save" instead of "List Item" for better clarity on the edit action.
- Making a claim request on a giveaway now triggers a email message and in-app notification to the item owner. Circle join requests + the decision reply messages now appear as in-app messages in addition to emails([#205](https://github.com/sfirke/meutch/pull/205)).

## Jan 2026

- Giveaways feature (grouped work across multiple PRs): core features and recipient selection, UI & timezone handling, notification emails, and homepage showcasing ([#124](https://github.com/sfirke/meutch/pull/124), [#126](https://github.com/sfirke/meutch/pull/126), [#135](https://github.com/sfirke/meutch/pull/135), [#138](https://github.com/sfirke/meutch/pull/138), [#139](https://github.com/sfirke/meutch/pull/139)) — Full giveaway workflow, recipient management, timezone handling, and homepage display of public giveaways.
- Footer navigation improvements: better wording and links ("How it Works") ([#152](https://github.com/sfirke/meutch/pull/152)).
- Add PR size labeler GitHub Action to help reviewers quickly see PR size ([#153](https://github.com/sfirke/meutch/pull/153)).
- Speed up tests via session-scoped fixtures and cleanup improvements ([#134](https://github.com/sfirke/meutch/pull/134)).
- Remove deprecated `search_circles` route ([#131](https://github.com/sfirke/meutch/pull/131)).
- Fix: users should not be able to browse another user's item list from their profile ([#133](https://github.com/sfirke/meutch/pull/133)).
- Fix: category field retained when editing items ([#130](https://github.com/sfirke/meutch/pull/130)).
- Fix URL in `README.md` ([#122](https://github.com/sfirke/meutch/pull/122)).
