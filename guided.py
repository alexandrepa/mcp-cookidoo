"""
Guided Cooking Settings

Converts structured steps to and from the Cookidoo annotations that preset the Thermomix
(time, temperature, speed, direction, modes) and link ingredient mentions to the list.
"""

from collections.abc import Mapping

from cookidoo_api import (
    CookidooCustomAnnotation,
    CookidooIngredientAnnotation,
    CookidooInstruction,
    CookidooTemperatureSetting,
    CookidooTTSAnnotation,
)
from pydantic import TypeAdapter, ValidationError

from schemas import (
    PLACEHOLDER,
    BlendSettings,
    BrowningSettings,
    DoughSettings,
    IngredientLink,
    ManualSettings,
    RiceCookerSettings,
    SteamingSettings,
    Step,
    StepSettings,
    TurboSettings,
    WarmUpSettings,
)

_WORDS = {
    "fr": {
        "speed": "vitesse",
        "soft": "vitesse mijotage",
        "reverse": "sens inverse",
        "dough": "Pétrin",
        "browning": "Rissolage",
        "gentle": "doux",
        "intense": "intense",
        "steaming": "Cuisson vapeur",
        "varoma": "Varoma",
        "simmering_basket": "panier cuisson",
        "varoma_and_simmering_basket": "Varoma et panier cuisson",
        "turbo": "Turbo",
        "pulses": "fois",
        "rice_cooker": "Rice cooker",
        "warm_up": "Réchauffage",
        "blend": "Mixage",
    },
    "en": {
        "speed": "speed",
        "soft": "stirring speed",
        "reverse": "reverse",
        "dough": "Dough mode",
        "browning": "Browning",
        "gentle": "gentle",
        "intense": "intense",
        "steaming": "Steaming",
        "varoma": "Varoma",
        "simmering_basket": "simmering basket",
        "varoma_and_simmering_basket": "Varoma and simmering basket",
        "turbo": "Turbo",
        "pulses": "times",
        "rice_cooker": "Rice cooker",
        "warm_up": "Warm up",
        "blend": "Blend",
    },
}
_ACCESSORIES = {
    "varoma": "Varoma",
    "simmering_basket": "SimmeringBasket",
    "varoma_and_simmering_basket": "VaromaAndSimmeringBasket",
}
_SETTINGS = TypeAdapter(StepSettings)


def _words(language: str) -> dict[str, str]:
    return _WORDS.get(language.split("-")[0].lower(), _WORDS["en"])


def format_time(seconds: float) -> str:
    if seconds < 1:
        return f"{seconds:g} sec"
    hours, rest = divmod(int(seconds), 3600)
    minutes, seconds = divmod(rest, 60)
    parts = [(hours, "h"), (minutes, "min"), (seconds, "sec")]
    return " ".join(f"{value} {unit}" for value, unit in parts if value)


def render(settings: StepSettings, language: str) -> str:
    """Settings as written in the step, e.g. "3 min/120°C/vitesse 1"."""
    words = _words(language)

    def speed(value: str) -> str:
        return words["soft"] if value == "soft" else f"{words['speed']} {value}"

    match settings:
        case ManualSettings():
            parts = [format_time(settings.time)]
            if settings.temperature == "varoma":
                parts.append("Varoma")
            elif settings.temperature is not None:
                parts.append(f"{settings.temperature}°C")
            parts += [words["reverse"]] if settings.reverse else []
            parts.append(speed(settings.speed))
        case DoughSettings():
            parts = [words["dough"], format_time(settings.time)]
        case BrowningSettings():
            parts = [words["browning"], format_time(settings.time), f"{settings.temperature}°C"]
            parts.append(words[settings.power])
        case SteamingSettings():
            parts = [words["steaming"], format_time(settings.time), words[settings.accessory]]
            parts += [words["reverse"]] if settings.reverse else []
            parts.append(speed(settings.speed))
        case TurboSettings():
            parts = [words["turbo"], format_time(settings.time)]
            parts.append(f"{settings.pulses} {words['pulses']}")
        case RiceCookerSettings():
            parts = [words["rice_cooker"]]
        case WarmUpSettings():
            parts = [words["warm_up"], f"{settings.temperature}°C", speed(settings.speed)]
        case BlendSettings():
            parts = [words["blend"], format_time(settings.time), speed(settings.speed)]
    return "/".join(parts)


def _celsius(value: str) -> dict[str, str]:
    return {"value": value, "unit": "C"}


def _annotation(settings: StepSettings, slot: str):
    """The Cookidoo annotation presetting these settings on the machine."""
    if isinstance(settings, ManualSettings):
        temperature = None
        if settings.temperature == "varoma":
            temperature = CookidooTemperatureSetting("varoma", None)
        elif settings.temperature is not None:
            temperature = CookidooTemperatureSetting(settings.temperature, "C")
        return CookidooTTSAnnotation(
            slot=slot,
            time=settings.time,
            temperature=temperature,
            speed=settings.speed,
            direction="CCW" if settings.reverse else None,
        )
    match settings:
        case DoughSettings():
            data = {"time": settings.time}
        case BrowningSettings():
            power = settings.power.capitalize()
            data = {"time": settings.time, "temperature": _celsius(settings.temperature)}
            data["power"] = power
        case SteamingSettings():
            data = {"time": settings.time, "speed": settings.speed}
            data["direction"] = "CCW" if settings.reverse else "CW"
            data["accessory"] = _ACCESSORIES[settings.accessory]
        case TurboSettings():
            data = {"time": settings.time, "pulseCount": settings.pulses}
        case RiceCookerSettings():
            data = {}
        case WarmUpSettings():
            data = {"temperature": _celsius(settings.temperature), "speed": settings.speed}
        case BlendSettings():
            data = {"time": settings.time, "speed": settings.speed}
    return CookidooCustomAnnotation("MODE", slot, data, settings.mode)


def to_instruction(step: str | Step, language: str) -> str | CookidooInstruction:
    """A step as sent to Cookidoo, with its settings and links as annotations."""
    if isinstance(step, str):
        return step
    text, annotations = step.text, []
    for settings in step.settings:
        slot = render(settings, language)
        position = text.index(PLACEHOLDER)
        if slot in text[:position]:
            raise ValueError(f"{slot!r} is written twice in one step: split the step")
        text = text.replace(PLACEHOLDER, slot, 1)
        annotations.append(_annotation(settings, slot))
    for link in step.ingredients:
        annotations.append(CookidooIngredientAnnotation(link.text, link.ingredient))
    return CookidooInstruction(text, annotations=annotations)


def _span(text: str, position: object) -> tuple[int, int] | None:
    """Python string indices of a Cookidoo position, given in UTF-16 code units."""
    if not isinstance(position, Mapping):
        return None
    offset, length = position.get("offset"), position.get("length")
    if not isinstance(offset, int) or not isinstance(length, int):
        return None
    units, start = 0, None
    for index, char in enumerate(text + "\0"):
        if units == offset:
            start = index
        if start is not None and units == offset + length:
            return start, index
        units += 2 if ord(char) > 0xFFFF else 1
    return None


def _settings(annotation: Mapping) -> StepSettings | None:
    """Structured settings of a TTS or MODE annotation, None when not supported."""
    data = dict(annotation.get("data") or {})
    temperature = data.get("temperature")
    if isinstance(temperature, Mapping):
        temperature = str(temperature.get("value", "")).lower() or None
    if annotation.get("type") == "TTS":
        value = {"time": data.get("time"), "speed": data.get("speed")}
        value["temperature"] = temperature
        value["reverse"] = data.get("direction") == "CCW"
    else:
        value = {"mode": annotation.get("name")}
        accessories = {wire: name for name, wire in _ACCESSORIES.items()}
        for key, raw in data.items():
            match key:
                case "temperature":
                    value[key] = temperature
                case "direction":
                    value["reverse"] = raw == "CCW"
                case "power":
                    value[key] = str(raw).lower()
                case "pulseCount":
                    value["pulses"] = raw
                case "accessory":
                    value[key] = accessories.get(raw, raw)
                case _:
                    value[key] = raw
    try:
        return _SETTINGS.validate_python(value)
    except ValidationError:
        return None


def from_raw(instruction: object) -> str | Step:
    """A step from Cookidoo's raw custom-recipe JSON, in the format accepted by CustomRecipe."""
    if isinstance(instruction, str):
        return instruction
    if not isinstance(instruction, Mapping):
        return ""
    text = str(instruction.get("text", ""))
    found, links = [], []
    for annotation in instruction.get("annotations") or []:
        if not isinstance(annotation, Mapping) or not (
            span := _span(text, annotation.get("position"))
        ):
            continue
        if annotation.get("type") == "INGREDIENT":
            description = (annotation.get("data") or {}).get("description")
            if isinstance(description, Mapping):
                description = description.get("text")
            if isinstance(description, str):
                links.append((span, description))
        elif settings := _settings(annotation):
            found.append((span, settings))
    found.sort(key=lambda item: item[0])
    rebuilt, settings_list, start = "", [], 0
    for (begin, end), settings in found:
        if begin < start:
            continue
        rebuilt += text[start:begin] + PLACEHOLDER
        settings_list.append(settings)
        start = end
    used = [span for span, _ in found]
    ingredients = [
        IngredientLink(text=text[begin:end], ingredient=description)
        for (begin, end), description in sorted(links)
        if not any(begin < e and s < end for s, e in used)
    ]
    if not (settings_list or ingredients):
        return text
    return Step(text=rebuilt + text[start:], settings=settings_list, ingredients=ingredients)
