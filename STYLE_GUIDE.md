# Meutch style guide

Meutch looks like cut paper and running stitch. The flat shapes and black
outlines come from the logo. The stitch comes from visible mending, which is what
sharing and repair have in common. Follow this guide when adding or changing any
page, so the site stays consistent without a designer reviewing every change.

The personality is warm, neighborly and a little playful. It should never feel
childish or careless, because people are trusting Meutch to connect them with
each other.

This guide describes where the site is headed, and the site is being moved to it
over several pull requests, so some pages don't match it yet. New work should follow the guide as far as it
can without making a page look out of place next to its neighbors.

## Colors

Use the CSS variables, not hex values. Don't add a new color without adding it
here first.

| Variable | Value | Job |
|---|---|---|
| `--ink` | `#1d2a2e` | Text, outlines, active states |
| `--paper` | `#fff9ef` | Page background |
| `--card-paper` | `#ffffff` | Cards, inputs, menus |
| `--line` | `#e7dcc5` | Quiet borders on cards and lists |
| `--muted` | `#5b6a6e` | Secondary text |
| `--teal` | `#4fd1c7` | Primary actions, "do something" |
| `--teal-deep` | `#0f5f5c` | Links and teal text on light backgrounds, small info badges |
| `--teal-wash` | `#dcf5f1` | Hover, unread and selected backgrounds |
| `--tangerine` | `#f6ad55` | Requests, stitches, landing hero |
| `--tangerine-wash` | `#fdeeda` | Soft orange sections |
| `--purple` | `#6d5698` | Unread counts and other new-activity markers, avatar and accent color |
| `--purple-wash` | `#ece6f5` | Soft purple backgrounds |
| `--emerald` | `#198754` | Giveaways |
| `--danger` | `#9d2b2b` | Errors, overdue loans, delete actions. Use it rarely, and only for these |
| `--danger-wash` | `#fee6e3` | Error message backgrounds |

Teal and tangerine are the exact logo colors. Keep them that way. Purple is a screen
match for Pantone 18-3737 TCX Passion Flower.

Purple is friendly and means "something new." It never means something went wrong.
That's what `--danger` is for.

### Contrast

- **Text on teal or tangerine is always `--ink`, never white.** White on teal is
  1.9:1. Ink on teal is about 8:1.
- **Text on `--purple`, `--emerald`, `--danger`, `--teal-deep` and `--ink` fills is white.** Ink on
  purple is only 2.4:1, while white is 6.1:1.
- Don't put purple text on teal or tangerine. It's only about 3.2:1. Purple text is
  fine on white or paper.
- Bright teal is never used for text or links on a light background. Use
  `--teal-deep`.
- Normal text needs at least 4.5:1 contrast with its background.

## Type

- Headings: **Gabarito**, via `--font-display`. Change the font in that one
  variable and the Google Fonts link.
- Everything else: **Figtree**, via `--font-body`.
- Page titles are plain `--ink`. No gradients and no colored titles.
- Each page has one `h1`.

## Shape

- Buttons, inputs and menus use a 10px corner radius (`--radius`). Cards use 14px
  (`--radius-card`). Tags use 6px (`--radius-tag`).
- Pills are only for filter chips and small counts. Filter chips are multi-select,
  and a selected chip is filled with `--ink`.
- No gradients and no soft drop shadows. Where something needs lift, use a hard
  offset shadow in `--ink`, such as `4px 4px 0 var(--ink)`.

## Outlines

A black outline means an object you can press, or something deliberately set
apart, like a tag or a framed photo.

- **Buttons:** 2px `--ink` outline. Primary buttons are filled teal. Others have
  no fill. Each view gets one primary button where possible.
- **Plain content cards:** 1.5px `--line` border and no shadow.
- **Clickable cards:** the same as content cards, with an ink outline and offset
  shadow on hover only. Cards you can't click don't react to hover.

## The stitch

A running stitch is the everyday decoration. It's a dashed line, 14px on and 9px
off, 3px tall, drawn with the `--stitch` repeating gradient so the spacing stays
consistent.

- Use it between blocks of content: under the nav, above the footer, around the
  owner row on an item page.
- **Never put a stitch under words in running text or a wrapping heading.** It
  runs into the line below. To emphasize a word in a heading, use the teal paper
  strip (`.paper-strip`): a teal background on an inline-block, tilted 1 degree.
- Use no more than one or two stitches on a screen.

## The pinked edge

Where a full-width colored band meets paper, cut the edge with a zigzag, like fabric
trimmed with pinking shears. Use it for big moments such as the landing hero, the
share previews and the final call to action, not on cards, soft wash sections or
inside everyday app pages. Draw it with an SVG mask (`--pinked-down`,
`--pinked-up`) so the teeth are true triangles: 24px wide and 12px tall.

## Whimsy

Tilts of 1 to 5 degrees are allowed on tags, thumbnails, avatars, the logo tile
and the emphasis strip. Everything else stays straight.

Keep these calm and straight, with no jokes: forms, error messages, anything to
do with safety, privacy, account deletion, or a problem with a loan.

Respect `prefers-reduced-motion`. Motion is short and only responds to something
the person did.

## Words

Write the way a friendly neighbor talks. Be short and specific.

| Say | Instead of |
|---|---|
| Up for grabs (tag on a giveaway) | Free, Free!, GIVEAWAY |
| Giveaways (category or filter) | Free stuff |
| Wanted (tag on a request) | Request badge |
| Found! | Fulfilled |
| Out on loan | Borrowed |
| Rehomed | Claimed |
| Ask to borrow this | Request to Borrow |

**Don't use "free" as a label on an item.** Meutch has no prices, so everything
on it costs nothing, and calling one thing free implies that others aren't. It's
fine to describe Meutch itself as free.

## Icons

Use Font Awesome. An icon should add meaning that the words don't already give.
Leave it out of nav links, footer links and buttons whose label is already clear.

## Photos and avatars

- Item card photos fill their frame. Item pages show the whole photo.
- Photos in cards and on item pages get an ink outline.
- People without a photo get initials on a colored circle with an ink outline.
  Initials are the first letters of the first and last names.

## Building pages

- Use an existing component in `app/templates/components/` before writing new
  markup. Don't wrap buttons, badges, alerts or cards in macros, because their
  shared CSS classes already do that job. Anything used only once stays where it
  is until a second use appears.
- Use the variables and shared classes in `app/static/css/style.css`. Avoid inline
  `style` attributes and new `!important` rules.
- Restyle Bootstrap through its `--bs-*` variables where it has one.
- Unread counts use `.bg-purple`. Don't add Bootstrap's `shadow` classes, which draw
  soft shadows.
- A card with one destination should be clickable as a whole, using a stretched
  link. Other links inside it, such as a person's name or a link in a description,
  must sit above the stretched link so they still work.
- Check every change at phone and desktop widths.
