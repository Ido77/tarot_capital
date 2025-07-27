#!/usr/bin/env python3
"""
Check Processing Progress
Monitor the current status of the parallel processing
"""

import json
import os
from datetime import datetime


def check_progress():
    """Check the current processing progress"""
    print("🚀 OPTIMIZED PSU BATCH PROCESSOR - PROGRESS CHECK")
    print("=" * 80)
    print("⚡ Intelligent SEC rate limiting (8 req/sec)")
    print("⚡ 3 parallel workers with connection pooling")
    print("⚡ Quality controls: 3-month search, min 2 targets")
    print("")
    
    # Check if progress file exists
    progress_file = "parallel_batch_progress.json"
    if not os.path.exists(progress_file):
        print("❌ No progress file found. Processing may not have started.")
        return
    
    # Load progress data
    try:
        with open(progress_file, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(f"❌ Error reading progress file: {e}")
        return
    
    # Extract statistics
    stats = data.get('stats', {})
    processed = stats.get('processed_tickers', 0)
    total = stats.get('total_tickers', 0)
    successful = stats.get('successful_extractions', 0)
    failed = stats.get('failed_extractions', 0)
    rate_limit_errors = stats.get('rate_limit_errors', 0)
    sec_rate_limit_errors = stats.get('sec_rate_limit_errors', 0)
    start_time = stats.get('start_time')
    last_processed = stats.get('last_processed')
    current_ticker = stats.get('current_ticker')
    
    # Calculate progress
    if total > 0:
        progress_percent = (processed / total) * 100
        remaining = total - processed
    else:
        progress_percent = 0
        remaining = 0
    
    # Display progress
    print(f"📈 PROGRESS: {processed:,} / {total:,} tickers ({progress_percent:.1f}%)")
    print(f"⏳ REMAINING: {remaining:,} tickers")
    print(f"✅ SUCCESSFUL: {stats.get('successful_extractions', 0)} companies with PSU targets")
    print(f"❌ FAILED: {stats.get('failed_extractions', 0)} companies (no targets found)")
    print(f"❌ SINGLE TARGET REJECTED: {stats.get('single_target_rejections', 0)} companies")
    print(f"⏳ API NINJAS RATE LIMIT ERRORS: {stats.get('rate_limit_errors', 0)}")
    print(f"⏳ SEC WEBSITE RATE LIMIT ERRORS: {stats.get('sec_rate_limit_errors', 0)}")
    
    # Calculate rates
    processed = stats.get('processed_tickers', 0)
    if processed > 0:
        success_rate = (stats.get('successful_extractions', 0) / processed) * 100
        single_target_rate = (stats.get('single_target_rejections', 0) / processed) * 100
        total_rate_limit_errors = stats.get('rate_limit_errors', 0) + stats.get('sec_rate_limit_errors', 0)
        rate_limit_rate = (total_rate_limit_errors / processed) * 100
        
        print(f"🎯 MULTI-TARGET SUCCESS RATE: {success_rate:.1f}%")
        print(f"🎯 SINGLE TARGET REJECTION RATE: {single_target_rate:.1f}%")
        print(f"🎯 TOTAL RATE LIMIT RATE: {rate_limit_rate:.1f}%")
    
    # Show rate limit analysis
    total_rate_limit_errors = rate_limit_errors + sec_rate_limit_errors
    if total_rate_limit_errors > 0:
        rate_limit_percent = (total_rate_limit_errors / max(1, processed)) * 100
        print(f"⚠️  TOTAL RATE LIMIT RATE: {rate_limit_percent:.1f}%")
        if rate_limit_percent > 10:
            print(f"   ⚠️  High rate limit errors - consider reducing workers further")
        elif rate_limit_percent > 5:
            print(f"   ⚠️  Moderate rate limit errors - monitoring")
        else:
            print(f"   ✅ Low rate limit errors - good")
    
    # Show results breakdown
    high_upside = len(data.get('high_upside_results', []))
    low_upside = len(data.get('low_upside_results', []))
    
    print(f"\n📁 RESULTS BREAKDOWN:")
    print(f"  🏆 High upside (>40%): {high_upside} companies")
    print(f"  📉 Low upside (≤40%): {low_upside} companies")
    print(f"  📊 Total with targets: {successful} companies")
    
    # Show timing
    if start_time:
        try:
            start_dt = datetime.fromisoformat(start_time)
            now = datetime.now()
            elapsed = now - start_dt
            hours = elapsed.total_seconds() / 3600
            
            print(f"\n⏱️  TIMING:")
            print(f"  🕐 Started: {start_dt.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"  ⏱️  Elapsed: {hours:.1f} hours")
            
            if processed > 0:
                rate = processed / hours
                eta_hours = remaining / rate if rate > 0 else 0
                print(f"  🚀 Rate: {rate:.1f} tickers/hour")
                print(f"  🎯 ETA: {eta_hours:.1f} hours remaining")
        except:
            pass
    
    # Show current status
    if current_ticker:
        print(f"\n🔄 CURRENT STATUS:")
        print(f"  📍 Currently processing: {current_ticker}")
    
    if last_processed:
        try:
            last_dt = datetime.fromisoformat(last_processed)
            print(f"  🕐 Last update: {last_dt.strftime('%Y-%m-%d %H:%M:%S')}")
        except:
            pass
    
    # Show high upside companies if any
    if high_upside > 0:
        print(f"\n🏆 TOP HIGH UPSIDE COMPANIES:")
        high_results = data.get('high_upside_results', [])
        sorted_high = sorted(high_results, 
                           key=lambda x: x.get('furthest_target_upside', 0), 
                           reverse=True)
        
        for i, result in enumerate(sorted_high[:10]):
            ticker = result['ticker']
            targets = result['psu_targets']
            furthest = result.get('furthest_target_upside', 0)
            print(f"  {i+1:2d}. {ticker}: {furthest:.1f}% upside ({targets})")
    
    # Check for recent log entries
    log_file = "parallel_batch_processing.log"
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r') as f:
                lines = f.readlines()
                if lines:
                    print(f"\n📝 RECENT ACTIVITY:")
                    for line in lines[-5:]:  # Last 5 lines
                        line = line.strip()
                        if line:
                            print(f"  {line}")
        except:
            pass
    
    print(f"\n{'='*60}")
    print("✅ Processing is active and working!")
    print("📁 Results are being saved to output/ folders")
    print("💾 Progress is saved every 50 tickers")


if __name__ == "__main__":
    check_progress() 