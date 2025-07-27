#!/usr/bin/env python3
"""
PSU Price Target Extractor - API Ninjas Integration
Uses API Ninjas for real-time stock prices and SEC filing data
Always uses 6 months and includes furthest_target_upside
"""

import re
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import time
import os

from api_ninjas_client import APINinjasClient


class PSUPriceExtractorAPINinjas:
    def __init__(self, api_key: str):
        self.api_client = APINinjasClient(api_key)
        
        # PSU-related regex patterns
        self.primary_patterns = [
            r'PSU.*?\$(\d+(?:\.\d+)?)',
            r'performance\s+stock\s+unit.*?\$(\d+(?:\.\d+)?)',
            r'performance.*?target.*?\$(\d+(?:\.\d+)?)',
            r'stock\s+price\s+target.*?\$(\d+(?:\.\d+)?)',
            r'price\s+target.*?\$(\d+(?:\.\d+)?)',
            r'performance\s+goal.*?\$(\d+(?:\.\d+)?)',
            r'vesting.*?target.*?\$(\d+(?:\.\d+)?)',
        ]
        
        self.secondary_patterns = [
            r'performance.*?\$(\d+(?:\.\d+)?)',
            r'target.*?\$(\d+(?:\.\d+)?)',
            r'goal.*?\$(\d+(?:\.\d+)?)',
            r'hurdle.*?\$(\d+(?:\.\d+)?)',
        ]
        
        # Price range patterns - capture ranges like "$12.50 to $20.00"
        self.range_patterns = [
            r'target.*?ranging?\s+from\s+\$(\d+(?:\.\d+)?)\s+to\s+\$(\d+(?:\.\d+)?)',
            r'price.*?target.*?\$(\d+(?:\.\d+)?)\s+to\s+\$(\d+(?:\.\d+)?)',
            r'target.*?\$(\d+(?:\.\d+)?)\s+to\s+\$(\d+(?:\.\d+)?)',
            r'from\s+\$(\d+(?:\.\d+)?)\s+to\s+\$(\d+(?:\.\d+)?)',
            r'\$(\d+(?:\.\d+)?)\s+to\s+\$(\d+(?:\.\d+)?)',
            r'\$(\d+(?:\.\d+)?)\s*-\s*\$(\d+(?:\.\d+)?)',
            r'between\s+\$(\d+(?:\.\d+)?)\s+and\s+\$(\d+(?:\.\d+)?)',
        ]
        
        # Multiple targets pattern
        self.multiple_targets_pattern = r'\$(\d+(?:\.\d+)?)(?:\s*[,\s]+\$(\d+(?:\.\d+)?))*(?:\s*[,\s]+\$(\d+(?:\.\d+)?))*(?:\s*[,\s]+\$(\d+(?:\.\d+)?))*'
        
        # Simple dollar pattern
        self.dollar_pattern = r'\$(\d+(?:\.\d+)?)'
    
    def extract_psu_price_targets(self, filing_text: str) -> List[float]:
        """
        Extract PSU price targets from filing text
        """
        targets = []
        
        # First, identify PSU-related sections with stronger filtering
        psu_keywords = [
            'PSU', 'performance stock unit', 'performance unit', 'performance share',
            'performance-based', 'performance target', 'performance goal',
            'vest', 'vesting', 'vesting schedule', 'vesting condition',
            'target', 'hurdle', 'threshold', 'performance metric'
        ]
        
        # Exclude non-PSU content that often contains dollar amounts
        exclude_keywords = [
            'warrant', 'exercise price', 'exercise of warrant',
            'transaction cost', 'advisory cost', 'legal fee', 'accounting fee',
            'merger', 'acquisition', 'exchange offer', 'tender offer',
            'dividend', 'distribution', 'split', 'spinoff',
            'underwriting', 'commission', 'expense', 'fee',
            'registration', 'prospectus', 'offering price',
            'market price', 'closing price', 'trading price',
            'book value', 'net worth', 'assets', 'liabilities'
        ]
        
        psu_sections = []
        
        # Improved sentence splitting that preserves price ranges
        # First, protect price ranges from being split
        protected_text = filing_text
        protected_text = re.sub(r'(\$\d+(?:\.\d+)?)\s+to\s+(\$\d+(?:\.\d+)?)', r'\1_TO_\2', protected_text)
        protected_text = re.sub(r'(\$\d+)\.(\d+)', r'\1_DOT_\2', protected_text)
        
        # Split text into sentences
        sentences = re.split(r'[.!?]', protected_text)
        
        for sentence in sentences:
            # Restore protected price ranges and decimals
            sentence = re.sub(r'_TO_', ' to ', sentence)
            sentence = re.sub(r'_DOT_', '.', sentence)
            
            sentence_lower = sentence.lower()
            
            # Must contain PSU-related keywords
            has_psu_keywords = any(keyword.lower() in sentence_lower for keyword in psu_keywords)
            
            # Must NOT contain excluded content
            has_excluded = any(exclude.lower() in sentence_lower for exclude in exclude_keywords)
            
            if has_psu_keywords and not has_excluded:
                psu_sections.append(sentence)
        
        # Only proceed if we found actual PSU-related content
        if not psu_sections:
            return []
        
        # First check for price ranges - these are often the most accurate
        for section in psu_sections:
            for pattern in self.range_patterns:
                for match in re.finditer(pattern, section, re.IGNORECASE):
                    # Extract all groups as potential targets
                    for i in range(1, len(match.groups()) + 1):
                        try:
                            target_str = match.group(i).replace('$', '').strip()
                            targets.append(float(target_str))
                        except ValueError:
                            continue
        
        # If no range targets found, apply primary and secondary patterns
        if not targets:
            for section in psu_sections:
                for pattern in self.primary_patterns:
                    for match in re.finditer(pattern, section, re.IGNORECASE):
                        try:
                            target_str = match.group(1).replace('$', '').strip()
                            targets.append(float(target_str))
                        except ValueError:
                            continue
                
                if not targets:
                    for section in psu_sections:
                        for pattern in self.secondary_patterns:
                            for match in re.finditer(pattern, section, re.IGNORECASE):
                                try:
                                    target_str = match.group(1).replace('$', '').strip()
                                    targets.append(float(target_str))
                                except ValueError:
                                    continue
        
        # Filter targets to a reasonable range for PSU targets
        # PSU targets are typically $5-$500 per share for most companies
        filtered_targets = [t for t in targets if 5.00 <= t <= 500.00]
        
        return list(set(filtered_targets)) # Remove duplicates
    
    def validate_psu_targets(self, targets: List[float], current_stock_price: float) -> List[float]:
        """
        Validate PSU targets against current stock price
        """
        valid_targets = []
        
        for target in targets:
            if target > current_stock_price:
                upside = (target - current_stock_price) / current_stock_price
                if 0.1 <= upside <= 10.0:  # 10% to 1000% upside
                    valid_targets.append(target)
        
        return valid_targets
    
    def extract_from_ticker(self, ticker: str, months_back: int = 3) -> Dict:
        """
        Extract PSU price targets from a specific ticker
        """
        try:
            print(f"🔍 Extracting PSU targets for {ticker.upper()}")
            
            # Get current stock price
            print(f"  Getting current stock price...")
            price_data = self.api_client.get_stock_price(ticker)
            if not price_data:
                return {
                    'ticker': ticker.upper(),
                    'error': f"Could not get current stock price for {ticker}",
                    'current_price': None,
                    'psu_targets': [],
                    'filing_source': None,
                    'filing_date': None,
                    'nearest_target_upside': None,
                    'furthest_target_upside': None,
                    'form4_filings_found': 0,
                    'filings_analyzed': [],
                    'filing_content_snippets': [],
                    'search_months_back': months_back
                }
            
            current_price = float(price_data)  # price_data is already a float
            print(f"  Current price: ${current_price}")
            
            # Get Form 4 filings
            filings = self.api_client.search_form4_filings(ticker, months_back=months_back)
            print(f"  Found {len(filings)} Form 4 filings")
            
            if not filings:
                return {
                    'ticker': ticker.upper(),
                    'current_price': current_price,
                    'psu_targets': [],
                    'filing_source': 'Form 4',
                    'filing_date': None,
                    'nearest_target_upside': None,
                    'furthest_target_upside': None,
                    'form4_filings_found': 0,
                    'filings_analyzed': [],
                    'filing_content_snippets': [],
                    'search_months_back': months_back
                }
            
            # Process each filing
            all_targets = []
            filings_analyzed = []
            filing_content_snippets = []
            
            for filing in filings:
                try:
                    filing_date = filing.get('filing_date')
                    filing_url = filing.get('filing_url')
                    form_type = filing.get('form', '4')  # Default to Form 4
                    
                    print(f"    Analyzing {filing_date} - {form_type}")
                    
                    # Download filing content (pass the entire filing dict)
                    content = self.api_client.download_filing_content(filing)
                    if not content:
                        print(f"      ❌ Could not download content")
                        continue  # Skip adding to filings_analyzed if no content
                    
                    # Extract targets from this filing
                    targets = self.extract_psu_price_targets(content)
                    
                    # Only include filings that found targets
                    if targets:
                        # Save filing content snippets that led to target extraction
                        import re
                        for target in targets:
                            # Look for the target in the content
                            target_str = f"${target:.2f}" if target % 1 == 0 else f"${target}"
                            if target_str in content:
                                # Find context around the target
                                index = content.find(target_str)
                                start = max(0, index - 500)  # 500 chars before
                                end = min(len(content), index + 500)  # 500 chars after
                                context = content[start:end]
                                
                                filing_content_snippets.append({
                                    'filing_date': filing_date,
                                    'filing_url': filing_url,
                                    'target_found': target,
                                    'target_string': target_str,
                                    'context': context,
                                    'position': index
                                })
                        
                        print(f"      Found {len(targets)} targets")
                        all_targets.extend(targets)
                        
                        # Only add to filings_analyzed if targets were found
                        filings_analyzed.append({
                            'date': filing_date,
                            'type': form_type,
                            'url': filing_url,
                            'targets_found': len(targets)
                        })
                    else:
                        print(f"      No targets found - skipping")
                    
                except Exception as e:
                    print(f"      ❌ Error processing filing: {e}")
                    # Don't add error filings to the analyzed list
                    continue
            
            # Remove duplicates and sort
            unique_targets = list(set(all_targets))
            unique_targets.sort()
            
            print(f"  Total unique targets found: {len(unique_targets)}")
            
            # Only proceed if we have multiple targets (2 or more)
            if len(unique_targets) < 2:
                print(f"  ❌ Only {len(unique_targets)} unique target(s) found - minimum 2 required")
                return {
                    'ticker': ticker.upper(),
                    'current_price': current_price,
                    'psu_targets': [],
                    'filing_source': 'Form 4',
                    'filing_date': None,
                    'nearest_target_upside': None,
                    'furthest_target_upside': None,
                    'form4_filings_found': len(filings),
                    'filings_analyzed': [],
                    'filing_content_snippets': [],
                    'search_months_back': months_back,
                    'rejection_reason': f'Only {len(unique_targets)} unique target(s) found - minimum 2 required'
                }
            
            # Validate targets
            if unique_targets:
                valid_targets = self.validate_psu_targets(unique_targets, current_price)
                print(f"  Valid targets after validation: {len(valid_targets)}")
            else:
                valid_targets = []
            
            # Only proceed if we have multiple valid targets (2 or more)
            if len(valid_targets) < 2:
                print(f"  ❌ Only {len(valid_targets)} valid target(s) after validation - minimum 2 required")
                return {
                    'ticker': ticker.upper(),
                    'current_price': current_price,
                    'psu_targets': [],
                    'filing_source': 'Form 4',
                    'filing_date': None,
                    'nearest_target_upside': None,
                    'furthest_target_upside': None,
                    'form4_filings_found': len(filings),
                    'filings_analyzed': [],
                    'filing_content_snippets': [],
                    'search_months_back': months_back,
                    'rejection_reason': f'Only {len(valid_targets)} valid target(s) after validation - minimum 2 required'
                }
            
            # Calculate upside percentages
            nearest_upside = None
            furthest_upside = None
            
            if valid_targets:
                nearest_upside = ((min(valid_targets) - current_price) / current_price) * 100
                furthest_upside = ((max(valid_targets) - current_price) / current_price) * 100
            
            # Get the filing date of the most recent filing with targets
            filing_date = None
            if filings_analyzed:
                # Find the most recent filing that had targets
                for filing in sorted(filings_analyzed, key=lambda x: x.get('date', ''), reverse=True):
                    if filing.get('targets_found', 0) > 0:
                        filing_date = filing.get('date')
                        break
            
            return {
                'ticker': ticker.upper(),
                'current_price': current_price,
                'psu_targets': valid_targets,
                'filing_source': 'Form 4',
                'filing_date': filing_date,
                'nearest_target_upside': nearest_upside,
                'furthest_target_upside': furthest_upside,
                'form4_filings_found': len(filings),
                'filings_analyzed': filings_analyzed,
                'filing_content_snippets': filing_content_snippets,
                'search_months_back': months_back
            }
            
        except Exception as e:
            print(f"❌ Error extracting from {ticker}: {e}")
            return {
                'ticker': ticker.upper(),
                'error': str(e),
                'current_price': None,
                'psu_targets': [],
                'filing_source': None,
                'filing_date': None,
                'nearest_target_upside': None,
                'furthest_target_upside': None,
                'form4_filings_found': 0,
                'filings_analyzed': [],
                'filing_content_snippets': [],
                'search_months_back': months_back
            }
    
    def process_tickers(self, tickers: List[str]) -> List[Dict]:
        """
        Process multiple tickers (always 6 months)
        """
        results = []
        
        for ticker in tickers:
            try:
                result = self.extract_from_ticker(ticker)
                results.append(result)
                
                # Rate limiting
                time.sleep(1)
                
            except Exception as e:
                print(f"Error processing {ticker}: {e}")
                results.append({
                    'ticker': ticker.upper(),
                    'psu_targets': [],
                    'error': str(e)
                })
        
        return results
    
    def save_results_to_file(self, results: List[Dict], filename: str = None) -> str:
        """
        Save results to JSON files in separate folders based on furthest_target_upside
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"psu_targets_api_ninjas_{timestamp}.json"
        
        # Create output directories
        output_dir = "output"
        high_upside_dir = os.path.join(output_dir, "high_upside_40plus")
        low_upside_dir = os.path.join(output_dir, "low_upside_below_40")
        
        for directory in [output_dir, high_upside_dir, low_upside_dir]:
            if not os.path.exists(directory):
                os.makedirs(directory)
        
        # Separate results by furthest_target_upside
        high_upside_results = []
        low_upside_results = []
        
        for result in results:
            furthest_upside = result.get('furthest_target_upside')
            if furthest_upside is not None and furthest_upside > 40:
                high_upside_results.append(result)
            else:
                low_upside_results.append(result)
        
        # Create output data
        output_data = {
            'extraction_date': datetime.now().isoformat(),
            'system': 'PSU Price Target Extractor - API Ninjas Integration (6 months)',
            'total_companies_analyzed': len(results),
            'companies_with_targets': len([r for r in results if r.get('psu_targets')]),
            'high_upside_companies': len(high_upside_results),
            'low_upside_companies': len(low_upside_results),
            'results': results
        }
        
        # Save main results file
        main_filepath = os.path.join(output_dir, filename)
        with open(main_filepath, 'w') as f:
            json.dump(output_data, f, indent=2)
        
        # Save high upside results
        if high_upside_results:
            high_upside_filename = f"high_upside_{filename}"
            high_upside_filepath = os.path.join(high_upside_dir, high_upside_filename)
            high_upside_data = {
                'extraction_date': datetime.now().isoformat(),
                'system': 'PSU Price Target Extractor - High Upside (40%+)',
                'total_companies': len(high_upside_results),
                'threshold': 'furthest_target_upside > 40%',
                'results': high_upside_results
            }
            with open(high_upside_filepath, 'w') as f:
                json.dump(high_upside_data, f, indent=2)
            print(f"✅ High upside results saved to: {high_upside_filepath}")
        
        # Save low upside results
        if low_upside_results:
            low_upside_filename = f"low_upside_{filename}"
            low_upside_filepath = os.path.join(low_upside_dir, low_upside_filename)
            low_upside_data = {
                'extraction_date': datetime.now().isoformat(),
                'system': 'PSU Price Target Extractor - Low Upside (<40%)',
                'total_companies': len(low_upside_results),
                'threshold': 'furthest_target_upside <= 40%',
                'results': low_upside_results
            }
            with open(low_upside_filepath, 'w') as f:
                json.dump(low_upside_data, f, indent=2)
            print(f"✅ Low upside results saved to: {low_upside_filepath}")
        
        print(f"\n✅ Results saved to: {main_filepath}")
        print(f"📁 High upside (>40%): {len(high_upside_results)} companies")
        print(f"📁 Low upside (≤40%): {len(low_upside_results)} companies")
        
        return main_filepath


# Test the API Ninjas integration
if __name__ == "__main__":
    # You'll need to provide your API key
    API_KEY = "YOUR_API_NINJAS_KEY"  # Replace with your actual API key
    
    if API_KEY == "YOUR_API_NINJAS_KEY":
        print("Please set your API Ninjas API key in the script")
        exit(1)
    
    extractor = PSUPriceExtractorAPINinjas(API_KEY)
    
    # Test with HROW and TH
    test_tickers = ["HROW", "TH"]
    
    print("Testing API Ninjas Integration (6 months, with furthest_target_upside)")
    print("=" * 70)
    
    for ticker in test_tickers:
        print(f"\nTesting {ticker}...")
        result = extractor.extract_from_ticker(ticker)
        
        if result.get('psu_targets'):
            print(f"✅ Found PSU targets: {result['psu_targets']}")
            print(f"   Current price: ${result['current_price']}")
            print(f"   Nearest target upside: {result['nearest_target_upside']:.1f}%")
            print(f"   Furthest target upside: {result['furthest_target_upside']:.1f}%")
        else:
            print(f"❌ No PSU targets found")
            if result.get('error'):
                print(f"   Error: {result['error']}")
    
    # Save results
    results = extractor.process_tickers(test_tickers)
    output_file = extractor.save_results_to_file(results, "test_api_ninjas_results.json")
    
    print(f"\n" + "=" * 70)
    print("API Ninjas integration test complete!")
    print(f"Results saved to: {output_file}") 