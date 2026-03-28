from datetime import datetime
from local_first_common.models import ContentMetadata


class TestAliasAndDefaults:
    def test_category_alias_loading(self):
        m = ContentMetadata.from_metadata({"Category": "[[Blog Post]]", "status": "published"})
        assert m.category == "[[Blog Post]]"
        assert m.status == "published"

    def test_missing_category_defaults_to_uncategorized(self):
        m = ContentMetadata.from_metadata({"title": "No category here"})
        assert m.category == "uncategorized"

    def test_default_status_is_draft(self):
        m = ContentMetadata.from_metadata({"Category": "[[Find]]"})
        assert m.status == "draft"
        assert isinstance(m.created, datetime)
        assert m.tags == []

    def test_extra_fields_preserved(self):
        m = ContentMetadata.from_metadata({"Category": "[[Blog Post]]", "extra_val": 123})
        assert m.extra_val == 123
        dump = m.to_metadata()
        assert dump["Category"] == "[[Blog Post]]"
        assert dump["extra_val"] == 123

    def test_serialization_round_trip(self):
        m = ContentMetadata(category="[[Newsletter]]", tags=["ai", "local"])
        dump = m.to_metadata()
        assert dump["Category"] == "[[Newsletter]]"
        assert dump["tags"] == ["ai", "local"]
        assert "status" in dump
        assert "created" in dump


class TestCategoryName:
    def test_strips_wikilink_brackets(self):
        m = ContentMetadata(category="[[Newsletter]]")
        assert m.category_name == "Newsletter"

    def test_strips_blog_post_brackets(self):
        m = ContentMetadata(category="[[Blog Post]]")
        assert m.category_name == "Blog Post"

    def test_uncategorized_passthrough(self):
        m = ContentMetadata()
        assert m.category_name == "uncategorized"

    def test_plain_string_passthrough(self):
        m = ContentMetadata(category="newsletter")
        assert m.category_name == "newsletter"


class TestPublishedDateCoercion:
    def test_empty_string_becomes_none(self):
        m = ContentMetadata.from_metadata({"Category": "[[Blog Post]]", "published_date": ""})
        assert m.published_date is None

    def test_whitespace_string_becomes_none(self):
        m = ContentMetadata.from_metadata({"Category": "[[Blog Post]]", "published_date": "   "})
        assert m.published_date is None

    def test_valid_date_string_parses(self):
        m = ContentMetadata.from_metadata({"Category": "[[Blog Post]]", "published_date": "2026-03-01"})
        assert m.published_date is not None
        assert m.published_date.year == 2026

    def test_none_stays_none(self):
        m = ContentMetadata.from_metadata({"Category": "[[Blog Post]]"})
        assert m.published_date is None


class TestTitleCaseNormalization:
    def test_uppercase_Title_accepted(self):
        m = ContentMetadata.from_metadata({"Title": "My Post"})
        assert m.title == "My Post"

    def test_lowercase_title_accepted(self):
        m = ContentMetadata.from_metadata({"title": "My Post"})
        assert m.title == "My Post"

    def test_lowercase_title_wins_over_Title(self):
        """If both present, lowercase wins (standard frontmatter)."""
        m = ContentMetadata.from_metadata({"title": "lowercase", "Title": "Uppercase"})
        assert m.title == "lowercase"

    def test_to_metadata_emits_lowercase_title(self):
        m = ContentMetadata.from_metadata({"Title": "My Post"})
        dump = m.to_metadata()
        assert dump.get("title") == "My Post"
        assert "Title" not in dump


class TestTagsCoercion:
    def test_list_passthrough(self):
        m = ContentMetadata.from_metadata({"Category": "[[Blog Post]]", "tags": ["ai", "python"]})
        assert m.tags == ["ai", "python"]

    def test_bare_string_becomes_list(self):
        m = ContentMetadata.from_metadata({"Category": "[[Blog Post]]", "tags": "ai"})
        assert m.tags == ["ai"]

    def test_empty_string_becomes_empty_list(self):
        m = ContentMetadata.from_metadata({"Category": "[[Blog Post]]", "tags": ""})
        assert m.tags == []

    def test_missing_tags_defaults_to_empty(self):
        m = ContentMetadata.from_metadata({"Category": "[[Blog Post]]"})
        assert m.tags == []


class TestToMetadata:
    def test_omits_uncategorized_default(self):
        """Round-tripping a note without Category must not add Category: uncategorized."""
        m = ContentMetadata.from_metadata({"title": "Plain note"})
        dump = m.to_metadata()
        assert "Category" not in dump

    def test_includes_explicit_category(self):
        m = ContentMetadata.from_metadata({"Category": "[[Newsletter]]"})
        dump = m.to_metadata()
        assert dump["Category"] == "[[Newsletter]]"

    def test_omits_none_fields(self):
        m = ContentMetadata.from_metadata({"Category": "[[Blog Post]]"})
        dump = m.to_metadata()
        assert "published_date" not in dump
        assert "canonical_url" not in dump
