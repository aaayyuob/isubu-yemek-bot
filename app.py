import base64
from flask import Flask, render_template, request
from playwright.sync_api import sync_playwright

app = Flask(__name__)

def run_automation(email, password, card_name, card_number, exp_month, exp_year, cvv, seans, selected_days):
    logs = []
    screenshot_b64 = None
    status = "info"
    
    logs.append(f"[ISLEM BASLADI] E-posta: {email} | Seans: {seans} | Gunler: {selected_days}")
    
    with sync_playwright() as p:
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
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()

        try:
            logs.append("1. Giris sayfasi aciliyor...")
            page.goto("https://yemek.isparta.edu.tr/", wait_until="domcontentloaded", timeout=60000)
            
            logs.append("2. Giris yap baglantisi tiklaniyor...")
            page.get_by_role("link", name="Giriş Yapmak İçin Tıklayınız").click()
            
            logs.append("3. Kimlik bilgileri dolduruluyor...")
            page.get_by_placeholder("E-posta").wait_for(timeout=30000)
            page.get_by_placeholder("E-posta").fill(email)
            page.get_by_placeholder("Parola").fill(password)
            page.get_by_role("button", name="Giriş").click()
            page.wait_for_load_state("domcontentloaded")

            logs.append("4. Seans secim sayfasina gidiliyor...")
            page.goto("https://yemek.isparta.edu.tr/Yemekhane/SeansSecim", wait_until="domcontentloaded", timeout=60000)

            logs.append(f"5. Seans seciliyor: {seans} yemegi...")
            if seans == "Ogle":
                page.get_by_role("link", name="Satın Al").first.click()
            else:
                page.get_by_role("link", name="Satın Al").nth(1).click()

            page.wait_for_load_state("domcontentloaded")

            if page.locator("text=Üzgünüz").is_visible() or page.locator("text=kapalı").is_visible():
                logs.append("[UYARI] Sistem su anda haftalik fis satis saatleri disindadir / Satis kapali.")
                status = "warning"
            else:
                logs.append("[BILGI] Gun secimi ve odeme sayfasi acildi.")
                status = "success"

            screenshot_bytes = page.screenshot(full_page=True)
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")

        except Exception as e:
            logs.append(f"[HATA OLUSTU] {str(e)}")
            status = "error"
            try:
                screenshot_bytes = page.screenshot(full_page=True)
                screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
            except Exception:
                pass
        finally:
            context.close()
            browser.close()

    return logs, screenshot_b64, status

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/book", methods=["POST"])
def book():
    email = request.form.get("email")
    password = request.form.get("password")
    card_name = request.form.get("card_name")
    card_number = request.form.get("card_number")
    exp_month = request.form.get("exp_month")
    exp_year = request.form.get("exp_year")
    cvv = request.form.get("cvv")
    seans = request.form.get("seans")
    selected_days = request.form.getlist("days")
    
    logs, screenshot, status = run_automation(
        email, password, card_name, card_number, exp_month, exp_year, cvv, seans, selected_days
    )
    
    return render_template(
        "result.html",
        logs=logs,
        screenshot=screenshot,
        status=status,
        selected_days=selected_days
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
