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
# Tool  (supports 'api', 'mcp', 'skill', and the new 'docker' type)
# ---------------------------------------------------------------------------
class Tool(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    version: str
    type: str  # 'api', 'mcp', 'skill', or 'docker'
    description: str
    definition: dict = Field(sa_column=Column(JSON))  # Stores the full JSON schema

    # Skill-specific fields: SKILL.md body and bundled files
    body: Optional[str] = Field(default=None)           # Markdown instructions body
    skill_files: Optional[dict] = Field(default=None, sa_column=Column(JSON))

    # Docker-specific fields (for type='docker')
    docker_image: Optional[str] = Field(default=None)   # custom image; None = use default
    code: Optional[str] = Field(default=None)            # executable Python code
    code_base64: Optional[str] = Field(default=None)     # base64-encoded code

    owner_id: Optional[int] = Field(default=None, foreign_key="user.id")
    owner: Optional[User] = Relationship(back_populates="tools")

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    downloads: int = Field(default=0)
