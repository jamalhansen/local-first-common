"""Tests for local_first_common.personas module."""
import pytest
import yaml

from local_first_common.personas import PersonaBias, PersonaCard, list_personas, load_persona

MINIMAL_PERSONA = {
    "name": "Testus",
    "archetype": "The Tester",
    "domain": "Testing",
    "principle": "Test Everything",
    "lens": "Looks for gaps in coverage.",
    "bias": {"overweights": ["coverage"], "underweights": ["speed"]},
    "evaluation_questions": ["Was everything tested?"],
    "rewards": ["Full coverage"],
    "penalizes": ["Skipped tests"],
    "conflict_signature": "Clashes with nobody.",
    "system_prompt": "You are Testus. Be thorough.",
}


def _write_persona(tmp_path, data: dict) -> None:
    name = data["name"].lower()
    path = tmp_path / f"{name}.yaml"
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f)


class TestPersonaCard:
    def test_valid_persona(self):
        card = PersonaCard(**MINIMAL_PERSONA)
        assert card.name == "Testus"
        assert card.archetype == "The Tester"
        assert card.principle == "Test Everything"

    def test_bias_defaults_to_empty_lists(self):
        data = {**MINIMAL_PERSONA, "bias": {}}
        card = PersonaCard(**data)
        assert card.bias.overweights == []
        assert card.bias.underweights == []

    def test_persona_bias_fields(self):
        bias = PersonaBias(overweights=["a", "b"], underweights=["c"])
        assert bias.overweights == ["a", "b"]
        assert bias.underweights == ["c"]


class TestLoadPersona:
    def test_loads_valid_persona(self, tmp_path):
        _write_persona(tmp_path, MINIMAL_PERSONA)
        card = load_persona("testus", personas_dir=tmp_path)
        assert card.name == "Testus"
        assert card.system_prompt == "You are Testus. Be thorough."

    def test_name_is_case_insensitive(self, tmp_path):
        _write_persona(tmp_path, MINIMAL_PERSONA)
        card = load_persona("TESTUS", personas_dir=tmp_path)
        assert card.name == "Testus"

    def test_missing_persona_raises_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="ghost"):
            load_persona("ghost", personas_dir=tmp_path)

    def test_error_message_lists_available_personas(self, tmp_path):
        _write_persona(tmp_path, MINIMAL_PERSONA)
        with pytest.raises(FileNotFoundError, match="testus"):
            load_persona("ghost", personas_dir=tmp_path)

    def test_missing_dir_raises_file_not_found(self, tmp_path):
        missing = tmp_path / "no_such_dir"
        with pytest.raises(FileNotFoundError):
            load_persona("anyone", personas_dir=missing)

    def test_malformed_yaml_raises(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text("name: [unclosed", encoding="utf-8")
        with pytest.raises(Exception):
            load_persona("bad", personas_dir=tmp_path)


class TestListPersonas:
    def test_empty_dir_returns_empty_list(self, tmp_path):
        result = list_personas(personas_dir=tmp_path)
        assert result == []

    def test_nonexistent_dir_returns_empty_list(self, tmp_path):
        result = list_personas(personas_dir=tmp_path / "missing")
        assert result == []

    def test_lists_all_personas(self, tmp_path):
        second = {**MINIMAL_PERSONA, "name": "Secondus"}
        _write_persona(tmp_path, MINIMAL_PERSONA)
        _write_persona(tmp_path, second)
        cards = list_personas(personas_dir=tmp_path)
        assert len(cards) == 2
        names = [c.name for c in cards]
        assert "Testus" in names
        assert "Secondus" in names

    def test_returns_sorted_by_filename(self, tmp_path):
        alpha = {**MINIMAL_PERSONA, "name": "Alpha"}
        zeta = {**MINIMAL_PERSONA, "name": "Zeta"}
        _write_persona(tmp_path, zeta)
        _write_persona(tmp_path, alpha)
        cards = list_personas(personas_dir=tmp_path)
        assert cards[0].name == "Alpha"
        assert cards[1].name == "Zeta"
