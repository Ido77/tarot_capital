#!/usr/bin/env python3
"""
Run All Tickers Processing - Form 4 Only
Process all tickers from tickers.txt with Form 4 only filtering
"""

import os
import sys
from parallel_batch_processor import ParallelBatchProcessor


def main():
    print("🚀 PSU PRICE TARGET EXTRACTOR - ALL TICKERS")
    print("=" * 80)
    print("✅ Form 4 Only Processing (DEF 14A filtered out)")
    print("✅ Parallel Processing for Speed")
    print("✅ 6 Months Default Time Period")
    print("✅ Automatic Folder Classification (>40% threshold)")
    print("✅ Crash Recovery and Progress Tracking")
    print("✅ Real-time Stock Prices from API Ninjas")
    
    # Get API key
    api_key = os.getenv('API_NINJAS_KEY')
    if not api_key:
        print(f"\n{'='*80}")
        print("API KEY REQUIRED")
        print(f"{'='*80}")
        print("Please enter your API Ninjas API key:")
        print("1. Get your API key from: https://api-ninjas.com/")
        print("2. Or enter it below:")
        api_key = input("API Key: ").strip()
        
        if not api_key or api_key == "YOUR_API_NINJAS_KEY":
            print("❌ No valid API key provided. Exiting.")
            return
    
    # Check if tickers file exists
    tickers_file = "tickers.txt"
    if not os.path.exists(tickers_file):
        print(f"❌ Tickers file not found: {tickers_file}")
        return
    
    # Count tickers
    with open(tickers_file, 'r') as f:
        ticker_count = len([line.strip() for line in f if line.strip()])
    
    print(f"\n{'='*80}")
    print("PROCESSING CONFIGURATION")
    print(f"{'='*80}")
    print(f"📋 Total tickers to process: {ticker_count:,}")
    print(f"⚡ Parallel workers: 1 (ultra-aggressive to eliminate rate limits)")
    print(f"⏱️  Estimated time: ~{ticker_count // 1 // 10:.1f} hours")
    print(f"📁 Output folders: high_upside_40plus, low_upside_below_40")
    print(f"💾 Progress tracking: parallel_batch_progress.json")
    print(f"📝 Logging: parallel_batch_processing.log")
    print(f"🔍 Search period: 3 months (recent data only)")
    print(f"🎯 Quality controls: minimum 2 targets required")
    print(f"🛡️  Global rate limiting: 3 seconds between ANY requests")
    print(f"🛡️  API Ninjas delays: 1 second before each call")
    print(f"🛡️  SEC website delays: 2 seconds before each filing download")
    print(f"🔄 Retry logic: 3 retries with exponential backoff")
    
    # Ask for confirmation
    print(f"\n{'='*80}")
    print("CONFIRMATION")
    print(f"{'='*80}")
    confirm = input("Start processing all tickers? (y/N): ").strip().lower()
    
    if confirm != 'y':
        print("❌ Processing cancelled.")
        return
    
    # Initialize processor with optimal settings
    print(f"\n{'='*80}")
    print("INITIALIZING PARALLEL PROCESSOR")
    print(f"{'='*80}")
    
    try:
        processor = ParallelBatchProcessor(
            api_key=api_key,
            tickers_file=tickers_file,
            max_workers=1  # Ultra-aggressive to eliminate rate limits
        )
        
        print("✅ Parallel processor initialized")
        print("✅ 1 worker ready (ultra-aggressive)")
        print("✅ Form 4 only filtering enabled")
        print("✅ 3-month search period (recent data)")
        print("✅ Minimum 2 targets required (quality control)")
        print("✅ Empty filings filtered out")
        print("✅ Single target rejection enabled")
        print("✅ Global rate limiting enabled (3s between requests)")
        print("✅ API Ninjas delays enabled")
        print("✅ SEC website delays enabled")
        print("✅ Retry logic with exponential backoff")
        print("✅ Progress tracking enabled")
        print("✅ File writing enabled")
        
        # Start processing
        print(f"\n{'='*80}")
        print("STARTING PROCESSING")
        print(f"{'='*80}")
        print("🚀 Processing all tickers with improved quality controls...")
        print("📊 Progress will be saved every 10 tickers")
        print("💾 Results will be saved to output/ folders")
        print("🎯 Only companies with 2+ PSU targets will be accepted")
        print("⏹️  Press Ctrl+C to stop and save progress")
        
        processor.process_all_tickers_parallel()
        
    except KeyboardInterrupt:
        print(f"\n⚠️  Processing interrupted by user")
        print("💾 Saving progress...")
        processor.save_progress()
        processor.save_results()
        print("✅ Progress saved. You can resume later.")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        print(f"📋 Traceback: {traceback.format_exc()}")
        
        # Try to save progress
        try:
            processor.save_progress()
            processor.save_results()
            print("✅ Progress saved despite error.")
        except:
            print("❌ Could not save progress.")


if __name__ == "__main__":
    main() 