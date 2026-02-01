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
# This looks for the secrets you set in GitHub Settings
POSTCODE = os.environ.get("BIN_POSTCODE")
HOUSE_NUMBER = os.environ.get("BIN_HOUSE_NUMBER")

# Fail safely if secrets aren't set
if not POSTCODE or not HOUSE_NUMBER:
    print("Error: BIN_POSTCODE or BIN_HOUSE_NUMBER not found. Check your GitHub Secrets.")
    sys.exit(1)

URL = "https://bolton.portal.uk.empro.verintcloudservices.com/site/empro-bolton/request/es_bin_collection_dates"

def get_bin_dates():
    print(f"Starting scraper for {POSTCODE} (House {HOUSE_NUMBER})...")

    chrome_options = Options()
    # Stability settings for Cloud/Headless environments
    chrome_options.add_argument("--headless=new") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    # Use a standard user agent to avoid detection
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        driver.get(URL)
        wait = WebDriverWait(driver, 30) # Increased timeout for cloud runners

        # 1. Handle Landing Page
        try:
            start_btn = driver.find_element(By.CSS_SELECTOR, "button.next")
            start_btn.click()
            time.sleep(1)
        except:
            pass 

        # 2. Enter Postcode
        print("Entering postcode...")
        postcode_input = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[contains(@aria-label, 'Postcode') or contains(@name, 'Postcode')]")))
        postcode_input.clear()
        postcode_input.send_keys(POSTCODE)
        
        find_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Find Address') or contains(@class, 'next')]")
        find_btn.click()
        
        time.sleep(3) # Wait for address list

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

        next_btn = driver.find_element(By.XPATH, "//button[contains(@class, 'next') or contains(text(), 'Next')]")
        next_btn.click()

        # 4. Scrape Dates
        print("Reading collection dates...")
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "field-content")))
        
        bins = []
        # Grab text from the form area where results are shown
        content_area = driver.find_element(By.CSS_SELECTOR, "form")
        text_content = content_area.text.split('\n')
        
        # Regex for dates like "Tuesday 14 October 2025"
        date_pattern = re.compile(r"(\w+ \d{1,2} \w+ \d{4})")
        
        current_bin = "Unknown Bin"
        
        for line in text_content:
            # Identify the bin type
            if "Bin" in line or "Container" in line:
                current_bin = line.strip()
            
            # Identify the date
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
        print(f"An error occurred: {e}")
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
        sys.exit(1) # Exit with error so GitHub notifies you of failure
