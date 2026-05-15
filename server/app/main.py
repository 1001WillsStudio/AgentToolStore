from datetime import datetime, timedelta
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
    email: str
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
    expected by the CLI client.
    """
    tools = session.exec(select(Tool)).all()
    
    index_list = []
    for tool in tools:
        tool_data = tool.definition.copy()
        tool_data["name"] = tool.name
        tool_data["description"] = tool.description
        tool_data["type"] = tool.type
        tool_data["owner"] = tool.owner.username if tool.owner else "unknown"
        index_list.append(tool_data)
        
    return index_list

@app.post("/publish")
def publish_tool(
    tool_def: dict, 
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Authenticated endpoint to publish a tool.
    """
    name = tool_def.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="Tool name required")
        
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
        existing.updated_at = datetime.utcnow()
        session.add(existing)
        session.commit()
        return {"success": True, "tool": name, "action": "updated"}
        
    # Create New
    tool = Tool(
        name=name,
        version=tool_def.get("version", "1.0.0"),
        type=tool_def.get("type", "api"),
        description=tool_def.get("description", ""),
        definition=tool_def,
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
