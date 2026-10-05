import base64
from datetime import datetime, timedelta
from flask import Flask, render_template, request, Response
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
            formatted_month = exp_month.zfill(2)
            formatted_year = str(exp_year).strip()
            clean_card_no = card_number.replace(" ", "").strip()

            page.evaluate("""
                ({cName, cNo, month, year, cvv}) => {
                    const textInputs = Array.from(document.querySelectorAll("input[type='text']"));
                    if (textInputs.length >= 2) {
                        const nameEl = textInputs[textInputs.length - 2];
                        const noEl = textInputs[textInputs.length - 1];
                        nameEl.value = cName;
                        nameEl.dispatchEvent(new Event('input', { bubbles: true }));
                        nameEl.dispatchEvent(new Event('change', { bubbles: true }));
                        
                        noEl.value = cNo;
                        noEl.dispatchEvent(new Event('input', { bubbles: true }));
                        noEl.dispatchEvent(new Event('change', { bubbles: true }));
                    }

                    const monthSelect = document.querySelector('#ExpMonth, select[name*="ExpMonth"], select:nth-of-type(2)');
                    if (monthSelect) {
                        for (let opt of monthSelect.options) {
                            if (opt.value === month || opt.text === month || parseInt(opt.value) === parseInt(month)) {
                                monthSelect.value = opt.value;
                                monthSelect.dispatchEvent(new Event('change', { bubbles: true }));
                                break;
                            }
                        }
                    }

                    const yearSelect = document.querySelector('#ExpYear, select[name*="ExpYear"], select:nth-of-type(3)');
                    if (yearSelect) {
                        for (let opt of yearSelect.options) {
                            if (opt.value === year || opt.text === year || opt.value.endsWith(year.slice(-2)) || opt.text.endsWith(year.slice(-2))) {
                                yearSelect.value = opt.value;
                                yearSelect.dispatchEvent(new Event('change', { bubbles: true }));
                                break;
                            }
                        }
                    }

                    const passInputs = Array.from(document.querySelectorAll("input[type='password']"));
                    if (passInputs.length > 0) {
                        const cvvEl = passInputs[passInputs.length - 1];
                        cvvEl.value = cvv;
                        cvvEl.dispatchEvent(new Event('input', { bubbles: true }));
                        cvvEl.dispatchEvent(new Event('change', { bubbles: true }));
                    }

                    const btn = document.querySelector('#btnYukle');
                    if (btn) {
                        btn.removeAttribute('disabled');
                        btn.disabled = false;
                    }
                }
            """, {
                "cName": card_name,
                "cNo": clean_card_no,
                "month": formatted_month,
                "year": formatted_year,
                "cvv": cvv
            })

            page.wait_for_timeout(1000)

            logs.append("9. Odeme onayi (Yukle butonu) tiklaniyor...")
            current_url = page.url

            btn_yukle = page.locator("#btnYukle")
            if btn_yukle.count() > 0:
                btn_yukle.click(force=True)
            else:
                page.locator("button:has-text('Yükle')").first.click(force=True)

            page.wait_for_timeout(1500)

            confirm_btn = page.locator("#confirm_modal button:has-text('Evet'), #confirm_modal .btn-primary, #confirm_modal .btn-success")
            if confirm_btn.is_visible():
                confirm_btn.first.click()

            payment_completed = False
            for _ in range(15):
                page.wait_for_timeout(1000)
                
                if page.locator(".alert-danger, .validation-summary-errors, .field-validation-error").is_visible() or \
                   page.get_by_text("Hata").is_visible() or \
                   page.get_by_text("Geçersiz").is_visible() or \
                   page.get_by_text("Başarısız").is_visible():
                    logs.append("[HATA] Odeme bilgileri hatali veya banka islemi reddetti!")
                    status = "error"
                    payment_completed = True
                    break
                
                if page.url != current_url or page.locator("iframe, text=SMS, text=Doğrulama, text=Onay").is_visible():
                    logs.append("10. Odeme basarili sekilde tetiklendi, Banka 3D Secure / SMS onay ekranina yonlendirildi.")
                    status = "success"
                    payment_completed = True
                    break

            if not payment_completed:
                logs.append("[BILGI] Islem tamamlandi, guncel durum asagidaki ekranda gosterilmektedir.")

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
    dates = get_next_week_dates()
    return render_template("index.html", dates=dates)

@app.route("/reminder.ics")
def reminder_ics():
    now_utc = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//ISUBU Yemek Rezervasyon//TR
CALSCALE:GREGORIAN
METHOD:PUBLISH
BEGIN:VEVENT
UID:isubu-yemek-reminder@isparta.edu.tr
DTSTAMP:{now_utc}
DTSTART;TZID=Europe/Istanbul:20261005T123000
DTEND;TZID=Europe/Istanbul:20261005T124500
RRULE:FREQ=WEEKLY;BYDAY=MO,FR
SUMMARY:ISUBÜ Yemek Rezervasyonu Hatırlatıcı
DESCRIPTION:Gelecek haftanın yemek rezervasyonunu yapmak için tıklayınız: https://isubu-yemek.onrender.com
URL:https://isubu-yemek.onrender.com
BEGIN:VALARM
TRIGGER:-PT10M
ACTION:DISPLAY
DESCRIPTION:ISUBÜ Yemek Rezervasyon Zamanı (12:30)
END:VALARM
END:VEVENT
END:VCALENDAR"""
    return Response(ics_content, mimetype="text/calendar", headers={"Content-Disposition": "attachment; filename=isubu_yemek_hatirlatici.ics"})

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
