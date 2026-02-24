import os
import time
import logging
import re
import urllib.request
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException

from config import USERNAME, PASSWORD

# ========================
# CONFIGURATION
# ========================
LOGIN_URL = "https://app.acadoinformatics.com/syllabus/department/login/"
TOOL_URL = "https://app.acadoinformatics.com/syllabus/department/tools/MeritForms"
DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")

# ========================
# LOGGING SETUP
# ========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("run_logs.txt"),
        logging.StreamHandler()
    ]
)

def sanitize_filename(name):
    """Sanitizes strings to be safe for filenames and folder paths."""
    return re.sub(r'[<>:"/\\|?*]', '_', name).strip()

def ensure_logged_in(driver):
    """Checks if session expired and logs back in if needed."""
    try:
        if len(driver.find_elements(By.NAME, "username")) > 0:
            logging.warning("Session expired. Logging in again...")
            driver.find_element(By.NAME, "username").send_keys(USERNAME)
            driver.find_element(By.NAME, "password").send_keys(PASSWORD)
            driver.find_element(By.XPATH, "//button[contains(text(), 'Log In')]").click()
            time.sleep(3)
            
            # Navigate back to tool
            if "MeritForms" not in driver.current_url:
                driver.get(TOOL_URL)
                time.sleep(3)
    except Exception as e:
         logging.error(f"Error checking login state: {e}")

# ========================
# SELENIUM SETUP
# ========================
chrome_options = Options()
chrome_options.add_experimental_option("prefs", {
    "download.default_directory": DOWNLOAD_DIR,
    "download.prompt_for_download": False,
    "download.directory_upgrade": True,
    "safebrowsing.enabled": True,
    "plugins.always_open_pdf_externally": True
})

# Initialize driver
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
driver.maximize_window()

try:
    # ========================
    # INITIAL LOGIN
    # ========================
    logging.info("Starting script...")
    driver.get(LOGIN_URL)
    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.NAME, "username"))).send_keys(USERNAME)
    driver.find_element(By.NAME, "password").send_keys(PASSWORD)
    driver.find_element(By.XPATH, "//button[contains(text(),'Log In')]").click()
    time.sleep(3)

    # Navigate to Consolidated Merit Review
    driver.get(TOOL_URL)
    time.sleep(4)

    ensure_logged_in(driver)

    # ========================
    # FETCH DROPDOWNS
    # ========================
    year_dropdown = WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "select-year")))
    school_dropdown = WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "select-program")))

    year_options = [y.text.strip() for y in Select(year_dropdown).options if y.get_attribute("value")]
    school_options = [s.text.strip() for s in Select(school_dropdown).options if s.get_attribute("value")]

    logging.info(f"Found {len(year_options)} years and {len(school_options)} schools/programs.")

    # ========================
    # ITERATE AND DOWNLOAD
    # ========================
    for year_text in year_options:
        for school_text in school_options:
            logging.info(f"== Processing School: {school_text}, Year: {year_text} ==")
            
            try:
                ensure_logged_in(driver)
                
                # Re-fetch dropdowns to avoid stale references
                y_select = Select(WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "select-year"))))
                y_select.select_by_visible_text(year_text)
                time.sleep(2)
                
                s_select = Select(WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "select-program"))))
                s_select.select_by_visible_text(school_text)
                time.sleep(5)  # Wait for table to populate
                
                # Check for empty state
                if "No data available in table" in driver.page_source:
                    logging.info("   -> No data found.")
                    continue

                # Parse the table
                rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
                
                if not rows:
                    logging.info("   -> No rows found.")
                    continue
                
                logging.info(f"   -> Found {len(rows)} potential instructors.")

                # Iterate instructors
                for row_index in range(len(rows)):
                    # Re-fetch row inside loop in case DOM updates slightly or we navigate
                    current_rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
                    if row_index >= len(current_rows):
                        break
                        
                    row = current_rows[row_index]
                    
                    try:
                        cells = row.find_elements(By.TAG_NAME, "td")
                        
                        # Expected length check
                        if len(cells) < 4:
                            continue
                            
                        # Extract Instructor Name (Column 0)
                        instructor_name = sanitize_filename(cells[0].text.strip())
                        
                        # Look for attachments in CV/Attachments (Column 3)
                        attachment_links = cells[3].find_elements(By.TAG_NAME, "a")
                        
                        if not attachment_links:
                            logging.info(f"   ⏩ Skipping {instructor_name}: No file or link found.")
                            continue
                            
                        # Prepare nested folder path
                        safe_year = sanitize_filename(year_text)
                        safe_school = sanitize_filename(school_text)
                        instructor_folder = os.path.join(DOWNLOAD_DIR, safe_year, safe_school, instructor_name)
                        os.makedirs(instructor_folder, exist_ok=True)
                        
                        # Download each link found in the cell
                        for link in attachment_links:
                            file_url = link.get_attribute("href")
                            if not file_url:
                                continue
                                
                            # Extract raw filename from URL, fallback to default if weird
                            filename = os.path.basename(urlparse(file_url).path)
                            if not filename or "." not in filename:
                                filename = f"attachment_{int(time.time())}.pdf" 
                                
                            save_path = os.path.join(instructor_folder, filename)
                            
                            # Skip if already downloaded
                            if os.path.exists(save_path):
                                logging.info(f"   ⏩ Skipping duplicate download: {filename}")
                                continue

                            # Try to download directly via urllib (S3 links are usually public)
                            max_retries = 2
                            for attempt in range(max_retries):
                                try:
                                    urllib.request.urlretrieve(file_url, save_path)
                                    logging.info(f"   ✅ Downloaded {filename} for {instructor_name}")
                                    break
                                except Exception as download_err:
                                    if attempt == 0:
                                        logging.warning(f"   ⚠️ Download failed for {filename}. Retrying once...")
                                        time.sleep(2)
                                    else:
                                        logging.error(f"   ❌ Final failure downloading {filename} for {instructor_name}: {download_err}")
                                        
                    except StaleElementReferenceException:
                         logging.warning("   ⚠️ Stale element during row parsing. Skipping row.")
                    except Exception as row_error:
                         logging.error(f"   ❌ Error processing instructor row: {row_error}")

            except Exception as e:
                logging.error(f"Error processing {school_text}/{year_text}: {e}")
                # Try to recover by going back to tool URL
                driver.get(TOOL_URL)
                time.sleep(4)

except Exception as critical_error:
    logging.critical(f"Critical execution error: {critical_error}")
    
finally:
    logging.info("Shutting down driver...")
    driver.quit()
