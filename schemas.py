"""
Recipe Schemas

Pydantic models for custom recipe data validation.
"""

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
    steps: list[str] = Field(..., description="List of cooking steps/instructions", min_length=1)
    servings: int = Field(default=4, description="Number of servings", ge=1, le=20)
    prep_time: int = Field(default=30, description="Preparation time in minutes", ge=1, le=1440)
    total_time: int = Field(default=60, description="Total cooking time in minutes", ge=1, le=1440)
    hints: list[str] | None = Field(default=None, description="Optional cooking tips or hints")

    @model_validator(mode="after")
    def check_times(self) -> "CustomRecipe":
        if self.prep_time > self.total_time:
            raise ValueError("prep_time must not exceed total_time")
        return self
