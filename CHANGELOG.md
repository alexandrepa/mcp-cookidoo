# Changelog

## [1.1.0] - 2026-10-20

### Added
- Guided cooking: a recipe step can be an object whose Thermomix settings are written into its
  text and preset on the machine: manual settings (time, temperature, speed, reverse) and the
  dough, browning, steaming, turbo, rice cooker, warm-up and blend modes, with the limits the
  Cookidoo API accepts. Plain-text steps are unchanged
- Ingredient links: words of a step can be linked to a line of the ingredient list
- `get_custom_recipe` returns steps with settings and links in the same format (read from the
  raw API response, so turbo pulses and sub-second times are kept), so editing a recipe keeps
  them
- The `create_thermomix_recipe` prompt asks for structured steps

## [1.0.0] - 2026-10-20

First stable release, rebuilt on cookidoo-api 0.19 and FastMCP 4.

### Added
- `search_recipes`: search the catalogue by keywords and/or ingredients, with a maximum total time
- `list_custom_recipes`, `get_custom_recipe` and `update_custom_recipe` to read and edit your own recipes
- `create_thermomix_recipe` MCP prompt (English / French) for the guided recipe workflow
- Automatic login on first use; `connect_to_cookidoo` is now optional
- `COOKIDOO_COUNTRY`, `COOKIDOO_LANGUAGE` and `COOKIDOO_DEVICE` settings
- STDIO entrypoint (`uv run server.py`) for Claude Desktop / Claude Code
- Docker image published to `ghcr.io/alexandrepa/mcp-cookidoo`
- Tests and CI

### Changed
- Recipe creation uses cookidoo-api's native custom-recipe API instead of hand-written HTTP calls
- `generate_recipe_structure` accepts lists, and only splits text on new lines, so ingredients like "300 g potatoes, sliced" stay intact
- Tool errors are reported as MCP errors, and tools carry read-only / write annotations
- Requires Python 3.12+; dependencies managed with uv (`pyproject.toml`, `uv.lock`)

### Fixed
- Recipe upload failing with recent cookidoo-api versions (`'Cookidoo' object has no attribute 'auth_data'`)
- TLS certificate verification was disabled
- Debug output on stdout broke the STDIO transport
- Blocking `time.sleep` in async code
- Recipe URLs starting with `https://https://`
- `get_recipe_details` never showed the steps and showed seconds as minutes

## [0.1.0] - 2025-10-12

Initial version: connect, get recipe details, generate and upload custom recipes.

[1.0.0]: https://github.com/alexandrepa/mcp-cookidoo/releases/tag/v1.0.0
