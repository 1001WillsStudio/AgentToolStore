# brand-guidelines

---
name: brand-guidelines
description: Apply official brand colors, typography, and visual identity to any design output. Use when the user mentions brand, branding, brand colors, brand guidelines, company style, or wants designs that match specific brand identity standards.
---

# Brand Guidelines

Apply consistent brand identity to all design outputs.

## Overview

This skill ensures all visual outputs (web pages, presentations, documents, images, etc.) adhere to brand guidelines. When active, it applies the brand's colors, fonts, and design system to every output.

## Instructions

### 1. Load Brand Identity

When activated, first determine:
- What brand are we working with?
- Are the brand guidelines provided by the user or in a reference file?
- What are the core brand elements?

Core elements to establish:
- **Color palette**: Primary, secondary, accent, neutral, background, text colors
- **Typography**: Primary font (headings), secondary font (body), fallback fonts
- **Logo**: Usage rules, placement, clear space
- **Spacing**: Grid system, standard spacing units
- **Tone**: Visual tone — minimalist, bold, playful, corporate, etc.

### 2. Apply Brand Colors

```
Primary:    #XXXXXX  → Main brand color, CTAs, active elements
Secondary:  #XXXXXX  → Supporting elements, highlights
Accent:     #XXXXXX  → Emphasis, call-outs
Neutral:    #XXXXXX  → Backgrounds, borders, dividers
Text:       #XXXXXX  → Body text, headings
```

Use CSS custom properties or design tokens for consistency.

### 3. Apply Typography

- Headings: `[Font Name]`, weights, sizes, line heights
- Body: `[Font Name]`, weights, sizes, line heights
- Monospace: `[Font Name]` for code/technical content
- Include web font import URLs if needed

### 4. Apply Visual Language

- **Borders**: Radius, width, style
- **Shadows**: Elevation system
- **Icons**: Style (filled, outlined), size
- **Illustrations**: Style guidelines
- **Photography**: Treatment, filters

### 5. Generate Brand-Compliant Outputs

For any visual output, verify:
- [ ] All colors are from the brand palette (or transparent)
- [ ] All fonts match brand typography
- [ ] Spacing uses the brand grid
- [ ] Logo usage follows guidelines (if logo is used)
- [ ] Overall design feels "on brand"

## Example: CSS Brand Variables

Generate this pattern at the top of any web/CSS output:

```css
:root {
  /* Brand colors */
  --brand-primary: #XXXXXX;
  --brand-secondary: #XXXXXX;
  --brand-accent: #XXXXXX;
  --brand-neutral-100: #XXXXXX;
  --brand-neutral-900: #XXXXXX;
  
  /* Typography */
  --font-heading: 'Brand Font', sans-serif;
  --font-body: 'Brand Font', sans-serif;
  
  /* Spacing */
  --space-unit: 8px;
  --space-sm: calc(var(--space-unit) * 1);
  --space-md: calc(var(--space-unit) * 2);
  --space-lg: calc(var(--space-unit) * 4);
}
```

## Guidelines

- **Ask for guidelines**: If the user mentions a brand but doesn't provide guidelines, ask for the brand colors, fonts, or a reference
- **Be consistent**: Apply the same brand rules across all outputs in a session
- **Don't improvise**: If brand guidelines aren't available, use neutral, professional defaults — don't guess brand colors
- **Handle multi-brand**: If the user works with multiple brands, keep them separate and ask which to apply
- **Document decisions**: When in doubt about a brand rule, note the assumption so it's clear
