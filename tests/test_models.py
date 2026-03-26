from datetime import datetime
from local_first_common.models import ContentMetadata

def test_metadata_alias_loading():
    raw = {
        "Category": "blog post",
        "status": "published",
        "title": "Hello"
    }
    m = ContentMetadata.from_metadata(raw)
    assert m.category == "blog post"
    assert m.status == "published"
    assert m.title == "Hello"

def test_metadata_defaults():
    raw = {"Category": "find"}
    m = ContentMetadata.from_metadata(raw)
    assert m.status == "draft"
    assert isinstance(m.created, datetime)
    assert m.tags == []

def test_metadata_extra_fields():
    raw = {
        "Category": "blog post",
        "extra_val": 123
    }
    m = ContentMetadata.from_metadata(raw)
    assert m.extra_val == 123
    
    dump = m.to_metadata()
    assert dump["Category"] == "blog post"
    assert dump["extra_val"] == 123

def test_metadata_serialization():
    m = ContentMetadata(category="newsletter", tags=["ai", "local"])
    dump = m.to_metadata()
    assert dump["Category"] == "newsletter"
    assert dump["tags"] == ["ai", "local"]
    assert "status" in dump
    assert "created" in dump
