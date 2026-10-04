from flask import Flask, render_template, request
from playwright.sync_api import sync_playwright

app = Flask(__name__)

def run_automation(email, password, seans, selected_days):
    print(f"\n[İŞLEM BAŞLADI] Kullanıcı: {email} | Seans: {seans} | Günler: {selected_days}")
    with sync_playwright() as p:
        # headless=False لعرض ما يحدث أثناء التجربة
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        print("1. Giris sayfasi aciliyor...")
        # استخدام domcontentloaded و timeout 60 ثانية لمنع الـ TimeoutError
        page.goto("https://yemek.isparta.edu.tr/", wait_until="domcontentloaded", timeout=60000)
        
        print("2. Giris butonu tiklaniyor...")
        page.get_by_role("link", name="Giriş Yapmak İçin Tıklayınız").click()
        
        print("3. Kimlik bilgileri yaziliyor...")
        page.get_by_placeholder("E-posta").wait_for(timeout=30000)
        page.get_by_placeholder("E-posta").fill(email)
        page.get_by_placeholder("Parola").fill(password)
        page.get_by_role("button", name="Giriş").click()
        page.wait_for_load_state("domcontentloaded")

        print("4. Seans secim sayfasina gidiliyor...")
        page.goto("https://yemek.isparta.edu.tr/Yemekhane/SeansSecim", wait_until="domcontentloaded", timeout=60000)

        print(f"5. Seans seciliyor: {seans}...")
        if seans == "Ogle":
            page.get_by_role("link", name="Satın Al").first.click()
        else:
            page.get_by_role("link", name="Satın Al").nth(1).click()

        page.wait_for_load_state("domcontentloaded")

        print("6. Islem tamamlandi, SMS veya sonraki adim bekleniyor...")
        # ابقاء المتصفح مفتوحاً للمعاينة
        page.wait_for_timeout(60000)
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
        return f"<h3>İşlem başarıyla tetiklendi! Seçilen günler: {', '.join(selected_days)}</h3>"
    except Exception as e:
        return f"<h3>Bir hata oluştu:</h3><pre>{str(e)}</pre>"

if __name__ == "__main__":
    # host='0.0.0.0' يسمح للهواتف والجهزة الأخرى في نفس الشبكة بفتح الموقع
    app.run(host="0.0.0.0", port=5000, debug=True)