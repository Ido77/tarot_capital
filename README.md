# PSU Price Target Extractor

Extract specific dollar amounts from PSU (Performance Stock Unit) vesting conditions to identify management's price targets from SEC filings.

## Overview

This tool analyzes SEC filings (primarily DEF 14A proxy statements and Form 4 insider trading reports) to extract concrete stock price targets that management has set for their PSU vesting conditions. These targets represent management's bets on future stock performance.

## Features

- **Multi-source extraction**: Searches both DEF 14A (primary) and Form 4 (secondary) filings
- **Advanced regex patterns**: 7 different patterns to catch various PSU target formats
- **Validation filters**: Ensures targets are reasonable and above current stock price
- **Upside calculations**: Shows percentage upside to nearest and highest targets
- **Batch processing**: Process multiple companies simultaneously
- **Multiple output formats**: JSON and CSV export options

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd psu-price-target-extractor
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Update configuration:
Edit `config.py` to add your email in the `SEC_USER_AGENT` field (required for SEC API access).

## Usage

### Basic Usage

```bash
python main.py
```

This will:
1. Run regex pattern tests
2. Process sample companies from `config.py`
3. Extract PSU targets from SEC filings
4. Filter results by minimum upside threshold (50% by default)
5. Display results and save to file

### Custom Company List

Edit `config.py` to add your target companies:

```python
SAMPLE_COMPANIES = [
    {
        'cik': '0001841668',
        'symbol': 'BLND',
        'name': 'Blend Labs, Inc.',
        'current_price': 3.50
    },
    # Add more companies...
]
```

### Configuration Options

Key settings in `config.py`:

- `MIN_UPSIDE_THRESHOLD`: Minimum upside percentage to include in results (default: 50%)
- `DEFAULT_MONTHS_BACK`: How far back to search for filings (default: 12 months)
- `OUTPUT_FORMAT`: Output format - 'json' or 'csv'
- `SEC_RATE_LIMIT_DELAY`: Delay between SEC API requests (default: 0.1 seconds)

## What We Extract

### Target Examples
```
"PSUs will vest upon the Company's stock price reaching $7.00"
"Performance hurdles of $10.00, $15.00, and $20.00 per share"
"Stock price targets of $12.50 and $18.75"
"Market-based vesting at $25.00 per share"
```

### What We Filter Out
- Percentage-based targets ("25% above grant price")
- Relative performance ("outperform S&P 500")
- Non-price metrics ("revenue targets")

## Regex Patterns

The system uses 7 different regex patterns in order of confidence:

### Primary Patterns (High Confidence)
1. `PSU?s?\s+.*?(?:vest|vesting).*?\$(\d+\.?\d*)`
2. `stock\s+price\s+.*?(?:target|hurdle|threshold).*?\$(\d+\.?\d*)`
3. `performance\s+.*?(?:hurdle|target).*?\$(\d+\.?\d*)`
4. `market.?based\s+.*?(?:vest|target).*?\$(\d+\.?\d*)`

### Secondary Patterns (Medium Confidence)
5. `\$(\d+\.?\d*)\s+per\s+share.*?vest`
6. `(?:reach|achieving?)\s+.*?\$(\d+\.?\d*)`
7. `stock\s+price\s+of\s+\$(\d+\.?\d*)`

## Output Format

For each company with PSU targets, the system returns:

```json
{
    "symbol": "BLND",
    "psu_targets": [7.0, 10.0, 15.0, 20.0],
    "filing_source": "DEF 14A",
    "filing_date": "2025-03-15",
    "current_price": 3.50,
    "nearest_target_upside": 100.0
}
```

## SEC Filing Sources

### DEF 14A (Proxy Statements) - Primary Source
- **Why**: Contains detailed compensation discussions with specific PSU vesting price hurdles
- **When Filed**: Annually (usually March-May)
- **Where to Find**: "Compensation Discussion and Analysis" section

### Form 4 (Insider Trading) - Secondary Source
- **Why**: Shows PSU grants in real-time but may lack specific price targets
- **When Filed**: Within 2 business days of grant
- **Where to Find**: Transaction descriptions

## Implementation Details

### Core Classes

- `PSUPriceExtractor`: Main extraction class with all regex patterns and SEC API integration
- Configuration management through `config.py`
- Test suite with sample cases

### Key Methods

- `extract_psu_price_targets()`: Core regex extraction logic
- `validate_psu_targets()`: Filters unrealistic targets
- `get_company_filings()`: Fetches filings from SEC EDGAR API
- `download_filing_content()`: Downloads filing text content

### Error Handling

- Graceful handling of SEC API failures
- Rate limiting to respect SEC guidelines
- Validation of price formats and ranges
- Duplicate removal and sorting

## Example Results

```
PSU PRICE TARGETS EXTRACTION RESULTS
================================================================================

BLND (Current: $3.50)
  PSU Targets: $7.00, $10.00, $15.00, $20.00
  Source: DEF 14A (2025-03-15)
  Nearest Target Upside: 100.0%
  Highest Target Upside: 471.4%
----------------------------------------
```

## Limitations

1. **SEC API Rate Limits**: Respects SEC guidelines with delays between requests
2. **Filing Availability**: Depends on companies having recent DEF 14A or Form 4 filings
3. **Pattern Matching**: May miss targets written in unusual formats
4. **Price Validation**: Filters out targets below current price or with unrealistic upside

## Contributing

1. Fork the repository
2. Add new regex patterns for edge cases
3. Improve validation logic
4. Add support for additional filing types
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This tool is for educational and research purposes. Always verify extracted data against original SEC filings. The authors are not responsible for any investment decisions made based on this data. 