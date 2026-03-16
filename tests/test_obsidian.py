from datetime import date

from local_first_common.obsidian import (
    find_vault_root,
    get_daily_note_path,
    get_week_dates,
    append_to_daily_note,
    render_obsidian_template,
    load_daily_notes_for_week,
    format_notes_for_llm,
)


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
