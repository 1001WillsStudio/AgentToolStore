"""doc-coauthoring-toolkit — Document structure outlines and templates.
======================================================================"""

from pathlib import Path

try:
    from toolstore.toolset import tool
except ImportError:
    def tool(fn):
        return fn


@tool
def document_outline(*, doc_type: str = "report", topic: str = "") -> dict:
    """Generate a document structure outline for a given type.

    Args:
        doc_type: One of report, proposal, tutorial, meeting_notes, spec.
        topic:    The document topic.

    Returns:
        dict with "title" and "sections" (ordered list).
    """
    outlines = {
        "report": ["Executive Summary", "Background", "Methodology", "Findings",
                    "Analysis", "Recommendations", "Conclusion", "Appendices"],
        "proposal": ["Problem Statement", "Proposed Solution", "Benefits",
                      "Implementation Plan", "Timeline", "Budget", "Risks", "Appendices"],
        "tutorial": ["Prerequisites", "Getting Started", "Core Concepts",
                      "Step-by-Step Guide", "Common Pitfalls", "Next Steps"],
        "meeting_notes": ["Attendees", "Agenda", "Discussion Points", "Decisions Made",
                           "Action Items", "Next Meeting"],
        "spec": ["Overview", "Requirements", "Architecture", "API Design",
                  "Data Model", "Security", "Testing Strategy", "Deployment"],
    }
    sections = outlines.get(doc_type, ["Introduction", "Main Content", "Conclusion"])
    title = f"{topic} - {doc_type.title()}" if topic else doc_type.title()
    return {"title": title, "doc_type": doc_type, "sections": sections, "count": len(sections)}


@tool
def markdown_template(*, doc_type: str, title: str = "", author: str = "") -> dict:
    """Generate a blank Markdown document template with frontmatter.

    Args:
        doc_type: One of readme, changelog, contributing, api_doc.
        title:    Document title.
        author:   Document author.

    Returns:
        dict with "filename" and "content" (markdown template).
    """
    templates = {
        "readme": f"""# {title or 'Project Name'}

## Overview

Brief description of the project.

## Installation

```bash
pip install package
```

## Usage

```python
import package
```

## License

MIT
""",
        "changelog": f"""# Changelog

## [Unreleased]

### Added
- 

### Changed
- 

### Fixed
- 

## [1.0.0] - {{{{date}}}}
- Initial release
""",
        "contributing": f"""# Contributing to {title or 'Project'}

## Setup

1. Clone the repo
2. Install dev dependencies
3. Create a branch

## Pull Request Process

1. Update tests
2. Update documentation
3. Request review
""",
        "api_doc": f"""# {title or 'API'} Documentation

## Authentication

Describe auth method.

## Endpoints

### GET /resource

Description.

**Response:**
```json
{{}}
```
""",
    }
    content = templates.get(doc_type, templates["readme"])
    return {"filename": f"{doc_type}.md", "content": content, "doc_type": doc_type}
