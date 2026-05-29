# keybindings

---
name: keybindings
description: View, customize, and manage keyboard shortcuts and keybindings. Use when the user wants to see available shortcuts, change keybindings, add custom shortcuts, or troubleshoot keyboard shortcut issues.
---

# Keybindings Management

Manage keyboard shortcuts and keybindings.

## Overview

This skill helps users discover, customize, and troubleshoot keyboard shortcuts.

## Instructions

### 1. Show Current Keybindings

When the user asks about keybindings:

**List all bindings**:
```
Keyboard Shortcuts:

Editing:
  Ctrl+C          Copy
  Ctrl+X          Cut
  Ctrl+V          Paste
  Ctrl+Z          Undo
  Ctrl+Y          Redo

Navigation:
  Ctrl+P          Previous item
  Ctrl+N          Next item
  Ctrl+F          Search/Find

Actions:
  Ctrl+S          Save
  Ctrl+Enter      Submit/Send
  Esc             Cancel/Close
  Ctrl+/          Show all shortcuts
```

**Search for a specific binding**:
- "What's the shortcut for undo?" → Show `Ctrl+Z`
- "What does Ctrl+K do?" → Show "Clear line / Delete to end"

### 2. Customize Keybindings

When the user wants to change a keybinding:

1. Identify the action they want to rebind
2. Check if the desired key combination is available (not already taken)
3. Apply the new binding
4. Confirm the change

```
Changed: "Save" is now bound to Cmd+Shift+S (was Cmd+S)
```

### 3. Add Custom Keybindings

When the user wants to add a new shortcut:

1. Understand what action it should trigger
2. Choose a key combination (suggest alternatives if the preferred one is taken)
3. Register the new binding
4. Confirm it works

### 4. Troubleshoot Keybindings

Common issues:
- **Conflict**: Two actions bound to the same keys → Identify conflict, suggest resolution
- **Not working**: Check if the binding is active in the current context/mode
- **Platform differences**: Ctrl vs Cmd, different modifier keys on different OSes

## Keybinding Notation

| Platform | Modifier notation |
|----------|-------------------|
| **macOS** | Cmd, Opt, Ctrl, Shift |
| **Windows/Linux** | Ctrl, Alt, Win, Shift |

Notation style: `Modifier+Key` (e.g., `Ctrl+Shift+K`, `Cmd+Option+P`)

## Guidelines

- **Check for conflicts**: Always verify a key combination isn't already in use before assigning
- **Platform awareness**: Use the correct modifier keys for the user's platform
- **Suggest alternatives**: If the preferred binding is taken, suggest nearby options
- **Document changes**: Note what was changed from the default
- **Reset option**: Always offer a way to reset to defaults
