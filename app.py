from flask import Flask, render_template, request
from playwright.sync_api import sync_playwright

app = Flask(__name__)

def run_automation(email, password, seans, selected_days):
    print(f"\n[TASK STARTED] User: {email} | Session: {seans} | Days: {selected_days}")
    
    with sync_playwright() as p:
        # Launch headless Chromium with full cloud-compatible flags
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--no-first-run",
                "--no-zygote",
                "--single-process"
            ]
        )
        context = browser.new_context()
        page = context.new_page()

        try:
            print("1. Loading home page...")
            page.goto("https://yemek.isparta.edu.tr/", wait_until="domcontentloaded", timeout=60000)
            
            print("2. Clicking login link...")
            page.get_by_role("link", name="Giriş Yapmak İçin Tıklayınız").click()
            
            print("3. Submitting credentials...")
            page.get_by_placeholder("E-posta").wait_for(timeout=30000)
            page.get_by_placeholder("E-posta").fill(email)
            page.get_by_placeholder("Parola").fill(password)
            page.get_by_role("button", name="Giriş").click()
            page.wait_for_load_state("domcontentloaded")

            print("4. Navigating to session selection...")
            page.goto("https://yemek.isparta.edu.tr/Yemekhane/SeansSecim", wait_until="domcontentloaded", timeout=60000)

            print(f"5. Selecting meal session: {seans}...")
            if seans == "Ogle":
                page.get_by_role("link", name="Satın Al").first.click()
            else:
                page.get_by_role("link", name="Satın Al").nth(1).click()

            page.wait_for_load_state("domcontentloaded")

            print("6. Reservation process completed successfully.")

        finally:
            context.close()
            browser.close()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/book", methods=["POST"])
def book():
    email = request.form.get("email")
    password = request.form.get("password")
    seans = request.form.get("seans")
    selected_days = request.form.getlist("days")
    
    try:
        run_automation(email, password, seans, selected_days)
        return f"<h3>Rezervasyon islemi basariyla tetiklendi! Secilen gunler: {', '.join(selected_days)}</h3>"
    except Exception as e:
        return f"<h3>Bir hata olustu:</h3><pre>{str(e)}</pre>"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
