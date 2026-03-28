from datetime import datetime
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator

class ContentMetadata(BaseModel):
    """Standard frontmatter metadata for local-first AI tools.

    ``Category`` is an Obsidian wikilink to a template note, e.g. ``[[Newsletter]]``.
    Use ``category_name`` to get the bare name without brackets.

    Notes that lack a ``Category`` field parse without error and get
    ``category = "uncategorized"`` — a sentinel you can query to find notes
    that still need categorising.  The sentinel is intentionally NOT a wikilink
    (there is no ``[[Uncategorized]]`` template).
    """
    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
    )

    category: str = Field("uncategorized", alias="Category")
    status: str = "draft"
    created: Optional[datetime] = Field(default_factory=datetime.now)
    published_date: Optional[datetime] = None
    canonical_url: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    title: Optional[str] = None
    description: Optional[str] = None
    author: List[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _normalize_key_case(cls, data: Any) -> Any:
        """Accept Title/title interchangeably — vault notes vary in capitalisation."""
        if isinstance(data, dict) and "Title" in data and "title" not in data:
            data = dict(data)
            data["title"] = data.pop("Title")
        return data

    @field_validator("published_date", mode="before")
    @classmethod
    def _coerce_empty_date(cls, v: Any) -> Any:
        """Convert empty/whitespace strings to None so Pydantic doesn't choke."""
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @field_validator("tags", mode="before")
    @classmethod
    def _coerce_tags(cls, v: Any) -> Any:
        """Normalise tags to List[str]: a bare string becomes a one-item list."""
        if isinstance(v, str):
            return [v] if v.strip() else []
        return v

    @property
    def category_name(self) -> str:
        """Category without Obsidian wikilink brackets.

        ``"[[Newsletter]]"`` → ``"Newsletter"``
        ``"uncategorized"`` → ``"uncategorized"``
        """
        return self.category.strip("[]")

    @classmethod
    def from_metadata(cls, metadata: Dict[str, Any]) -> "ContentMetadata":
        """Create from a raw frontmatter dict (e.g. from python-frontmatter)."""
        return cls(**metadata)

    def to_metadata(self) -> Dict[str, Any]:
        """Serialise back to a dict suitable for frontmatter writing.

        Omits None values and the default ``"uncategorized"`` category so that
        round-tripping a note that had no Category doesn't pollute it.
        """
        data = self.model_dump(by_alias=True, exclude_none=True)
        if data.get("Category") == "uncategorized":
            data.pop("Category")
        return data
