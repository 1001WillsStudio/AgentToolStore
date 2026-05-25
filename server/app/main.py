from datetime import datetime, timedelta
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select
from app.database import create_db_and_tables, get_session
from app.models import Tool, User
from app.auth import (
    get_password_hash, verify_password, create_access_token, 
    get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES
)
from contextlib import asynccontextmanager
from pydantic import BaseModel

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield

app = FastAPI(title="ToolStore Registry", lifespan=lifespan)

# -- Pydantic Models for Auth --
class UserCreate(BaseModel):
    username: str
    email: Optional[str] = None
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

# -- Endpoints --

@app.get("/")
def read_root():
    return {"message": "Welcome to ToolStore Registry API"}

@app.post("/auth/register", response_model=Token)
def register(user: UserCreate, session: Session = Depends(get_session)):
    # Check existing
    existing = session.exec(select(User).where(User.username == user.username)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    # Create User
    hashed_pw = get_password_hash(user.password)
    db_user = User(username=user.username, email=user.email, password_hash=hashed_pw)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    
    # Return Login Token immediately
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/auth/token", response_model=Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.username == form_data.username)).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/index.json")
def get_index(session: Session = Depends(get_session)):
    """
    Returns the full list of tools in the simplified JSON format
    expected by the CLI client. Skills include 'body' for progressive disclosure.
    """
    tools = session.exec(select(Tool)).all()
    
    index_list = []
    for tool in tools:
        tool_data = tool.definition.copy()
        tool_data["name"] = tool.name
        tool_data["description"] = tool.description
        tool_data["type"] = tool.type
        tool_data["owner"] = tool.owner.username if tool.owner else "unknown"
        # Include docker fields for docker-type tools
        if tool.type == "docker":
            if tool.docker_image:
                tool_data["docker_image"] = tool.docker_image
            if tool.code:
                tool_data["code"] = tool.code
            if tool.code_base64:
                tool_data["code_base64"] = tool.code_base64
        # Include body for skills (progressive disclosure)
        if tool.type == "skill" and tool.body:
            tool_data["body"] = tool.body
        if tool.type == "skill" and tool.skill_files:
            tool_data["skill_files"] = tool.skill_files
        index_list.append(tool_data)
        
    return index_list

@app.post("/publish")
def publish_tool(
    tool_def: dict, 
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Authenticated endpoint to publish a tool (api, mcp, or skill).
    For skills, include 'body' (SKILL.md body text) and optional
    'skill_files' ({filename: content} dict).
    For docker, include 'docker_image' (optional custom image), 'code'
    (the executable Python code), and optional 'code_base64'.
    """
    name = tool_def.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="Tool name required")

    tool_type = tool_def.get("type", "api")
    if tool_type not in ("api", "mcp", "skill", "docker"):
        raise HTTPException(status_code=400, detail=f"Invalid type: {tool_type}. Must be 'api', 'mcp', 'skill', or 'docker'")
        
    # Check if exists
    existing = session.exec(select(Tool).where(Tool.name == name)).first()
    if existing:
        # Only owner can update
        if existing.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="You do not own this tool")
        
        # Update existing
        existing.definition = tool_def
        existing.version = tool_def.get("version", existing.version)
        existing.description = tool_def.get("description", existing.description)
        existing.type = tool_type
        existing.updated_at = datetime.utcnow()
        # Handle skill-specific fields
        if tool_type == "skill":
            existing.body = tool_def.get("body")
            existing.skill_files = tool_def.get("skill_files")
        # Handle docker-specific fields
        if tool_type == "docker":
            existing.docker_image = tool_def.get("docker_image")
            existing.code = tool_def.get("code")
            existing.code_base64 = tool_def.get("code_base64")
        session.add(existing)
        session.commit()
        return {"success": True, "tool": name, "action": "updated"}
        
    # Create New
    tool = Tool(
        name=name,
        version=tool_def.get("version", "1.0.0"),
        type=tool_type,
        description=tool_def.get("description", ""),
        definition=tool_def,
        body=tool_def.get("body") if tool_type == "skill" else None,
        skill_files=tool_def.get("skill_files") if tool_type == "skill" else None,
        docker_image=tool_def.get("docker_image") if tool_type == "docker" else None,
        code=tool_def.get("code") if tool_type == "docker" else None,
        code_base64=tool_def.get("code_base64") if tool_type == "docker" else None,
        owner_id=current_user.id
    )
    
    session.add(tool)
    session.commit()
    session.refresh(tool)
    
    return {"success": True, "tool": tool.name, "action": "created"}

@app.delete("/tools/{name}")
def delete_tool(
    name: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Authenticated endpoint to delete a tool.
    """
    tool = session.exec(select(Tool).where(Tool.name == name)).first()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
        
    if tool.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="You do not own this tool")
        
    session.delete(tool)
    session.commit()
    
    return {"success": True, "tool": name, "action": "deleted"}


# ---------------------------------------------------------------------------
# Skill-specific endpoints — publish, fetch, download
# ---------------------------------------------------------------------------

class SkillPublishRequest(BaseModel):
    """Request body for publishing a skill.
    Mirrors the SkillDefinition.to_upload_dict() output."""
    name: str
    description: str
    version: str = "1.0.0"
    body: str  # SKILL.md body (Markdown instructions)
    license: str = ""
    compatibility: str = ""
    metadata: dict = {}
    allowed_tools: str = ""
    skill_files: Optional[dict] = None  # {filename: content}


@app.post("/skills/publish")
def publish_skill(
    req: SkillPublishRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Publish a skill to the ToolStore registry.
    Accepts a JSON body with skill metadata, SKILL.md body, and optional
    bundled files (skill_files dict).
    """
    name = req.name

    # Build the full tool definition for storage in 'definition' column
    definition = {
        "name": name,
        "type": "skill",
        "description": req.description,
        "version": req.version,
        "license": req.license,
        "compatibility": req.compatibility,
        "metadata": req.metadata,
        "allowed_tools": req.allowed_tools,
        "source": "skill",
        "schema": {
            "input_schema": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["load", "files", "file", "run"],
                        "description": "load = read full SKILL.md, "
                                       "files = list bundled files, "
                                       "file = read a specific file, "
                                       "run = execute script from scripts/",
                    },
                    "file_path": {
                        "type": "string",
                        "description": "Relative path of file to read "
                                       "(required for action='file')",
                    },
                    "script": {
                        "type": "string",
                        "description": "Script to run from scripts/ dir "
                                       "(for action='run')",
                    },
                },
                "required": ["action"],
            },
        },
    }

    # Check if exists
    existing = session.exec(select(Tool).where(Tool.name == name)).first()
    if existing:
        if existing.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="You do not own this skill")
        existing.definition = definition
        existing.description = req.description
        existing.version = req.version
        existing.body = req.body
        existing.skill_files = req.skill_files
        existing.updated_at = datetime.utcnow()
        session.add(existing)
        session.commit()
        return {"success": True, "skill": name, "action": "updated"}

    tool = Tool(
        name=name,
        version=req.version,
        type="skill",
        description=req.description,
        definition=definition,
        body=req.body,
        skill_files=req.skill_files,
        owner_id=current_user.id,
    )
    session.add(tool)
    session.commit()
    session.refresh(tool)
    return {"success": True, "skill": name, "action": "created"}


@app.get("/skills/{name}")
def get_skill(
    name: str,
    session: Session = Depends(get_session)
):
    """
    Get full skill data including the SKILL.md body (progressive disclosure).
    """
    tool = session.exec(select(Tool).where(Tool.name == name)).first()
    if not tool or tool.type != "skill":
        raise HTTPException(status_code=404, detail="Skill not found")

    return {
        "name": tool.name,
        "type": tool.type,
        "description": tool.description,
        "version": tool.version,
        "body": tool.body,
        "definition": tool.definition,
        "skill_files": tool.skill_files,
        "owner": tool.owner.username if tool.owner else "unknown",
        "created_at": str(tool.created_at),
        "downloads": tool.downloads,
    }


@app.get("/skills/{name}/download")
def download_skill(
    name: str,
    session: Session = Depends(get_session)
):
    """
    Download a skill as a zip file containing SKILL.md and bundled files.
    Returns a binary zip stream.
    """
    import io
    import zipfile
    from fastapi.responses import StreamingResponse

    tool = session.exec(select(Tool).where(Tool.name == name)).first()
    if not tool or tool.type != "skill":
        raise HTTPException(status_code=404, detail="Skill not found")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Build SKILL.md content (frontmatter + body)
        fm_lines = [
            "---",
            f"name: {tool.name}",
            f"description: {tool.description}",
        ]
        definition = tool.definition or {}
        if definition.get("license"):
            fm_lines.append(f"license: {definition['license']}")
        if definition.get("compatibility"):
            fm_lines.append(f"compatibility: {definition['compatibility']}")
        if definition.get("allowed_tools"):
            fm_lines.append(f"allowed-tools: {definition['allowed_tools']}")
        metadata = definition.get("metadata", {})
        if metadata:
            fm_lines.append("metadata:")
            for k, v in metadata.items():
                fm_lines.append(f"  {k}: {v}")
        fm_lines.append("---")
        skill_md = "\n".join(fm_lines) + "\n\n" + (tool.body or "")
        zf.writestr(f"{name}/SKILL.md", skill_md)

        # Write bundled files
        if tool.skill_files:
            for fname, content in tool.skill_files.items():
                zf.writestr(f"{name}/{fname}", content)

    buf.seek(0)

    # Increment downloads counter
    tool.downloads = (tool.downloads or 0) + 1
    session.add(tool)
    session.commit()

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{name}.zip"'
        },
    )


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
def health_check(session: Session = Depends(get_session)):
    """Health check endpoint — verifies DB connectivity."""
    try:
        count = len(session.exec(select(Tool)).all())
        return {"status": "ok", "tools_count": count}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
