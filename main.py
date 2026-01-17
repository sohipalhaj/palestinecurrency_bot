import telebot
import yfinance as yf
from statistics import mean
from flask import Flask
from threading import Thread
import time
import os

# --- 1. إعدادات السيرفر (Render Keep-Alive) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot V11 (Expanded Layout) is running!"

def run():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- 2. إعدادات البوت ---
# التوكين الجديد الخاص بك
TOKEN = "8582182426:AAFcsty3Dy6Dowhrc_J0IRRLxe-ImWyH2Ws"
bot = telebot.TeleBot(TOKEN)

# هامش ربح الصراف (الثابت)
MARGIN_ILS = 0.10   # 10 أغورات عند التحويل لشيكل
MARGIN_JOD_USD = 0.005 # هامش بسيط جداً بين الدينار والدولار

# ذاكرة التنبيهات (الرادار)
user_alerts = {}

# --- 3. جلب البيانات ---
def get_live_market_data():
    try:
        ticker = yf.Ticker("USDILS=X")
        hist = ticker.history(period="1mo")
        if hist.empty: return None
        usd_history = hist['Close'].tolist()
        current_usd = usd_history[-1]
        
        # تثبيت الدينار مقابل الدولار
        PEG_RATE = 1.41 
        current_jod = current_usd * PEG_RATE
        jod_history = [price * PEG_RATE for price in usd_history]

        return {
            "USD": {"current": current_usd, "history": usd_history, "name": "الدولار 🇺🇸"},
            "JOD": {"current": current_jod, "history": jod_history, "name": "الدينار 🇯🇴"},
            "ILS": {"current": 1.0, "history": [1.0]*len(usd_history), "name": "الشيكل ₪"}
        }
    except: return None

# --- 4. الرادار (يعمل في الخلفية) ---
def monitor_market():
    while True:
        try:
            data = get_live_market_data()
            if data:
                for chat_id, alerts in list(user_alerts.items()):
                    for alert in alerts[:]:
                        coin = alert['coin']
                        target = alert['target']
                        condition = alert['type']
                        current_price = data[coin]['current']
                        
                        triggered = False
                        if condition == 'below' and current_price <= target:
                            msg = f"🚨 تنبيه الرادار:\n{data[coin]['name']} وصل للسعر المستهدف: {current_price:.2f}\n(أقل من {target})"
                            triggered = True
                        elif condition == 'above' and current_price >= target:
                            msg = f"🚨 تنبيه الرادار:\n{data[coin]['name']} وصل للسعر المستهدف: {current_price:.2f}\n(أعلى من {target})"
                            triggered = True
                        
                        if triggered:
                            try:
                                bot.send_message(chat_id, msg)
                                alerts.remove(alert)
                            except: pass
            time.sleep(60)
        except: time.sleep(60)

Thread(target=monitor_market).start()

# --- 5. دوال التحليل والرد (النموذج الجديد) ---

def calculate_rsi(history):
    if len(history) < 14: return 50 # محايد
    gains, losses = [], []
    for i in range(1, len(history)):
        delta = history[i] - history[i-1]
        if delta > 0: gains.append(delta)
        else: losses.append(abs(delta))
    avg_gain = sum(gains) / len(gains) if gains else 0
    avg_loss = sum(losses) / len(losses) if losses else 0
    if avg_loss == 0: return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def analyze_conversion(amount, from_curr, to_curr, market_data):
    # تحديد الأسعار
    rate_from = market_data[from_curr]["current"]
    rate_to = market_data[to_curr]["current"]
    
    # 1. السعر العالمي (Exchange Rate)
    if from_curr == "ILS": 
        # تحويل من شيكل لعملة أجنبية (نقسم على سعر العملة)
        exchange_rate = 1 / rate_to
        # الصراف يبيعك العملة بسعر أغلى (يضيف هامش)
        shop_rate = 1 / (rate_to + MARGIN_ILS) 
    elif to_curr == "ILS": 
        # تحويل من عملة أجنبية لشيكل (سعر العملة نفسها)
        exchange_rate = rate_from
        # الصراف يشتري منك بسعر أرخص (يخصم هامش)
        shop_rate = rate_from - MARGIN_ILS
    else: 
        # بين عملات أجنبية (دينار ودولار)
        exchange_rate = rate_from / rate_to
        shop_rate = exchange_rate - MARGIN_JOD_USD

    # القيم المالية
    global_val = amount * exchange_rate
    net_val = amount * shop_rate

    # تحديد البيانات للتحليل (نحلل العملة الأجنبية مقابل الشيكل دائماً لتحديد الاتجاه)
    if to_curr == "ILS":
        analyze_curr = from_curr
        hist = market_data[from_curr]["history"]
        current_price_for_analysis = rate_from
    elif from_curr == "ILS":
        analyze_curr = to_curr
        hist = market_data[to_curr]["history"]
        current_price_for_analysis = rate_to
    else:
        # حالة خاصة دينار/دولار
        analyze_curr = to_curr
        hist = market_data[to_curr]["history"] # تحليل تقريبي
        current_price_for_analysis = exchange_rate

    # الحسابات الرياضية
    avg_7_days = mean(hist[-7:])
    rsi = calculate_rsi(hist)

    # 5. الاتجاه
    trend_txt = "مستقر نوعاً ما"
    if current_price_for_analysis > avg_7_days: trend_txt = "صعود (ارتفاع)"
    elif current_price_for_analysis < avg_7_days: trend_txt = "هبوط (انخفاض)"

    # 6. التوقعات (بناءً على الزخم)
    forecast_txt = "السوق متذبذب، الحركة غير واضحة"
    if rsi > 70: forecast_txt = "وصل القمة، احتمال يهبط قريباً (تصحيح)"
    elif rsi < 30: forecast_txt = "وصل القاع، احتمال يرتد للصعود"
    elif 50 <= rsi <= 70: forecast_txt = "زخم شرائي، قد يكمل الصعود"
    elif 30 <= rsi < 50: forecast_txt = "زخم بيعي، قد يكمل الهبوط"

    # 8. النصيحة
    advice_txt = "راقب السوق"
    if to_curr == "ILS": # أنا ببيع عملة أجنبية وبوخذ شيكل
        if rsi > 60: advice_txt = "السعر ممتاز (غالي)، فرصة مناسبة للبيع والتحويل لشيكل"
        elif rsi < 40: advice_txt = "السعر منخفض، لا تبيع خسارة، انتظر يرتفع"
        else: advice_txt = "السعر متوسط، حول إذا محتاج ضروري فقط"
    elif from_curr == "ILS": # أنا بشتري عملة أجنبية
        if rsi < 40: advice_txt = "السعر لقطة (رخيص)، فرصة ممتازة تشتري دولار/دينار"
        elif rsi > 60: advice_txt = "السعر غالي، اصبر شوية ممكن يرخص"
        else: advice_txt = "السعر طبيعي، اشتري على دفعات"

    # --- بناء الرسالة (بدون نجوم، مسافات واسعة) ---
    text = f"🔹 التحويل لـ: {market_data[to_curr]['name']}\n\n"
    
    text += "1- السعر العالمي للعملة:\n"
    text += f"{exchange_rate:.4f}\n\n"
    
    text += "2- القيمة حسب السعر العالمي:\n"
    text += f"{global_val:.2f}\n\n"
    
    text += "3- سعر الصراف المتوقع (بعد خصم عمولة):\n"
    text += f"{shop_rate:.4f}\n\n"
    
    text += "4- المبلغ الصافي اللي بتقبضه بيدك:\n"
    text += f"{net_val:.2f}\n\n"
    
    text += "5- اتجاه العملة الحالي:\n"
    text += f"{trend_txt}\n\n"
    
    text += "6- التوقعات القريبة:\n"
    text += f"{forecast_txt}\n\n"
    
    text += "7- متوسط السعر (آخر أسبوع):\n"
    text += f"{avg_7_days:.3f}\n\n"
    
    text += "8- النصيحة:\n"
    text += f"{advice_txt}\n"
    
    text += "ـــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــ\n\n"
    return text

# --- معالجة الرسائل ---
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "أهلاً بك\nاكتب المبلغ والعملة (مثال: 100 دولار)\nأو استخدم التنبيه: تنبيه 3.60 دولار")

@bot.message_handler(func=lambda m: True)
def handle_message(message):
    text = message.text.lower()
    
    # الرادار
    if "تنبيه" in text or "alert" in text:
        try:
            amount_str = ''.join(filter(lambda x: x.isdigit() or x == '.', text))
            target_price = float(amount_str)
            coin = "USD"
            if "دينار" in text: coin = "JOD"
            
            data = get_live_market_data()
            if data:
                current = data[coin]['current']
                typ = 'below' if target_price < current else 'above'
                
                chat_id = message.chat.id
                if chat_id not in user_alerts: user_alerts[chat_id] = []
                user_alerts[chat_id].append({'coin': coin, 'target': target_price, 'type': typ})
                
                bot.reply_to(message, f"تم تفعيل التنبيه على سعر {target_price}")
        except: bot.reply_to(message, "تأكد من صيغة الأمر")
        return

    # التحويل
    try:
        data = get_live_market_data()
