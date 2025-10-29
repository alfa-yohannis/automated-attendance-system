#!/usr/bin/env python3
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
from webdriver_manager.chrome import ChromeDriverManager

# === CONSTANTS ===
LOGIN_URL = "https://siakad.pradita.ac.id/login"
DAFTAR_HADIR_URL = "https://siakad.pradita.ac.id/dosen/daftar_hadir"
TIMEOUT = 30

# === LOG FILE (absolute for cron) ===
SCRIPT_DIR = Path(__file__).resolve().parent
LOG_FILE = SCRIPT_DIR / "log.txt"

def mask_password(pwd: str) -> str:
    """Hide most characters of the password for logging."""
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

def build_driver():
    options = Options()
    # options.add_argument("--start-maximized")  # Visible (unheadless) mode
    options.add_argument("--headless=new")       # Run in headless mode
    options.add_argument("--window-size=1920,1080")  # Optional: set resolution
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

def login(driver, wait, email: str, password: str):
    driver.get(LOGIN_URL)
    email_field = wait.until(EC.presence_of_element_located((By.ID, "exampleInputEmail1")))
    password_field = driver.find_element(By.ID, "password-field")
    login_button = driver.find_element(By.CSS_SELECTOR, "button.btn.btn-login")

    email_field.clear()
    email_field.send_keys(email)
    password_field.clear()
    password_field.send_keys(password)
    login_button.click()

    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/logout']")))
    log(f"✅ Logged in as {email} (password={mask_password(password)})")

def go_to_daftar_hadir(driver, wait):
    driver.get(DAFTAR_HADIR_URL)
    wait.until(EC.presence_of_element_located((By.XPATH, "//table")))
    log("📄 Opened daftar hadir page.")

def click_absensi_and_submit(driver, wait, matkul_text: str):
    """Click Absensi for the given matkul, tick 'Hadir semua', fill topik, and Submit."""
    row_xpath = (
        f"//tr[td[@data-label and "
        f"contains(translate(@data-label,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'mata kuliah') "
        f"and contains(normalize-space(.), '{matkul_text}')]]"
    )
    row = wait.until(EC.presence_of_element_located((By.XPATH, row_xpath)))

    absensi_btn = row.find_element(By.XPATH, ".//button[contains(@class,'btn-detail') and contains(.,'Absensi')]")
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", absensi_btn)
    wait.until(EC.element_to_be_clickable(absensi_btn))
    absensi_btn.click()
    log(f"🖱️ Clicked 'Absensi' for {matkul_text}")

    # Wait for modal to open
    wait.until(EC.visibility_of_element_located((By.ID, "modal_daring")))
    log("💬 Modal opened.")

    # Fill Topik Pembahasan
    input_field = wait.until(EC.element_to_be_clickable((By.ID, "topik_pembahasan")))
    topic_text = "Topik Hari Ini"
    input_field.clear()
    input_field.send_keys(topic_text)
    log(f"✍️ Filled Topik Pembahasan with: {topic_text}")

    # Check 'Hadir semua'
    hadir_semua = wait.until(EC.element_to_be_clickable((By.NAME, "masuk_semua")))
    if not hadir_semua.is_selected():
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", hadir_semua)
        hadir_semua.click()
        log("☑️ Checked 'Hadir semua'.")

    # Click Submit button
    submit_button = wait.until(EC.element_to_be_clickable((
        By.XPATH,
        "//div[@id='modal_daring']//button[contains(@class,'btn-primary') and .//i[contains(@class,'fa-save')]]"
    )))
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", submit_button)
    submit_button.click()
    log("💾 Clicked Submit button inside modal.")

def main():
    if len(sys.argv) < 4:
        print("Usage: python absensi.py \"Nama Mata Kuliah\" \"Email\" \"Password\"")
        sys.exit(1)

    matkul = sys.argv[1].strip()
    email = sys.argv[2].strip()
    password = sys.argv[3]

    log("=== Script started: APPROVE KEHADIRAN ===")
    log(f"Target Mata Kuliah: {matkul}")
    log(f"Login user: {email} (password={mask_password(password)})")

    driver = build_driver()
    wait = WebDriverWait(driver, TIMEOUT)

    try:
        login(driver, wait, email, password)
        go_to_daftar_hadir(driver, wait)
        click_absensi_and_submit(driver, wait, matkul)
        log("✅ Absensi selesai.")
        log("=== Script finished successfully ===")
        log("👀 Browser left open for manual inspection.")
        time.sleep(5)
    except Exception as e:
        log(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
