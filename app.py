import base64
from datetime import datetime, timedelta
from flask import Flask, render_template, request
from playwright.sync_api import sync_playwright

app = Flask(__name__)

def get_next_week_dates():
    today = datetime.now()
    days_ahead = 7 - today.weekday()
    monday = today + timedelta(days=days_ahead)
    
    dates_map = {
        "Pazartesi": (monday + timedelta(days=0)).strftime("%d.%m.%Y"),
        "Sali": (monday + timedelta(days=1)).strftime("%d.%m.%Y"),
        "Carsamba": (monday + timedelta(days=2)).strftime("%d.%m.%Y"),
        "Persembe": (monday + timedelta(days=3)).strftime("%d.%m.%Y"),
        "Cuma": (monday + timedelta(days=4)).strftime("%d.%m.%Y")
    }
    return dates_map

def run_automation(email, password, card_name, card_number, exp_month, exp_year, cvv, seans, yemekhane, selected_days):
    logs = []
    screenshot_b64 = None
    status = "info"
    
    logs.append(f"[ISLEM BASLADI] Kullanici: {email} | Seans: {seans} | Yerleske: {yemekhane} | Gunler: {selected_days}")
    
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
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()

        try:
            logs.append("1. Giris sayfasi aciliyor...")
            page.goto("https://yemek.isparta.edu.tr/", wait_until="domcontentloaded", timeout=45000)
            
            logs.append("2. Giris butonu tiklaniyor...")
            page.get_by_role("link", name="Giriş Yapmak İçin Tıklayınız").click()
            
            page.get_by_placeholder("E-posta").wait_for(timeout=20000)
            logs.append("3. Kimlik bilgileri dolduruluyor...")
            page.get_by_placeholder("E-posta").fill(email)
            page.get_by_placeholder("Parola").fill(password)
            page.get_by_role("button", name="Giriş").click()
            
            page.wait_for_timeout(3000)

            if "Kimlik/Giris" in page.url or page.locator(".alert-danger, .validation-summary-errors, text=Hatalı").is_visible():
                logs.append("[HATA] Giris basarisiz! E-posta veya parola hatali.")
                status = "error"
                screenshot_bytes = page.screenshot(full_page=True)
                screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
                return logs, screenshot_b64, status

            logs.append("4. Seans secim sayfasina gidiliyor...")
            page.goto("https://yemek.isparta.edu.tr/Yemekhane/SeansSecim", wait_until="domcontentloaded", timeout=30000)

            if page.locator("text=Üzgünüz").is_visible() or page.locator("text=kapalı").is_visible():
                logs.append("[BILGI] Sistem su anda haftalik fis satis saatleri disindadir / Satis kapali.")
                status = "warning"
                screenshot_bytes = page.screenshot(full_page=True)
                screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
                return logs, screenshot_b64, status

            logs.append(f"5. Seans seciliyor: {seans}...")
            if seans == "Ogle":
                btn = page.get_by_role("link", name="Satın Al").first
            else:
                btn = page.get_by_role("link", name="Satın Al").nth(1)

            btn.wait_for(timeout=10000)
            btn.click()
            page.wait_for_load_state("domcontentloaded")

            logs.append(f"6. Yemekhane secimi yapiliyor: {yemekhane}...")
            page.locator("select").first.select_option(label=yemekhane)
            page.wait_for_timeout(1000)

            logs.append("7. Gun tercihleri isleniyor...")
            day_labels = {
                "Pazartesi": "Pazartesi",
                "Sali": "Salı",
                "Carsamba": "Çarşamba",
                "Persembe": "Perşembe",
                "Cuma": "Cuma"
            }
            
            for d_key, d_text in day_labels.items():
                chk = page.locator(f"//label[contains(., '{d_text}')]//input[@type='checkbox']")
                if chk.count() > 0:
                    if d_key in selected_days:
                        chk.check()
                    else:
                        chk.uncheck()

            logs.append("8. Kart bilgileri dolduruluyor...")
            page.locator("input[name*='KartSahibi'], input[placeholder*='Ad Soyad'], input#KartSahibi").first.fill(card_name)
            page.locator("input[name*='KartNo'], input[placeholder*='kart'], input#KartNo").first.fill(card_number)
            
            month_select = page.locator("select").nth(1)
            year_select = page.locator("select").nth(2)
            month_select.select_option(value=exp_month.zfill(2))
            year_select.select_option(value=exp_year)

            page.locator("input[name*='Cvv'], input[name*='CVV'], input[type='password']").last.fill(cvv)

            logs.append("9. Odeme onayi (Yukle butonu) tiklaniyor...")
            page.get_by_role("button", name="Yükle").click()
            
            page.wait_for_timeout(4000)

            logs.append("10. Islem tamamlandi, SMS dogrulama ekranina yonlendirildi.")
            status = "success"

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
    dates = get_next_week_dates()
    return render_template("index.html", dates=dates)

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
    yemekhane = request.form.get("yemekhane")
    selected_days = request.form.getlist("days")
    
    logs, screenshot, status = run_automation(
        email, password, card_name, card_number, exp_month, exp_year, cvv, seans, yemekhane, selected_days
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
