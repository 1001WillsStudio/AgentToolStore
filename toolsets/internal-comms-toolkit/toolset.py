"""internal-comms-toolkit — Communication templates for common scenarios.
======================================================================"""

from pathlib import Path

try:
    from toolstore.toolset import tool
except ImportError:
    def tool(fn):
        return fn


@tool
def comms_template(*, template_type: str, context: str = "") -> dict:
    """Return a communication template with placeholders.

    Args:
        template_type: One of status_update, announcement, incident_report, decision.
        context:       Brief context to customize the template.

    Returns:
        dict with "subject" and "body" (template text with {placeholders}).
    """
    templates = {
        "status_update": {
            "subject": "Status Update: {project} — {date}",
            "body": "**TL;DR:** {summary}\n\n**Progress this week:**\n- {progress}\n\n**Plans for next week:**\n- {plans}\n\n**Blockers:** {blockers or 'None'}",
        },
        "announcement": {
            "subject": "Announcement: {topic}",
            "body": "Hi team,\n\n{message}\n\n**Key details:**\n- {detail1}\n- {detail2}\n\nLet me know if you have questions.\n\nThanks,\n{sender}",
        },
        "incident_report": {
            "subject": "Incident Report: {incident} — {date}",
            "body": "**Summary:** {summary}\n\n**Timeline:**\n- {time_start}: Issue detected\n- {time_resolve}: Issue resolved\n\n**Root Cause:** {root_cause}\n\n**Impact:** {impact}\n\n**Action Items:**\n- {actions}",
        },
        "decision": {
            "subject": "Decision: {decision}",
            "body": "**Decision:** {decision}\n\n**Rationale:** {rationale}\n\n**Alternatives Considered:**\n- {alt1}\n- {alt2}\n\n**Next Steps:** {next_steps}",
        },
    }
    tmpl = templates.get(template_type, templates["status_update"])
    # Get the doc.md content for full guidance
    try:
        doc_content = (Path(__file__).parent / "doc.md").read_text()
    except Exception:
        doc_content = ""
    return {"template_type": template_type, "subject": tmpl["subject"],
            "body": tmpl["body"], "has_full_doc": bool(doc_content)}


@tool
def format_bullets(*, items: list, style: str = "bullet") -> dict:
    """Format a list of items as Markdown bullets, numbered list, or checklist.

    Args:
        items: List of strings.
        style: "bullet", "numbered", or "checklist".

    Returns:
        dict with "formatted" (Markdown string) and "count".
    """
    if style == "numbered":
        lines = [f"{i+1}. {item}" for i, item in enumerate(items)]
    elif style == "checklist":
        lines = [f"- [ ] {item}" for item in items]
    else:
        lines = [f"- {item}" for item in items]
    return {"formatted": "\n".join(lines), "count": len(items)}
