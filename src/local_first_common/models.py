from datetime import datetime
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, ConfigDict

class ContentMetadata(BaseModel):
    """
    Standard frontmatter metadata for local-first AI tools.
    Aligned with Content Format Spec.
    """
    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
    )

    category: str = Field(..., alias="Category")
    status: str = "draft"
    created: Optional[datetime] = Field(default_factory=datetime.now)
    published_date: Optional[datetime] = None
    canonical_url: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    title: Optional[str] = None
    description: Optional[str] = None
    author: List[str] = Field(default_factory=list)
    
    @classmethod
    def from_metadata(cls, metadata: Dict[str, Any]) -> "ContentMetadata":
        """Create a model from a raw dictionary (e.g. from frontmatter)."""
        return cls(**metadata)

    def to_metadata(self) -> Dict[str, Any]:
        """Convert back to a raw dictionary for frontmatter dumping."""
        return self.model_dump(by_alias=True, exclude_none=True)
