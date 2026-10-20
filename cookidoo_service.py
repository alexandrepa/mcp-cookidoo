"""
Cookidoo Service

Module to encapsulate all cookidoo-api logic for interacting with the Cookidoo platform.
"""

import asyncio
import os
from dataclasses import dataclass

from aiohttp import ClientSession
from cookidoo_api import (
    Cookidoo,
    CookidooConfig,
    CookidooCreateCustomRecipe,
    CookidooCustomRecipe,
    CookidooSearchResult,
    CookidooShoppingRecipeDetails,
    CookidooUpdateCustomRecipe,
    ThermomixMachineType,
)
from cookidoo_api.const import CUSTOM_RECIPES_PATH_ACCEPT
from cookidoo_api.helpers import (
    cookidoo_custom_recipe_from_json,
    cookidoo_search_result_from_json,
    get_localization_options,
)
from dotenv import load_dotenv

from guided import to_instruction
from schemas import CustomRecipe


@dataclass(frozen=True)
class CookidooSettings:
    """Settings loaded from the environment / .env file."""

    email: str
    password: str
    country: str = "fr"
    language: str = "fr-FR"
    device: ThermomixMachineType = ThermomixMachineType.TM6


def load_cookidoo_settings() -> CookidooSettings:
    """
    Load Cookidoo settings from the environment (and .env file if present).

    Returns:
        CookidooSettings: Credentials, localization and default device

    Raises:
        ValueError: If credentials are missing or the device is unknown
    """
    load_dotenv()

    email = os.getenv("COOKIDOO_EMAIL")
    password = os.getenv("COOKIDOO_PASSWORD")
    if not email or not password:
        raise ValueError(
            "Missing Cookidoo credentials. Please set COOKIDOO_EMAIL and "
            "COOKIDOO_PASSWORD in your environment or .env file"
        )

    device = os.getenv("COOKIDOO_DEVICE", "TM6").upper()
    try:
        machine = ThermomixMachineType(device)
    except ValueError:
        valid = ", ".join(m.value for m in ThermomixMachineType)
        raise ValueError(f"Unknown COOKIDOO_DEVICE '{device}'. Use one of: {valid}") from None

    return CookidooSettings(
        email=email,
        password=password,
        country=os.getenv("COOKIDOO_COUNTRY", "fr").lower(),
        language=os.getenv("COOKIDOO_LANGUAGE", "fr-FR"),
        device=machine,
    )


class CookidooService:
    """Service class for managing Cookidoo API interactions."""

    def __init__(self, settings: CookidooSettings):
        self.settings = settings
        self._api_client: Cookidoo | None = None
        self._session: ClientSession | None = None
        self._lock = asyncio.Lock()

    async def login(self) -> Cookidoo:
        """
        Authenticate with Cookidoo and return the API client.

        Raises:
            ValueError: If the configured country/language is not supported
            CookidooException: If authentication fails
        """
        async with self._lock:
            await self._close_session()

            localizations = await get_localization_options(
                country=self.settings.country, language=self.settings.language
            )
            if not localizations:
                raise ValueError(
                    f"No Cookidoo site for country '{self.settings.country}' and "
                    f"language '{self.settings.language}'"
                )

            self._session = ClientSession()
            try:
                client = Cookidoo(
                    session=self._session,
                    cfg=CookidooConfig(
                        email=self.settings.email,
                        password=self.settings.password,
                        localization=localizations[0],
                    ),
                )
                await client.login()
            except BaseException:
                await self._close_session()
                raise

            self._api_client = client
            return client

    async def client(self) -> Cookidoo:
        """Return the authenticated client, logging in on first use."""
        if self._api_client is None:
            return await self.login()
        return self._api_client

    async def _close_session(self) -> None:
        self._api_client = None
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def close(self) -> None:
        """Close the aiohttp session."""
        async with self._lock:
            await self._close_session()

    async def search_recipes(
        self,
        query: str | None = None,
        ingredients: list[str] | None = None,
        max_total_time: int | None = None,
        max_results: int = 10,
    ) -> CookidooSearchResult:
        """
        Search the Cookidoo catalogue. `max_total_time` is in minutes.

        Calls the search endpoint directly rather than Cookidoo.search_recipes: the
        API expects one `ingredients` parameter per ingredient (a comma-joined value
        returns nothing), `limit` rather than `pageSize`, and `languages` to keep
        results in the account's language.
        """
        api = await self.client()
        locale = api.localization.language.split("-")[0]
        params: list[tuple[str, str]] = [("languages", locale)]
        if query:
            params.append(("query", query))
        params += [("ingredients", ingredient) for ingredient in ingredients or []]
        if max_total_time:
            params.append(("totalTime", str(max_total_time * 60)))
        params.append(("limit", str(max_results)))

        await api._ensure_endpoints()
        url = api.api_endpoint / api._path("search:home").format(locale=locale)
        result = await api._request_json("get", url, "search recipes", params=params)
        if not result:
            return CookidooSearchResult(recipes=[], total=0)
        return cookidoo_search_result_from_json(result, api.localization)

    async def get_recipe_details(self, recipe_id: str) -> CookidooShoppingRecipeDetails:
        api = await self.client()
        return await api.get_recipe_details(recipe_id)

    async def list_custom_recipes(self) -> list[CookidooCustomRecipe]:
        api = await self.client()
        return await api.list_custom_recipes()

    async def get_custom_recipe(self, recipe_id: str) -> tuple[CookidooCustomRecipe, list]:
        """
        A custom recipe, with its steps as Cookidoo's raw JSON.

        cookidoo-api parses the recipe but drops annotation fields it does not model (turbo
        pulses, sub-second times), so the steps are read from the same response.
        """
        api = await self.client()
        await api._ensure_endpoints()
        url = api.api_endpoint / api._path("customer-recipes:recipe-details").format(
            **api.localization.__dict__, id=recipe_id
        )
        result = await api._request_json(
            "get", url, "loading custom recipe", headers={"ACCEPT": CUSTOM_RECIPES_PATH_ACCEPT}
        )
        recipe = cookidoo_custom_recipe_from_json(result, api.localization)
        steps = result["recipeContent"].get("instructions") or [
            step if isinstance(step, str) else step.text for step in recipe.instructions
        ]
        return recipe, list(steps)

    async def create_custom_recipe(self, recipe: CustomRecipe) -> CookidooCustomRecipe:
        """Create a brand new custom recipe on the user's account."""
        api = await self.client()
        return await api.create_custom_recipe(
            CookidooCreateCustomRecipe(
                name=recipe.name,
                ingredients=recipe.ingredients,
                instructions=[
                    to_instruction(step, self.settings.language) for step in recipe.steps
                ],
                serving_size=recipe.servings,
                active_time=recipe.prep_time * 60,
                total_time=recipe.total_time * 60,
                tools=[self.settings.device],
                hints=recipe.hints or [],
            )
        )

    async def update_custom_recipe(
        self, recipe_id: str, recipe: CustomRecipe
    ) -> CookidooCustomRecipe:
        """Replace the content of an existing custom recipe."""
        api = await self.client()
        return await api.update_custom_recipe(
            recipe_id,
            CookidooUpdateCustomRecipe(
                name=recipe.name,
                ingredients=recipe.ingredients,
                instructions=[
                    to_instruction(step, self.settings.language) for step in recipe.steps
                ],
                serving_size=recipe.servings,
                active_time=recipe.prep_time * 60,
                total_time=recipe.total_time * 60,
                hints=recipe.hints or [],
            ),
        )

    @property
    def localization_url(self) -> str | None:
        """Base URL of the Cookidoo site, once connected."""
        return self._api_client.localization.url if self._api_client else None
