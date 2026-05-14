"""
Bidirectional schema conversion between ToolStore tool definitions,
OpenAI function-calling schemas, and MCP tool schemas (JSON Schema).
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional


# ---------------------------------------------------------------------------
# ToolStore → OpenAI function schema
# ---------------------------------------------------------------------------

def toolstore_to_openai(tool_def: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a ToolStore tool definition to an OpenAI function-calling schema."""
    name = tool_def["name"]
    desc = tool_def.get("description", "")
    schema = tool_def.get("schema", {})

    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    # Try input schema first (MCP-compatible), then plain schema
    input_schema = schema.get("input_schema") or schema.get("inputSchema")
    if input_schema:
        # It's already JSON Schema — pass through with minor cleanup
        parameters = input_schema
    elif schema.get("input"):
        # Legacy ToolStore format: {"input": {"param": {"type": ..., "required": ...}}}
        for pname, pinfo in schema["input"].items():
            prop = {"type": pinfo.get("type", "string")}
            if "description" in pinfo:
                prop["description"] = pinfo["description"]
            if "enum" in pinfo:
                prop["enum"] = pinfo["enum"]
            if "default" in pinfo:
                prop["default"] = pinfo["default"]
            parameters["properties"][pname] = prop
            if pinfo.get("required"):
                parameters["required"].append(pname)

    return {
        "type": "function",
        "function": {
            "name": name,
            "description": desc,
            "parameters": parameters,
        },
    }


# ---------------------------------------------------------------------------
# MCP tool schema → OpenAI function schema
# ---------------------------------------------------------------------------

def mcp_to_openai(mcp_tool: Dict[str, Any]) -> Dict[str, Any]:
    """Convert an MCP tool definition (from tools/list) to OpenAI schema."""
    return {
        "type": "function",
        "function": {
            "name": mcp_tool["name"],
            "description": mcp_tool.get("description", ""),
            "parameters": mcp_tool.get("inputSchema", {
                "type": "object",
                "properties": {},
            }),
        },
    }


# ---------------------------------------------------------------------------
# OpenAI function schema → MCP tool schema
# ---------------------------------------------------------------------------

def openai_to_mcp(openai_schema: Dict[str, Any]) -> Dict[str, Any]:
    """Convert an OpenAI function schema to an MCP-compatible tool definition."""
    func = openai_schema.get("function", openai_schema)
    return {
        "name": func["name"],
        "description": func.get("description", ""),
        "inputSchema": func.get("parameters", {
            "type": "object",
            "properties": {},
        }),
    }


# ---------------------------------------------------------------------------
# ToolStore → MCP tool schema
# ---------------------------------------------------------------------------

def toolstore_to_mcp(tool_def: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a ToolStore tool to MCP-compatible format."""
    name = tool_def["name"]
    desc = tool_def.get("description", "")
    schema = tool_def.get("schema", {})

    # Build inputSchema
    input_schema = schema.get("input_schema") or schema.get("inputSchema")
    if not input_schema:
        input_schema = {"type": "object", "properties": {}}
        if schema.get("input"):
            for pname, pinfo in schema["input"].items():
                prop = {"type": pinfo.get("type", "string")}
                if "description" in pinfo:
                    prop["description"] = pinfo["description"]
                input_schema["properties"][pname] = prop

    return {
        "name": name,
        "description": desc,
        "inputSchema": input_schema,
    }


# ---------------------------------------------------------------------------
# Bulk conversion helpers
# ---------------------------------------------------------------------------

def bulk_to_openai(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert a list of ToolStore tools to OpenAI schemas."""
    return [toolstore_to_openai(t) for t in tools]


def bulk_mcp_to_openai(mcp_tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert a list of MCP tools to OpenAI schemas."""
    return [mcp_to_openai(t) for t in mcp_tools]


def bulk_to_mcp(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert a list of ToolStore tools to MCP schemas."""
    return [toolstore_to_mcp(t) for t in tools]


# ---------------------------------------------------------------------------
# MCP content flattening (for text-only agent consumption)
# ---------------------------------------------------------------------------

def flatten_mcp_content(content_list: List[Dict[str, Any]]) -> str:
    """Flatten an MCP content array into a single text string.

    Handles: text, image (base64 note), resource (inline).
    """
    parts: list[str] = []
    for item in content_list:
        t = item.get("type", "text")
        if t == "text":
            parts.append(item.get("text", ""))
        elif t == "image":
            parts.append(f"[image: {item.get('mimeType', 'unknown')}, "
                         f"{len(item.get('data', ''))} bytes]")
        elif t == "resource":
            r = item.get("resource", {})
            uri = r.get("uri", "?")
            if "text" in r:
                parts.append(f"[resource {uri}]\n{r['text']}")
            elif "blob" in r:
                parts.append(f"[resource {uri}: {r.get('mimeType', 'binary')} "
                             f"{len(r['blob'])} bytes]")
            else:
                parts.append(f"[resource {uri}]")
        else:
            parts.append(json.dumps(item))
    return "\n".join(parts)


import json
