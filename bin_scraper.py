name: Update Bin Calendar

on:
  schedule:
    - cron: '0 6 * * 0' # Runs at 06:00 UTC every Sunday
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'

      - name: Install dependencies
        run: |
          pip install selenium ics

      - name: Run Scraper
        env:
          # This connects the GitHub Secret to the Python Script
          BIN_POSTCODE: ${{ secrets.BIN_POSTCODE }}
          BIN_HOUSE_NUMBER: ${{ secrets.BIN_HOUSE_NUMBER }}
        run: python bin_scraper.py

      - name: Commit and Push changes
        run: |
          git config --global user.name "BinBot"
          git config --global user.email "actions@github.com"
          git add bolton_bins.ics
          git diff --quiet && git diff --staged --quiet || (git commit -m "Update bin dates" && git push)
