from local_first_common.text import looks_like_article, strip_wikilinks


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
