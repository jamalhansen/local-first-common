from datetime import date

from local_first_common.obsidian import (
    append_to_daily_note,
    find_vault_root,
    format_notes_for_llm,
    get_daily_note_path,
    get_week_dates,
    load_daily_notes_for_week,
    parse_frontmatter,
    parse_frontmatter_text,
    read_body,
    render_obsidian_template,
    split_frontmatter,
)


class TestFrontmatter:
    def test_basic(self):
        assert parse_frontmatter_text("---\ntitle: A\ntags: [x]\n---\nBody\n") == (
            {"title": "A", "tags": ["x"]},
            "Body\n",
        )

    def test_no_frontmatter_returns_text_unchanged(self):
        assert parse_frontmatter_text("# Heading\n\nText") == ({}, "# Heading\n\nText")

    def test_horizontal_rule_in_body_is_kept(self):
        text = "---\ntitle: A\n---\nIntro\n\n---\n\nAfter the rule\n"
        assert parse_frontmatter_text(text)[1] == "Intro\n\n---\n\nAfter the rule\n"

    def test_dashes_inside_a_value_do_not_close_the_block(self):
        text = "---\nnote: a\n  ---b\n---\nBody"
        assert parse_frontmatter_text(text) == ({"note": "a ---b"}, "Body")

    def test_dot_terminator(self):
        assert parse_frontmatter_text("---\na: 1\n...\nBody") == ({"a": 1}, "Body")

    def test_bom_and_crlf(self):
        assert parse_frontmatter_text("﻿---\r\na: 1\r\n---\r\nBody") == ({"a": 1}, "Body")

    def test_empty_block(self):
        assert parse_frontmatter_text("---\n---\nBody") == ({}, "Body")

    def test_unclosed_block_is_not_frontmatter(self):
        assert split_frontmatter("---\na: 1\nno close") is None

    def test_invalid_yaml_keeps_body(self):
        assert parse_frontmatter_text("---\na: [unclosed\n---\nBody") == ({}, "Body")

    def test_non_mapping_yaml(self):
        assert parse_frontmatter_text("---\n- a\n- b\n---\nBody") == ({}, "Body")

    def test_split_preserves_raw_yaml_for_rewrites(self):
        text = "---\nTitle: A  # comment\n---\n\nBody"
        raw, body = split_frontmatter(text)
        assert f"---\n{raw}---\n{body}" == text

    def test_file_helpers(self, tmp_path):
        p = tmp_path / "n.md"
        p.write_text("---\na: 1\n---\nBody", encoding="utf-8")
        assert parse_frontmatter(p) == {"a": 1}
        assert read_body(p) == "Body"
        assert parse_frontmatter(tmp_path / "missing.md") == {}
        assert read_body(tmp_path / "missing.md") == ""


class TestFindVaultRoot:
    def test_uses_env_var(self, monkeypatch, tmp_path):
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
        assert find_vault_root() == tmp_path

    def test_discovers_obsidian_dir(self, monkeypatch, tmp_path):
        monkeypatch.delenv("OBSIDIAN_VAULT_PATH", raising=False)
        (tmp_path / ".obsidian").mkdir()
        monkeypatch.chdir(tmp_path)
        assert find_vault_root() == tmp_path

    def test_falls_back_to_cwd(self, monkeypatch, tmp_path):
        monkeypatch.delenv("OBSIDIAN_VAULT_PATH", raising=False)
        monkeypatch.chdir(tmp_path)
        assert find_vault_root() == tmp_path


class TestGetDailyNotePath:
    def test_returns_dated_md_path(self, tmp_path):
        d = date(2026, 3, 10)
        path = get_daily_note_path(tmp_path, d)
        assert path == tmp_path / "2026-03-10.md"

    def test_respects_subdir(self, tmp_path):
        d = date(2026, 3, 10)
        path = get_daily_note_path(tmp_path, d, subdir="Timeline")
        assert path == tmp_path / "Timeline" / "2026-03-10.md"


class TestGetWeekDates:
    def test_returns_seven_dates(self):
        dates = get_week_dates(date(2026, 3, 10))
        assert len(dates) == 7

    def test_starts_on_monday(self):
        dates = get_week_dates(date(2026, 3, 10))  # Tuesday
        assert dates[0].weekday() == 0  # Monday

    def test_ends_on_sunday(self):
        dates = get_week_dates(date(2026, 3, 10))
        assert dates[-1].weekday() == 6  # Sunday

    def test_monday_input_returns_same_monday(self):
        monday = date(2026, 3, 9)
        dates = get_week_dates(monday)
        assert dates[0] == monday


class TestRenderObsidianTemplate:
    def test_date_format_yyyy_mm_dd(self):
        result = render_obsidian_template("{{date:YYYY-MM-DD}}", date(2026, 3, 10))
        assert result == "2026-03-10"

    def test_date_format_iso_week(self):
        result = render_obsidian_template("{{date:YYYY-[W]W}}", date(2026, 3, 10))
        assert "W" in result

    def test_yesterday(self):
        result = render_obsidian_template("{{yesterday}}", date(2026, 3, 10))
        assert result == "2026-03-09"

    def test_tomorrow(self):
        result = render_obsidian_template("{{tomorrow}}", date(2026, 3, 10))
        assert result == "2026-03-11"


class TestAppendToDailyNote:
    def test_creates_new_note_with_content(self, tmp_path):
        note_path = tmp_path / "2026-03-10.md"
        append_to_daily_note(note_path, "## Thoughts\n\n- idea one\n")
        assert note_path.exists()
        assert "idea one" in note_path.read_text()

    def test_appends_to_existing_note_with_separator(self, tmp_path):
        note_path = tmp_path / "2026-03-10.md"
        note_path.write_text("---\ndate: 2026-03-10\n---\n\nExisting content.\n")
        append_to_daily_note(note_path, "## New Section\n\n- new item\n")
        text = note_path.read_text()
        assert "Existing content." in text
        assert "---" in text
        assert "new item" in text

    def test_creates_parent_dirs(self, tmp_path):
        note_path = tmp_path / "Timeline" / "2026-03-10.md"
        append_to_daily_note(note_path, "content")
        assert note_path.exists()

    def test_renders_template_for_new_note(self, tmp_path):
        template = tmp_path / "template.md"
        template.write_text("---\ndate: {{date:YYYY-MM-DD}}\n---\n\n")
        note_path = tmp_path / "2026-03-10.md"
        append_to_daily_note(note_path, "## Content\n\n- item\n", template_path=template)
        text = note_path.read_text()
        assert "2026-03-10" in text


class TestLoadDailyNotesForWeek:
    def test_loads_existing_notes(self, tmp_path):
        (tmp_path / "2026-03-09.md").write_text("---\n---\n\nMonday content")
        (tmp_path / "2026-03-10.md").write_text("---\n---\n\nTuesday content")
        dates = [date(2026, 3, 9), date(2026, 3, 10), date(2026, 3, 11)]
        notes = load_daily_notes_for_week(tmp_path, dates)
        assert len(notes) == 2
        assert any("Monday" in n["content"] for n in notes)

    def test_skips_missing_dates(self, tmp_path):
        dates = [date(2026, 3, 9), date(2026, 3, 10)]
        notes = load_daily_notes_for_week(tmp_path, dates)
        assert notes == []

    def test_note_has_date_and_content_keys(self, tmp_path):
        (tmp_path / "2026-03-10.md").write_text("---\n---\n\nContent here")
        notes = load_daily_notes_for_week(tmp_path, [date(2026, 3, 10)])
        assert "date" in notes[0]
        assert "content" in notes[0]


class TestFormatNotesForLlm:
    def test_includes_date_headers(self):
        notes = [
            {"date": date(2026, 3, 9), "content": "Monday stuff"},
            {"date": date(2026, 3, 10), "content": "Tuesday stuff"},
        ]
        result = format_notes_for_llm(notes)
        assert "2026-03-09" in result
        assert "2026-03-10" in result
        assert "Monday stuff" in result
