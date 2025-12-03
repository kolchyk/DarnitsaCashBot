"""Test script to verify SMS sending during user registration."""

import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path to import from apps
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from libs.common import configure_logging, get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_registration_scenarios() -> None:
    """Test different registration scenarios."""
    settings = get_settings()
    configure_logging(settings.log_level)
    
    api_url = settings.api_gateway_url
    test_telegram_id = 999999999  # Test Telegram ID
    test_phone = "380992227160"
    
    logger.info("=" * 60)
    logger.info("Testing user registration SMS scenarios")
    logger.info("=" * 60)
    logger.info(f"API Gateway URL: {api_url}")
    logger.info(f"TurboSMS enabled: {settings.turbosms_enabled}")
    logger.info(f"TurboSMS token configured: {bool(settings.turbosms_token)}")
    logger.info("")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Scenario 1: New user registration WITH phone number
        logger.info("Scenario 1: New user registration WITH phone number")
        logger.info("-" * 60)
        try:
            response = await client.post(
                f"{api_url}/bot/users",
                json={
                    "telegram_id": test_telegram_id,
                    "phone_number": test_phone,
                    "locale": "uk",
                },
            )
            response.raise_for_status()
            result = response.json()
            logger.info(f"✅ User created: {result}")
            logger.info(f"   Has phone: {result.get('has_phone')}")
            logger.info("   Expected: SMS should be sent (new user with phone)")
            logger.info("")
        except Exception as e:
            logger.error(f"❌ Error: {e}")
            logger.info("")
        
        # Wait a bit for background task
        await asyncio.sleep(2)
        
        # Scenario 2: Same user registration again (should NOT send SMS)
        logger.info("Scenario 2: Same user registration again (existing user)")
        logger.info("-" * 60)
        try:
            response = await client.post(
                f"{api_url}/bot/users",
                json={
                    "telegram_id": test_telegram_id,
                    "phone_number": test_phone,
                    "locale": "uk",
                },
            )
            response.raise_for_status()
            result = response.json()
            logger.info(f"✅ User updated: {result}")
            logger.info("   Expected: SMS should NOT be sent (existing user)")
            logger.info("")
        except Exception as e:
            logger.error(f"❌ Error: {e}")
            logger.info("")
        
        await asyncio.sleep(2)
        
        # Scenario 3: New user WITHOUT phone number
        logger.info("Scenario 3: New user registration WITHOUT phone number")
        logger.info("-" * 60)
        test_telegram_id_2 = test_telegram_id + 1
        try:
            response = await client.post(
                f"{api_url}/bot/users",
                json={
                    "telegram_id": test_telegram_id_2,
                    "phone_number": None,
                    "locale": "uk",
                },
            )
            response.raise_for_status()
            result = response.json()
            logger.info(f"✅ User created: {result}")
            logger.info(f"   Has phone: {result.get('has_phone')}")
            logger.info("   Expected: SMS should NOT be sent (no phone number)")
            logger.info("")
        except Exception as e:
            logger.error(f"❌ Error: {e}")
            logger.info("")
        
        await asyncio.sleep(2)
        
        # Scenario 4: User adds phone number for the first time
        logger.info("Scenario 4: User adds phone number for the first time")
        logger.info("-" * 60)
        try:
            response = await client.post(
                f"{api_url}/bot/users",
                json={
                    "telegram_id": test_telegram_id_2,
                    "phone_number": test_phone,
                    "locale": "uk",
                },
            )
            response.raise_for_status()
            result = response.json()
            logger.info(f"✅ User updated: {result}")
            logger.info(f"   Has phone: {result.get('has_phone')}")
            logger.info("   Expected: SMS should be sent (first time adding phone)")
            logger.info("")
        except Exception as e:
            logger.error(f"❌ Error: {e}")
            logger.info("")
        
        await asyncio.sleep(2)
        
        logger.info("=" * 60)
        logger.info("Test scenarios completed!")
        logger.info("=" * 60)
        logger.info("")
        logger.info("Note: Check TurboSMS logs/API to verify SMS were sent correctly.")
        logger.info("      SMS are sent as background tasks, so they may take a moment.")


if __name__ == "__main__":
    try:
        asyncio.run(test_registration_scenarios())
    except KeyboardInterrupt:
        logger.info("\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        sys.exit(1)

