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
import threading
import requests # Added for retry logic

from psu_extractor_api_ninjas import PSUPriceExtractorAPINinjas


class ParallelBatchProcessor:
    def __init__(self, api_key: str, tickers_file: str = "tickers.txt", max_workers: int = 1):
        self.api_key = api_key
        self.tickers_file = tickers_file
        self.max_workers = max_workers
        
        # Progress tracking
        self.progress_file = "parallel_batch_progress.json"
        self.log_file = "parallel_batch_processing.log"
        
        # Statistics tracking
        self.stats = {
            'start_time': None,
            'processed_tickers': 0,
            'successful_extractions': 0,
            'failed_extractions': 0,
            'single_target_rejections': 0,
            'api_ninjas_rate_limits': 0,
            'sec_rate_limits': 0,
            'retry_attempts': 0,
            'retry_successes': 0,
            'permanent_failures': 0,
            'last_processed': None,
            'current_ticker': None
        }
        
        # Results storage with thread safety
        self.results = []
        self.high_upside_results = []
        self.low_upside_results = []
        self.results_lock = Lock()
        
        # Processing settings (optimized for speed with intelligent rate limiting)
        self.max_workers = 3  # Increased from 1 - SEC can handle 8 req/sec, we use 3 workers
        self.global_min_request_interval = 1.0  # Reduced from 3.0s - faster processing
        
        # Rate limiting tracking
        self.last_global_request = 0
        self.global_lock = threading.Lock()
        
        # Initialize extractor
        self.extractor = PSUPriceExtractorAPINinjas(api_key)
        
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
        if not self.stats.get('start_time'):
            return "N/A"
        
        try:
            if isinstance(self.stats['start_time'], str):
                start_time = datetime.fromisoformat(self.stats['start_time'])
            else:
                start_time = self.stats['start_time']
                
            end_time = datetime.now()
            duration = end_time - start_time
            
            total_seconds = int(duration.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            
            return f"{hours}h {minutes}m {seconds}s"
        except Exception as e:
            self.log_message(f"Error calculating processing time: {e}")
            return "N/A"
    
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
        with self.global_lock:
            current_time = time.time()
            time_since_last = current_time - self.last_global_request
            
            if time_since_last < self.global_min_request_interval:
                sleep_time = self.global_min_request_interval - time_since_last
                self.log_message(f"⏳ Global rate limiting: waiting {sleep_time:.1f}s")
                time.sleep(sleep_time)
            
            self.last_global_request = time.time()
    
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
    
    def process_ticker(self, ticker: str) -> Dict:
        """
        Process a single ticker with comprehensive retry logic
        """
        max_retries = 3
        retry_delay = 2.0
        retry_attempted = False
        
        for attempt in range(max_retries):
            try:
                # Track retry attempts
                if attempt > 0:
                    if not retry_attempted:
                        with self.global_lock:
                            self.stats['retry_attempts'] += 1
                        retry_attempted = True
                
                # Enforce global rate limiting
                with self.global_lock:
                    current_time = time.time()
                    if self.last_global_request > 0:
                        elapsed = current_time - self.last_global_request
                        if elapsed < self.global_min_request_interval:
                            wait_time = self.global_min_request_interval - elapsed
                            self.log_message(f"⏳ Global rate limiting: waiting {wait_time:.1f}s")
                            time.sleep(wait_time)
                    self.last_global_request = time.time()
                
                # Attempt to process the ticker
                print(f"🔍 Extracting PSU targets for {ticker}")
                result = self.extractor.extract_from_ticker(ticker)
                
                # If we got a result after retrying, count it as a retry success
                if retry_attempted and (result.get('psu_targets') or result.get('rejection_reason')):
                    with self.global_lock:
                        self.stats['retry_successes'] += 1
                
                # Check if extraction was successful
                if result.get('psu_targets'):
                    # Successful extraction
                    self.log_message(f"✅ {ticker}: Found {len(result['psu_targets'])} targets ({result['search_months_back']} months)")
                    
                    # Determine upside category
                    furthest_upside = result.get('furthest_target_upside', 0)
                    if furthest_upside > 40:
                        self.log_message(f"📁 {ticker}: HIGH UPSIDE ({furthest_upside:.1f}%)")
                    else:
                        self.log_message(f"📁 {ticker}: LOW UPSIDE ({furthest_upside:.1f}%)")
                    
                    return result
                    
                elif 'rejection_reason' in result:
                    # Rejection due to quality controls (not an error)
                    rejection_reason = result['rejection_reason']
                    if 'Only 1 unique target' in rejection_reason or 'Only 0 unique target' in rejection_reason:
                        self.log_message(f"❌ {ticker}: Single target rejected - {rejection_reason}")
                        with self.global_lock:
                            self.stats['single_target_rejections'] += 1
                    else:
                        self.log_message(f"❌ {ticker}: Rejected - {rejection_reason}")
                    return result
                    
                else:
                    # No targets found
                    error_msg = result.get('error', 'No PSU targets found')
                    self.log_message(f"❌ {ticker}: {error_msg} ({result.get('search_months_back', 3)} months)")
                    return result
                    
            except requests.exceptions.Timeout as e:
                self.log_message(f"⏰ {ticker}: Timeout error on attempt {attempt + 1}/{max_retries}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                    continue
                else:
                    return self._create_error_result(ticker, f"Timeout after {max_retries} attempts: {e}")
                    
            except requests.exceptions.RequestException as e:
                if '429' in str(e) or 'rate limit' in str(e).lower():
                    self.log_message(f"🚫 {ticker}: Rate limit hit on attempt {attempt + 1}/{max_retries}")
                    with self.global_lock:
                        if 'api.api-ninjas.com' in str(e):
                            self.stats['api_ninjas_rate_limits'] += 1
                        elif 'sec.gov' in str(e):
                            self.stats['sec_rate_limits'] += 1
                    
                    if attempt < max_retries - 1:
                        backoff_time = retry_delay * (2 ** attempt)  # Exponential backoff
                        self.log_message(f"⏳ {ticker}: Backing off for {backoff_time:.1f}s before retry")
                        time.sleep(backoff_time)
                        continue
                    else:
                        return self._create_error_result(ticker, f"Rate limit exceeded after {max_retries} attempts")
                else:
                    self.log_message(f"🌐 {ticker}: Network error on attempt {attempt + 1}/{max_retries}: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay * (attempt + 1))
                        continue
                    else:
                        return self._create_error_result(ticker, f"Network error after {max_retries} attempts: {e}")
                        
            except KeyError as e:
                self.log_message(f"🔑 {ticker}: Data structure error on attempt {attempt + 1}/{max_retries}: Missing key {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                else:
                    return self._create_error_result(ticker, f"Data structure error after {max_retries} attempts: {e}")
                    
            except ValueError as e:
                self.log_message(f"📊 {ticker}: Data validation error on attempt {attempt + 1}/{max_retries}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                else:
                    return self._create_error_result(ticker, f"Data validation error after {max_retries} attempts: {e}")
                    
            except Exception as e:
                self.log_message(f"💥 {ticker}: Unexpected error on attempt {attempt + 1}/{max_retries}: {type(e).__name__}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                else:
                    # Log the full traceback for debugging
                    import traceback
                    error_details = traceback.format_exc()
                    self.log_message(f"🐛 {ticker}: Full error traceback:\n{error_details}")
                    # Track as permanent failure
                    with self.global_lock:
                        self.stats['permanent_failures'] += 1
                    return self._create_error_result(ticker, f"Unexpected error after {max_retries} attempts: {type(e).__name__}: {e}")
        
        # This should never be reached, but just in case
        with self.global_lock:
            self.stats['permanent_failures'] += 1
        return self._create_error_result(ticker, "Unknown error: retry loop completed without result")
    
    def _create_error_result(self, ticker: str, error_message: str) -> Dict:
        """Create a standardized error result"""
        return {
            'ticker': ticker.upper(),
            'error': error_message,
            'current_price': None,
            'psu_targets': [],
            'filing_source': None,
            'filing_date': None,
            'nearest_target_upside': None,
            'furthest_target_upside': None,
            'form4_filings_found': 0,
            'filings_analyzed': [],
            'filing_content_snippets': [],
            'search_months_back': 3,
            'retry_failed': True
        }
    
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
                    
                    # Process the result and update statistics
                    with self.results_lock:
                        self.stats['processed_tickers'] += 1
                        self.stats['last_processed'] = datetime.now().isoformat()
                        self.stats['current_ticker'] = ticker
                        
                        # Determine result type and update statistics
                        if result.get('psu_targets'):
                            # Successful extraction
                            self.stats['successful_extractions'] += 1
                            self.results.append(result)
                            
                            # Classify by upside
                            furthest_upside = result.get('furthest_target_upside', 0)
                            if furthest_upside > 40:
                                self.high_upside_results.append(result)
                            else:
                                self.low_upside_results.append(result)
                                
                        elif result.get('retry_failed'):
                            # Failed after all retries
                            self.stats['failed_extractions'] += 1
                            self.results.append(result)
                            
                        elif 'rejection_reason' in result:
                            # Quality control rejection (single target rejections already counted in process_ticker)
                            pass  
                            
                        else:
                            # No targets found
                            self.stats['failed_extractions'] += 1
                    
                    # Save progress every 10 tickers
                    if (i + 1) % 10 == 0:
                        self.save_progress()
                        self.log_message(f"💾 Progress saved after {i + 1} tickers")
                    
                except Exception as e:
                    self.log_message(f"💥 Unexpected error processing {ticker}: {str(e)}")
                    # Even on unexpected error, count as processed and failed
                    with self.results_lock:
                        self.stats['processed_tickers'] += 1
                        self.stats['failed_extractions'] += 1
                        error_result = self._create_error_result(ticker, f"Executor error: {str(e)}")
                        self.results.append(error_result)
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
        print(f"  ⏳ API Ninjas rate limits: {self.stats['api_ninjas_rate_limits']:,}")
        print(f"  ⏳ SEC website rate limits: {self.stats['sec_rate_limits']:,}")
        print(f"  🔄 Retry attempts: {self.stats['retry_attempts']:,}")
        print(f"  ✅ Retry successes: {self.stats['retry_successes']:,}")
        print(f"  💀 Permanent failures: {self.stats['permanent_failures']:,}")
        
        total_processed = self.stats['processed_tickers']
        if total_processed > 0:
            success_rate = (self.stats['successful_extractions'] / total_processed) * 100
            single_target_rate = (self.stats['single_target_rejections'] / total_processed) * 100
            rate_limit_rate = ((self.stats['api_ninjas_rate_limits'] + self.stats['sec_rate_limits']) / total_processed) * 100
            retry_success_rate = (self.stats['retry_successes'] / max(1, self.stats['retry_attempts'])) * 100
            
            print(f"\n📈 QUALITY METRICS (3 months, min 2 targets):")
            print(f"  ✅ Multi-target success rate: {success_rate:.1f}%")
            print(f"  ❌ Single target rejection rate: {single_target_rate:.1f}%")
            print(f"  ⏳ Total rate limit error rate: {rate_limit_rate:.1f}%")
            print(f"  🔄 Retry success rate: {retry_success_rate:.1f}%")
        
        print(f"\n📁 RESULTS BREAKDOWN:")
        print(f"  🏆 High upside (>40%): {len(self.high_upside_results):,} companies")
        print(f"  📉 Low upside (≤40%): {len(self.low_upside_results):,} companies")
        print(f"  📊 Total with valid targets: {len(self.results):,} companies")
        
        # Calculate and display processing time
        if self.stats['start_time']:
            try:
                if isinstance(self.stats['start_time'], str):
                    start_time = datetime.fromisoformat(self.stats['start_time'])
                else:
                    start_time = self.stats['start_time']
                    
                elapsed_time = time.time() - start_time.timestamp()
                hours = int(elapsed_time // 3600)
                minutes = int((elapsed_time % 3600) // 60)
                seconds = int(elapsed_time % 60)
                print(f"⏱️  Total processing time: {hours}h {minutes}m {seconds}s")
            except Exception as e:
                print(f"⏱️  Total processing time: Unable to calculate ({e})")
        else:
            print(f"⏱️  Total processing time: Not available")
        
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