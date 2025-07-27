#!/usr/bin/env python3
"""
Configuration for API Ninjas Integration
"""

import os
from typing import Optional


class APINinjasConfig:
    """
    Configuration class for API Ninjas integration
    """
    
    def __init__(self):
        self.api_key = self._get_api_key()
        self.stock_price_url = "https://api.api-ninjas.com/v1/stockprice"
        self.sec_url = "https://api.api-ninjas.com/v1/sec"
        
        # Rate limiting settings
        self.requests_per_minute = 50  # API Ninjas free tier limit
        self.delay_between_requests = 1.2  # seconds
        
        # Filing search settings
        self.default_months_back = 12
        self.max_filings_per_search = 100
        
        # Supported filing types
        self.supported_filing_types = [
            "10-K", "10-Q", "S-1", "S-2", "S-3", "8-K", "DEF14A", "13D", "4"
        ]
    
    def _get_api_key(self) -> Optional[str]:
        """
        Get API key from environment variable or prompt user
        """
        # Try environment variable first
        api_key = os.getenv('API_NINJAS_KEY')
        
        if api_key:
            return api_key
        
        # Try to read from file
        try:
            with open('.api_ninjas_key', 'r') as f:
                api_key = f.read().strip()
                if api_key:
                    return api_key
        except FileNotFoundError:
            pass
        
        # Prompt user
        print("API Ninjas API Key Required")
        print("=" * 40)
        print("To use the API Ninjas integration, you need an API key.")
        print("1. Sign up at: https://api-ninjas.com/")
        print("2. Get your API key from your dashboard")
        print("3. Enter it below or set environment variable API_NINJAS_KEY")
        print()
        
        api_key = input("Enter your API Ninjas API key: ").strip()
        
        if api_key:
            # Save to file for future use
            try:
                with open('.api_ninjas_key', 'w') as f:
                    f.write(api_key)
                print("✅ API key saved to .api_ninjas_key file")
            except Exception as e:
                print(f"⚠️  Could not save API key to file: {e}")
            
            return api_key
        
        return None
    
    def is_valid(self) -> bool:
        """
        Check if configuration is valid
        """
        return self.api_key is not None and len(self.api_key) > 0
    
    def get_headers(self) -> dict:
        """
        Get headers for API requests
        """
        return {
            'X-Api-Key': self.api_key,
            'Content-Type': 'application/json'
        }
    
    def get_sec_headers(self) -> dict:
        """
        Get headers for SEC API requests
        """
        return {
            'User-Agent': 'PSU Extractor Tool (your-email@domain.com)',
            'Accept': 'application/json, text/html, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }


# Global configuration instance
config = APINinjasConfig()


def get_config() -> APINinjasConfig:
    """
    Get the global configuration instance
    """
    return config


def validate_config() -> bool:
    """
    Validate the configuration
    """
    if not config.is_valid():
        print("❌ Invalid API Ninjas configuration")
        print("Please set up your API key in config_api_ninjas.py")
        return False
    
    print("✅ API Ninjas configuration is valid")
    return True


if __name__ == "__main__":
    print("API Ninjas Configuration Test")
    print("=" * 40)
    
    if validate_config():
        print(f"API Key: {'*' * (len(config.api_key) - 4) + config.api_key[-4:] if config.api_key else 'None'}")
        print(f"Stock Price URL: {config.stock_price_url}")
        print(f"SEC URL: {config.sec_url}")
        print(f"Rate Limit: {config.requests_per_minute} requests/minute")
        print(f"Default Search: {config.default_months_back} months back")
        print(f"Supported Filing Types: {', '.join(config.supported_filing_types)}")
    else:
        print("❌ Configuration validation failed") 