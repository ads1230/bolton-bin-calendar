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
    POSTCODE = "BL1 5DB"
    HOUSE_NUMBER = "36"
    print("Warning: Using default test credentials.")

URL = "https://bolton.portal.uk.empro.verintcloudservices.com/site/empro-bolton/request/es_bin_collection_dates"

def get_bin_dates():
    print(f"Starting scraper for {POSTCODE}...")

    chrome_options = Options()
    chrome_options.add_argument("--headless=new") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        driver.get(URL)
        wait = WebDriverWait(driver, 30)
        print(f"Page loaded: {driver.title}")

        # 0. Cookie Banner
        try:
            cookie_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Accept') or contains(text(), 'Allow') or contains(@class, 'cookie')]")
            cookie_btn.click()
            time.sleep(1)
        except:
            pass 

        # 1. "Start now" Button
        try:
            start_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Start now')]")))
            start_btn.click()
            print("Clicked 'Start now'.")
            time.sleep(2) 
        except:
            print("Start button not found (might be on form).")

        # 2. Enter Postcode (Smart Find)
        print("Entering postcode...")
        postcode_input = None
        try:
            # Try finding by label first
            postcode_input = wait.until(EC.element_to_be_clickable((By.XPATH, "//label[contains(., 'Postcode')]/following::input[1]")))
        except:
            # Fallback to any visible text input
            inputs = driver.find_elements(By.TAG_NAME, "input")
            for inp in inputs:
                if inp.is_displayed() and inp.get_attribute("type") in ["text", "search", "email", "tel", ""]:
                    postcode_input = inp
                    break
        
        if postcode_input:
            postcode_input.clear()
            postcode_input.send_keys(POSTCODE)
        else:
            raise Exception("Could not find Postcode input.")

        # 3. Click Find Address
        print("Clicking 'Find address'...")
        find_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Find')]")))
        find_btn.click()
        
        time.sleep(4) 

        # 4. Select Address
        print("Selecting address...")
        try:
            address_select = wait.until(EC.presence_of_element_located((By.TAG_NAME, "select")))
            select = Select(address_select)
            found_address = False
            for option in select.options:
                if HOUSE_NUMBER in option.text:
                    select.select_by_visible_text(option.text)
                    found_address = True
                    print(f"Selected: {option.text}")
                    break
            if not found_address:
                select.select_by_index(1)
        except:
            print("Could not select address from dropdown (maybe it auto-selected?). Continuing...")

        # 5. Click Continue (FIXED: Was failing here looking for 'Next')
        print("Clicking Continue...")
        # Look for 'Continue' OR 'Next'
        continue_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Continue') or contains(text(), 'Next')]")))
        continue_btn.click()

        # 6. Scrape Dates
        print("Reading collection dates...")
        # Wait for either 'field-content' OR text that looks like a bin collection
        try:
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "field-content")))
        except:
            # Fallback: wait for the word "Bin" to appear in body
            wait.until(EC.text_to_be_present_in_element((By.TAG_NAME, "body"), "Bin"))
        
        bins = []
        # Grab all text from the form to be safe
        content_area = driver.find_element(By.TAG_NAME, "form")
        text_content = content_area.text.split('\n')
        
        date_pattern = re.compile(r"(\w+ \d{1,2} \w+ \d{4})")
        current_bin = "Unknown Bin"
        
        for line in text_content:
            line = line.strip()
            if not line: continue
            
            # Heuristic: If line contains 'Bin' or 'Container', it's a label
            if "Bin" in line or "Container" in line:
                current_bin = line
            
            match = date_pattern.search(line)
            if match:
                date_str = match.group(1)
                try:
                    date_obj = datetime.strptime(date_str, "%A %d %B %Y")
                    # Only add if we haven't seen this exact combo (deduplication)
                    if not any(b[0] == current_bin and b[1] == date_obj for b in bins):
                        bins.append((current_bin, date_obj))
                        print(f"Found: {current_bin} on {date_str}")
                except Exception as e:
                    print(f"Skipping date parse error: {e}")

        return bins

    except Exception as e:
        print(f"An error occurred. Page Title: {driver.title}")
        print(f"Error details: {str(e)}")
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
