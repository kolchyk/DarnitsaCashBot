"""Test script to send SMS via TurboSMS."""

import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path to import from apps
sys.path.insert(0, str(Path(__file__).parent.parent))

from libs.common import configure_logging, get_settings
from apps.api_gateway.services.turbosms.client import TurboSmsClient

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


async def main() -> None:
    """Send a test SMS."""
    phone_number = "380992227160"
    test_message = "Test SMS from DarnitsaCashBot"
    
    settings = get_settings()
    configure_logging(settings.log_level)
    
    # Enable TurboSMS for testing
    settings.turbosms_enabled = True
    
    logger.info(f"Sending test SMS to {phone_number}")
    logger.info(f"Message: {test_message}")
    logger.info(f"TurboSMS enabled: {settings.turbosms_enabled}")
    logger.info(f"TurboSMS token configured: {bool(settings.turbosms_token)}")
    logger.info(f"TurboSMS sender: {settings.turbosms_sender}")
    
    client = TurboSmsClient(settings)
    
    try:
        success = await client.send_sms(
            phone_number=phone_number,
            message=test_message,
        )
        
        if success:
            logger.info("✅ SMS sent successfully!")
        else:
            logger.error("❌ Failed to send SMS")
            sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Error sending SMS: {e}", exc_info=True)
        sys.exit(1)
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())

