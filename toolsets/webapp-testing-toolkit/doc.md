# webapp-testing

---
name: webapp-testing
description: Test local web applications using browser automation (Playwright) — verify functionality, debug UI behavior, capture screenshots, and view browser logs. Use when the user wants to test a web app, verify frontend behavior, debug UI issues, or automate browser interactions.
---

# Web Application Testing

Test local web applications using Playwright browser automation.

## Overview

This skill provides patterns and helpers for testing web applications — verifying functionality, debugging UI issues, capturing browser state, and automating browser interactions.

## Decision Tree

```
User task → Is it static HTML?
    ├─ Yes → Read HTML file directly to identify selectors
    │         ├─ Success → Write Playwright script using selectors
    │         └─ Incomplete → Treat as dynamic webapp (below)
    │
    └─ No (dynamic webapp) → Is the server already running?
        ├─ No → Start the server first, then test
        │
        └─ Yes → Reconnaissance-then-action:
            1. Navigate and wait for network idle
            2. Take screenshot or inspect DOM
            3. Identify selectors from rendered state
            4. Execute actions with discovered selectors
```

## Instructions

### 1. Start the Server (if needed)

If the webapp isn't running, start it first. Use a helper script or start the server directly:

```bash
# Single server
cd /path/to/project && npm run dev &

# Or use a process manager
```

Wait for the server to be ready before proceeding.

### 2. Reconnaissance (for dynamic apps)

Before writing automation, understand what's on the page:

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    
    # Navigate and wait for JS to execute
    page.goto('http://localhost:PORT')
    page.wait_for_load_state('networkidle')  # CRITICAL for dynamic apps
    
    # Inspect the rendered page
    page.screenshot(path='/tmp/inspect.png', full_page=True)
    
    # Discover available elements
    buttons = page.locator('button').all()
    inputs = page.locator('input').all()
    links = page.locator('a').all()
    
    browser.close()
```

### 3. Write the Test/Automation Script

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    
    page.goto('http://localhost:PORT')
    page.wait_for_load_state('networkidle')
    
    # Your automation logic:
    # - Click buttons
    # - Fill forms
    # - Verify text/content
    # - Take screenshots at key moments
    # - Check console logs
    
    page.screenshot(path='/tmp/result.png', full_page=True)
    browser.close()
```

### 4. Verify Results

- Take screenshots at key interaction points
- Check page content and element states
- Capture console logs for debugging
- Verify network requests if relevant

## Common Patterns

### Form Testing
```python
# Fill a form
page.fill('#name', 'Test User')
page.fill('#email', 'test@example.com')
page.click('button[type="submit"]')

# Wait for success message
page.wait_for_selector('.success-message')
```

### Multi-Step Flow
```python
# Step 1: Navigate
page.goto('http://localhost:PORT/login')
page.wait_for_load_state('networkidle')

# Step 2: Login
page.fill('#username', 'admin')
page.fill('#password', 'password')
page.click('button[type="submit"]')
page.wait_for_url('**/dashboard')

# Step 3: Verify dashboard loaded
assert page.locator('h1').text_content() == 'Dashboard'
```

### Debugging
```python
# Capture console logs
page.on('console', lambda msg: print(f'CONSOLE: {msg.text}'))

# Take screenshots at failures
try:
    page.wait_for_selector('.expected-element', timeout=5000)
except:
    page.screenshot(path='/tmp/debug-failure.png')
    raise
```

## Best Practices

- Always wait for `networkidle` on dynamic apps before inspection
- Use descriptive selectors: `text=`, `role=`, CSS selectors, IDs
- Add appropriate waits: `wait_for_selector()`, `wait_for_timeout()`
- Use `sync_playwright()` for synchronous scripts
- Always close the browser when done
- Take screenshots at key moments for debugging

## Guidelines

- **Test in headless mode**: `headless=True` for automation
- **Handle timeouts**: Set appropriate timeouts; don't hang indefinitely
- **Clean up**: Close browser even on failures (use try/finally)
- **One assertion per test**: Keep test scripts focused
- **Use data-testid**: Prefer `data-testid` attributes over CSS classes for test selectors
