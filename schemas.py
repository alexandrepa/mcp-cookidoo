"""
Recipe Schemas

Pydantic models for custom recipe data validation.
"""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Discriminator, Field, Tag, model_validator

PLACEHOLDER = "{settings}"
MAX_TIME = 359940  # 99 h 59 min, the longest duration Cookidoo accepts

Speed = Literal[
    "soft", "0.5", "1", "1.5", "2", "2.5", "3", "3.5", "4", "4.5", "5",
    "5.5", "6", "6.5", "7", "7.5", "8", "8.5", "9", "9.5", "10",
]  # fmt: skip
SteamingSpeed = Literal["soft", "0.5", "1", "1.5", "2", "2.5", "3", "3.5", "4", "4.5", "5"]
Temperature = Literal[
    "37", "40", "45", "50", "55", "60", "65", "70", "75", "80",
    "85", "90", "95", "98", "100", "105", "110", "115", "120",
]  # fmt: skip
ManualTemperature = Literal[
    "37", "40", "45", "50", "55", "60", "65", "70", "75", "80",
    "85", "90", "95", "98", "100", "105", "110", "115", "120", "varoma",
]  # fmt: skip
BrowningTemperature = Literal["140", "145", "150", "155", "160"]

_SPEED = 'Speed, "soft" being the stirring speed (mijotage)'
_TIME = "Duration in seconds"


class _Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ManualSettings(_Settings):
    """Time, temperature and speed, the default when mode is omitted."""

    mode: Literal["manual"] = "manual"
    time: int = Field(..., description=_TIME, ge=1, le=MAX_TIME)
    temperature: ManualTemperature | None = Field(
        default=None, description='Temperature in °C, or "varoma"; omit for no heating'
    )
    speed: Speed = Field(..., description=_SPEED)
    reverse: bool = Field(default=False, description="Reverse blade direction")


class DoughSettings(_Settings):
    """Dough mode (kneading)."""

    mode: Literal["dough"]
    time: int = Field(..., description=_TIME, ge=1, le=MAX_TIME)


class BrowningSettings(_Settings):
    """Browning mode (high temperature, TM6/TM7)."""

    mode: Literal["browning"]
    time: int = Field(..., description=_TIME, ge=1, le=1800)
    temperature: BrowningTemperature = Field(..., description="Temperature in °C")
    power: Literal["gentle", "intense"]


class SteamingSettings(_Settings):
    """Steaming mode."""

    mode: Literal["steaming"]
    time: int = Field(..., description=_TIME, ge=1, le=MAX_TIME)
    speed: SteamingSpeed = Field(..., description=_SPEED)
    reverse: bool = Field(default=False, description="Reverse blade direction")
    accessory: Literal["varoma", "simmering_basket", "varoma_and_simmering_basket"] = "varoma"


class TurboSettings(_Settings):
    """Turbo pulses."""

    mode: Literal["turbo"]
    time: Literal[0.5, 1, 2] = Field(
        ..., description="Duration of each pulse in seconds: 0.5, 1 or 2"
    )
    pulses: int = Field(default=1, description="Number of pulses", ge=1, le=10)


class RiceCookerSettings(_Settings):
    """Rice cooker mode, without settings."""

    mode: Literal["rice_cooker"]


class WarmUpSettings(_Settings):
    """Warm-up mode (no duration: it keeps warm until stopped)."""

    mode: Literal["warm_up"]
    temperature: Temperature = Field(..., description="Temperature in °C")
    speed: Speed = Field(..., description=_SPEED)


class BlendSettings(_Settings):
    """Blend mode."""

    mode: Literal["blend"]
    time: int = Field(..., description=_TIME, ge=1, le=MAX_TIME)
    speed: Speed = Field(..., description=_SPEED)


def _mode(value: Any) -> str:
    if isinstance(value, dict):
        return value.get("mode", "manual")
    return getattr(value, "mode", "manual")


StepSettings = Annotated[
    Annotated[ManualSettings, Tag("manual")]
    | Annotated[DoughSettings, Tag("dough")]
    | Annotated[BrowningSettings, Tag("browning")]
    | Annotated[SteamingSettings, Tag("steaming")]
    | Annotated[TurboSettings, Tag("turbo")]
    | Annotated[RiceCookerSettings, Tag("rice_cooker")]
    | Annotated[WarmUpSettings, Tag("warm_up")]
    | Annotated[BlendSettings, Tag("blend")],
    Discriminator(_mode),
]


class IngredientLink(BaseModel):
    """Part of a step text highlighted as one of the recipe's ingredients."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(..., min_length=1, description='Words of the step text, e.g. "les oignons"')
    ingredient: str = Field(..., min_length=1, description="The ingredient line, exactly as listed")


class Step(BaseModel):
    """A recipe step with Thermomix settings preset on the machine and/or ingredient links."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(
        ...,
        min_length=1,
        description=(
            f"Step text with one {PLACEHOLDER} placeholder per entry of settings, replaced "
            f'by the written settings, e.g. "Add the oil and sauté {PLACEHOLDER}."'
        ),
    )
    settings: list[StepSettings] = Field(default_factory=list)
    ingredients: list[IngredientLink] = Field(
        default_factory=list,
        description="Ingredient mentions in the text (first occurrence) to link to the list",
    )

    @model_validator(mode="after")
    def check_placeholders(self) -> "Step":
        if not (self.settings or self.ingredients):
            raise ValueError("a step object needs settings or ingredients; else use plain text")
        if self.text.count(PLACEHOLDER) != len(self.settings):
            raise ValueError(
                f"the text must contain one {PLACEHOLDER} placeholder per entry of settings "
                f"({len(self.settings)})"
            )
        for link in self.ingredients:
            if link.text not in self.text.replace(PLACEHOLDER, "\0"):
                raise ValueError(f"ingredient link text {link.text!r} is not in the step text")
        return self


class CustomRecipe(BaseModel):
    """Model for a custom recipe to be created on Cookidoo."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Chocolate Chip Cookies",
                "ingredients": [
                    "200g flour",
                    "100g butter",
                    "100g sugar",
                    "1 egg",
                    "100g chocolate chips",
                ],
                "steps": [
                    "Mix butter and sugar until creamy",
                    "Add egg and mix well",
                    "Add flour and chocolate chips",
                    "Bake at 180°C for 12 minutes",
                ],
                "servings": 6,
                "prep_time": 15,
                "total_time": 30,
                "hints": ["Don't overmix the dough", "Cookies will firm up as they cool"],
            }
        }
    )

    name: str = Field(..., description="Recipe name", min_length=1, max_length=200)
    ingredients: list[str] = Field(
        ..., description="List of ingredients with quantities", min_length=1
    )
    steps: list[str | Step] = Field(
        ...,
        description="Cooking steps: plain text, or a Step with machine settings and links",
        min_length=1,
    )
    servings: int = Field(default=4, description="Number of servings", ge=1, le=20)
    prep_time: int = Field(default=30, description="Preparation time in minutes", ge=1, le=1440)
    total_time: int = Field(default=60, description="Total cooking time in minutes", ge=1, le=1440)
    hints: list[str] | None = Field(default=None, description="Optional cooking tips or hints")

    @model_validator(mode="after")
    def check_plain_steps(self) -> "CustomRecipe":
        for number, step in enumerate(self.steps, 1):
            if isinstance(step, str) and PLACEHOLDER in step:
                raise ValueError(
                    f"Step {number}: {PLACEHOLDER} needs a step object with its settings"
                )
            for link in [] if isinstance(step, str) else step.ingredients:
                if link.ingredient not in self.ingredients:
                    raise ValueError(
                        f"Step {number}: {link.ingredient!r} is not in the ingredient list"
                    )
        return self

    @model_validator(mode="after")
    def check_times(self) -> "CustomRecipe":
        if self.prep_time > self.total_time:
            raise ValueError("prep_time must not exceed total_time")
        return self
