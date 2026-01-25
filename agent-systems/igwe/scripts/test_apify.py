"""
Test Apify Integration
Tests the complete Apify workflow: connect, run actor, download, import.
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from src.sources.apify import ApifyClient, test_connection
from src.sources.param_rotator import ParamRotator
from src.ingestion.apify_adapter import ApifyLeadAdapter
from src.config import apify_config


async def test_1_connection():
    """Test 1: Verify Apify API connection"""
    logger.info("=" * 60)
    logger.info("TEST 1: Apify Connection")
    logger.info("=" * 60)
    
    success = await test_connection()
    
    if success:
        logger.info("✅ TEST 1 PASSED: Connection successful")
    else:
        logger.error("❌ TEST 1 FAILED: Connection failed")
        return False
    
    return True


async def test_2_actor_info():
    """Test 2: Get actor information"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 2: Actor Information")
    logger.info("=" * 60)
    
    client = ApifyClient()
    
    for actor_id in apify_config.actors:
        info = client.get_actor_info(actor_id)
        logger.info(f"\nActor: {actor_id}")
        logger.info(f"  Name: {info['name']}")
        logger.info(f"  Description: {info['description']}")
    
    logger.info("✅ TEST 2 PASSED: Actor info retrieved")
    return True


def test_3_param_rotation():
    """Test 3: Parameter rotation logic"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 3: Parameter Rotation")
    logger.info("=" * 60)
    
    rotator = ParamRotator()
    
    # Test Actor 1 params
    logger.info("\nGenerating params for Actor 1:")
    params1 = rotator.get_next_params_actor1()
    logger.info(f"  Search term: {params1['searchTerm']}")
    logger.info(f"  Location: {params1['location']}")
    logger.info(f"  Max results: {params1['maxResults']}")
    
    # Test Actor 2 params
    logger.info("\nGenerating params for Actor 2:")
    params2 = rotator.get_next_params_actor2()
    logger.info(f"  Titles: {params2['personTitles']}")
    logger.info(f"  Locations: {params2['personLocations']}")
    logger.info(f"  Size ranges: {params2['organizationNumEmployeesRanges']}")
    
    # Test hash generation
    hash1 = rotator.generate_param_hash(params1)
    hash2 = rotator.generate_param_hash(params2)
    logger.info(f"\nParam hash 1: {hash1}")
    logger.info(f"Param hash 2: {hash2}")
    
    logger.info("✅ TEST 3 PASSED: Parameter rotation working")
    return True


def test_4_field_mapping():
    """Test 4: CSV field mapping"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 4: Field Mapping")
    logger.info("=" * 60)
    
    adapter = ApifyLeadAdapter()
    
    # Test Actor 2 row mapping
    sample_row = {
        "fullName": "John Doe",
        "email": "john@example.com",
        "position": "Managing Partner",
        "phone": "+1 (555) 123-4567",
        "linkedinUrl": "https://linkedin.com/in/johndoe",
        "orgName": "Doe & Associates",
        "orgWebsite": "https://doelaw.com",
        "orgSize": "21-50",
        "orgIndustry": "['Legal Services']",
        "city": "Austin",
        "state": "Texas",
        "country": "United States"
    }
    
    logger.info("\nSample Actor 2 row:")
    for k, v in sample_row.items():
        logger.info(f"  {k}: {v}")
    
    mapped = adapter.map_actor2_row(sample_row)
    
    logger.info("\nMapped lead:")
    for k, v in mapped.items():
        if k != 'metadata':
            logger.info(f"  {k}: {v}")
    
    # Validate mapping
    assert mapped['first_name'] == "John"
    assert mapped['last_name'] == "Doe"
    assert mapped['email'] == "john@example.com"
    assert mapped['company_name'] == "Doe & Associates"
    assert mapped['industry'] == "Legal Services"
    assert mapped['employee_size'] == "35"  # Midpoint of 21-50
    
    logger.info("✅ TEST 4 PASSED: Field mapping correct")
    return True


async def test_5_run_actor_minimal():
    """Test 5: Run actor with minimal test params (LIVE TEST - uses quota)"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 5: Run Actor (LIVE TEST)")
    logger.info("=" * 60)
    logger.warning("⚠️  This test will consume Apify credits")
    
    response = input("Run live Apify test? (y/n): ")
    if response.lower() != 'y':
        logger.info("⏭️  TEST 5 SKIPPED: User declined")
        return True
    
    client = ApifyClient()
    rotator = ParamRotator()
    
    # Use Actor 2 with minimal params
    actor_id = apify_config.actors[1] if len(apify_config.actors) > 1 else apify_config.actors[0]
    
    # Minimal params for quick test
    if "pipelinelabs" in actor_id:
        params = {
            "personTitles": ["Owner"],
            "personLocations": ["Austin, Texas, United States"],
            "organizationNumEmployeesRanges": ["20-50"],
            "contactEmailStatus": ["verified"],
            "page": 1,
            "perPage": 5  # Only 5 results for testing
        }
    else:
        params = {
            "searchTerm": "law firm owner",
            "location": "Austin, Texas",
            "maxResults": 5
        }
    
    logger.info(f"\nRunning actor: {actor_id}")
    logger.info(f"Params: {params}")
    
    try:
        # Run actor
        result = await client.run_and_download(actor_id, params)
        
        logger.info(f"\n✅ Actor run completed:")
        logger.info(f"  Run ID: {result['run_id']}")
        logger.info(f"  Dataset ID: {result['dataset_id']}")
        logger.info(f"  CSV Path: {result['csv_path']}")
        
        # Test CSV loading
        adapter = ApifyLeadAdapter()
        csv_path = Path(result['csv_path'])
        
        if csv_path.exists():
            leads = adapter.process_csv(csv_path, actor_id)
            logger.info(f"\n✅ CSV processed:")
            logger.info(f"  Total leads: {len(leads)}")
            
            if leads:
                logger.info(f"\nFirst lead sample:")
                for k, v in list(leads[0].items())[:10]:
                    logger.info(f"  {k}: {v}")
            
            # Cleanup
            csv_path.unlink()
        
        logger.info("✅ TEST 5 PASSED: Live actor run successful")
        return True
    
    except Exception as e:
        logger.error(f"❌ TEST 5 FAILED: {e}")
        return False


async def main():
    """Run all tests"""
    logger.info("Starting Apify Integration Tests\n")
    
    results = []
    
    # Test 1: Connection
    results.append(await test_1_connection())
    
    # Test 2: Actor info
    results.append(await test_2_actor_info())
    
    # Test 3: Param rotation
    results.append(test_3_param_rotation())
    
    # Test 4: Field mapping
    results.append(test_4_field_mapping())
    
    # Test 5: Live run (optional)
    results.append(await test_5_run_actor_minimal())
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    passed = sum(results)
    total = len(results)
    logger.info(f"Passed: {passed}/{total}")
    
    if passed == total:
        logger.info("✅ ALL TESTS PASSED")
    else:
        logger.error(f"❌ {total - passed} TESTS FAILED")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
