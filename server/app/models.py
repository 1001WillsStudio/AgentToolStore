from typing import Optional, List
from datetime import datetime
from sqlmodel import Field, SQLModel, Relationship
from sqlalchemy import Column, JSON


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    email: Optional[str] = Field(default="")
    password_hash: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    tools: List["Tool"] = Relationship(back_populates="owner")


# ---------------------------------------------------------------------------
# Tool  (toolset type only — mcp and skill are established external ecosystems)
# ---------------------------------------------------------------------------
class Tool(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    version: str
    type: str = "toolset"
    description: str
    definition: dict = Field(sa_column=Column(JSON))  # Stores the full JSON schema

    # Toolset fields
    code: Optional[str] = Field(default=None)            # toolset.py source code
    code_base64: Optional[str] = Field(default=None)     # base64-encoded code
    doc: Optional[str] = Field(default=None)              # doc.md content
    docker_image: Optional[str] = Field(default=None)     # custom Docker image
    env_vars: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    requirements: Optional[str] = Field(default=None)    # pip requirements (one per line)

    owner_id: Optional[int] = Field(default=None, foreign_key="user.id")
    owner: Optional[User] = Relationship(back_populates="tools")

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    downloads: int = Field(default=0)


