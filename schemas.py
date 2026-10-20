"""
Recipe Schemas

Pydantic models for custom recipe data validation.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

PLACEHOLDER = "{settings}"

Speed = Literal[
    "soft", "0.5", "1", "1.5", "2", "2.5", "3", "3.5", "4", "4.5", "5",
    "5.5", "6", "6.5", "7", "7.5", "8", "8.5", "9", "9.5", "10",
]  # fmt: skip
Temperature = Literal[
    "37", "40", "45", "50", "55", "60", "65", "70", "75", "80",
    "85", "90", "95", "98", "100", "105", "110", "115", "120", "varoma",
]  # fmt: skip


class StepSettings(BaseModel):
    """Thermomix settings preset on the machine for one action of a step."""

    model_config = ConfigDict(extra="forbid")

    time: int = Field(..., description="Duration in seconds", ge=1, le=43200)
    temperature: Temperature | None = Field(
        default=None, description='Temperature in °C, or "varoma"; omit for no heating'
    )
    speed: Speed = Field(..., description='Speed, "soft" being the stirring speed (mijotage)')
    reverse: bool = Field(default=False, description="Reverse blade direction")


class Step(BaseModel):
    """A recipe step with Thermomix settings preset on the machine."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(
        ...,
        min_length=1,
        description=(
            f"Step text with one {PLACEHOLDER} placeholder per entry of settings, replaced "
            f'by the written settings, e.g. "Add the oil and sauté {PLACEHOLDER}."'
        ),
    )
    settings: list[StepSettings] = Field(..., min_length=1)

    @model_validator(mode="after")
    def check_placeholders(self) -> "Step":
        if self.text.count(PLACEHOLDER) != len(self.settings):
            raise ValueError(
                f"the text must contain one {PLACEHOLDER} placeholder per entry of settings "
                f"({len(self.settings)})"
            )
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
        description="Cooking steps: plain text, or a Step with settings preset on the Thermomix",
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
        return self

    @model_validator(mode="after")
    def check_times(self) -> "CustomRecipe":
        if self.prep_time > self.total_time:
            raise ValueError("prep_time must not exceed total_time")
        return self
