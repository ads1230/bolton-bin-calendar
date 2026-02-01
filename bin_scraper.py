import time
import re
import os
import sys
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from ics import Calendar, Event

# --- CONFIGURATION (SECURE) ---
POSTCODE = os.environ.get("BIN_POSTCODE")
HOUSE_NUMBER = os.environ.get("BIN_HOUSE_NUMBER")

if not POSTCODE or not HOUSE_NUMBER:
    # Fallback for local testing if secrets are missing
    POSTCODE = "BL1 5DB"
    HOUSE_NUMBER = "36"
    print("Warning: Using default test credentials (Secrets not found).")

URL = "https://bolton.portal.uk.empro.verintcloudservices.com/site/empro-bolton/request/es_bin_collection_dates"

def get_bin_dates():
    print(f"Starting scraper for {POSTCODE}...")

    chrome_options = Options()
    # Cloud stability settings
    chrome_options.add_argument("--headless=new") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    
    # Stealth settings to bypass basic bot detection
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        driver.get(URL)
        wait = WebDriverWait(driver, 30)
        print(f"Page loaded: {driver.title}")

        # 0. Handle Cookie Banner (If present)
        try:
            cookie_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Accept') or contains(text(), 'Allow') or contains(@class, 'cookie')]")
            cookie_btn.click()
            print("Cookie banner clicked.")
            time.sleep(1)
        except:
            pass 

        # 1. Handle "Start now" Landing Page (Specific fix for your screenshot)
        try:
            print("Looking for 'Start now' button...")
            # Search for button or link with "Start now" text
            start_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Start now')]")))
            start_btn.click()
            print("Clicked 'Start now'.")
            time.sleep(2) 
        except Exception as e:
            print(f"Start button logic skipped (maybe not on landing page?): {e}")

        # 2. Enter Postcode
        print("Entering postcode...")
        postcode_input = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[contains(@aria-label, 'Postcode') or contains(@name, 'Postcode')]")))
        postcode_input.clear()
        postcode_input.send_keys(POSTCODE)
        
        # Click Find Address
        find_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Find Address') or contains(@class, 'next')]")
        find_btn.click()
        
        time.sleep(4) # Wait for address dropdown

        # 3. Select Address
        print("Selecting address...")
        address_select = wait.until(EC.presence_of_element_located((By.TAG_NAME, "select")))
        select = Select(address_select)
        
        found_address = False
        for option in select.options:
            if HOUSE_NUMBER in option.text:
                select.select_by_visible_text(option.text)
                found_address = True
                break
        
        if not found_address:
            print(f"Warning: Could not match house number '{HOUSE_NUMBER}'. Selecting first option.")
            select.select_by_index(1) 

        # Click Next after selecting address
        next_btn = driver.find_element(By.XPATH, "//button[contains(@class, 'next') or contains(text(), 'Next')]")
        next_btn.click()

        # 4. Scrape Dates
        print("Reading collection dates...")
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "field-content")))
        
        bins = []
        content_area = driver.find_element(By.CSS_SELECTOR, "form")
        text_content = content_area.text.split('\n')
        
        date_pattern = re.compile(r"(\w+ \d{1,2} \w+ \d{4})")
        current_bin = "Unknown Bin"
        
        for line in text_content:
            if "Bin" in line or "Container" in line:
                current_bin = line.strip()
            
            match = date_pattern.search(line)
            if match:
                date_str = match.group(1)
                try:
                    date_obj = datetime.strptime(date_str, "%A %d %B %Y")
                    bins.append((current_bin, date_obj))
                    print(f"Found: {current_bin} on {date_str}")
                except Exception as e:
                    print(f"Skipping date parse error: {e}")

        return bins

    except Exception as e:
        print(f"An error occurred. Page Title: {driver.title}")
        print(f"Error details: {str(e)}")
        # Save screenshot for debugging
        driver.save_screenshot("error_screenshot.png")
        return []
    finally:
        driver.quit()

def create_ics(bin_data):
    c = Calendar()
    for bin_name, bin_date in bin_data:
        e = Event()
        e.name = f"♻️ {bin_name}"
        e.begin = bin_date.replace(hour=7, minute=0, second=0)
        e.duration = {"hours": 1}
        e.description = f"Put out the {bin_name} today."
        c.events.add(e)
    
    filename = "bolton_bins.ics"
    with open(filename, 'w') as f:
        f.writelines(c.serialize())
    print(f"\n[FILE SAVED] Calendar file saved to: {filename}")

if __name__ == "__main__":
    data = get_bin_dates()
    if data:
        create_ics(data)
    else:
        print("No dates found.")
        sys.exit(1)
