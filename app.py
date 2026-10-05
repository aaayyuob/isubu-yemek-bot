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
            clean_card_no = card_number.replace(" ", "").strip()
            formatted_month = exp_month.zfill(2)
            formatted_year = str(exp_year).strip()

            page.evaluate("""
                ({name, num, month, year, cvv}) => {
                    const cardSection = Array.from(document.querySelectorAll('div, section')).find(el => el.innerText && el.innerText.includes('Kart Bilgileri'));
                    const container = cardSection || document;
                    const inputs = Array.from(container.querySelectorAll('input')).filter(i => i.type !== 'checkbox' && i.type !== 'hidden' && i.type !== 'button' && i.type !== 'submit');

                    if (inputs.length >= 1) {
                        inputs[0].value = name;
                        inputs[0].dispatchEvent(new Event('input', { bubbles: true }));
                        inputs[0].dispatchEvent(new Event('change', { bubbles: true }));
                    }

                    if (inputs.length >= 2) {
                        inputs[1].value = num;
                        inputs[1].dispatchEvent(new Event('input', { bubbles: true }));
                        inputs[1].dispatchEvent(new Event('change', { bubbles: true }));
                        inputs[1].dispatchEvent(new Event('keyup', { bubbles: true }));
                    }

                    const monthSelect = document.querySelector('#ExpMonth, select[name*="ExpMonth"], select:nth-of-type(2)');
                    if (monthSelect) {
                        for (let opt of monthSelect.options) {
                            if (opt.value === month || opt.text.trim() === month || parseInt(opt.value) === parseInt(month)) {
                                monthSelect.value = opt.value;
                                monthSelect.dispatchEvent(new Event('change', { bubbles: true }));
                                break;
                            }
                        }
                    }

                    const yearSelect = document.querySelector('#ExpYear, select[name*="ExpYear"], select:nth-of-type(3)');
                    if (yearSelect) {
                        for (let opt of yearSelect.options) {
                            if (opt.value === year || opt.text.trim() === year || opt.value.endsWith(year.slice(-2)) || opt.text.trim().endsWith(year.slice(-2))) {
                                yearSelect.value = opt.value;
                                yearSelect.dispatchEvent(new Event('change', { bubbles: true }));
                                break;
                            }
                        }
                    }

                    if (inputs.length >= 3) {
                        inputs[2].value = cvv;
                        inputs[2].dispatchEvent(new Event('input', { bubbles: true }));
                        inputs[2].dispatchEvent(new Event('change', { bubbles: true }));
                    }

                    const btn = document.querySelector('#btnYukle');
                    if (btn) {
                        btn.removeAttribute('disabled');
                        btn.disabled = false;
                    }
                }
            """, {
                "name": card_name,
                "num": clean_card_no,
                "month": formatted_month,
                "year": formatted_year,
                "cvv": cvv
            })

            page.wait_for_timeout(1000)

            logs.append("9. Odeme onayi (Yukle butonu) tiklaniyor...")
            page.evaluate("""
                () => {
                    const btn = document.querySelector('#btnYukle');
                    if (btn) btn.click();
                }
            """)
            page.wait_for_timeout(1500)

            page.evaluate("""
                () => {
                    const modal = document.querySelector('#confirm_modal');
                    if (modal) {
                        const confirmBtn = modal.querySelector('button.btn-primary, button.btn-success, button[type="submit"]');
                        if (confirmBtn) {
                            confirmBtn.click();
                        } else {
                            const btns = Array.from(modal.querySelectorAll('button'));
                            const yesBtn = btns.find(b => b.innerText.includes('Evet') || b.innerText.includes('Onay'));
                            if (yesBtn) yesBtn.click();
                        }
                    }
                }
            """)

            logs.append("10. Banka 3D Secure / Onay sayfasina gecis bekleniyor...")
            
            try:
                page.wait_for_load_state("networkidle", timeout=12000)
            except Exception:
                page.wait_for_timeout(5000)

            screenshot_bytes = page.screenshot(full_page=True)
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")

            if page.locator(".alert-danger, .validation-summary-errors, .field-validation-error").is_visible() or \
               page.get_by_text("Hata").is_visible() or \
               page.get_by_text("Geçersiz").is_visible():
                logs.append("[HATA] Odeme bilgileri hatali veya banka islemi reddetti!")
                status = "error"
            else:
                logs.append("11. Banka ekranina ulasildi! Lutfen SMS kodunu kontrol ediniz.")
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

@app.route("/reminder.ics")
def reminder_ics():
    now_utc = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//ISUBU Yemek Rezervasyon//TR
CALSCALE:GREGORIAN
METHOD:PUBLISH
BEGIN:VEVENT
UID:isubu-yemek-reminder-v2@isparta.edu.tr
DTSTAMP:{now_utc}
DTSTART:20261009T093000Z
DTEND:20261009T094500Z
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
    return Response(
        ics_content,
        mimetype="text/calendar",
        headers={
            "Content-Disposition": "attachment; filename=isubu_hatirlatici.ics",
            "Content-Type": "text/calendar; charset=utf-8"
        }
    )

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
