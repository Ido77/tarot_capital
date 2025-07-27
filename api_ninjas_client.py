#!/usr/bin/env python3
"""
API Ninjas Client for SEC Filings and Stock Prices
Optimized rate limiting based on SEC best practices
"""

import requests
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json
from urllib.parse import urljoin


class APINinjasClient:
    """
    Optimized client for API Ninjas with intelligent SEC rate limiting
    """
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.api-ninjas.com/v1"
        self.sec_base_url = "https://www.sec.gov"
        
        # Rate limiting settings (optimized for speed within limits)
        self.api_ninjas_delay = 0.5  # Reduced from 1.0s - API Ninjas has no rate limit
        self.sec_delay = 0.12  # 8.3 requests per second (within 10/sec limit)
        self.sec_timeout = 30  # Reduced from 60s for faster processing
        
        # Connection optimization
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'PSU Target Extractor 1.0 (contact@example.com)',  # Required by SEC
            'Accept': 'application/json, text/html, */*',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        })
        
        # Request tracking for intelligent rate limiting
        self.last_sec_request = 0
        self.request_count = 0
        self.sec_request_times = []
        
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def _enforce_sec_rate_limit(self):
        """
        Intelligent SEC rate limiting: 8 requests per second with burst handling
        """
        now = time.time()
        
        # Clean old request times (older than 1 second)
        self.sec_request_times = [t for t in self.sec_request_times if now - t < 1.0]
        
        # If we're approaching the limit (8 requests in last second), wait
        if len(self.sec_request_times) >= 8:
            sleep_time = 1.0 - (now - self.sec_request_times[0]) + 0.01  # Small buffer
            if sleep_time > 0:
                time.sleep(sleep_time)
        
        # Add current request time
        self.sec_request_times.append(now)

    def _api_ninjas_request(self, endpoint: str, params: Dict) -> Optional[Dict]:
        """
        Optimized API Ninjas request with minimal delay
        """
        time.sleep(self.api_ninjas_delay)  # Minimal delay for API Ninjas
        
        url = f"{self.base_url}/{endpoint}"
        headers = {'X-Api-Key': self.api_key}
        
        try:
            response = self.session.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 429:
                self.logger.warning("API Ninjas rate limit hit, backing off...")
                time.sleep(2.0)  # Brief backoff for 429
                return None
                
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"API Ninjas request failed: {e}")
            return None

    def get_stock_price(self, ticker: str) -> Optional[float]:
        """Get current stock price for ticker"""
        result = self._api_ninjas_request('stockprice', {'ticker': ticker})
        
        if result and 'price' in result:
            return result['price']
        
        self.logger.warning(f"No stock price found for {ticker}")
        return None

    def get_sec_filings(self, ticker: str, months_back: int = 3) -> List[Dict]:
        """
        Get SEC filings using API Ninjas SEC endpoint
        """
        self.logger.info(f"🔍 Searching Form 4 filings for {ticker} (last {months_back} months)")
        
        # Use API Ninjas SEC endpoint with correct parameters
        try:
            result = self._api_ninjas_request('sec', {
                'ticker': ticker, 
                'filing': '4'  # Form 4 filings
            })
            
            if not result:
                self.logger.warning(f"No SEC data returned for {ticker}")
                return []
            
            # API Ninjas returns a list of filings
            filings = []
            if isinstance(result, list):
                # Calculate date range for filtering
                end_date = datetime.now()
                start_date = end_date - timedelta(days=months_back * 30)
                
                for filing in result:
                    if isinstance(filing, dict):
                        filing_date_str = filing.get('filing_date')
                        if filing_date_str:
                            try:
                                filing_date = datetime.strptime(filing_date_str, '%Y-%m-%d')
                                if start_date <= filing_date <= end_date:
                                    # Add required fields for our processing
                                    processed_filing = {
                                        'form': '4',
                                        'filing_date': filing_date_str,
                                        'filing_url': filing.get('filing_url', ''),
                                        'ticker': ticker
                                    }
                                    filings.append(processed_filing)
                            except ValueError:
                                # Skip filings with invalid dates
                                continue
            
            self.logger.info(f"Found {len(filings)} Form 4 filings for {ticker}")
            return filings
            
        except requests.exceptions.RequestException as e:
            if '429' in str(e) or 'rate limit' in str(e).lower():
                self.logger.warning(f"API Ninjas rate limit for {ticker}: {e}")
                time.sleep(2.0)
            else:
                self.logger.error(f"API Ninjas SEC request failed for {ticker}: {e}")
            return []
    
    def download_filing_content(self, filing: Dict) -> Optional[str]:
        """
        Download filing content from API Ninjas filing URL
        """
        filing_url = filing.get('filing_url', '')
        if not filing_url:
            self.logger.warning("No filing URL provided")
            return None
        
        # Enforce SEC rate limiting for content downloads
        self._enforce_sec_rate_limit()
        
        try:
            time.sleep(2.0)  # Additional delay for SEC website access
            
            response = self.session.get(
                filing_url,
                timeout=60,
                headers={
                    'User-Agent': 'PSU Target Extractor 1.0 (contact@example.com)',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
                }
            )
            
            if response.status_code == 429:
                self.logger.warning("SEC rate limit hit during content download, backing off...")
                time.sleep(10.0)
                return None
            
            response.raise_for_status()
            return response.text
            
        except requests.exceptions.Timeout:
            self.logger.warning(f"Timeout downloading filing content from {filing_url}")
            time.sleep(5.0)
            return None
        except requests.exceptions.RequestException as e:
            if '429' in str(e) or 'rate limit' in str(e).lower():
                self.logger.warning(f"Rate limit during content download: {e}")
                time.sleep(10.0)
            else:
                self.logger.error(f"Failed to download filing content: {e}")
            return None

    def search_form4_filings(self, ticker: str, months_back: int = 3) -> List[Dict]:
        """
        High-level method to search for Form 4 filings with content
        """
        self.logger.info(f"🔍 Searching Form 4 filings for {ticker} (last {months_back} months)")
        
        # Get filing metadata
        filings = self.get_sec_filings(ticker, months_back)
        
        if not filings:
            return []
        
        # Download content for each filing with optimized batching
        filings_with_content = []
        
        for filing in filings:
            content = self.download_filing_content(filing)
            
            if content:
                filing['content'] = content
                filings_with_content.append(filing)
                
                # Log progress for user feedback
                self.logger.info(f"✅ Downloaded filing {filing['filing_date']}")
            else:
                self.logger.warning(f"⚠️ Failed to download filing {filing['filing_date']}")
        
        self.logger.info(f"📁 Successfully downloaded {len(filings_with_content)}/{len(filings)} filings")
        return filings_with_content

    def __del__(self):
        """Clean up session on object destruction"""
        if hasattr(self, 'session'):
            self.session.close() 