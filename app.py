import base64
import json
import time
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

@app.route("/execute_booking", methods=["POST"])
def execute_booking():
    data = request.json or {}
    email = data.get("email")
    password = data.get("password")
    card_name = data.get("card_name")
    card_number = data.get("card_number")
    exp_month = data.get("exp_month")
    exp_year = data.get("exp_year")
    cvv = data.get("cvv")
    seans = data.get("seans")
    yemekhane = data.get("yemekhane")
    selected_days = data.get("days", [])

    def stream_process():
        def sse(msg, sshot=None, complete=False, status="info"):
            payload = {"log": msg, "screenshot": sshot, "complete": complete, "status": status}
            return f"data: {json.dumps(payload)}\n\n"

        yield sse(f"İşlem başlatıldı: {email}")

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu"
                ]
            )
            context = browser.new_context(
                viewport={"width": 1280, "height": 950},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            try:
                yield sse("1. Yemekhane ana sayfası açılıyor...")
                page.goto("https://yemek.isparta.edu.tr/", wait_until="domcontentloaded", timeout=30000)

                yield sse("2. Giriş yapılıyor...")
                page.get_by_role("link", name="Giriş Yapmak İçin Tıklayınız").click()
                page.get_by_placeholder("E-posta").wait_for(timeout=15000)
                page.get_by_placeholder("E-posta").fill(email)
                page.get_by_placeholder("Parola").fill(password)
                page.get_by_role("button", name="Giriş").click()
                page.wait_for_timeout(2500)

                if "Kimlik/Giris" in page.url:
                    sshot = base64.b64encode(page.screenshot(full_page=True)).decode("utf-8")
                    yield sse("Giriş başarısız! Bilgileri kontrol ediniz.", sshot=sshot, complete=True, status="error")
                    return

                yield sse("3. Seans sayfasına gidiliyor...")
                page.goto("https://yemek.isparta.edu.tr/Yemekhane/SeansSecim", wait_until="domcontentloaded", timeout=25000)
                page.wait_for_timeout(1500)

                yield sse(f"4. Seans seçiliyor: {seans}...")
                if seans == "Ogle":
                    btn = page.get_by_role("link", name="Satın Al").first
                else:
                    btn = page.get_by_role("link", name="Satın Al").nth(1)
                btn.wait_for(timeout=8000)
                btn.click()
                page.wait_for_load_state("domcontentloaded")
                page.wait_for_timeout(1500)

                yield sse(f"5. Yemekhane seçiliyor: {yemekhane}...")
                selects = page.locator("select")
                if selects.count() > 0:
                    selects.first.select_option(label=yemekhane)
                page.wait_for_timeout(800)

                yield sse("6. Gün tercihleri işaretleniyor...")
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

                yield sse("7. Kart bilgileri dolduruluyor...")
                clean_card_no = card_number.replace(" ", "").strip()
                formatted_month = exp_month.zfill(2)
                formatted_year = str(exp_year).strip()

                page.evaluate("""
                    ({name, num, month, year, cvv}) => {
                        const cardBox = Array.from(document.querySelectorAll('div, section')).find(el => el.innerText && el.innerText.includes('Kart Bilgileri')) || document;
                        const inputs = Array.from(cardBox.querySelectorAll('input:not([type="hidden"]):not([type="checkbox"]):not([type="button"]):not([type="submit"])'));

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
                            inputs[inputs.length - 1].value = cvv;
                            inputs[inputs.length - 1].dispatchEvent(new Event('input', { bubbles: true }));
                            inputs[inputs.length - 1].dispatchEvent(new Event('change', { bubbles: true }));
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

                page.wait_for_timeout(800)

                yield sse("8. Yükle butonuna basılıyor...")
                page.locator("#btnYukle, button:has-text('Yükle')").first.click(force=True)
                page.wait_for_timeout(1500)

                yield sse("9. Onay modalı kabul ediliyor...")
                page.evaluate("""() => {
                    const confirmBtns = Array.from(document.querySelectorAll('.modal button, .bootbox button, button.btn-primary, button.btn-success'));
                    const tamam = confirmBtns.find(b => b.innerText.trim().includes('Tamam') || b.innerText.trim().includes('Evet'));
                    if (tamam) tamam.click();

                    setTimeout(() => {
                        const form = document.querySelector('form[action*="Odeme"], form[action*="Yukle"], form');
                        if (form && !window.submitted) {
                            window.submitted = true;
                            form.submit();
                        }
                    }, 800);
                }""")

                yield sse("10. VakıfBank sayfasına geçiliyor...")
                try:
                    page.wait_for_url(lambda u: "vakifbank" in u.lower() or "3d" in u.lower() or "pos" in u.lower(), timeout=18000)
                except Exception:
                    page.wait_for_timeout(4000)

                target_scope = page
                for frame in page.frames:
                    if "vakifbank" in frame.url.lower():
                        target_scope = frame
                        break

                yield sse("11. Cep İmza seçilip Devam Et tıklanıyor...")
                for selector in ["button:has-text('Devam Et')", "input[value*='Devam']", ".btn:has-text('Devam')", "button:has-text('Devam')"]:
                    loc = target_scope.locator(selector).first
                    if loc.is_visible():
                        loc.click(force=True)
                        break

                yield sse("12. BİLDİRİM TELEFONUNUZA GÖNDERİLDİ! Lütfen VakıfBank uygulamasından ONAYLAYINIZ...")

                # حلقة مراقبة حية لانتظار تأكيدك وعودة صفحة الجامعة بنجاح
                completed = False
                for sec in range(60):
                    time.sleep(2)
                    yield sse(f"Banka onayı bekleniyor ({sec * 2}/120 sn)...")

                    # إذا ظهر زر موافقة أو إنهاء أخير في نافذة البنك بعد التأكيد
                    try:
                        final_btn = page.locator("button:has-text('Tamam'), button:has-text('Kapat'), button:has-text('Geri Dön'), a:has-text('Tamam')").first
                        if final_btn.is_visible():
                            final_btn.click(force=True)
                    except Exception:
                        pass

                    cur_url = page.url.lower()
                    try:
                        body_txt = page.inner_text("body").lower()
                    except Exception:
                        body_txt = ""

                    if "yemek.isparta.edu.tr" in cur_url and ("başarı" in body_txt or "alınmıştır" in body_txt or "fiş" in body_txt or "hareket" in body_txt or "bakiye" in body_txt):
                        completed = True
                        break

                yield sse("13. Sonuç ekranı yakalanıyor...")
                page.wait_for_timeout(2000)
                sshot = base64.b64encode(page.screenshot(full_page=True)).decode("utf-8")

                if completed:
                    yield sse("TEBRİKLER! Yemek rezervasyonunuz başarıyla tamamlandı.", sshot=sshot, complete=True, status="success")
                else:
                    yield sse("İşlem sonlandı, güncel durum görüntüsü aşağıdadır.", sshot=sshot, complete=True, status="info")

            except Exception as ex:
                err_sshot = None
                try:
                    err_sshot = base64.b64encode(page.screenshot(full_page=True)).decode("utf-8")
                except Exception:
                    pass
                yield sse(f"Hata oluştu: {str(ex)}", sshot=err_sshot, complete=True, status="error")
            finally:
                context.close()
                browser.close()

    return Response(stream_process(), mimetype="text/event-stream")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
