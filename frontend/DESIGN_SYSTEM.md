# Basketball Brawl design system

Home is the reference implementation for the permanent frontend system. New and migrated pages should reuse the tokens in `src/styles.css` and the primitives in `src/components/Layout.jsx` before adding page-specific styles.

## Visual direction

Basketball Brawl is a modern sports editorial and league-information site. Data, team marks, results, and strong numerical typography provide the visual interest. The hierarchy is always page → section → card → content. Sections organize the story; cards visibly contain meaningful modules. Individual rows and small statistics are not separate cards.

## Color

- Brand orange: `--color-brand: #ea580c`; hover/strong orange: `--color-brand-strong: #c2410c`; pale brand tint: `--color-brand-soft: #fff1e8`.
- Ink: `--color-ink: #171717`; secondary ink: `--color-ink-muted: #66615c`; inverse ink: white.
- Page background: `--color-page: #f4f3f1`, a very light neutral warm gray.
- Card/surface: `--color-surface: #ffffff`; subdued surface: `--color-surface-muted: #faf9f7`.
- Borders: `--color-border: #d8d5d1`; strong dividers: `--color-border-strong: #aaa49d`.
- Achievement gold: `--color-gold: #a36f08`; pale gold: `--color-gold-soft: #fff8df`. Gold is reserved for winners, champions, and MVPs.
- Semantic danger uses `--color-danger: #b42318`. Green is not a brand color and should appear only when a future data meaning specifically requires it.

## Type

Typography is controlled in one place through `--font-family-base` and `--font-family-heading` in `src/styles.css`. Both currently use the same local system-font stack, but they remain separate tokens so body and display typography can be tested independently later. Do not hardcode another font stack in component or page CSS, and do not add an external font dependency without an explicit design decision.

Body copy is 1rem/1.55. Labels and metadata are 0.75–0.8125rem with deliberate tracking. Page headings use 2–2.75rem, section headings 1.25–1.5rem, and card headings 0.75rem uppercase. Scores and fantasy points use bold tabular numerals. Avoid display copy or marketing subtitles.

## Dimensions and spacing

- Maximum page width: `--page-max: 1180px`.
- Mobile page gutter: `--space-page-mobile: 16px` (12px at widths below 360px).
- Desktop page gutter: `--space-page-desktop: 32px`.
- Card padding: 16px mobile, 20–24px desktop.
- Card gap: 16px mobile, 20px desktop.
- Major section spacing: 40px mobile, 56px desktop.
- Radius: `--radius-card: 11px`; small controls/modules: `--radius-small: 7px`.
- Shadows are normally absent. Borders create containment; `--shadow-card` is available only as a nearly imperceptible lift.

## Breakpoints

- Base/mobile: 0–719px.
- Standard desktop/tablet: 720px and above.
- Wide editorial layout: 960px and above.
- Compact phone adjustment: below 360px. The supported checks are 390px and 320px.

## Page and section treatment

`PageShell` owns the shared width and gutters. `PageHeader` is compact, left aligned, and separated from the first section by whitespace rather than a hero panel. `Section` uses a bold editorial title, right-aligned metadata when space permits, and an orange rule. Sections contain one or more cards; cards never replace section hierarchy.

## Card treatment

`Card` and `TableCard` use a white surface, subtle neutral 1px border, 11px radius, and consistent padding. Related rows sit together inside one card with internal dividers. Avoid cards inside cards and avoid separate cards for tiny metrics.

## Layout density

### Home page

- Home is the one page where a denser editorial layout is encouraged.
- Complementary cards may sit side by side, with a maximum of two content cards in one row.
- Never place three or more content cards across in one row.
- Mobile stacks cards naturally into one column.

### All other pages

- Default to a wide-form, vertically stacked layout.
- Major cards and tables should generally span the main content width.
- Do not turn Team Stats, Historical H2H, Record Book, or future detail pages into dense dashboard grids.
- Side-by-side content is the exception and should be used only when the content is very small and clearly benefits from pairing.
- Shared layout primitives do not create multi-column grids. A page must opt into any exceptional pairing explicitly.

## Tables

Tables live inside `TableCard`. Headers use the muted surface, uppercase compact labels, and a strong bottom divider. Rows use comfortable but dense padding and light dividers. Team identity stays left aligned; records, scores, and stats use right-aligned tabular numerals. At small widths, purpose-built stacked rows may replace a table without removing information. No page-level horizontal scrolling is allowed.

## Navigation

The masthead uses dark ink with a 3px orange identity rule. The Basketball Brawl mark and active destination use orange. Desktop navigation is inline at 720px and above; mobile uses the existing accessible menu button and stacked menu. Unavailable destinations remain visually quiet and non-interactive. Do not promote Power Rankings until its migration is explicitly scheduled.

## Achievement treatment

Champions and MVPs use gold text/borders on the pale gold surface. Gold is never used for ordinary selected or active UI; those states use orange. A champion label is text-first and restrained rather than a decorative badge.

## Responsive rules

- Editorial two-column layouts collapse to one column below 720px.
- Cards use nearly the full viewport width and reduce padding below 360px.
- Important numbers retain size and align right; names may wrap safely.
- Tables either remain readable within their card or switch to the existing complete mobile-row presentation. Do not hide useful columns simply to avoid responsive work.
- Team logos retain fixed dimensions and never distort.
- Navigation returns to the mobile menu below 720px.
- Test at desktop, 390px, and 320px; `document.documentElement.scrollWidth` must not exceed the viewport width.
