"""
Cookidoo Service

Module to encapsulate all cookidoo-api logic for interacting with the Cookidoo platform.
"""

import os
from typing import Optional
from dotenv import load_dotenv
from aiohttp import ClientSession
from cookidoo_api import Cookidoo, CookidooConfig
from cookidoo_api.helpers import (
    get_localization_options,
)
import aiohttp
import time


def load_cookidoo_credentials() -> tuple[str, str]:
    """
    Load Cookidoo credentials from .env file.
    
    Returns:
        tuple[str, str]: Email and password
        
    Raises:
        ValueError: If credentials are not found in environment variables
    """
    load_dotenv()
    
    email = os.getenv("COOKIDOO_EMAIL")
    password = os.getenv("COOKIDOO_PASSWORD")
    
    if not email or not password:
        raise ValueError(
            "Missing Cookidoo credentials. Please set COOKIDOO_EMAIL and "
            "COOKIDOO_PASSWORD in your .env file"
        )
    
    return email, password


class CookidooService:
    """Service class for managing Cookidoo API interactions."""
    
    def __init__(self, email: str, password: str):
        """
        Initialize the Cookidoo service with credentials.
        
        Args:
            email: Cookidoo account email
            password: Cookidoo account password
        """
        self.email = email
        self.password = password
        self._api_client: Optional[Cookidoo] = None
        self._session: Optional[ClientSession] = None
    
    async def login(self) -> Cookidoo:
        """
        Authenticate with Cookidoo and return the API client.
        
        Returns:
            Cookidoo: Authenticated Cookidoo API client
            
        Raises:
            Exception: If authentication fails
        """
        try:
            # Create aiohttp ClientSession with a timeout
            self._session = ClientSession(connector=aiohttp.TCPConnector(verify_ssl=False))
            

            # Create CookidooConfig with credentials
            config = CookidooConfig(
                email=self.email,
                password=self.password,
                localization=(
                    await get_localization_options(country="fr", language="fr-FR")
                )[0],
            )
            
            # Create Cookidoo API client with session and config
            self._api_client = Cookidoo(session=self._session, cfg=config)
            
            # Perform login (no parameters needed - uses config)
            await self._api_client.login()
            
            return self._api_client
            
        except Exception as e:
            # Clean up session if login fails
            if self._session:
                await self._session.close()
            raise Exception(f"Failed to authenticate with Cookidoo: {str(e)}") from e
    
    async def close(self) -> None:
        """Close the aiohttp session."""
        if self._session:
            await self._session.close()
    
    async def create_custom_recipe(
        self,
        name: str,
        ingredients: list[str],
        steps: list[str],
        servings: int = 4,
        prep_time: int = 30,
        total_time: int = 60,
        hints: Optional[list[str]] = None,
    ) -> str:
        """
        Create a completely new custom recipe from scratch using the undocumented API.
        
        Args:
            name: Recipe name
            ingredients: List of ingredient descriptions
            steps: List of cooking step descriptions
            servings: Number of servings (default: 4)
            prep_time: Preparation time in minutes (default: 30)
            total_time: Total cooking time in minutes (default: 60)
            hints: Optional list of hints/tips for the recipe
            
        Returns:
            str: The created recipe ID
            
        Raises:
            Exception: If recipe creation fails
        """
        if not self._api_client or not self._session:
            raise Exception("Not authenticated. Please call login() first.")
        
        try:
            # Get the access token from the authenticated client
            auth_data = self._api_client.auth_data
            if not auth_data:
                raise Exception("No authentication data available")
            
            localization = self._api_client.localization
            # Extract base domain from the URL (e.g., "https://cookidoo.fr/foundation/fr-FR" -> "https://cookidoo.fr")
            url_parts = localization.url.split("/")
            base_url = f"{url_parts[0]}//{url_parts[2]}"  # protocol + domain
            locale = localization.language 
            
            # Headers for the undocumented API
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_client.auth_data.access_token}"
            }
            
            # Use the API client's session to ensure cookies are shared
            api_session = self._api_client._session
        
            
            # Step 1: Create the recipe with just the name
            create_url = f"{base_url}/created-recipes/{locale}"
            create_data = {"recipeName": name}
            
            async with api_session.post(
                create_url, json=create_data, headers=headers
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(
                        f"Failed to create recipe. Status: {response.status}, Error: {error_text}"
                    )
                
                result = await response.json()
                recipe_id = result.get("recipeId")
                
                if not recipe_id:
                    raise Exception("No recipe ID returned from creation")
            
            # Step 2: Update recipe with ingredients
            update_url = f"{base_url}/created-recipes/{locale}/{recipe_id}"
            
            # PATCH requires a complete recipe structure with ALL required fields
            update_data = {
                "name": name,
                "image": None,  # Can be null or match pattern: ^((prod|nonprod)/img/customer-recipe/)?[A-Za-z0-9-_]{1,}.(bmp|jpe|jpeg|jpg|png)$
                "isImageOwnedByUser": False,
                "tools": ["TM6"],
                "yield": {"value": servings, "unitText": "portion"},
                "prepTime": prep_time * 60,  # Convert minutes to seconds
                "cookTime": 0,
                "totalTime": total_time * 60,  # Convert minutes to seconds
                "ingredients": [{"type": "INGREDIENT", "text": ing} for ing in ingredients],
                "instructions": [{"type": "STEP", "text": step} for step in steps],
                "hints": "\n".join(hints) if hints and isinstance(hints, list) else (hints if hints else ""),
                "workStatus": "PRIVATE",
                "recipeMetadata": {
                    "requiresAnnotationsCheck": False
                }
            }
            
            time.sleep(5)

            async with api_session.patch(update_url, json=update_data, headers=headers) as response:
                print(f"  Response Status: {response.status}")
                response_text = await response.text()
                print(f"  Response Body: {response_text}")
                
                if response.status not in [200, 204]:
                    raise Exception(f"Failed to update recipe: {response_text}")
            
            return recipe_id
            
        except Exception as e:
            raise Exception(f"Failed to create custom recipe: {str(e)}") from e

    async def search_recipes(
        self,
        ingredients: list[str],
        query: Optional[str] = None,
        language: Optional[str] = None,
        max_results: int = 5,
    ) -> list[dict]:
        """Search Cookidoo recipes, optionally filtered by ingredients.

        Hits the public search endpoint (``{base}/search/{locale}``) using the
        authenticated session's cookies.

        Note on encoding: each ingredient is sent as its OWN query parameter
        (``ingredients=chicken&ingredients=zucchini``). Comma-joining them into a
        single value (``ingredients=chicken,zucchini``) makes the API treat it as
        one ingredient named "chicken,zucchini" and return zero results -- hence
        the list-of-tuples below.

        Args:
            ingredients: Ingredients to filter by, e.g. ["chicken", "zucchini"].
            query: Optional free-text query.
            language: Optional locale (e.g. "en", "fr"); defaults to the account's.
            max_results: Maximum number of recipes to return.

        Returns:
            list[dict]: Each with keys ``id``, ``name``, ``url``, ``total_time``.
        """
        if not self._api_client:
            raise Exception("Not authenticated. Please call login() first.")

        localization = self._api_client.localization
        locale = language or localization.language.split("-")[0]
        base_url = str(self._api_client.api_endpoint)

        params: list[tuple[str, str]] = []
        if query:
            params.append(("query", query))
        for ingredient in ingredients:
            if ingredient and ingredient.strip():
                params.append(("ingredients", ingredient.strip()))
        if max_results:
            params.append(("pageSize", str(max_results)))

        headers = {"Accept": "application/json"}
        search_url = f"{base_url}/search/{locale}"

        async with self._api_client._session.get(
            search_url, params=params, headers=headers
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                raise Exception(
                    f"Search failed. Status: {response.status}, Error: {error_text}"
                )
            data = await response.json()

        recipes: list[dict] = []
        for hit in (data.get("data") or data.get("recipes") or [])[:max_results]:
            recipe_id = hit.get("id") or hit.get("objectID")
            if not recipe_id:
                continue
            recipes.append(
                {
                    "id": recipe_id,
                    "name": hit.get("title") or hit.get("name") or recipe_id,
                    "url": f"{base_url}/recipes/recipe/{localization.language}/{recipe_id}",
                    "total_time": hit.get("totalTime"),
                }
            )
        return recipes

    @property
    def api_client(self) -> Optional[Cookidoo]:
        """Get the current API client instance."""
        return self._api_client
