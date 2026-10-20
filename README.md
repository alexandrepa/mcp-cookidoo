# Cookidoo MCP Server

An MCP (Model Context Protocol) server for interacting with the Thermomix Cookidoo platform, built with [FastMCP](https://gofastmcp.com).

> **Disclaimer:** This is an unofficial project. The developers are not affiliated with, endorsed by, or connected to Cookidoo, Vorwerk, Thermomix, or any of their subsidiaries or trademarks.

## Features

- **Recipe Search**: Find recipes by keywords and/or ingredients, with a maximum total time
- **Recipe Details**: Fetch ingredients, steps and times of any Cookidoo recipe
- **Custom Recipes**: List, read, create and update the recipes on your own account
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

## Development

```bash
uv run pytest
uv run ruff check . && uv run ruff format .
```

## Acknowledgments

This project is built on top of [cookidoo-api](https://github.com/miaucl/cookidoo-api), which provides the Python interface to the Cookidoo platform. Thanks also to everyone who opened pull requests on this repository — their ideas (search, recipe editing, Docker/STDIO support) shaped this version.

## License

MIT
