from unittest.mock import patch

from local_first_common.text import is_english, looks_like_article, strip_wikilinks


class TestIsEnglish:
    def test_english_text_returns_true(self):
        text = "This is a post about building local-first AI tools with Python and DuckDB."
        assert is_english(text) is True

    def test_non_english_text_returns_false(self):
        # Japanese — clearly not English
        text = "これはPythonとDuckDBを使ったローカルファーストAIツールの構築についての投稿です。"
        assert is_english(text) is False

    def test_german_text_returns_false(self):
        text = "Dies ist ein Beitrag über den Aufbau von lokalen KI-Werkzeugen mit Python."
        assert is_english(text) is False

    def test_fails_open_on_langdetect_exception(self):
        from langdetect.lang_detect_exception import LangDetectException
        # detect is imported lazily inside is_english, so we patch at the source module
        with patch("langdetect.detect", side_effect=LangDetectException(0, "no features")):
            assert is_english("???") is True

    def test_fails_open_when_langdetect_missing(self):
        import builtins
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "langdetect":
                raise ImportError("no module named langdetect")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            assert is_english("some text") is True


class TestStripWikilinks:
    def test_alias_form(self):
        assert strip_wikilinks("[[local-first-common|local AI]]") == "local AI"

    def test_plain_link(self):
        assert strip_wikilinks("[[Python]]") == "Python"

    def test_multiple_links(self):
        result = strip_wikilinks("See [[Obsidian|Obsidian app]] and [[Python]]")
        assert result == "See Obsidian app and Python"

    def test_no_links_unchanged(self):
        text = "Plain text with no wikilinks."
        assert strip_wikilinks(text) == text

    def test_mixed_content(self):
        result = strip_wikilinks("Read [[The Content Curator|this post]] for details.")
        assert result == "Read this post for details."

    def test_nested_pipe_in_alias(self):
        # Alias is everything after the last pipe — outer alias wins
        result = strip_wikilinks("[[Page|Alias Text]]")
        assert result == "Alias Text"


class TestLooksLikeArticle:
    def test_long_text_is_article(self):
        text = " ".join(["word"] * 300)
        assert looks_like_article(text) is True

    def test_short_text_is_not_article(self):
        assert looks_like_article("Just a short snippet.") is False

    def test_exactly_min_words_is_article(self):
        text = " ".join(["word"] * 200)
        assert looks_like_article(text) is True

    def test_custom_min_words(self):
        text = " ".join(["word"] * 50)
        assert looks_like_article(text, min_words=50) is True
        assert looks_like_article(text, min_words=51) is False
