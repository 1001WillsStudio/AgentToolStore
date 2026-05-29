# theme-factory

---
name: theme-factory
description: Apply and manage visual themes for web artifacts and UI components — color schemes, typography pairs, and design tokens. Use when the user wants to change themes, apply a visual style, or needs theme options for their web project.
---

# Theme Factory

Generate and apply visual themes for web artifacts and UI components.

## Overview

This skill manages visual themes — color palettes, typography sets, spacing systems, and design tokens — that can be applied to web pages, dashboards, and UI components.

## Instructions

### 1. Present Theme Options

When the user wants a theme, present categorized options:

```
Theme Categories:
  Professional:  Minimal, Clean, Corporate, Enterprise
  Creative:      Playful, Bold, Artistic, Retro
  Dark:          Midnight, Cyberpunk, Dark Mode, OLED
  Nature:        Forest, Ocean, Desert, Garden
  Seasonal:      Spring, Summer, Autumn, Winter
  Industry:      Healthcare, Finance, Education, Tech
```

Let the user choose a direction before generating specifics.

### 2. Generate Theme Tokens

For the chosen direction, produce design tokens:

```css
:root {
  /* Colors */
  --color-primary: #XXXXXX;
  --color-primary-hover: #XXXXXX;
  --color-secondary: #XXXXXX;
  --color-accent: #XXXXXX;
  --color-background: #XXXXXX;
  --color-surface: #XXXXXX;
  --color-text-primary: #XXXXXX;
  --color-text-secondary: #XXXXXX;
  --color-border: #XXXXXX;
  --color-success: #XXXXXX;
  --color-warning: #XXXXXX;
  --color-error: #XXXXXX;
  
  /* Typography */
  --font-heading: '...', sans-serif;
  --font-body: '...', sans-serif;
  --font-mono: '...', monospace;
  
  /* Spacing */
  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 16px;
  --space-lg: 24px;
  --space-xl: 48px;
  
  /* Borders */
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 16px;
  
  /* Shadows */
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
  --shadow-md: 0 4px 6px rgba(0,0,0,0.1);
  --shadow-lg: 0 10px 15px rgba(0,0,0,0.1);
}
```

### 3. Apply Themes

- Inject the CSS variables into the target artifact
- Update component styles to use theme variables instead of hardcoded values
- Provide a theme switcher if the user wants toggleable themes

### 4. Theme Preview

Generate a preview card showing:
- Color swatches (primary, secondary, accent, background, text)
- Typography samples (heading, body, mono)
- A sample UI component (button, card, input)

## Color Palette Guidelines

- **Primary**: Main brand color; use for CTAs, active states, key elements
- **Secondary**: Supporting color; use for backgrounds, secondary elements
- **Accent**: Highlight color; use sparingly for emphasis
- **Neutrals**: Grays for text, borders, backgrounds (at least 5-6 shades)
- **Semantic**: Success (green), Warning (amber), Error (red), Info (blue)

Ensure WCAG AA contrast ratios: 4.5:1 for normal text, 3:1 for large text.

## Typography Pairing Guidelines

- **Heading + Body**: Pair a distinctive heading font with a readable body font
- **Serif + Sans-serif**: Classic pairing (e.g., Playfair Display + Inter)
- **Sans-serif + Sans-serif**: Modern, clean (e.g., Montserrat + Open Sans)
- **Mono**: Always include a monospace font for code

## Guidelines

- **Accessibility first**: Ensure sufficient contrast, especially for text
- **Provide options**: Give the user 3-5 theme variations to choose from
- **Dark mode**: Consider both light and dark variants
- **Consistency**: Apply the same tokens everywhere
- **Web-safe fallbacks**: Always include fallback font stacks
