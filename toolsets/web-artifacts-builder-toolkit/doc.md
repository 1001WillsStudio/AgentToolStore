# web-artifacts-builder

---
name: web-artifacts-builder
description: Build complex, multi-component HTML artifacts using modern frontend patterns — React, Tailwind CSS, shadcn/ui components, and interactive web apps. Use when the user wants a complex web application, interactive tool, or sophisticated single-page artifact.
---

# Web Artifacts Builder

Build complex, interactive web applications as single-page artifacts.

## Overview

This skill creates sophisticated browser-based artifacts — tools, dashboards, interactive visualizations, and mini-applications — using modern frontend technologies embedded in self-contained HTML files.

## Instructions

### 1. Understand Requirements

Determine:
- **Purpose**: What does the user want to build?
- **Interactivity**: What can users do? Forms, drag-and-drop, real-time updates?
- **Data**: Static, user-provided, or fetched from an API?
- **Complexity**: Simple tool or full mini-application?
- **Dependencies**: Acceptable to use CDN-loaded libraries?

### 2. Choose the Architecture

| Complexity | Approach |
|------------|----------|
| **Simple** | Vanilla HTML/CSS/JS in a single file |
| **Medium** | Single file with CDN-loaded libraries (React, D3, etc.) |
| **Complex** | Build tool with bundled output, or single file with ES modules from CDN |

### 3. Build the Artifact

For a React-based artifact:

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <script src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
  <script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
  <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
  <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
  <style>
    /* Custom styles */
  </style>
</head>
<body>
  <div id="root"></div>
  <script type="text/babel">
    // React application code
  </script>
</body>
</html>
```

### 4. Include Essential Features

- **State management**: Track user input and application state
- **Error handling**: Graceful handling of edge cases
- **Loading states**: Feedback during async operations
- **Empty states**: What to show when there's no data
- **Responsive design**: Works on different screen sizes

### 5. Polish

- Test all interactive flows
- Verify rendering at different viewport sizes
- Check for console errors
- Ensure keyboard accessibility basics

## Component Patterns

### Data Dashboard
- Summary KPI cards with trends
- Filterable data tables with sorting
- Interactive charts (bar, line, pie)
- Date range pickers
- Export functionality

### Form-Based Tool
- Multi-step form with progress indicator
- Input validation with inline errors
- Auto-save or draft persistence
- Results/summary view

### Interactive Visualization
- Canvas or SVG rendering
- Zoom/pan controls
- Tooltips and hover states
- Legend and scale indicators

## Guidelines

- **Self-contained**: Everything in one HTML file (or clearly documented dependencies)
- **CDN for dependencies**: Use CDN links for libraries; don't require a build step
- **Progressive enhancement**: Core functionality without JS; enhanced with JS
- **State management**: Keep state organized; use reducer pattern for complex state
- **Performance**: Lazy load heavy content; debounce expensive operations
- **Test thoroughly**: Click every button, submit every form, resize the window
