import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from cookidoo_api import CookidooInstruction
from fastmcp import Client
from fastmcp.exceptions import ToolError

import server
from cookidoo_service import CookidooService, CookidooSettings, load_cookidoo_settings
from guided import to_instruction
from schemas import CustomRecipe, Step

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


async def test_server_reports_project_version():
    async with Client(server.mcp) as client:
        assert client.server_info.version == server.VERSION == "1.1.0"


async def test_generate_recipe_structure_round_trips_to_upload(service):
    service.create_custom_recipe.return_value = SimpleNamespace(
        name="Cookies", id="01ABC", url="https://cookidoo.fr/created-recipes/fr-FR/01ABC"
    )
    generated = await call(
        "generate_recipe_structure",
        name="Cookies",
        ingredients="200 g flour\n100 g butter",
        steps="1. Mix 20 sec/speed 4\n2) Bake 12 min at 180°C",
        servings=6,
        prep_time=15,
        total_time=30,
    )
    assert json.loads(generated) == RECIPE

    text = await call("upload_custom_recipe", recipe_json=generated)
    assert "01ABC" in text
    service.create_custom_recipe.assert_awaited_once_with(CustomRecipe(**RECIPE))


async def test_generate_keeps_commas_and_accepts_lists(service):
    generated = await call(
        "generate_recipe_structure",
        name="Quiche",
        ingredients=["300 g potatoes, sliced", "2 eggs"],
        steps="1. Slice 5 sec/speed 5\n- Bake 30 min, 180°C",
        hints="Serve warm, with salad",
    )
    recipe = json.loads(generated)
    assert recipe["ingredients"] == ["300 g potatoes, sliced", "2 eggs"]
    assert recipe["steps"] == ["Slice 5 sec/speed 5", "Bake 30 min, 180°C"]
    assert recipe["hints"] == ["Serve warm, with salad"]


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
        instructions=[RECIPE["steps"][0], CookidooInstruction(RECIPE["steps"][1])],
        serving_size=6,
        active_time=900,
        total_time=1800,
        hints=[],
        url="https://x",
    )
    text = await call("get_custom_recipe", recipe_id="01ABC")
    assert json.loads(text.split("\n\n", 1)[1]) == RECIPE


SAUTE = {
    "text": "Faire revenir {settings}.",
    "settings": [{"time": 180, "temperature": "120", "speed": "1", "reverse": False}],
}


async def test_generate_accepts_structured_steps(service):
    generated = await call(
        "generate_recipe_structure",
        name="Soupe",
        ingredients=["1 oignon"],
        steps=["1. Éplucher l'oignon.", SAUTE],
    )
    assert json.loads(generated)["steps"] == ["Éplucher l'oignon.", SAUTE]


async def test_generate_rejects_invalid_settings(service):
    with pytest.raises(ToolError):
        await call(
            "generate_recipe_structure",
            name="Soupe",
            ingredients=["1 oignon"],
            steps=[{"text": "Mixer {settings}.", "settings": [{"time": 10, "speed": "12"}]}],
        )


async def test_get_custom_recipe_returns_structured_steps(service):
    service.get_custom_recipe.return_value = SimpleNamespace(
        name="Soupe",
        ingredients=["1 oignon"],
        instructions=["Éplucher.", to_instruction(Step(**SAUTE), "fr-FR")],
        serving_size=4,
        active_time=600,
        total_time=1800,
        hints=[],
        url="https://x",
    )
    recipe = json.loads((await call("get_custom_recipe", recipe_id="01ABC")).split("\n\n", 1)[1])
    assert recipe["steps"] == ["Éplucher.", SAUTE]
    plain = {"text": "Mixer {settings}.", "settings": [{"time": 10, "speed": "4"}]}
    service.get_custom_recipe.return_value.instructions = [to_instruction(Step(**plain), "fr-FR")]
    read = (await call("get_custom_recipe", recipe_id="01ABC")).split("\n\n", 1)[1]
    generated = await call(
        "generate_recipe_structure", name="Soupe", ingredients="a", steps=[plain]
    )
    assert json.loads(read)["steps"] == json.loads(generated)["steps"]


async def test_service_sends_settings_in_account_language(monkeypatch):
    api = SimpleNamespace(create_custom_recipe=AsyncMock(), update_custom_recipe=AsyncMock())
    svc = CookidooService(CookidooSettings(email="a@b.c", password="x", language="fr-FR"))
    monkeypatch.setattr(svc, "client", AsyncMock(return_value=api))
    recipe = CustomRecipe(name="Soupe", ingredients=["1 oignon"], steps=["Éplucher.", SAUTE])
    await svc.create_custom_recipe(recipe)
    await svc.update_custom_recipe("01ABC", recipe)
    expected = ["Éplucher.", to_instruction(Step(**SAUTE), "fr-FR")]
    assert expected[1].text == "Faire revenir 3 min/120°C/vitesse 1."
    assert api.create_custom_recipe.await_args.args[0].instructions == expected
    assert api.update_custom_recipe.await_args.args[1].instructions == expected


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
