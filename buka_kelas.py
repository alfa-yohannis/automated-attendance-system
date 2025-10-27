#!/usr/bin/env python3
import sys
import time
from pathlib import Path
from datetime import datetime
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

# Use absolute path for safety in cron
SCRIPT_DIR = Path(__file__).resolve().parent
LOG_FILE = SCRIPT_DIR / "log.txt"


# === HELPER FUNCTIONS ===
def mask_password(pwd: str) -> str:
    """Hide most characters of the password for logging."""
    if not pwd:
        return ""
    if len(pwd) <= 3:
        return "*" * len(pwd)
    return pwd[0] + "*" * (len(pwd) - 2) + pwd[-1]


def log(msg: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def build_driver():
    options = Options()
    options.add_argument("--start-maximized")
    # Always visible (no headless mode)
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    return driver


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
    log(f"Logged in as {email} (password={mask_password(password)})")


def go_to_daftar_hadir(driver, wait):
    driver.get(DAFTAR_HADIR_URL)
    wait.until(EC.presence_of_element_located((By.XPATH, "//table")))
    log("Opened daftar hadir page.")


def click_buka_kelas_and_confirm(driver, wait, matkul_text: str):
    row_xpath = (
        f"//tr[td[@data-label and "
        f"contains(translate(@data-label,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'mata kuliah') "
        f"and contains(normalize-space(.), '{matkul_text}')]]"
    )
    row = wait.until(EC.presence_of_element_located((By.XPATH, row_xpath)))

    buka_button = row.find_element(
        By.XPATH,
        ".//button[contains(@class,'btn-buka') and (contains(.,'Buka') or contains(@title,'Buka'))]"
    )
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", buka_button)
    wait.until(EC.element_to_be_clickable(buka_button))
    buka_button.click()
    log(f"Clicked 'Buka Kelas' for: {matkul_text}")

    modal = wait.until(EC.visibility_of_element_located((By.ID, "confirmation")))
    ya_button = wait.until(
        EC.element_to_be_clickable(
            (By.CSS_SELECTOR, "#confirmation .modal-footer .btn-ok.btn.btn-success")
        )
    )
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", ya_button)
    try:
        ya_button.click()
    except Exception:
        driver.execute_script("arguments[0].click();", ya_button)
    log("Confirmed 'Buka Kelas' by clicking 'Ya'.")


# === MAIN ===
def main():
    if len(sys.argv) < 4:
        print("Usage: python buka_kelas.py \"Nama Mata Kuliah\" \"Email\" \"Password\"")
        sys.exit(1)

    matkul, email, password = sys.argv[1], sys.argv[2], sys.argv[3]

    log("=== Script started ===")
    log(f"Target Mata Kuliah: {matkul}")
    log(f"Login user: {email} (password={mask_password(password)})")

    driver = build_driver()
    wait = WebDriverWait(driver, TIMEOUT)

    try:
        login(driver, wait, email, password)
        go_to_daftar_hadir(driver, wait)
        click_buka_kelas_and_confirm(driver, wait, matkul)
        log("Buka kelas selesai.")
        log("=== Script finished successfully ===")
        time.sleep(5)
    except Exception as e:
        log(f"Error: {e}")
    finally:
        log("The End of the Program.")


if __name__ == "__main__":
    main()
