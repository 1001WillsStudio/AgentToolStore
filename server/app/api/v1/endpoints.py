from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from typing import List

from app.db import get_session
from app.models import Tool, ToolCreate, ToolRead

router = APIRouter()

@router.post("/tools", response_model=ToolRead)
def create_tool(*, session: Session = Depends(get_session), tool: ToolCreate):
    db_tool = session.exec(select(Tool).where(Tool.name == tool.name)).first()
    if db_tool:
        raise HTTPException(status_code=400, detail="Tool with this name already exists")
    
    db_tool = Tool.model_validate(tool)
    session.add(db_tool)
    session.commit()
    session.refresh(db_tool)
    return db_tool

@router.get("/tools", response_model=List[ToolRead])
def read_tools(
    *,
    session: Session = Depends(get_session),
    offset: int = 0,
    limit: int = Query(default=100, le=100),
):
    tools = session.exec(select(Tool).offset(offset).limit(limit)).all()
    return tools

@router.get("/tools/{name}", response_model=ToolRead)
def read_tool(*, session: Session = Depends(get_session), name: str):
    tool = session.exec(select(Tool).where(Tool.name == name)).first()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    return tool

@router.get("/online_index")
def get_online_index(*, session: Session = Depends(get_session)):
    """
    Serve the online tool catalogue as JSON.
    This matches the format expected by IndexManager in the client.
    """
    tools = session.exec(select(Tool)).all()

    index_tools = {}
    for tool in tools:
        # Convert DB model to the JSON schema expected by CLI
        tool_dict = tool.model_dump()

        # Remap fields if necessary (e.g. schema_data -> schema)
        tool_dict["schema"] = tool_dict.pop("schema_data", {})
        tool_dict["auth"] = tool_dict.pop("auth_config", {})

        index_tools[tool.name] = tool_dict

    return {
        "meta": {
            "version": "1.0",
            "count": len(tools),
            "last_updated": "2025-11-25"  # TODO: Real timestamp
        },
        "tools": index_tools
    }

