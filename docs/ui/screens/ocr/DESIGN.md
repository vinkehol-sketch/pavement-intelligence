---
name: Pavement Intelligence System
colors:
  surface: '#faf8ff'
  surface-dim: '#d9d9e4'
  surface-bright: '#faf8ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f3f3fe'
  surface-container: '#ededf8'
  surface-container-high: '#e7e7f3'
  surface-container-highest: '#e2e1ed'
  on-surface: '#191b23'
  on-surface-variant: '#434654'
  inverse-surface: '#2e3039'
  inverse-on-surface: '#f0f0fb'
  outline: '#737686'
  outline-variant: '#c3c5d7'
  surface-tint: '#1353d8'
  primary: '#003fb1'
  on-primary: '#ffffff'
  primary-container: '#1a56db'
  on-primary-container: '#d4dcff'
  inverse-primary: '#b5c4ff'
  secondary: '#555f6d'
  on-secondary: '#ffffff'
  secondary-container: '#d6e0f1'
  on-secondary-container: '#596372'
  tertiary: '#852b00'
  on-tertiary: '#ffffff'
  tertiary-container: '#ad3b00'
  on-tertiary-container: '#ffd4c5'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dbe1ff'
  primary-fixed-dim: '#b5c4ff'
  on-primary-fixed: '#00174d'
  on-primary-fixed-variant: '#003dab'
  secondary-fixed: '#d9e3f4'
  secondary-fixed-dim: '#bdc7d8'
  on-secondary-fixed: '#121c28'
  on-secondary-fixed-variant: '#3e4755'
  tertiary-fixed: '#ffdbcf'
  tertiary-fixed-dim: '#ffb59a'
  on-tertiary-fixed: '#380d00'
  on-tertiary-fixed-variant: '#802a00'
  background: '#faf8ff'
  on-background: '#191b23'
  surface-variant: '#e2e1ed'
typography:
  display-lg:
    fontFamily: Inter
    fontSize: 36px
    fontWeight: '700'
    lineHeight: 44px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.05em
  data-mono:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
    letterSpacing: -0.01em
  headline-md-mobile:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  unit: 4px
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
  gutter: 16px
  margin-mobile: 16px
  margin-desktop: 32px
  max-width: 1440px
---

## Brand & Style

The design system is engineered for precision, reliability, and high-density data visualization. It targets civil engineers, urban planners, and smart mobility operators who require a "tool-first" environment. The aesthetic is strictly professional and utilitarian, stripping away decorative elements in favor of clarity and structural integrity.

The style draws from **Modern Corporate and Systematic** movements, emphasizing a high-contrast, "Engineering Software" look. It prioritizes information hierarchy through crisp borders and a restrained palette, ensuring that technical data remains the focal point without visual fatigue. The emotional response is one of confidence, stability, and institutional trust.

## Colors

The palette is anchored by a deep **Primary Blue (#1A56DB)** used for action states and brand presence. The background utilizes a very light gray to reduce screen glare during long operational shifts, while the primary workspace surfaces are pure white to provide maximum contrast for data.

**Operational States** are strictly reserved for functional status indicators:
- **Success (Green):** System healthy, pavement within spec.
- **Warning (Yellow):** Maintenance required, threshold reached.
- **Error (Red):** Critical failure, structural damage.

Neutral tones (Grays) are used for borders, secondary text, and inactive states to maintain a sober, balanced UI.

## Typography

This design system utilizes **Inter** for its exceptional legibility in data-heavy environments. The typeface provides a neutral, systematic tone that performs well at small sizes, which is critical for labeling metrics and units.

- **Headlines:** Use SemiBold (600) for clear section identification.
- **Data Labels:** Small, uppercase labels with slightly increased letter spacing are used for table headers and metric categories.
- **Units:** Measurement units (e.g., km/h, %) should follow the value in a slightly lighter weight or smaller size to differentiate from the primary number.
- **Scaling:** On mobile devices, display sizes are capped to maintain readability within compact card structures.

## Layout & Spacing

The layout follows a **Fluid Grid** model with a 12-column structure for desktop. A 4px baseline grid ensures consistent vertical rhythm across dense technical forms and dashboards.

- **Desktop:** 12 columns with 16px gutters and 32px outer margins.
- **Tablet:** 8 columns with 16px gutters and 24px outer margins.
- **Mobile:** 4 columns with 12px gutters and 16px outer margins.

The layout philosophy emphasizes **compact density**. White space is used strategically to separate logical groups, but components are kept tight to maximize the amount of information visible on a single screen without scrolling.

## Elevation & Depth

This design system avoids heavy shadows and deep layering. Depth is communicated primarily through **Low-Contrast Outlines** and subtle tonal changes.

- **Level 0 (Background):** #F9FAFB.
- **Level 1 (Cards/Surfaces):** Pure white background with a 1px border (#E5E7EB).
- **Interactive States:** On hover, a card may transition to a subtle "Ambient Shadow" (4px blur, 2% opacity) to indicate clickability.
- **Separation:** Horizontal and vertical dividers use 1px lines in #F3F4F6 to define data rows without adding visual bulk.

## Shapes

The shape language is **Soft (0.25rem)**, providing a modern but disciplined appearance.

- **Primary Elements:** Buttons, inputs, and small cards use a 4px corner radius.
- **Containers:** Large dashboard widgets or modals use the `rounded-lg` (8px) token to soften the overall interface slightly.
- **Data Points:** Graphs and charts utilize square or slightly rounded markers to maintain the technical aesthetic.

## Components

### Buttons & Controls
- **Primary Button:** Solid Blue (#1A56DB) with white text. 4px radius. High contrast.
- **Secondary Button:** White background with a 1px Gray-300 border. Blue or Dark Gray text.
- **Input Fields:** 1px border (#D1D5DB) that shifts to #1A56DB on focus. Labels sit clearly above the field in `label-md`.

### Data Displays
- **Compact Cards:** Used for KPIs. Title in `label-md`, Value in `headline-md`, and secondary trend data in a smaller body font.
- **Data Tables:** Highly structured with 1px row borders. No zebra striping; use hover highlights instead.
- **Status Chips:** Small, low-profile badges with a light background tint and bold text in the same color (e.g., Light Green background with Dark Green text for "Active").

### Icons
- **Line Icons:** 20px or 24px grid. Consistent 1.5px or 2px stroke weight. Use monochrome gray unless the icon represents a specific status (Red for Alert).

### Interactive Elements
- **Tabs:** Flat styling with a 2px bottom border for the active state in Primary Blue.
- **Checkboxes/Radios:** Professional, standard forms. No "bouncy" or playful animations. Transitions should be instant and crisp.
