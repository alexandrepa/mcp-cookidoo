import pytest
from cookidoo_api import (
    CookidooCustomAnnotation,
    CookidooInstruction,
    CookidooTemperatureSetting,
    CookidooTTSAnnotation,
)
from pydantic import ValidationError

from guided import format_time, from_instruction, render, to_instruction
from schemas import CustomRecipe, Step, StepSettings

SAUTE = Step(
    text="Ajouter l'huile et faire revenir {settings}, sans le gobelet doseur.",
    settings=[StepSettings(time=180, temperature="120", speed="1")],
)
SAUTE_TTS = CookidooTTSAnnotation(
    slot="3 min/120°C/vitesse 1",
    time=180,
    temperature=CookidooTemperatureSetting("120", "C"),
    speed="1",
)


def test_format_time():
    assert format_time(5) == "5 sec"
    assert format_time(90) == "1 min 30 sec"
    assert format_time(5400) == "1 h 30 min"


def test_render_in_french_and_english():
    simmer = StepSettings(time=1200, temperature="100", speed="soft", reverse=True)
    assert render(simmer, "fr-FR") == "20 min/100°C/sens inverse/vitesse mijotage"
    assert render(simmer, "en-GB") == "20 min/100°C/reverse/stirring speed"
    steam = StepSettings(time=1200, temperature="varoma", speed="1")
    assert render(steam, "de-DE") == "20 min/Varoma/speed 1"


def test_to_instruction():
    assert to_instruction("Servir chaud.", "fr-FR") == "Servir chaud."
    assert to_instruction(SAUTE, "fr-FR") == CookidooInstruction(
        "Ajouter l'huile et faire revenir 3 min/120°C/vitesse 1, sans le gobelet doseur.",
        annotations=[SAUTE_TTS],
    )


def test_to_instruction_varoma_reverse_and_several_settings():
    step = Step(
        text="Mixer {settings}, puis cuire {settings}.",
        settings=[
            StepSettings(time=10, speed="4"),
            StepSettings(time=1200, temperature="varoma", speed="soft", reverse=True),
        ],
    )
    instruction = to_instruction(step, "fr-FR")
    assert (
        instruction.text
        == "Mixer 10 sec/vitesse 4, puis cuire 20 min/Varoma/sens inverse/vitesse mijotage."
    )
    assert instruction.annotations[1] == CookidooTTSAnnotation(
        slot="20 min/Varoma/sens inverse/vitesse mijotage",
        time=1200,
        temperature=CookidooTemperatureSetting("varoma", None),
        speed="soft",
        direction="CCW",
    )


def test_from_instruction_round_trips():
    assert from_instruction("Servir chaud.") == "Servir chaud."
    assert from_instruction(to_instruction(SAUTE, "fr-FR")) == SAUTE


def test_from_instruction_keeps_text_of_other_annotations():
    instruction = CookidooInstruction(
        "Mettre le gruyère et râper 5 sec/vitesse 10.",
        annotations=[
            CookidooCustomAnnotation("INGREDIENT", "gruyère"),
            CookidooTTSAnnotation("5 sec/vitesse 10", time=5, speed="10"),
        ],
    )
    assert from_instruction(instruction) == Step(
        text="Mettre le gruyère et râper {settings}.",
        settings=[StepSettings(time=5, speed="10")],
    )
    plain = CookidooInstruction("Mettre le gruyère.", annotations=[instruction.annotations[0]])
    assert from_instruction(plain) == "Mettre le gruyère."


def test_from_instruction_skips_unsupported_settings():
    odd = CookidooTTSAnnotation("5 sec/vitesse 12", time=5, speed="12")
    assert from_instruction(CookidooInstruction("Râper 5 sec/vitesse 12.", annotations=[odd])) == (
        "Râper 5 sec/vitesse 12."
    )


@pytest.mark.parametrize(
    "settings",
    [
        {"time": 10, "speed": "12"},
        {"time": 10, "speed": "4", "temperature": "130"},
        {"time": 0, "speed": "4"},
        {"time": 10, "speed": "4", "power": "high"},
    ],
)
def test_invalid_settings_are_rejected(settings):
    with pytest.raises(ValidationError):
        StepSettings(**settings)


def test_placeholders_must_match_settings():
    with pytest.raises(ValidationError, match="placeholder"):
        Step(text="Mixer.", settings=[StepSettings(time=10, speed="4")])
    with pytest.raises(ValidationError, match="step object"):
        CustomRecipe(name="x", ingredients=["a"], steps=["Mixer {settings}."])
