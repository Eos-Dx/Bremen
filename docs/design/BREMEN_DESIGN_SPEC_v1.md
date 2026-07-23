# Bremen Design Specification v1

## Visual source of truth for the Bremen product-grade demo redesign (PR0082b).

---

## 1. Color System

### Base Colors

| Token | Hex | Usage |
|-------|-----|-------|
| `--bg-page` | `#F7F8F8` | Page background |
| `--bg-surface` | `#FFFFFF` | Card, panel, surface backgrounds |
| `--text-primary` | `#16202A` | Primary text, headings |
| `--text-secondary` | `#5B6570` | Secondary text, captions, metadata |
| `--accent` | `#1F6F6B` | Primary actions, active states, links |
| `--border` | `#E3E7E6` | Borders, dividers, rails (upcoming) |

### Status Colors

| Token | Hex | Usage |
|-------|-----|-------|
| `--status-available` | `#2E7D5B` | Completed, available, success |
| `--status-pending` | `#B8894A` | Pending, in-progress, warning |
| `--status-unconfigured` | `#9AA3A8` | Disabled, unavailable, not configured |
| `--status-error` | `#C1483D` | Error, failed, rejected |

### Tint Colors

| Token | Hex | Usage |
|-------|-----|-------|
| `--tint-accent` | `#F1F5F4` | Active stage background |
| `--tint-pending` | `#FBF3E9` | Warning/notice background |
| `--tint-error` | `#FBEEEC` | Error stage background |

### Prohibited Colors

No `#0969da`, `#1a7f37`, `#cf222e`, `#9a6700`, `#d0d7de`, `#656d76`, `#1f2328`,
or any other color outside the specification. No gradients. No pink. No rose.
No blue accent system. No GitHub palette.

---

## 2. Typography

### Font Stack

```
-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif
```

### Size Scale

| Token | Size | Weight | Usage |
|-------|------|--------|-------|
| `--fs-32` | 32px | 700 | h1, page title |
| `--fs-22` | 22px | 600 | h2, section title |
| `--fs-17` | 17px | 600 | h3, card title, primary CTA |
| `--fs-14` | 14px | 400 | Body text |
| `--fs-13` | 13px | 400 | Small, caption, secondary text |
| `--fs-11` | 11px | 400 | Tiny, identifier, monospace values |

No other font sizes. Mobile may remap to smaller approved sizes but must not
introduce new sizes.

---

## 3. Spacing Scale

| Token | Value |
|-------|-------|
| `--sp-4` | 4px |
| `--sp-8` | 8px |
| `--sp-12` | 12px |
| `--sp-16` | 16px |
| `--sp-24` | 24px |
| `--sp-32` | 32px |
| `--sp-48` | 48px |
| `--sp-64` | 64px |

No 20px, 40px, or any other spacing values.

---

## 4. Radii

| Token | Value | Usage |
|-------|-------|-------|
| `--radius-card` | 10px | Cards, panels, primary CTA on Start page |
| `--radius-pill` | 999px | Badges, pills, status indicators |

No 6px radius.

---

## 5. Shadows

Only two shadow values are allowed:

| Token | Value |
|-------|-------|
| `--shadow-card` | `0 1px 2px rgba(22,32,42,0.04)` |
| `--shadow-elevated` | `0 1px 8px rgba(22,32,42,0.03)` |

Cards use both: `0 1px 2px rgba(22,32,42,0.04), 0 1px 8px rgba(22,32,42,0.03)`

No other shadow values.

---

## 6. Status Rails

- State-bearing cards: 3px left rail (`border-left`)
- Event and history rows: 2px left rail (`border-left`)

Rail colors follow status colors:
- Upcoming: `--border` (#E3E7E6)
- Active: `--accent` (#1F6F6B)
- Completed: `--status-available` (#2E7D5B)
- Failed: `--status-error` (#C1483D)

---

## 7. Disabled State

Model-card content uses opacity reduction for disabled state.
The status rail retains full opacity. This ensures the rail color is always
visible regardless of disabled state.

---

## 8. Field/Value Gap

Minimum 16px gap between label and value columns in field/value tables.
Label column: 160px fixed width.

---

## 9. Page Layout

- Page maximum width: 1440px
- Desktop side padding: 32px
- Tablet side padding: 16px
- Mobile side padding: 12px

### Control Room Columns

- Left column: 320px fixed width
- Center column: flexible, minimum 480px
- Right column: 360px fixed width

### Job History

- Max height: 280px
- Independent scrolling
- 2px left rail on rows

### Live Events

- Empty state: fixed height 120px (not min-height)
- When events arrive: flex-grow expansion from parent flex container
- 2px left rail on event rows
- Max 200 DOM rows
- Auto-scroll with pause/follow

---

## 10. Component Specifications

### Cards

```
background: #FFFFFF
border: 1px solid #E3E7E6
border-radius: 10px
box-shadow: 0 1px 2px rgba(22,32,42,0.04), 0 1px 8px rgba(22,32,42,0.03)
```

### Primary Button

```
background: #1F6F6B
color: #FFFFFF
border-radius: 10px
padding: 12px 32px
font-weight: 600
font-size: 17px
border: none
```

Disabled primary button:
```
background: #9AA3A8
cursor: not-allowed
```

### Selected Card

```
border: 2px solid #1F6F6B
```

### Pipeline Stages

- Upcoming: rail `#E3E7E6`
- Active: rail `#1F6F6B`, background `#F1F5F4`
- Completed: rail `#2E7D5B`
- Failed: rail `#C1483D`, background `#FBEEEC`

### Decision Summary Card

```
background: #FFFFFF
border: 1px solid #E3E7E6
border-radius: 10px
box-shadow: 0 1px 2px rgba(22,32,42,0.04), 0 1px 8px rgba(22,32,42,0.03)
```

### Technical Demo Notice

```
background: #FBF3E9
border: 1px solid #B8894A
border-radius: 10px
```

---

## 11. Accessibility

- Keyboard operable model cards with radio semantics
- `role="radio"` and `role="radiogroup"` on model selection
- `aria-checked` on selected model cards
- `aria-current="true"` on selected container
- Visible 3px focus outline using `--accent` color
- Non-color status labels (text-based status in addition to color)
- `aria-live="polite"` on event feed
- `role="alert"` on decision summary
- `prefers-reduced-motion` media query
- Semantic headings (h1, h2, h3)
- Pipeline uses `<ol role="list">`
- Container list uses `<ul>`
- Event feed uses `<div role="log">`
- Field/value uses `<dl>`, `<dt>`, `<dd>`

---

## 12. Responsive Breakpoints

| Breakpoint | Layout | Padding |
|------------|--------|---------|
| >= 1440px | Three columns | 32px |
| 768-1439px | Vertical stack | 16px |
| < 768px | Vertical stack | 12px |

No horizontal overflow at any width.
