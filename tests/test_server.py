import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

import server
from cookidoo_service import CookidooService, CookidooSettings, load_cookidoo_settings
from schemas import CustomRecipe

RECIPE = {
    "name": "Cookies",
    "ingredients": ["200 g flour", "100 g butter"],
    "steps": ["Mix 20 sec/speed 4", "Bake 12 min at 180°C"],
    "servings": 6,
    "prep_time": 15,
    "total_time": 30,
    "hints": None,
}


@pytest.fixture
def service(monkeypatch):
    svc = CookidooService(CookidooSettings(email="a@b.c", password="x"))
    for name in (
        "login",
        "search_recipes",
        "get_recipe_details",
        "list_custom_recipes",
        "get_custom_recipe",
        "create_custom_recipe",
        "update_custom_recipe",
    ):
        monkeypatch.setattr(svc, name, AsyncMock())
    monkeypatch.setattr(server, "_cookidoo_service", svc)
    return svc


async def call(tool, **args):
    async with Client(server.mcp) as client:
        result = await client.call_tool(tool, args)
        return result.content[0].text


async def test_all_tools_registered():
    async with Client(server.mcp) as client:
        names = {t.name for t in await client.list_tools()}
        prompts = {p.name for p in await client.list_prompts()}
    assert names == {
        "connect_to_cookidoo",
        "search_recipes",
        "get_recipe_details",
        "list_custom_recipes",
        "get_custom_recipe",
        "generate_recipe_structure",
        "upload_custom_recipe",
        "update_custom_recipe",
    }
    assert prompts == {"create_thermomix_recipe"}


async def test_generate_recipe_structure_round_trips_to_upload(service):
    service.create_custom_recipe.return_value = SimpleNamespace(
        name="Cookies", id="01ABC", url="https://cookidoo.fr/created-recipes/fr-FR/01ABC"
    )
    generated = await call(
        "generate_recipe_structure",
        name="Cookies",
        ingredients="200 g flour, 100 g butter",
        steps="1. Mix 20 sec/speed 4\n2) Bake 12 min at 180°C",
        servings=6,
        prep_time=15,
        total_time=30,
    )
    assert json.loads(generated) == RECIPE

    text = await call("upload_custom_recipe", recipe_json=generated)
    assert "01ABC" in text
    service.create_custom_recipe.assert_awaited_once_with(CustomRecipe(**RECIPE))


async def test_prep_time_cannot_exceed_total_time(service):
    with pytest.raises(ToolError, match="prep_time"):
        await call(
            "generate_recipe_structure",
            name="x",
            ingredients="a",
            steps="b",
            prep_time=40,
            total_time=30,
        )


async def test_upload_rejects_invalid_json(service):
    with pytest.raises(ToolError, match="Invalid recipe data"):
        await call("upload_custom_recipe", recipe_json="{not json")
    service.create_custom_recipe.assert_not_awaited()


async def test_search_splits_ingredients(service):
    service.search_recipes.return_value = SimpleNamespace(
        total=1, recipes=[SimpleNamespace(name="Gratin", id="r1", url="https://x/r1")]
    )
    text = await call("search_recipes", ingredients="chicken, zucchini")
    assert "Gratin" in text and "r1" in text
    assert service.search_recipes.await_args.kwargs["ingredients"] == ["chicken", "zucchini"]


async def test_search_requires_criteria(service):
    with pytest.raises(ToolError):
        await call("search_recipes")


async def test_get_recipe_details_formats_steps_and_times(service):
    service.get_recipe_details.return_value = SimpleNamespace(
        id="r1",
        name="Soup",
        serving_size=4,
        active_time=600,
        total_time=1800,
        difficulty="easy",
        utensils=[],
        ingredients=[SimpleNamespace(name="carrots", description="300 g", preparation="sliced")],
        step_groups=[
            SimpleNamespace(
                title="", recipe_steps=[SimpleNamespace(formatted_text="Cook <b>20 min</b>")]
            )
        ],
        notes=[],
        url="https://x/r1",
    )
    text = await call("get_recipe_details", recipe_id="r1")
    assert "Total time: 30 min" in text
    assert "  - 300 g carrots, sliced" in text
    assert "1. Cook 20 min" in text


async def test_get_custom_recipe_returns_editable_json(service):
    service.get_custom_recipe.return_value = SimpleNamespace(
        name="Cookies",
        ingredients=RECIPE["ingredients"],
        instructions=[RECIPE["steps"][0], SimpleNamespace(text=RECIPE["steps"][1])],
        serving_size=6,
        active_time=900,
        total_time=1800,
        hints=[],
        url="https://x",
    )
    text = await call("get_custom_recipe", recipe_id="01ABC")
    assert json.loads(text.split("\n\n", 1)[1]) == RECIPE


async def test_prompt_inserts_dish():
    async with Client(server.mcp) as client:
        result = await client.get_prompt(
            "create_thermomix_recipe", {"dish": "Risotto", "language": "fr"}
        )
    text = result.messages[0].content.text
    assert '"Risotto"' in text and "[" not in text.splitlines()[2]


def test_settings_from_env(monkeypatch):
    monkeypatch.setattr("cookidoo_service.load_dotenv", lambda: None)
    monkeypatch.setenv("COOKIDOO_EMAIL", "a@b.c")
    monkeypatch.setenv("COOKIDOO_PASSWORD", "x")
    monkeypatch.setenv("COOKIDOO_DEVICE", "tm7")
    assert load_cookidoo_settings().device.value == "TM7"

    monkeypatch.setenv("COOKIDOO_DEVICE", "TM99")
    with pytest.raises(ValueError, match="COOKIDOO_DEVICE"):
        load_cookidoo_settings()

    monkeypatch.delenv("COOKIDOO_PASSWORD")
    with pytest.raises(ValueError, match="Missing"):
        load_cookidoo_settings()
