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
    Returns the full list of published toolsets in JSON format.
    """
    tools = session.exec(select(Tool)).all()
    
    index_list = []
    for tool in tools:
        tool_data = tool.definition.copy()
        tool_data["name"] = tool.name
        tool_data["description"] = tool.description
        tool_data["type"] = tool.type
        tool_data["owner"] = tool.owner.username if tool.owner else "unknown"
        # Include toolset fields for toolset-type tools
        if tool.type == "toolset":
            if tool.docker_image:
                tool_data["docker_image"] = tool.docker_image
            if tool.code:
                tool_data["code"] = tool.code
            if tool.code_base64:
                tool_data["code_base64"] = tool.code_base64
            if tool.doc:
                tool_data["doc"] = tool.doc
            if tool.env_vars:
                tool_data["env_vars"] = tool.env_vars
            if tool.requirements:
                tool_data["requirements"] = tool.requirements
        index_list.append(tool_data)
        
    return index_list

@app.post("/publish")
def publish_tool(
    tool_def: dict, 
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Authenticated endpoint to publish a toolset.
    Include 'doc' (doc.md), 'code' (toolset.py),
    optional 'docker_image', 'env_vars', 'requirements'.
    """
    name = tool_def.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="Tool name required")

    tool_type = "toolset"
        
    # Check if exists
    existing = session.exec(select(Tool).where(Tool.name == name)).first()
    if existing:
        if existing.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="You do not own this tool")
        existing.definition = tool_def
        existing.version = tool_def.get("version", existing.version)
        existing.description = tool_def.get("description", existing.description)
        existing.type = tool_type
        existing.updated_at = datetime.utcnow()
        existing.docker_image = tool_def.get("docker_image")
        existing.code = tool_def.get("code")
        existing.code_base64 = tool_def.get("code_base64")
        existing.doc = tool_def.get("doc")
        existing.env_vars = tool_def.get("env_vars")
        existing.requirements = tool_def.get("requirements")
        session.add(existing)
        session.commit()
        return {"success": True, "tool": name, "action": "updated"}
        
    # Create New
    tool = Tool(
        name=name,
        version=tool_def.get("version", "1.0.0"),
        type="toolset",
        description=tool_def.get("description", ""),
        definition=tool_def,
        docker_image=tool_def.get("docker_image"),
        code=tool_def.get("code"),
        code_base64=tool_def.get("code_base64"),
        doc=tool_def.get("doc"),
        env_vars=tool_def.get("env_vars"),
        requirements=tool_def.get("requirements"),
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


@app.get("/health")
def health_check(session: Session = Depends(get_session)):
    try:
        count = len(session.exec(select(Tool)).all())
        return {"status": "ok", "tools_count": count}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
