import pytest
from cookidoo_api import Cookidoo
from pydantic import ValidationError

from guided import format_time, from_raw, render, to_instruction
from schemas import CustomRecipe, Step

INGREDIENTS = ["1 oignon", "500 g de farine"]


def step(text, *settings, ingredients=()):
    return Step(text=text, settings=list(settings), ingredients=list(ingredients))


def wire(instruction):
    """The step as cookidoo-api sends it to Cookidoo."""
    return Cookidoo._process_recipe_steps([instruction], INGREDIENTS)[0]


def test_format_time():
    assert format_time(5) == "5 sec"
    assert format_time(90) == "1 min 30 sec"
    assert format_time(5400) == "1 h 30 min"
    assert format_time(0.5) == "0.5 sec"


@pytest.mark.parametrize(
    ("settings", "french", "english"),
    [
        (
            {"time": 1200, "temperature": "100", "speed": "soft", "reverse": True},
            "20 min/100°C/sens inverse/vitesse mijotage",
            "20 min/100°C/reverse/stirring speed",
        ),
        ({"time": 1200, "temperature": "varoma", "speed": "1"}, "20 min/Varoma/vitesse 1", None),
        ({"mode": "dough", "time": 120}, "Pétrin/2 min", "Dough mode/2 min"),
        (
            {"mode": "browning", "time": 300, "temperature": "160", "power": "intense"},
            "Rissolage/5 min/160°C/intense",
            "Browning/5 min/160°C/intense",
        ),
        (
            {"mode": "steaming", "time": 1200, "speed": "1", "accessory": "simmering_basket"},
            "Cuisson vapeur/20 min/panier cuisson/vitesse 1",
            "Steaming/20 min/simmering basket/speed 1",
        ),
        (
            {"mode": "turbo", "time": 0.5, "pulses": 3},
            "Turbo/0.5 sec/3 fois",
            "Turbo/0.5 sec/3 times",
        ),
        ({"mode": "rice_cooker"}, "Rice cooker", "Rice cooker"),
        (
            {"mode": "warm_up", "temperature": "65", "speed": "soft"},
            "Réchauffage/65°C/vitesse mijotage",
            "Warm up/65°C/stirring speed",
        ),
        (
            {"mode": "blend", "time": 60, "speed": "10"},
            "Mixage/1 min/vitesse 10",
            "Blend/1 min/speed 10",
        ),
    ],
)
def test_render(settings, french, english):
    parsed = step("{settings}", settings).settings[0]
    assert render(parsed, "fr-FR") == french
    if english:
        assert render(parsed, "en-GB") == english


@pytest.mark.parametrize(
    ("settings", "annotation"),
    [
        (
            {"time": 180, "temperature": "120", "speed": "1"},
            {
                "type": "TTS",
                "data": {"time": 180, "temperature": {"value": "120", "unit": "C"}, "speed": "1"},
            },
        ),
        (
            {"time": 1200, "temperature": "varoma", "speed": "soft", "reverse": True},
            {
                "type": "TTS",
                "data": {
                    "time": 1200,
                    "temperature": {"value": "varoma"},
                    "speed": "soft",
                    "direction": "CCW",
                },
            },
        ),
        ({"mode": "dough", "time": 120}, {"type": "MODE", "name": "dough", "data": {"time": 120}}),
        (
            {"mode": "browning", "time": 300, "temperature": "140", "power": "gentle"},
            {
                "type": "MODE",
                "name": "browning",
                "data": {
                    "time": 300,
                    "temperature": {"value": "140", "unit": "C"},
                    "power": "Gentle",
                },
            },
        ),
        (
            {
                "mode": "steaming",
                "time": 1200,
                "speed": "1",
                "reverse": True,
                "accessory": "varoma_and_simmering_basket",
            },
            {
                "type": "MODE",
                "name": "steaming",
                "data": {
                    "time": 1200,
                    "speed": "1",
                    "direction": "CCW",
                    "accessory": "VaromaAndSimmeringBasket",
                },
            },
        ),
        (
            {"mode": "turbo", "time": 0.5, "pulses": 3},
            {"type": "MODE", "name": "turbo", "data": {"time": 0.5, "pulseCount": 3}},
        ),
        ({"mode": "rice_cooker"}, {"type": "MODE", "name": "rice_cooker", "data": {}}),
        (
            {"mode": "warm_up", "temperature": "65", "speed": "2"},
            {
                "type": "MODE",
                "name": "warm_up",
                "data": {"temperature": {"value": "65", "unit": "C"}, "speed": "2"},
            },
        ),
        (
            {"mode": "blend", "time": 60, "speed": "10"},
            {"type": "MODE", "name": "blend", "data": {"time": 60, "speed": "10"}},
        ),
    ],
)
def test_wire_format_and_round_trip(settings, annotation):
    original = step("Puis {settings}.", settings)
    sent = wire(to_instruction(original, "fr-FR"))
    slot = render(original.settings[0], "fr-FR")
    assert sent["text"] == f"Puis {slot}."
    assert sent["annotations"] == [{**annotation, "position": {"offset": 5, "length": len(slot)}}]
    assert from_raw(sent) == original


def test_plain_steps():
    assert to_instruction("Servir chaud.", "fr-FR") == "Servir chaud."
    assert from_raw("Servir chaud.") == "Servir chaud."
    assert from_raw({"type": "STEP", "text": "Servir chaud."}) == "Servir chaud."


def test_several_settings_and_ingredient_links():
    original = step(
        "Mettre l'oignon, mixer {settings}, puis faire revenir {settings}.",
        {"time": 5, "speed": "5"},
        {"time": 180, "temperature": "120", "speed": "1"},
        ingredients=[{"text": "l'oignon", "ingredient": "1 oignon"}],
    )
    instruction = to_instruction(original, "fr-FR")
    assert instruction.text == (
        "Mettre l'oignon, mixer 5 sec/vitesse 5, puis faire revenir 3 min/120°C/vitesse 1."
    )
    sent = wire(instruction)
    assert sent["annotations"][2] == {
        "type": "INGREDIENT",
        "data": {"description": "1 oignon"},
        "position": {"offset": 7, "length": 8},
    }
    assert from_raw(sent) == original


def test_reads_ingredients_as_cookidoo_stores_them():
    stored = {
        "type": "STEP",
        "text": "Ajouter la farine et pétrir Pétrin/2 min.",
        "annotations": [
            {
                "type": "INGREDIENT",
                "position": {"offset": 8, "length": 9},
                "data": {"description": {"text": "500 g de farine", "annotations": []}},
            },
            {
                "type": "MODE",
                "name": "dough",
                "position": {"offset": 28, "length": 12},
                "data": {"time": 120},
            },
        ],
    }
    assert from_raw(stored) == step(
        "Ajouter la farine et pétrir {settings}.",
        {"mode": "dough", "time": 120},
        ingredients=[{"text": "la farine", "ingredient": "500 g de farine"}],
    )


def test_positions_count_utf16_units():
    stored = {
        "type": "STEP",
        "text": "🔥 Hacher 5 sec/vitesse 5.",
        "annotations": [
            {
                "type": "TTS",
                "position": {"offset": 10, "length": 15},
                "data": {"time": 5, "speed": "5"},
            }
        ],
    }
    assert from_raw(stored) == step("🔥 Hacher {settings}.", {"time": 5, "speed": "5"})


def test_unsupported_annotations_keep_the_text():
    stored = {
        "type": "STEP",
        "text": "Cuire sous vide 1 h/60°C.",
        "annotations": [
            {
                "type": "MODE",
                "name": "sous_vide",
                "position": {"offset": 16, "length": 8},
                "data": {"time": 3600},
            },
            {
                "type": "TTS",
                "position": {"offset": 0, "length": 5},
                "data": {"time": 5, "speed": "12"},
            },
        ],
    }
    assert from_raw(stored) == "Cuire sous vide 1 h/60°C."


def test_same_settings_twice_in_a_step_is_rejected():
    twice = step(
        "Mixer {settings}, puis {settings}.", {"time": 5, "speed": "5"}, {"time": 5, "speed": "5"}
    )
    with pytest.raises(ValueError, match="split the step"):
        to_instruction(twice, "fr-FR")


@pytest.mark.parametrize(
    "settings",
    [
        {"time": 10, "speed": "12"},
        {"time": 10, "speed": "4", "temperature": "130"},
        {"time": 0, "speed": "4"},
        {"time": 360000, "speed": "4"},
        {"time": 10, "speed": "4", "power": "high"},
        {"mode": "browning", "time": 300, "temperature": "120", "power": "gentle"},
        {"mode": "browning", "time": 2700, "temperature": "150", "power": "gentle"},
        {"mode": "steaming", "time": 600, "speed": "6"},
        {"mode": "turbo", "time": 3},
        {"mode": "turbo", "time": 1, "pulses": 11},
        {"mode": "warm_up", "temperature": "65", "speed": "1", "time": 600},
        {"mode": "sous_vide", "time": 3600},
    ],
)
def test_invalid_settings_are_rejected(settings):
    with pytest.raises(ValidationError):
        step("{settings}", settings)


def test_step_checks():
    with pytest.raises(ValidationError, match="placeholder"):
        step("Mixer.", {"time": 10, "speed": "4"})
    with pytest.raises(ValidationError, match="settings or ingredients"):
        step("Mixer.")
    with pytest.raises(ValidationError, match="not in the step text"):
        step("Mixer.", ingredients=[{"text": "farine", "ingredient": "500 g de farine"}])
    with pytest.raises(ValidationError, match="step object"):
        CustomRecipe(name="x", ingredients=["a"], steps=["Mixer {settings}."])
    with pytest.raises(ValidationError, match="ingredient list"):
        CustomRecipe(
            name="x",
            ingredients=["a"],
            steps=[step("Ajouter le sel.", ingredients=[{"text": "le sel", "ingredient": "sel"}])],
        )
