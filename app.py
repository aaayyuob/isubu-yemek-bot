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
        context = browser.new_context(viewport={"width": 1280, "height": 1000})
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

            if "Kimlik/Giris" in page.url:
                logs.append("[HATA] Giris basarisiz! E-posta veya parola hatali.")
                status = "error"
                screenshot_bytes = page.screenshot(full_page=True)
                screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
                return logs, screenshot_b64, status

            logs.append("4. Seans secim sayfasina gidiliyor...")
            page.goto("https://yemek.isparta.edu.tr/Yemekhane/SeansSecim", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)

            if page.get_by_text("Üzgünüz").is_visible() or page.get_by_text("kapalı").is_visible():
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
            page.wait_for_timeout(2000)

            logs.append(f"6. Yemekhane secimi yapiliyor: {yemekhane}...")
            selects = page.locator("select")
            if selects.count() > 0:
                selects.first.select_option(label=yemekhane)
            page.wait_for_timeout(1000)

            logs.append("7. Gun tercihleri isleniyor...")
            day_order = ["Pazartesi", "Sali", "Carsamba", "Persembe", "Cuma"]
            checkboxes = page.locator("input[type='checkbox']")
            total_chks = checkboxes.count()
            
            for idx, day_name in enumerate(day_order):
                if idx < total_chks:
                    chk = checkboxes.nth(idx)
                    if day_name in selected_days:
                        chk.check()
                    else:
                        chk.uncheck()

            logs.append("8. Kart bilgileri dolduruluyor...")
            name_input = page.locator("#KartSahibi, input[name*='KartSahibi'], input[name*='CardHolder']").first
            if name_input.count() > 0:
                name_input.fill(card_name)
            else:
                page.locator("input[type='text']").nth(-2).fill(card_name)

            num_input = page.locator("#KartNo, input[name*='KartNo'], input[name*='CardNumber']").first
            if num_input.count() > 0:
                num_input.fill(card_number)
            else:
                page.locator("input[type='text']").last.fill(card_number)

            month_elem = page.locator("#ExpMonth, select[name*='ExpMonth']").first
            if month_elem.count() > 0:
                try:
                    month_elem.select_option(value=exp_month.zfill(2))
                except Exception:
                    month_elem.select_option(label=exp_month.zfill(2))
            else:
                page.locator("select").nth(1).select_option(index=int(exp_month))

            year_elem = page.locator("#ExpYear, select[name*='ExpYear']").first
            if year_elem.count() > 0:
                try:
                    year_elem.select_option(value=str(exp_year))
                except Exception:
                    try:
                        year_elem.select_option(label=str(exp_year))
                    except Exception:
                        year_elem.select_option(value=str(exp_year)[-2:])
            else:
                page.locator("select").nth(2).select_option(value=str(exp_year))

            cvv_elem = page.locator("#Cvv2, #CVV, input[name*='Cvv'], input[type='password']").last
            cvv_elem.fill(cvv)

            logs.append("9. Odeme onayi (Yukle butonu) tiklaniyor...")
            page.locator("button:has-text('Yükle'), input[value='Yükle'], .btn:has-text('Yükle')").first.click()
            
            page.wait_for_timeout(6000)

            screenshot_bytes = page.screenshot(full_page=True)
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")

            logs.append("10. Odeme emri verildi. Banka/SMS ekran durumu asagidaki gibidir.")
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
