# Cookidoo MCP Server

An MCP (Model Context Protocol) server for interacting with the Thermomix Cookidoo platform, built with `fastmcp`.

> **Disclaimer:** This is an unofficial project. The developers are not affiliated with, endorsed by, or connected to Cookidoo, Vorwerk, Thermomix, or any of their subsidiaries or trademarks.

## Features

- **Authentication**: Connect to your Cookidoo account securely
- **Recipe Details**: Fetch detailed recipe information by ID
- **Recipe Generation**: Structure new custom recipes
- **Recipe Upload**: Upload custom recipes to your Cookidoo account

## Setup

1. **Clone the repository and navigate to the project directory**

2. **Create a virtual environment and activate it:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On macOS/Linux
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure your credentials:**
   ```bash
   cp .env.example .env
   # Edit .env with your Cookidoo credentials
   ```

5. **Run the MCP server:**
   ```bash
   fastmcp run server.py
   ```

### Claude Desktop (Docker)

1. **Build the Docker image:**
   ```bash
   docker build -t cookidoo-mcp .
   ```

2. **Add to Claude Desktop config** (`~/Library/Application Support/Claude/claude_desktop_config.json`):
   ```json
   {
     "mcpServers": {
       "cookidoo": {
         "command": "docker",
         "args": ["run", "--rm", "-i", "-e", "COOKIDOO_EMAIL", "-e", "COOKIDOO_PASSWORD", "cookidoo-mcp"],
         "env": {
           "COOKIDOO_EMAIL": "your-email@example.com",
           "COOKIDOO_PASSWORD": "your-password"
         }
       }
     }
   }
   ```

## Available Tools

- `connect_to_cookidoo` - Authenticate with Cookidoo
- `get_recipe_details` - Get detailed recipe by ID
- `generate_recipe_structure` - Structure a new recipe
- `upload_custom_recipe` - Upload a recipe to Cookidoo

## Acknowledgments

This project is built on top of the [cookidoo-api](https://github.com/miaucl/cookidoo-api), which provides the Python interface to interact with the Cookidoo platform. Special thanks for making this integration possible!

## License

MIT
