"""
Guided Cooking Settings

Converts structured step settings to and from the Cookidoo annotations that preset time,
temperature, speed and direction on the Thermomix.
"""

from cookidoo_api import CookidooInstruction, CookidooTemperatureSetting, CookidooTTSAnnotation
from pydantic import ValidationError

from schemas import PLACEHOLDER, Step, StepSettings

_WORDS = {
    "fr": {"speed": "vitesse", "soft": "vitesse mijotage", "reverse": "sens inverse"},
    "en": {"speed": "speed", "soft": "stirring speed", "reverse": "reverse"},
}


def _words(language: str) -> dict[str, str]:
    return _WORDS.get(language.split("-")[0].lower(), _WORDS["en"])


def format_time(seconds: int) -> str:
    hours, rest = divmod(seconds, 3600)
    minutes, seconds = divmod(rest, 60)
    parts = [(hours, "h"), (minutes, "min"), (seconds, "sec")]
    return " ".join(f"{value} {unit}" for value, unit in parts if value)


def render(settings: StepSettings, language: str) -> str:
    """Settings as written in the step, e.g. "3 min/120°C/vitesse 1"."""
    words = _words(language)
    parts = [format_time(settings.time)]
    if settings.temperature == "varoma":
        parts.append("Varoma")
    elif settings.temperature is not None:
        parts.append(f"{settings.temperature}°C")
    if settings.reverse:
        parts.append(words["reverse"])
    parts.append(
        words["soft"] if settings.speed == "soft" else f"{words['speed']} {settings.speed}"
    )
    return "/".join(parts)


def to_instruction(step: str | Step, language: str) -> str | CookidooInstruction:
    """A step as sent to Cookidoo, with its settings as guided-cooking annotations."""
    if isinstance(step, str):
        return step
    text, annotations = step.text, []
    for settings in step.settings:
        slot = render(settings, language)
        text = text.replace(PLACEHOLDER, slot, 1)
        temperature = None
        if settings.temperature == "varoma":
            temperature = CookidooTemperatureSetting("varoma", None)
        elif settings.temperature is not None:
            temperature = CookidooTemperatureSetting(settings.temperature, "C")
        annotations.append(
            CookidooTTSAnnotation(
                slot=slot,
                time=settings.time,
                temperature=temperature,
                speed=settings.speed,
                direction="CCW" if settings.reverse else None,
            )
        )
    return CookidooInstruction(text, annotations=annotations)


def _settings(annotation: CookidooTTSAnnotation) -> StepSettings | None:
    temperature = str(annotation.temperature.value).lower() if annotation.temperature else None
    try:
        return StepSettings(
            time=annotation.time,
            temperature=temperature,
            speed=annotation.speed,
            reverse=annotation.direction == "CCW",
        )
    except ValidationError:
        return None


def from_instruction(instruction: str | CookidooInstruction) -> str | Step:
    """A step read from Cookidoo, in the format accepted by CustomRecipe."""
    if isinstance(instruction, str):
        return instruction
    found = []
    for annotation in instruction.annotations:
        if isinstance(annotation, CookidooTTSAnnotation) and (settings := _settings(annotation)):
            found.append((annotation.slot, settings))
    text, rebuilt, settings_list, start = instruction.text, "", [], 0
    found.sort(key=lambda item: text.find(item[0]))
    for slot, settings in found:
        position = text.find(slot, start)
        if position < 0:
            continue
        rebuilt += text[start:position] + PLACEHOLDER
        settings_list.append(settings)
        start = position + len(slot)
    if not settings_list:
        return instruction.text
    return Step(text=rebuilt + text[start:], settings=settings_list)
