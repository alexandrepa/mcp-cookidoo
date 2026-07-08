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
            localization = self._api_client.localization
            # Extract base domain from the URL (e.g., "https://cookidoo.fr/foundation/fr-FR" -> "https://cookidoo.fr")
            url_parts = localization.url.split("/")
            base_url = f"{url_parts[0]}//{url_parts[2]}"  # protocol + domain
            locale = localization.language 
            
            # Headers for the undocumented API (cookidoo-api >= 0.17)
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
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
    
    @property
    def api_client(self) -> Optional[Cookidoo]:
        """Get the current API client instance."""
        return self._api_client
