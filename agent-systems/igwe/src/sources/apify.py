"""
Apify API Client
Handles actor runs, token rotation, and dataset downloads.
"""
import httpx
import asyncio
import time
import csv
from typing import Dict, Any, Optional, List
from pathlib import Path
from loguru import logger
from ..config import apify_config


class ApifyClient:
    """
    Client for Apify API with token rotation support.
    """
    
    BASE_URL = "https://api.apify.com/v2"
    
    def __init__(self):
        self.tokens = apify_config.tokens
        self.current_token_index = 0
        self.timeout = apify_config.run_timeout_seconds
        
        if not self.tokens:
            raise ValueError("No Apify tokens configured. Set APIFY_API_TOKEN in .env")
        
        logger.info(f"Initialized Apify client with {len(self.tokens)} token(s)")
    
    def _get_next_token(self) -> str:
        """Get next token using round-robin rotation"""
        token = self.tokens[self.current_token_index]
        self.current_token_index = (self.current_token_index + 1) % len(self.tokens)
        return token
    
    async def start_actor_run(
        self,
        actor_id: str,
        input_params: Dict[str, Any],
        token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Start an Apify actor run.
        
        Args:
            actor_id: Actor ID (e.g., "code_crafter~leads-finder")
            input_params: Input parameters for the actor
            token: Optional specific token (uses rotation if not provided)
        
        Returns:
            Dict with run metadata including run_id
        """
        if token is None:
            token = self._get_next_token()
        
        url = f"{self.BASE_URL}/acts/{actor_id}/runs"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        logger.info(f"Starting Apify actor: {actor_id}")
        logger.debug(f"Input params: {input_params}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(url, json=input_params, headers=headers)
                response.raise_for_status()
                
                data = response.json()["data"]
                run_id = data["id"]
                
                logger.info(f"Started actor run: {run_id}")
                return {
                    "run_id": run_id,
                    "actor_id": actor_id,
                    "status": data["status"],
                    "started_at": data["startedAt"],
                    "token_used": token[:20] + "..."  # Log partial token for debugging
                }
            
            except httpx.HTTPStatusError as e:
                logger.error(f"Failed to start actor run: {e.response.status_code} - {e.response.text}")
                raise
            except Exception as e:
                logger.error(f"Error starting actor run: {e}")
                raise
    
    async def wait_for_completion(
        self,
        run_id: str,
        token: str,
        poll_interval: int = 5
    ) -> Dict[str, Any]:
        """
        Wait for an actor run to complete.
        
        Args:
            run_id: The run ID to wait for
            token: The token that was used to start the run
            poll_interval: Seconds between status checks
        
        Returns:
            Dict with final run status and dataset_id
        """
        url = f"{self.BASE_URL}/actor-runs/{run_id}"
        headers = {"Authorization": f"Bearer {token}"}
        
        start_time = time.time()
        logger.info(f"Waiting for run {run_id} to complete...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                # Check timeout
                elapsed = time.time() - start_time
                if elapsed > self.timeout:
                    logger.error(f"Run {run_id} timed out after {self.timeout}s")
                    raise TimeoutError(f"Actor run exceeded {self.timeout}s timeout")
                
                # Get run status
                try:
                    response = await client.get(url, headers=headers)
                    response.raise_for_status()
                    data = response.json()["data"]
                    
                    status = data["status"]
                    logger.debug(f"Run {run_id} status: {status} (elapsed: {int(elapsed)}s)")
                    
                    if status == "SUCCEEDED":
                        dataset_id = data["defaultDatasetId"]
                        logger.info(f"Run {run_id} completed successfully. Dataset: {dataset_id}")
                        return {
                            "run_id": run_id,
                            "status": status,
                            "dataset_id": dataset_id,
                            "finished_at": data.get("finishedAt"),
                            "stats": data.get("stats", {})
                        }
                    
                    elif status in ["FAILED", "TIMED-OUT", "ABORTED"]:
                        logger.error(f"Run {run_id} ended with status: {status}")
                        raise RuntimeError(f"Actor run failed with status: {status}")
                    
                    # Still running, wait and retry
                    await asyncio.sleep(poll_interval)
                
                except httpx.HTTPStatusError as e:
                    logger.error(f"Error checking run status: {e.response.status_code}")
                    raise
    
    async def download_dataset_csv(
        self,
        dataset_id: str,
        token: str,
        output_path: Optional[Path] = None
    ) -> Path:
        """
        Download dataset as CSV.
        
        Args:
            dataset_id: The dataset ID
            token: API token
            output_path: Optional path to save CSV (defaults to temp file)
        
        Returns:
            Path to downloaded CSV file
        """
        url = f"{self.BASE_URL}/datasets/{dataset_id}/items?format=csv"
        headers = {"Authorization": f"Bearer {token}"}
        
        if output_path is None:
            output_path = Path(f"/tmp/apify_dataset_{dataset_id}.csv")
        
        logger.info(f"Downloading dataset {dataset_id} to {output_path}")
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                
                # Save to file
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(response.content)
                
                # Count rows
                with open(output_path, 'r', encoding='utf-8') as f:
                    row_count = sum(1 for _ in csv.reader(f)) - 1  # Exclude header
                
                logger.info(f"Downloaded {row_count} rows to {output_path}")
                return output_path
            
            except httpx.HTTPStatusError as e:
                logger.error(f"Failed to download dataset: {e.response.status_code}")
                raise
            except Exception as e:
                logger.error(f"Error downloading dataset: {e}")
                raise
    
    async def run_and_download(
        self,
        actor_id: str,
        input_params: Dict[str, Any],
        output_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Convenience method: Start actor, wait for completion, download CSV.
        
        Returns:
            Dict with run metadata and csv_path
        """
        # Start run
        token = self._get_next_token()
        run_result = await self.start_actor_run(actor_id, input_params, token)
        run_id = run_result["run_id"]
        
        # Wait for completion
        completion_result = await self.wait_for_completion(run_id, token)
        dataset_id = completion_result["dataset_id"]
        
        # Download CSV
        csv_path = await self.download_dataset_csv(dataset_id, token, output_path)
        
        return {
            **run_result,
            **completion_result,
            "csv_path": str(csv_path)
        }
    
    def get_actor_info(self, actor_id: str) -> Dict[str, Any]:
        """Get information about which actor this is and expected input format"""
        actor_configs = {
            "code_crafter~leads-finder": {
                "name": "Leads Finder (Actor 1)",
                "description": "Scrapes Apollo for business professionals",
                "sample_input": {
                    "searchTerm": "law firm partners",
                    "location": "Texas, United States",
                    "maxResults": 100
                }
            },
            "pipelinelabs~lead-scraper-apollo-zoominfo-lusha-ppe": {
                "name": "Lead Scraper (Actor 2)",
                "description": "Multi-source lead scraper",
                "sample_input": {
                    "personTitles": ["Owner", "Managing Partner"],
                    "organizationIndustryTagIds": ["5567cd4773696439b10b23ba"],
                    "organizationNumEmployeesRanges": ["21-50", "51-100"],
                    "personLocations": ["Texas, United States"],
                    "contactEmailStatus": ["verified"],
                    "page": 1,
                    "perPage": 100
                }
            }
        }
        
        return actor_configs.get(actor_id, {
            "name": actor_id,
            "description": "Unknown actor",
            "sample_input": {}
        })


# Convenience functions for common operations

async def run_actor_with_rotation(
    actor_id: str,
    input_params: Dict[str, Any],
    output_path: Optional[Path] = None
) -> Dict[str, Any]:
    """Run an actor with automatic token rotation"""
    client = ApifyClient()
    return await client.run_and_download(actor_id, input_params, output_path)


async def test_connection() -> bool:
    """Test Apify connection with first available token"""
    client = ApifyClient()
    token = client.tokens[0]
    
    url = f"{client.BASE_URL}/users/me"
    headers = {"Authorization": f"Bearer {token}"}
    
    async with httpx.AsyncClient(timeout=10.0) as http_client:
        try:
            response = await http_client.get(url, headers=headers)
            response.raise_for_status()
            user_data = response.json()["data"]
            logger.info(f"Apify connection successful. User: {user_data.get('username')}")
            return True
        except Exception as e:
            logger.error(f"Apify connection failed: {e}")
            return False
