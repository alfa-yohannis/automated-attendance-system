#!/usr/bin/env python3
import csv
import sys
import time
from datetime import datetime
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    StaleElementReferenceException,
    ElementClickInterceptedException,
)
from webdriver_manager.chrome import ChromeDriverManager

# === DEFAULT CONSTANTS ===
LOGIN_URL = "https://siakad.pradita.ac.id/login"
DAFTAR_HADIR_URL = "https://siakad.pradita.ac.id/mahasiswa/daftar_hadir"
TIMEOUT = 30

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_TARGET_MATKUL = "Pengantar Teknologi Informasi"
DEFAULT_CSV_FILE = SCRIPT_DIR / "pemdas_senin.csv"
LOG_FILE = SCRIPT_DIR / "log.txt"

# ----------------- Utility Functions -----------------
def mask_password(pwd: str) -> str:
    if not pwd:
        return ""
    if len(pwd) <= 3:
        return "*" * len(pwd)
    return pwd[0] + "*" * (len(pwd) - 2) + pwd[-1]

def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def xpath_literal(s: str) -> str:
    if "'" not in s:
        return f"'{s}'"
    parts = s.split("'")
    return "concat(" + ", \"'\", ".join(f"'{p}'" for p in parts) + ")"

def read_all_users(filepath: Path):
    with open(filepath, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def build_driver():
    options = Options()
    # options.add_argument("--start-maximized")
    options.add_argument("--headless=new")       # Run in headless mode
    options.add_argument("--window-size=1920,1080")  # Optional: set resolution
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

def safe_click(driver, element):
    try:
        element.click()
    except (ElementClickInterceptedException, StaleElementReferenceException):
        driver.execute_script("arguments[0].click();", element)

# ----------------- Selenium Steps -----------------
def login(driver, wait, email: str, password: str):
    driver.get(LOGIN_URL)
    email_field = wait.until(EC.presence_of_element_located((By.ID, "exampleInputEmail1")))
    password_field = driver.find_element(By.ID, "password-field")
    login_button = driver.find_element(By.CSS_SELECTOR, "button.btn.btn-login")

    email_field.clear(); email_field.send_keys(email)
    password_field.clear(); password_field.send_keys(password)
    login_button.click()

    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/logout']")))
    log(f"✅ Logged in as {email} (password={mask_password(password)})")

def go_to_daftar_hadir(driver, wait):
    driver.get(DAFTAR_HADIR_URL)
    wait.until(EC.presence_of_element_located((By.XPATH, "//table")))
    log("📄 Opened mahasiswa/daftar_hadir page.")

def wait_for_table_to_load(driver, timeout=60):
    log("⏳ Waiting for table rows to be populated by JavaScript...")
    end = time.time() + timeout
    while time.time() < end:
        rows = driver.find_elements(By.XPATH, "//table//tbody/tr")
        if rows:
            log(f"✅ Table populated. Rows detected: {len(rows)}")
            return
        time.sleep(0.5)
    raise TimeoutException("Table rows not loaded within timeout.")

def list_all_icon_attributes(driver, row):
    icons = row.find_elements(By.TAG_NAME, "i")
    if not icons:
        log("⚠️ No <i> icons found in this row.")
        return

    log(f"ℹ️ Found {len(icons)} <i> icon(s) in the row:")
    for idx, icon in enumerate(icons, start=1):
        attrs = driver.execute_script(
            """
            const el = arguments[0];
            const attrs = {};
            for (const a of el.attributes) {
                attrs[a.name] = a.value;
            }
            return attrs;
            """,
            icon,
        )
        formatted_attrs = " ".join(f'{k}="{v}"' for k, v in attrs.items())
        log(f"   {idx}. <i {formatted_attrs}>")

def process_row_for_matkul(driver, wait, matkul_text: str):
    matkul_lit = xpath_literal(matkul_text)
    row_xpath = (
        f"//table//tr[td[@data-label and "
        f"contains(translate(@data-label,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'mata kuliah') "
        f"and contains(normalize-space(.), {matkul_lit})]]"
    )
    row = wait.until(EC.presence_of_element_located((By.XPATH, row_xpath)))
    log(f"🔎 Found row for matkul: {matkul_text}")

    btn = None
    for xp in [
        ".//button[@title='Submit Kehadiran']",
        ".//button[@data-original-title='Submit Kehadiran']",
    ]:
        found = row.find_elements(By.XPATH, xp)
        if found:
            btn = found[0]
            break

    if btn:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
        wait.until(EC.element_to_be_clickable(btn))
        safe_click(driver, btn)
        log(f"🖱️ Clicked 'Submit Kehadiran' for: {matkul_text}")
    else:
        log("ℹ️ No 'Submit Kehadiran' button found. Listing all <i> icons instead:")
        list_all_icon_attributes(driver, row)

def logout(driver, wait):
    try:
        logout_link = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/logout']")))
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", logout_link)
        safe_click(driver, logout_link)
        WebDriverWait(driver, TIMEOUT).until(
            EC.presence_of_element_located((By.ID, "exampleInputEmail1"))
        )
        log("🚪 Logged out successfully.")
    except TimeoutException:
        log("⚠️ Logout timeout — possibly already logged out.")
    except Exception as e:
        log(f"⚠️ Logout error: {e}")

# ----------------- Main -----------------
def main():
    # Parameter order: 1) target matkul, 2) CSV file
    target_matkul = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TARGET_MATKUL
    csv_file = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_CSV_FILE

    log("=== Script started: MAHASISWA SUBMIT KEHADIRAN ===")
    log(f"Target Mata Kuliah: {target_matkul}")
    log(f"CSV file: {csv_file}")

    users = read_all_users(csv_file)
    if not users:
        log("❌ No data found in the CSV file.")
        return

    driver = build_driver()
    wait = WebDriverWait(driver, TIMEOUT)

    try:
        for idx, user in enumerate(users, start=1):
            email = (user.get("username") or "").strip()
            password = (user.get("password") or "").strip()
            hari = (user.get("hari") or "").strip()

            if not email or not password:
                log(f"⚠️ Skipping empty credentials at row {idx}.")
                continue

            log("=" * 60)
            log(f"▶️  User {idx}: {email} (Hari: {hari})")
            try:
                login(driver, wait, email, password)
                go_to_daftar_hadir(driver, wait)
                wait_for_table_to_load(driver, timeout=60)
                process_row_for_matkul(driver, wait, target_matkul)
                logout(driver, wait)
            except Exception as e:
                log(f"❌ Error while processing {email}: {e}")
                try:
                    driver.get(LOGIN_URL)
                except Exception:
                    pass
            time.sleep(2)

        log("🎯 All users processed. Done.")
        # while True:
        #     time.sleep(60)

    except Exception as e:
        log(f"❌ Fatal error: {e}")

if __name__ == "__main__":
    main()
