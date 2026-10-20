# Cookidoo MCP Server

An MCP (Model Context Protocol) server for interacting with the Thermomix Cookidoo platform, built with [FastMCP](https://gofastmcp.com).

> **Disclaimer:** This is an unofficial project. The developers are not affiliated with, endorsed by, or connected to Cookidoo, Vorwerk, Thermomix, or any of their subsidiaries or trademarks.

## Features

- **Recipe Search**: Find recipes by keywords and/or ingredients, with a maximum total time
- **Recipe Details**: Fetch ingredients, steps and times of any Cookidoo recipe
- **Custom Recipes**: List, read, create and update the recipes on your own account
- **Guided Cooking**: Steps can carry Thermomix settings (time, temperature, speed, reverse), preset on the machine
- **Guided Prompt**: `create_thermomix_recipe` walks the assistant through writing a proper Thermomix recipe (EN / FR)

## Setup

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.example .env   # then fill in your Cookidoo credentials
```

| Variable | Default | Description |
| --- | --- | --- |
| `COOKIDOO_EMAIL` | — | Cookidoo account email (required) |
| `COOKIDOO_PASSWORD` | — | Cookidoo account password (required) |
| `COOKIDOO_COUNTRY` | `fr` | Cookidoo site country code (`fr`, `de`, `gb`, `es`, …) |
| `COOKIDOO_LANGUAGE` | `fr-FR` | Site language |
| `COOKIDOO_DEVICE` | `TM6` | Thermomix model set on created recipes (`TM5`, `TM6`, `TM7`) |

## Usage

### Claude Code

```bash
claude mcp add cookidoo -- uv run --directory /path/to/mcp-cookidoo server.py
```

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "cookidoo": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/mcp-cookidoo", "server.py"]
    }
  }
}
```

### Docker

A prebuilt image (amd64 / arm64) is published for each release, no Python needed:

```json
{
  "mcpServers": {
    "cookidoo": {
      "command": "docker",
      "args": ["run", "--rm", "-i", "-e", "COOKIDOO_EMAIL", "-e", "COOKIDOO_PASSWORD", "ghcr.io/alexandrepa/mcp-cookidoo:1"],
      "env": {
        "COOKIDOO_EMAIL": "your-email@example.com",
        "COOKIDOO_PASSWORD": "your-password"
      }
    }
  }
}
```

To build it yourself instead: `docker build -t cookidoo-mcp .`

### HTTP / development

```bash
uv run fastmcp run fastmcp.json --transport http   # HTTP server
uv run fastmcp dev inspector fastmcp.json           # MCP Inspector
```

## Available Tools

| Tool | Description |
| --- | --- |
| `connect_to_cookidoo` | Check the configuration / force a fresh login (optional, tools log in automatically) |
| `search_recipes` | Search recipes by query, ingredients and max total time |
| `get_recipe_details` | Get ingredients, steps and times of a recipe by ID |
| `list_custom_recipes` | List the custom recipes on your account |
| `get_custom_recipe` | Get a custom recipe as editable JSON |
| `generate_recipe_structure` | Validate a new recipe and return its JSON |
| `upload_custom_recipe` | Create a custom recipe from that JSON |
| `update_custom_recipe` | Replace an existing custom recipe with that JSON |

## Recipe steps

A step is either plain text, or an object with Thermomix settings preset in guided cooking
and/or ingredient links. The text holds one `{settings}` placeholder per setting, replaced
by the setting written out in the account's language:

```json
{
  "text": "Add the onion and the olive oil, then sauté {settings}.",
  "settings": [{"time": 180, "temperature": "120", "speed": "1", "reverse": true}],
  "ingredients": [{"text": "the onion", "ingredient": "1 onion, halved"}]
}
```

A setting's `mode` selects its fields. The limits are those the Cookidoo API accepts:

| `mode` | Fields | Written as (fr) |
| --- | --- | --- |
| `manual` (default) | `time` (s, up to 99 h 59), `temperature` (optional: `"37"`…`"95"` by 5, `"98"`, `"100"`…`"120"` by 5, or `"varoma"`), `speed`, `reverse` | `3 min/120°C/vitesse 1` |
| `dough` | `time` | `Pétrin/2 min` |
| `browning` | `time` (up to 30 min), `temperature` (`"140"`…`"160"` by 5), `power` (`gentle`, `intense`) | `Rissolage/5 min/160°C/intense` |
| `steaming` | `time`, `speed` (up to `"5"`), `reverse`, `accessory` (`varoma`, `simmering_basket`, `varoma_and_simmering_basket`) | `Cuisson vapeur/20 min/Varoma/vitesse 1` |
| `turbo` | `time` (0.5, 1 or 2 s), `pulses` (1 to 10) | `Turbo/0.5 sec/3 fois` |
| `rice_cooker` | none | `Rice cooker` |
| `warm_up` | `temperature`, `speed` (no time: Cookidoo drops it) | `Réchauffage/65°C/vitesse 2` |
| `blend` | `time`, `speed` | `Mixage/1 min/vitesse 10` |

`speed` is `"soft"` (stirring speed) or `"0.5"` to `"10"` by halves. Cookidoo has no other
mode for custom recipes (sous-vide, slow cooking, fermentation… only exist in catalogue
recipes). It does not check that the modes exist on the devices listed for the recipe.

Modes are written with their name, so the text should not repeat it ("then start
{settings}" rather than "knead {settings}").

`ingredients` links words of the step text (their first occurrence) to a line of the
ingredient list. Invalid settings and links are rejected. `get_custom_recipe` returns steps
in the same format, so a recipe keeps its settings and links when edited.

## Development

```bash
uv run pytest
uv run ruff check . && uv run ruff format .
```

## Acknowledgments

This project is built on top of [cookidoo-api](https://github.com/miaucl/cookidoo-api), which provides the Python interface to the Cookidoo platform. Thanks also to everyone who opened pull requests on this repository — their ideas (search, recipe editing, Docker/STDIO support) shaped this version.

## License

MIT
