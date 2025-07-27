#!/usr/bin/env python3
"""
Run All Tickers Processing - Form 4 Only
Process all tickers from tickers.txt with Form 4 only filtering
"""

import os
import sys
from parallel_batch_processor import ParallelBatchProcessor


def main():
    """Main function to run all tickers processing"""
    
    print("🚀 OPTIMIZED PSU BATCH PROCESSOR")
    print("=" * 80)
    print("✅ Intelligent SEC rate limiting (8 req/sec within limits)")
    print("✅ Connection pooling and session reuse")
    print("✅ 3 parallel workers for faster processing")
    print("✅ Quality controls: 3-month search, minimum 2 targets")
    print("✅ Progress tracking with crash recovery")
    print("✅ API Ninjas integration (no rate limits)")
    print("")
    
    # Get API key first
    from config_api_ninjas import APINinjasConfig
    config = APINinjasConfig()
    if not config.api_key:
        print(f"\n{'='*80}")
        print("API KEY REQUIRED")
        print("=" * 80)
        print("❌ No API key found!")
        print("📝 Please add your API key to api_key.txt")
        print("🔗 Get your key from: https://api-ninjas.com/")
        return
    
    # Initialize processor with API key and optimized settings
    processor = ParallelBatchProcessor(
        api_key=config.api_key,
        tickers_file='tickers.txt',
        max_workers=3  # Optimized for speed
    )
    
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
    
    print("✅ Parallel processor initialized")
    print("✅ 3 workers ready (optimized)")
    print("✅ Form 4 only filtering enabled")
    print("✅ 3-month search period (recent data)")
    print("✅ Minimum 2 targets required (quality control)")
    print("✅ Empty filings filtered out")
    print("✅ Single target rejection enabled")
    print("✅ Enhanced retry logic enabled (3 retries)")
    print("✅ Intelligent rate limiting enabled")
    
    try:
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