# update-config

---
name: update-config
description: View, modify, and manage configuration settings. Use when the user wants to change settings, update preferences, toggle features, or view current configuration values.
---

# Update Configuration

Manage configuration settings — view, modify, and explain configuration options.

## Overview

This skill helps the user manage their configuration settings. It covers discovering what's configurable, viewing current values, making changes, and resetting to defaults.

## Instructions

### 1. Discover Configuration

When the user asks about configuration:

1. **Check what's available**: Read the configuration file or system to understand what settings exist
2. **Show current values**: Present settings in a readable format

```
Current Configuration:
  Setting           Value       Default    Description
  ─────────         ─────       ───────    ───────────
  theme             dark        system     UI theme (light/dark/system)
  auto_save         true        true       Auto-save work in progress
  max_context       100000      100000     Maximum context window size
  language          en          en         Interface language
```

### 2. Understand the Change

When the user wants to change a setting:

- What setting do they want to change?
- What value do they want to set it to?
- Do they understand the implications?

Explain what the setting controls and any trade-offs before making changes.

### 3. Apply the Change

1. Validate the new value (correct type, within valid range)
2. Update the configuration
3. Confirm the change was applied
4. Note if a restart is required for the change to take effect

### 4. Special Operations

**View all settings**: Show the complete configuration in a readable format

**Reset to defaults**: 
- "Reset all settings" → Reset everything
- "Reset [specific setting]" → Reset just that one
- Always confirm before resetting

**Export/Import**:
- Export: Save configuration to a file for backup or sharing
- Import: Apply settings from a configuration file

## Common Settings Categories

| Category | Examples |
|----------|----------|
| **Appearance** | Theme, font size, color scheme |
| **Behavior** | Auto-save, confirmations, notifications |
| **Performance** | Context window, token limits, parallelism |
| **Privacy** | Data collection, history, telemetry |
| **Integrations** | API keys, connected services |
| **Language** | Interface language, output language |

## Guidelines

- **Show before/after**: Always confirm what changed and what it was before
- **Explain implications**: Help the user understand trade-offs
- **Validate input**: Don't apply invalid values; suggest valid alternatives
- **Don't change without asking**: Never modify configuration without explicit user request
- **Handle errors gracefully**: If a change fails, explain why and suggest alternatives
- **Backup when appropriate**: For significant changes, offer to save current config first
