#!/usr/bin/env python3
"""
API Ninjas Client - Stock Price and SEC Filing Integration
Uses API Ninjas for real-time stock prices and SEC filing data
"""

import requests
import json
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import time


class APINinjasClient:
    """
    API Ninjas client for stock prices and SEC filings
    """
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.stock_price_url = "https://api.api-ninjas.com/v1/stockprice"
        self.sec_url = "https://api.api-ninjas.com/v1/sec"
        
        # Headers for API Ninjas
        self.headers = {
            'X-Api-Key': api_key,
            'Content-Type': 'application/json'
        }
        
        # Headers for SEC API (for downloading filing content)
        self.sec_headers = {
            'User-Agent': 'PSU Extractor Tool (your-email@domain.com)',
            'Accept': 'application/json, text/html, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
    
    def get_stock_price(self, ticker: str) -> Optional[Dict]:
        """
        Get current stock price using API Ninjas
        """
        try:
            # Add delay before API Ninjas calls
            time.sleep(1.0)  # 1 second delay before API Ninjas calls
            
            params = {'ticker': ticker}
            response = requests.get(self.stock_price_url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            return {
                'ticker': data.get('ticker'),
                'name': data.get('name'),
                'price': data.get('price'),
                'exchange': data.get('exchange'),
                'currency': data.get('currency'),
                'updated': data.get('updated')
            }
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                print(f"API Ninjas rate limit hit for {ticker}")
                time.sleep(5)  # Wait 5 seconds on rate limit
            else:
                print(f"HTTP error getting stock price for {ticker}: {e}")
            return None
        except Exception as e:
            print(f"Error getting stock price for {ticker}: {e}")
            return None
    
    def get_sec_filings(self, ticker: str, filing_type: str = "DEF14A", 
                       start_date: str = None, end_date: str = None, 
                       limit: int = 10) -> List[Dict]:
        """
        Get SEC filings using API Ninjas
        """
        try:
            # Add delay before API Ninjas calls
            time.sleep(1.0)  # 1 second delay before API Ninjas calls
            
            params = {
                'ticker': ticker,
                'filing': filing_type,
                'limit': limit
            }
            
            # Add date parameters if provided
            if start_date:
                params['start'] = start_date
            if end_date:
                params['end'] = end_date
            
            response = requests.get(self.sec_url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            
            filings = response.json()
            return filings
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                print(f"API Ninjas rate limit hit for {ticker} SEC filings")
                time.sleep(5)  # Wait 5 seconds on rate limit
            else:
                print(f"HTTP error getting SEC filings for {ticker}: {e}")
            return []
        except Exception as e:
            print(f"Error getting SEC filings for {ticker}: {e}")
            return []
    
    def get_company_cik_from_filings(self, ticker: str) -> Optional[str]:
        """
        Extract CIK from SEC filing URLs
        """
        try:
            # Get any recent filing to extract CIK
            filings = self.get_sec_filings(ticker, "10-K", limit=1)
            
            if filings and len(filings) > 0:
                filing_url = filings[0].get('filing_url', '')
                
                # Extract CIK from URL pattern: /edgar/data/{CIK}/
                match = re.search(r'/edgar/data/(\d+)/', filing_url)
                if match:
                    cik = match.group(1)
                    return cik.zfill(10)
            
            return None
            
        except Exception as e:
            print(f"Error extracting CIK for {ticker}: {e}")
            return None
    
    def download_filing_content(self, filing_url: str) -> Optional[str]:
        """
        Download filing content from SEC with aggressive rate limiting
        """
        try:
            # Add aggressive delay before SEC website calls to avoid rate limiting
            time.sleep(2.0)  # 2 second delay before each SEC website call
            
            response = requests.get(filing_url, headers=self.sec_headers, timeout=60)
            response.raise_for_status()
            
            return response.text
            
        except requests.exceptions.Timeout:
            print(f"Timeout downloading filing from {filing_url}")
            time.sleep(5)  # Wait 5 seconds on timeout
            return None
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                print(f"Rate limit hit downloading filing from {filing_url}")
                time.sleep(10)  # Wait 10 seconds on rate limit
                return None
            else:
                print(f"HTTP error downloading filing from {filing_url}: {e}")
                time.sleep(3)  # Wait 3 seconds on other HTTP errors
                return None
        except Exception as e:
            print(f"Error downloading filing from {filing_url}: {e}")
            time.sleep(3)  # Wait 3 seconds on any error
            return None
    
    def search_form4_filings(self, ticker: str, months_back: int = 12) -> List[Dict]:
        """
        Search for Form 4 filings using API Ninjas
        """
        print(f"Searching Form 4 filings for {ticker.upper()}")
        print(f"  Date range: {months_back} months back")
        
        # Calculate date range
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=months_back * 30)).strftime('%Y-%m-%d')
        
        # Get Form 4 filings
        filings = self.get_sec_filings(
            ticker=ticker,
            filing_type="4",
            start_date=start_date,
            end_date=end_date,
            limit=100  # Get more filings
        )
        
        print(f"  Found {len(filings)} total filings from API")
        
        # Explicitly filter for Form 4 filings only
        form4_filings = []
        for filing in filings:
            form_type = filing.get('form_type', '').upper()
            if form_type in ['4', 'FORM 4', 'FORM4']:
                form4_filings.append(filing)
            else:
                print(f"    Filtered out non-Form 4 filing: {form_type}")
        
        print(f"  After filtering: {len(form4_filings)} Form 4 filings")
        
        # Format filings for consistency
        formatted_filings = []
        for filing in form4_filings:
            formatted_filings.append({
                'ticker': ticker.upper(),
                'filing_date': filing.get('filing_date'),
                'filing_url': filing.get('filing_url'),
                'form_type': filing.get('form_type'),
                'accession_number': filing.get('accession_number', '')
            })
        
        # Sort by date (newest first)
        formatted_filings.sort(key=lambda x: x['filing_date'], reverse=True)
        
        return formatted_filings
    
    def search_def14a_filings(self, ticker: str, months_back: int = 12) -> List[Dict]:
        """
        Search for DEF14A filings using API Ninjas
        """
        print(f"Searching DEF14A filings for {ticker.upper()}")
        print(f"  Date range: {months_back} months back")
        
        # Calculate date range
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=months_back * 30)).strftime('%Y-%m-%d')
        
        # Get DEF14A filings
        filings = self.get_sec_filings(
            ticker=ticker,
            filing_type="DEF14A",
            start_date=start_date,
            end_date=end_date,
            limit=50
        )
        
        print(f"  Found {len(filings)} DEF14A filings")
        
        # Format filings for consistency
        formatted_filings = []
        for filing in filings:
            formatted_filings.append({
                'ticker': ticker.upper(),
                'filing_date': filing.get('filing_date'),
                'filing_url': filing.get('filing_url'),
                'form_type': filing.get('form_type'),
                'accession_number': filing.get('accession_number', '')
            })
        
        # Sort by date (newest first)
        formatted_filings.sort(key=lambda x: x['filing_date'], reverse=True)
        
        return formatted_filings


# Test the API Ninjas client
if __name__ == "__main__":
    # You'll need to provide your API key
    API_KEY = "YOUR_API_NINJAS_KEY"  # Replace with your actual API key
    
    if API_KEY == "YOUR_API_NINJAS_KEY":
        print("Please set your API Ninjas API key in the script")
        exit(1)
    
    client = APINinjasClient(API_KEY)
    
    print("API Ninjas Client Test")
    print("=" * 50)
    
    # Test stock price
    print("\nTesting stock price for AAPL:")
    aapl_price = client.get_stock_price("AAPL")
    if aapl_price:
        print(f"  Ticker: {aapl_price['ticker']}")
        print(f"  Name: {aapl_price['name']}")
        print(f"  Price: ${aapl_price['price']}")
        print(f"  Exchange: {aapl_price['exchange']}")
        print(f"  Currency: {aapl_price['currency']}")
    else:
        print("  Failed to get AAPL price")
    
    # Test SEC filings
    print("\nTesting SEC filings for AAPL:")
    aapl_filings = client.get_sec_filings("AAPL", "10-K", limit=2)
    if aapl_filings:
        print(f"  Found {len(aapl_filings)} 10-K filings")
        for filing in aapl_filings:
            print(f"    {filing['filing_date']} - {filing['form_type']}")
    else:
        print("  Failed to get AAPL filings")
    
    # Test Form 4 filings
    print("\nTesting Form 4 filings for HROW:")
    hrow_form4 = client.search_form4_filings("HROW", months_back=6)
    if hrow_form4:
        print(f"  Found {len(hrow_form4)} Form 4 filings")
        for filing in hrow_form4[:3]:
            print(f"    {filing['filing_date']} - {filing['form_type']}")
    else:
        print("  Failed to get HROW Form 4 filings")
    
    print(f"\n" + "=" * 50)
    print("API Ninjas integration ready!")
    print("✅ Real-time stock prices")
    print("✅ SEC filing data")
    print("✅ Automatic CIK extraction")
    print("✅ Date range filtering") 