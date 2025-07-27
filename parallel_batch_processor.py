#!/usr/bin/env python3
"""
Parallel Batch Processor for All Tickers - API Ninjas Integration
Processes multiple tickers simultaneously for much faster processing
"""

import json
import csv
import os
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import time
import signal
import traceback
import concurrent.futures
from threading import Lock
import queue

from psu_extractor_api_ninjas import PSUPriceExtractorAPINinjas


class ParallelBatchProcessor:
    def __init__(self, api_key: str, tickers_file: str = "tickers.txt", max_workers: int = 1):
        self.api_key = api_key
        self.tickers_file = tickers_file
        self.max_workers = max_workers
        
        # Progress tracking
        self.progress_file = "parallel_batch_progress.json"
        self.log_file = "parallel_batch_processing.log"
        
        # Statistics
        self.stats = {
            'total_tickers': 0,
            'processed_tickers': 0,
            'successful_extractions': 0,
            'failed_extractions': 0,
            'skipped_tickers': 0,
            'rate_limit_errors': 0,
            'sec_rate_limit_errors': 0,
            'single_target_rejections': 0,
            'empty_filing_filtered': 0,
            'start_time': None,
            'last_processed': None,
            'current_ticker': None
        }
        
        # Results storage with thread safety
        self.results = []
        self.high_upside_results = []
        self.low_upside_results = []
        self.results_lock = Lock()
        
        # Global rate limiting - Extremely conservative to avoid ALL API failures
        self.global_last_request_time = 0
        self.global_min_request_interval = 3.0  # 3 seconds between ANY requests (global)
        self.global_rate_lock = Lock()
        
        # Load existing progress if available
        self.load_progress()
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        """Handle interrupt signals gracefully"""
        print(f"\n⚠️  Received signal {signum}. Saving progress and shutting down gracefully...")
        self.save_progress()
        self.save_results()
        print("✅ Progress saved. You can resume later.")
        sys.exit(0)
    
    def load_progress(self):
        """Load existing progress from file"""
        try:
            if os.path.exists(self.progress_file):
                with open(self.progress_file, 'r') as f:
                    data = json.load(f)
                    self.stats = data.get('stats', self.stats)
                    self.results = data.get('results', [])
                    self.high_upside_results = data.get('high_upside_results', [])
                    self.low_upside_results = data.get('low_upside_results', [])
                
                print(f"📁 Loaded existing progress:")
                print(f"  • Processed: {self.stats['processed_tickers']} tickers")
                print(f"  • Successful: {self.stats['successful_extractions']}")
                print(f"  • Failed: {self.stats['failed_extractions']}")
                print(f"  • Last processed: {self.stats['last_processed']}")
                
                if self.stats['current_ticker']:
                    print(f"  • Current ticker: {self.stats['current_ticker']}")
        except Exception as e:
            print(f"⚠️  Could not load progress: {e}")
    
    def save_progress(self):
        """Save current progress to file"""
        try:
            with self.results_lock:
                progress_data = {
                    'stats': self.stats,
                    'results': self.results,
                    'high_upside_results': self.high_upside_results,
                    'low_upside_results': self.low_upside_results,
                    'timestamp': datetime.now().isoformat()
                }
            
            with open(self.progress_file, 'w') as f:
                json.dump(progress_data, f, indent=2)
            
            print(f"💾 Progress saved: {self.progress_file}")
        except Exception as e:
            print(f"❌ Error saving progress: {e}")
    
    def save_results(self):
        """Save results to output files"""
        try:
            # Create output directories
            output_dir = "output"
            high_upside_dir = os.path.join(output_dir, "high_upside_40plus")
            low_upside_dir = os.path.join(output_dir, "low_upside_below_40")
            
            for directory in [output_dir, high_upside_dir, low_upside_dir]:
                if not os.path.exists(directory):
                    os.makedirs(directory)
            
            # Create the main results structure
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            main_filename = f"parallel_all_tickers_batch_{timestamp}.json"
            
            output_data = {
                'extraction_date': datetime.now().isoformat(),
                'system': 'PSU Price Target Extractor - Parallel Processing (3 months, min 2 targets)',
                'search_period': '3 months',
                'quality_controls': {
                    'minimum_targets_required': 2,
                    'empty_filings_filtered': True,
                    'single_target_rejection': True,
                    'filing_content_snippets': True
                },
                'processing_settings': {
                    'max_workers': self.max_workers,
                    'global_rate_limiting': '3 seconds between requests',
                    'api_ninjas_delays': '1 second per call',
                    'sec_website_delays': '2 seconds per filing download'
                },
                'statistics': self.stats,
                'total_companies_processed': len(self.results),
                'results': self.results
            }
            
            main_filepath = os.path.join(output_dir, main_filename)
            
            with open(main_filepath, 'w') as f:
                json.dump(output_data, f, indent=2)
            
            # Save high upside results
            if self.high_upside_results:
                high_upside_filename = f"parallel_high_upside_all_tickers_{timestamp}.json"
                high_upside_filepath = os.path.join(high_upside_dir, high_upside_filename)
                
                high_upside_data = {
                    'extraction_date': datetime.now().isoformat(),
                    'system': 'PSU Price Target Extractor - Parallel High Upside (40%+) - 3 months, min 2 targets',
                    'total_companies': len(self.high_upside_results),
                    'threshold': 'furthest_target_upside > 40%',
                    'search_period': '3 months',
                    'quality_controls': {
                        'minimum_targets_required': 2,
                        'empty_filings_filtered': True,
                        'single_target_rejection': True
                    },
                    'max_workers': self.max_workers,
                    'results': self.high_upside_results
                }
                
                with open(high_upside_filepath, 'w') as f:
                    json.dump(high_upside_data, f, indent=2)
                
                self.log_message(f"📁 High upside results saved: {high_upside_filepath}")
            
            # Save low upside results
            if self.low_upside_results:
                low_upside_filename = f"parallel_low_upside_all_tickers_{timestamp}.json"
                low_upside_filepath = os.path.join(low_upside_dir, low_upside_filename)
                
                low_upside_data = {
                    'extraction_date': datetime.now().isoformat(),
                    'system': 'PSU Price Target Extractor - Parallel Low Upside (<40%) - 3 months, min 2 targets',
                    'total_companies': len(self.low_upside_results),
                    'threshold': 'furthest_target_upside <= 40%',
                    'search_period': '3 months',
                    'quality_controls': {
                        'minimum_targets_required': 2,
                        'empty_filings_filtered': True,
                        'single_target_rejection': True
                    },
                    'max_workers': self.max_workers,
                    'results': self.low_upside_results
                }
                
                with open(low_upside_filepath, 'w') as f:
                    json.dump(low_upside_data, f, indent=2)
                
                self.log_message(f"📁 Low upside results saved: {low_upside_filepath}")
            
            print(f"📁 Results saved:")
            print(f"  • Main: {main_filepath}")
            if self.high_upside_results:
                print(f"  • High upside: {high_upside_filepath}")
            if self.low_upside_results:
                print(f"  • Low upside: {low_upside_filepath}")
            
            return main_filepath
            
        except Exception as e:
            print(f"❌ Error saving results: {e}")
            return None
    
    def get_processing_time(self) -> str:
        """Calculate total processing time"""
        if not self.stats['start_time']:
            return "N/A"
        
        start_time = datetime.fromisoformat(self.stats['start_time'])
        end_time = datetime.now()
        duration = end_time - start_time
        
        hours = duration.seconds // 3600
        minutes = (duration.seconds % 3600) // 60
        seconds = duration.seconds % 60
        
        return f"{hours}h {minutes}m {seconds}s"
    
    def log_message(self, message: str):
        """Log message to file and print to console"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        
        print(log_entry)
        
        try:
            with open(self.log_file, 'a') as f:
                f.write(log_entry + "\n")
        except Exception as e:
            print(f"⚠️  Could not write to log file: {e}")
    
    def rate_limit(self):
        """Global rate limiting for ALL API calls across all threads"""
        with self.global_rate_lock:
            current_time = time.time()
            time_since_last = current_time - self.global_last_request_time
            
            if time_since_last < self.global_min_request_interval:
                sleep_time = self.global_min_request_interval - time_since_last
                self.log_message(f"⏳ Global rate limiting: waiting {sleep_time:.1f}s")
                time.sleep(sleep_time)
            
            self.global_last_request_time = time.time()
    
    def handle_rate_limit_error(self, ticker: str, retry_count: int = 0):
        """Handle rate limit errors with exponential backoff"""
        max_retries = 3
        base_delay = 2  # 2 seconds base delay
        
        if retry_count >= max_retries:
            self.log_message(f"💥 {ticker}: Max retries exceeded for rate limit")
            return False
        
        delay = base_delay * (2 ** retry_count)  # Exponential backoff: 2s, 4s, 8s
        self.log_message(f"⏳ {ticker}: Rate limit hit, waiting {delay}s (retry {retry_count + 1}/{max_retries})")
        time.sleep(delay)
        return True
    
    def load_tickers(self) -> List[str]:
        """Load tickers from file"""
        tickers = []
        
        try:
            with open(self.tickers_file, 'r') as f:
                for line in f:
                    ticker = line.strip().upper()
                    if ticker and len(ticker) <= 5:  # Basic validation
                        tickers.append(ticker)
            
            self.stats['total_tickers'] = len(tickers)
            self.log_message(f"📋 Loaded {len(tickers)} tickers from {self.tickers_file}")
            
        except Exception as e:
            self.log_message(f"❌ Error loading tickers: {e}")
        
        return tickers
    
    def process_ticker(self, ticker: str) -> Optional[Dict]:
        """Process a single ticker with rate limiting and error handling"""
        max_retries = 3
        
        for retry_count in range(max_retries + 1):
            try:
                # Rate limiting
                self.rate_limit()
                
                # Create extractor for this thread
                extractor = PSUPriceExtractorAPINinjas(self.api_key)
                
                # Extract PSU targets for this ticker
                self.rate_limit()
                result = extractor.extract_from_ticker(ticker)
                
                # Check if extraction was successful (multiple targets required)
                targets = result.get('psu_targets', [])
                rejection_reason = result.get('rejection_reason', None)
                
                if targets and len(targets) >= 2:
                    # Successful extraction with multiple targets
                    self.stats['successful_extractions'] += 1
                    
                    with self.results_lock:
                        self.results.append(result)
                        
                        # Classify by upside
                        furthest_upside = result.get('furthest_target_upside', 0)
                        if furthest_upside > 40:
                            self.high_upside_results.append(result)
                        else:
                            self.low_upside_results.append(result)
                    
                    self.log_message(f"✅ {ticker}: Found {len(targets)} targets (3 months)")
                    
                    # Log upside classification
                    furthest_upside = result.get('furthest_target_upside', 0)
                    if furthest_upside > 40:
                        self.log_message(f"📁 {ticker}: HIGH UPSIDE ({furthest_upside:.1f}%)")
                    else:
                        self.log_message(f"📁 {ticker}: LOW UPSIDE ({furthest_upside:.1f}%)")
                        
                elif rejection_reason:
                    # Explicitly rejected due to insufficient targets or other quality controls
                    if 'unique target(s) found - minimum 2 required' in rejection_reason:
                        self.stats['single_target_rejections'] += 1
                        self.log_message(f"❌ {ticker}: Single target rejected - {rejection_reason}")
                    else:
                        self.stats['failed_extractions'] += 1
                        self.log_message(f"❌ {ticker}: Quality control rejection - {rejection_reason}")
                    
                elif result.get('error'):
                    # Error occurred
                    error_msg = result['error']
                    if 'rate limit' in error_msg.lower() or '429' in error_msg:
                        self.stats['rate_limit_errors'] += 1
                        self.log_message(f"⏳ {ticker}: API Ninjas rate limit error - {error_msg}")
                    elif 'sec' in error_msg.lower() or 'timeout' in error_msg.lower():
                        self.stats['sec_rate_limit_errors'] += 1
                        self.log_message(f"⏳ {ticker}: SEC website error - {error_msg}")
                    else:
                        self.log_message(f"❌ {ticker}: Error - {error_msg}")
                    
                    self.stats['failed_extractions'] += 1
                else:
                    # No targets found
                    self.stats['failed_extractions'] += 1
                    self.log_message(f"❌ {ticker}: No PSU targets found (3 months)")
                
                self.stats['processed_tickers'] += 1
                self.stats['last_processed'] = datetime.now().isoformat()
                self.stats['current_ticker'] = ticker
                
                return result
                
            except Exception as e:
                error_msg = str(e).lower()
                
                # Check if it's a rate limit error
                if 'rate limit' in error_msg or '429' in error_msg or 'too many requests' in error_msg:
                    self.stats['rate_limit_errors'] += 1
                    
                    if retry_count < max_retries:
                        if self.handle_rate_limit_error(ticker, retry_count):
                            continue  # Retry
                        else:
                            break  # Max retries exceeded
                    else:
                        self.log_message(f"💥 {ticker}: Max retries exceeded for rate limit")
                else:
                    # Non-rate-limit error, don't retry
                    self.log_message(f"💥 {ticker}: Non-retryable error - {str(e)}")
                    break
        
        # If we get here, all retries failed or it was a non-retryable error
        with self.results_lock:
            self.stats['failed_extractions'] += 1
            self.stats['processed_tickers'] += 1
            self.stats['last_processed'] = datetime.now().isoformat()
            
            error_result = {
                'ticker': ticker.upper(),
                'psu_targets': [],
                'error': f"Failed after {max_retries + 1} attempts: {str(e)}",
                'processing_time': datetime.now().isoformat()
            }
            
            self.results.append(error_result)
            self.log_message(f"💥 {ticker}: Final failure after retries")
        
        return error_result
    
    def process_all_tickers_parallel(self, start_from: Optional[str] = None, max_tickers: Optional[int] = None):
        """Process all tickers in parallel"""
        tickers = self.load_tickers()
        
        if not tickers:
            self.log_message("❌ No tickers loaded. Exiting.")
            return
        
        # Initialize start time if not already set
        if not self.stats['start_time']:
            self.stats['start_time'] = datetime.now().isoformat()
        
        # Find starting position
        start_index = 0
        if start_from:
            try:
                start_index = tickers.index(start_from.upper())
                self.log_message(f"🎯 Starting from ticker: {start_from.upper()} (index {start_index})")
            except ValueError:
                self.log_message(f"⚠️  Ticker {start_from} not found, starting from beginning")
        
        # Apply max tickers limit
        if max_tickers:
            tickers = tickers[start_index:start_index + max_tickers]
            self.log_message(f"📊 Processing {len(tickers)} tickers (max limit)")
        else:
            tickers = tickers[start_index:]
            self.log_message(f"📊 Processing {len(tickers)} tickers")
        
        # Process tickers in parallel
        self.log_message(f"🚀 Starting parallel processing with {self.max_workers} workers")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_ticker = {executor.submit(self.process_ticker, ticker): ticker for ticker in tickers}
            
            # Process completed tasks
            for i, future in enumerate(concurrent.futures.as_completed(future_to_ticker)):
                ticker = future_to_ticker[future]
                
                try:
                    result = future.result()
                    
                    # Save progress every 10 tickers (very frequent due to slow processing)
                    if (i + 1) % 10 == 0:
                        self.save_progress()
                        self.log_message(f"💾 Progress saved after {i + 1} tickers")
                    
                except Exception as e:
                    self.log_message(f"💥 Unexpected error processing {ticker}: {str(e)}")
                    continue
        
        # Final save
        self.save_progress()
        self.save_results()
        
        # Print final statistics
        self.print_final_stats()
    
    def print_final_stats(self):
        """Print final processing statistics"""
        processing_time = self.get_processing_time()
        
        print(f"\n{'='*80}")
        print("FINAL SUMMARY")
        print(f"{'='*80}")
        print(f"📊 PROCESSING STATISTICS:")
        print(f"  Total tickers processed: {self.stats['processed_tickers']:,}")
        print(f"  ✅ Successful extractions: {self.stats['successful_extractions']:,}")
        print(f"  ❌ Failed extractions: {self.stats['failed_extractions']:,}")
        print(f"  ❌ Single target rejections: {self.stats['single_target_rejections']:,}")
        print(f"  ⏳ API Ninjas rate limits: {self.stats['rate_limit_errors']:,}")
        print(f"  ⏳ SEC website rate limits: {self.stats['sec_rate_limit_errors']:,}")
        
        total_processed = self.stats['processed_tickers']
        if total_processed > 0:
            success_rate = (self.stats['successful_extractions'] / total_processed) * 100
            single_target_rate = (self.stats['single_target_rejections'] / total_processed) * 100
            rate_limit_rate = ((self.stats['rate_limit_errors'] + self.stats['sec_rate_limit_errors']) / total_processed) * 100
            
            print(f"\n📈 QUALITY METRICS (3 months, min 2 targets):")
            print(f"  ✅ Multi-target success rate: {success_rate:.1f}%")
            print(f"  ❌ Single target rejection rate: {single_target_rate:.1f}%")
            print(f"  ⏳ Total rate limit error rate: {rate_limit_rate:.1f}%")
        
        print(f"\n📁 RESULTS BREAKDOWN:")
        print(f"  🏆 High upside (>40%): {len(self.high_upside_results):,} companies")
        print(f"  📉 Low upside (≤40%): {len(self.low_upside_results):,} companies")
        print(f"  📊 Total with valid targets: {len(self.results):,} companies")
        
        elapsed_time = time.time() - self.stats['start_time'] if self.stats['start_time'] else 0
        if elapsed_time > 0:
            rate = self.stats['processed_tickers'] / (elapsed_time / 3600)
            print(f"\n⏱️  TIMING:")
            print(f"  Total elapsed time: {elapsed_time/3600:.1f} hours")
            print(f"  Processing rate: {rate:.1f} tickers/hour")
            
        print(f"\n🎯 QUALITY IMPROVEMENTS APPLIED:")
        print(f"  ✅ 3-month search period (more recent data)")
        print(f"  ✅ Minimum 2 targets required (no single targets)")
        print(f"  ✅ Empty filings filtered out (clean results)")
        print(f"  ✅ Filing content snippets included (evidence)")
        print(f"  ✅ Improved rate limiting (ultra-conservative)")
        
        # Save final results
        print(f"\n💾 SAVING FINAL RESULTS...")
        self.save_results()
        print(f"✅ All results saved to output/ folders")


def main():
    print("PSU Price Target Extractor - Parallel All Tickers Batch Processor")
    print("=" * 80)
    print("Features:")
    print("✅ Parallel processing for speed")
    print("✅ Processes all tickers from tickers.txt")
    print("✅ Crash recovery and progress tracking")
    print("✅ Real-time stock prices from API Ninjas")
    print("✅ 6-month default time period")
    print("✅ Furthest target upside calculation")
    print("✅ Automatic folder classification (>40% threshold)")
    print("✅ Detailed logging and statistics")
    print("✅ Graceful shutdown handling")
    
    # Get API key
    api_key = os.getenv('API_NINJAS_KEY')
    if not api_key:
        print(f"\n{'='*80}")
        print("API KEY REQUIRED")
        print(f"{'='*80}")
        print("Please set your API Ninjas API key:")
        print("1. Get your API key from: https://api-ninjas.com/")
        print("2. Set environment variable: export API_NINJAS_KEY='your_key_here'")
        print("3. Or enter it below:")
        api_key = input("API Key: ").strip()
        
        if not api_key or api_key == "YOUR_API_NINJAS_KEY":
            print("❌ No valid API key provided. Exiting.")
            return
    
    # Check if tickers file exists
    tickers_file = "tickers.txt"
    if not os.path.exists(tickers_file):
        print(f"❌ Tickers file not found: {tickers_file}")
        return
    
    # Get processing options
    print(f"\n{'='*80}")
    print("PARALLEL PROCESSING OPTIONS")
    print(f"{'='*80}")
    
    # Number of workers
    max_workers_input = input("Number of parallel workers (default 10, max 20): ").strip()
    max_workers = 10
    if max_workers_input:
        try:
            max_workers = int(max_workers_input)
            max_workers = min(max_workers, 20)  # Cap at 20
            max_workers = max(max_workers, 1)   # Minimum 1
        except ValueError:
            print("⚠️  Invalid number, using default 10 workers")
    
    # Resume from specific ticker
    resume_from = input("Resume from specific ticker (or press Enter to start from beginning): ").strip()
    if not resume_from:
        resume_from = None
    
    # Max tickers limit
    max_tickers_input = input("Max number of tickers to process (or press Enter for all): ").strip()
    max_tickers = None
    if max_tickers_input:
        try:
            max_tickers = int(max_tickers_input)
        except ValueError:
            print("⚠️  Invalid number, processing all tickers")
    
    # Initialize processor
    processor = ParallelBatchProcessor(api_key, tickers_file, max_workers)
    
    # Start processing
    print(f"\n{'='*80}")
    print("STARTING PARALLEL BATCH PROCESSING")
    print(f"{'='*80}")
    print(f"🚀 Parallel workers: {max_workers}")
    print(f"⚡ Expected speedup: ~{max_workers}x faster")
    print(f"⏱️  Estimated time: ~{22 // max_workers} hours")
    
    try:
        processor.process_all_tickers_parallel(start_from=resume_from, max_tickers=max_tickers)
    except Exception as e:
        print(f"💥 Fatal error: {e}")
        print(f"📋 Traceback: {traceback.format_exc()}")
        processor.save_progress()
        processor.save_results()


if __name__ == "__main__":
    main() 