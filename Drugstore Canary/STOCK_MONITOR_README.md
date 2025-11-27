# Stock Monitoring Bot - Quick Start Guide

## Installation

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

## Usage

### 1. Run Once (Test)

```bash
# Run all scrapers once
python bots/bot_scheduler.py --once --debug
```

### 2. Scheduled Monitoring

```bash
# Run every 2 hours (default)
python bots/bot_scheduler.py

# Custom interval (e.g., every 4 hours)
python bots/bot_scheduler.py --interval 4
```

### 3. Test Individual Scrapers

```bash
# Test Grab scraper
python bots/grab_scraper.py

# Test Lineman scraper
python bots/lineman_scraper.py
```

### 4. Analyze Results

```bash
# Generate stock analysis report
python bots/stock_analyzer.py
```

## Results

Results are saved to `bot_results/`:
- `stock_check_YYYYMMDD_HHMMSS.json` - Individual runs
- `latest.json` - Most recent results
- `stock_analysis_report.json` - Analysis report

## Configuration

Edit `bots/key_items.json` to customize tracked medicines.

## Notes

- Bots run in headless mode by default
- Screenshots saved to `screenshots/` on errors
- Results include stockout rate and availability status
