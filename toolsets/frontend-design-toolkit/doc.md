# frontend-design

---
name: frontend-design
description: Create production-grade frontend interfaces — web pages, dashboards, landing pages, UI components with HTML/CSS/JS. Use when the user asks to build a UI, create a webpage, design a dashboard, make a landing page, or build any frontend interface.
---

# Frontend Design

Create polished, production-grade frontend interfaces.

## Overview

This skill covers building web frontends: pages, dashboards, components, and full interfaces. Focus on visual quality, usability, and production readiness.

## Instructions

### 1. Understand Requirements

Clarify:
- **Purpose**: What should the user accomplish with this interface?
- **Audience**: Who will use it? Technical or non-technical?
- **Content**: What information needs to be displayed?
- **Interactivity**: What can users do? Click, type, navigate, filter, sort?
- **Constraints**: Mobile? Performance targets? Brand guidelines?
- **Data**: Static content or dynamic (API, database)?

### 2. Design Approach

Choose the right approach:
- **Single page**: One HTML file with embedded CSS/JS — good for demos, simple tools
- **Multi-page site**: Multiple pages with shared styles — good for content sites
- **Component-based**: Framework components (React, Vue) — good for complex apps
- **Dashboard**: Grid layout with widgets (charts, tables, KPIs)

### 3. Visual Design Principles

- **Hierarchy**: Most important information should be most prominent
- **Spacing**: Consistent margins and padding; don't crowd elements
- **Typography**: Choose readable fonts; establish clear heading/body hierarchy
- **Color**: Use a cohesive palette (2-3 primary colors, 1 accent)
- **Contrast**: Ensure text is readable against backgrounds
- **Responsive**: Design for the target screen sizes; use media queries
- **Empty states**: Design what users see when there's no data

### 4. Build

- Start with semantic HTML structure
- Add CSS for layout and styling (grid/flexbox for layouts)
- Add JavaScript for interactivity (vanilla JS or framework)
- Use modern CSS features: CSS variables, grid, flexbox, transitions
- Add subtle animations for polish (hover effects, transitions)

### 5. Polish

- Test all interactive elements work
- Verify responsive layout at different screen sizes
- Check loading and error states
- Ensure accessibility basics (labels, contrast, keyboard navigation)

## Common Patterns

### Dashboard
```
- Header with title and filters/date range
- KPI cards row (key metrics, big numbers)
- Main chart area (trends over time)
- Secondary widgets (breakdowns, tables)
- Use grid layout for responsive widget arrangement
```

### Landing Page
```
- Hero section with headline, subtitle, CTA
- Value proposition / features section
- How it works / workflow
- Social proof / testimonials
- Footer with links and contact
```

### Data Table
```
- Search/filter bar at top
- Sortable column headers
- Pagination or infinite scroll
- Row actions (edit, delete, view)
- Bulk selection and actions
```

## Guidelines

- **Mobile-first**: Design for the smallest target screen, then enhance
- **Performance**: Minimize dependencies; optimize images
- **Progressive enhancement**: Core functionality works without JS
- **Consistency**: Use the same spacing, colors, and patterns throughout
- **User feedback**: Loading states, success messages, error messages
- **Don't over-engineer**: Match complexity to the task
