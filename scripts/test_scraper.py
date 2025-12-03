#!/usr/bin/env python
"""
Test script to verify receipt scraping from tax.gov.ua using Playwright.
Run from project root: python scripts/test_scraper.py [url]
"""
from __future__ import annotations

import sys
from pathlib import Path
import json

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


def test_scraping(url: str) -> None:
    """Test receipt scraping from a specific URL using Playwright."""
    from apps.api_gateway.services.ocr.receipt_scraper import scrape_receipt_data, ScrapingError
    
    print(f"🌐 Testing Playwright scraping: {url}")
    print("-" * 60)
    
    try:
        result = scrape_receipt_data(url)
        
        print(f"\n✅ Scraping SUCCESSFUL!")
        print(f"\n📊 Results:")
        print(f"   Merchant: {result.get('merchant')}")
        print(f"   Purchase date: {result.get('purchase_ts')}")
        print(f"   Total: {result.get('total')} kopecks")
        print(f"   Line items: {len(result.get('line_items', []))}")
        
        if result.get('line_items'):
            print(f"\n📦 Line items:")
            for i, item in enumerate(result['line_items'], 1):
                print(f"   {i}. {item['name']}")
                print(f"      Qty: {item['quantity']}, Price: {item['price']} kopecks")
        else:
            print(f"\n⚠️  No line items found!")
        
        # Save result to file
        output_file = PROJECT_ROOT / "scripts" / "scrape_result.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n💾 Full result saved to: {output_file}")
        
    except ScrapingError as e:
        print(f"\n❌ Scraping Error: {e}")
    except Exception as e:
        print(f"\n❌ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


def main() -> None:
    """Main entry point."""
    print("=" * 60)
    print("Receipt Scraper Test Script (Playwright)")
    print("=" * 60)
    
    # Default test URL (from QR code)
    default_url = "https://cabinet.tax.gov.ua/cashregs/check?id=UxI07gWmYOQ&date=20251201&time=16:12&fn=4001246197&sm=46.50"
    
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = default_url
    
    test_scraping(url)
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
