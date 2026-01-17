import telebot
import yfinance as yf
from statistics import mean
from flask import Flask
from threading import Thread
import time
import os

# --- 1. إعدادات السيرفر (Render) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot V10 (Radar) is alive!"

def run():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- 2. إعدادات البوت والذاكرة ---
TOKEN = "8582182426:AAFcsty3Dy6Dowhrc_J0IRRLxe-ImWyH2Ws"
bot = telebot.TeleBot(TOKEN)
COMMISSION_PCT = 0.008 

# ذاكرة لتخزين التنبيهات (ستمسح عند إعادة تشغيل السيرفر)
# الشكل: {chat_id: [{'coin': 'USD', 'target': 3.60, 'type': 'below'}, ...]}
user_alerts = {}

# --- 3. دوال جلب البيانات ---
def get_live_market_data():
    try:
        ticker = yf.Ticker("USDILS=X")
        hist = ticker.history(period="1mo")
        if hist.empty: return None
        usd_history = hist['Close'].tolist()
        current_usd = usd_history[-1]
        
        PEG_RATE = 1.41 
        current_jod = current_usd * PEG_RATE
        jod_history = [price * PEG_RATE for price in usd_history]

        return {
            "USD": {"current": current_usd, "history": usd_history, "name": "الدولار 🇺🇸"},
            "JOD": {"current": current_jod, "history": jod_history, "name": "الدينار 🇯🇴"},
            "ILS": {"current": 1.0, "history": [1.0]*len(usd_history), "name": "الشيكل ₪"}
        }
    except: return None

# --- 4. نظام الرادار (المراقبة الخلفية) ---
def monitor_market():
    while True:
        try:
            data = get_live_market_data()
            if data:
                # فحص كل التنبيهات المسجلة
                # نستخدم list(user_alerts.items()) لنسخ القائمة وتجنب الأخطاء أثناء التعديل
                for chat_id, alerts in list(user_alerts.items()):
                    for alert in alerts[:]: # نسخة من التنبيهات
                        coin = alert['coin']
                        target = alert['target']
                        condition = alert['type']
                        current_price = data[coin]['current']
                        
                        triggered = False
                        if condition == 'below' and current_price <= target:
                            msg = f"🚨 **رادار الشراء:**\n{data[coin]['name']} نزل ووصل للسعر المستهدف: **{current_price:.2f}** شيكل!\n(أقل من {target})\n💡 فرصة للشراء؟"
                            triggered = True
                        elif condition == 'above' and current_price >= target:
                            msg = f"🚨 **رادار البيع:**\n{data[coin]['name']} ارتفع ووصل للسعر المستهدف: **{current_price:.2f}** شيكل!\n(أعلى من {target})\n💡 فرصة للبيع؟"
                            triggered = True
                        
                        if triggered:
                            try:
                                bot.send_message(chat_id, msg)
                                alerts.remove(alert) # حذف التنبيه بعد التحقق
                            except:
                                pass # في حال المستخدم حظر البوت
            
            time.sleep(60) # فحص كل 60 ثانية
        except Exception as e:
            print(f"Error in monitor: {e}")
            time.sleep(60)

# تشغيل الرادار في خيط منفصل
Thread(target=monitor_market).start()

# --- 5. دوال التحليل والرد ---
def interpret_indicators(current, history, coin_name, my_coin_name):
    if len(history) < 14: return "غير معروف", "غير معروف"
    gains, losses = [], []
    for i in range(1, len(history)):
        delta = history[i] - history[i-1]
        if delta > 0: gains.append(delta)
        else: losses.append(abs(delta))
    avg_gain = sum(gains) / len(gains) if gains else 0
    avg_loss = sum(losses) / len(losses) if losses else 0
    if avg_loss == 0: rsi = 100
    else:
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
    
    rsi_desc = "⚖️ السعر مستقر."
    if rsi >= 70: rsi_desc = "🔥 السعر مرتفع (غالي) - فرصة بيع."
    elif rsi <= 30: rsi_desc = "💎 السعر لقطة (رخيص) - فرصة شراء."

    avg_price = mean(history[-7:])
    trend_desc = f"➖ {coin_name} مستقر."
    if current < avg_price: trend_desc = f"📉 {coin_name} في انخفاض."
    elif current > avg_price: trend_desc = f"📈 {coin_name} في ارتفاع."

    return rsi_desc, trend_desc

def analyze_conversion(amount, from_curr, to_curr, market_data):
    rate_from = market_data[from_curr]["current"]
    rate_to = market_data[to_curr]["current"]
    if from_curr == "ILS": exchange_rate = 1 / rate_to
    elif to_curr == "ILS": exchange_rate = rate_from 
    else: exchange_rate = rate_from / rate_to
    
    shop_rate = exchange_rate * (1 - COMMISSION_PCT)
    net_hand_val = amount * shop_rate
    
    # تحديد العملة التي يتم تحليلها
    if to_curr == "ILS":
        analyze_val, analyze_hist = rate_from, market_data[from_curr]["history"]
        coin_label, base_label = market_data[from_curr]["name"], market_data[to_curr]["name"]
    elif from_curr == "ILS":
        analyze_val, analyze_hist = rate_to, market_data[to_curr]["history"]
        coin_label, base_label = market_data[to_curr]["name"], market_data[from_curr]["name"]
    else:
        # بين عملات أجنبية
        return f"🔹 **التحويل لـ {market_data[to_curr]['name']}**\n   🌐 السعر: {exchange_rate:.4f}\n   💵 الصافي: {net_hand_val:.2f}\nــــــــــــــــــــ\n"

    rsi_msg, trend_msg = interpret_indicators(analyze_val, analyze_hist, coin_label, base_label)
    
    text = f"🔹 **التحويل لـ {market_data[to_curr]['name']}**\n"
    text += f"   🌐 السعر العالمي: {exchange_rate:.4f}\n"
    text += f"   🏪 سعر الصراف: {shop_rate:.4f}\n"
    text += f"   💵 **الصافي بيدك: {net_hand_val:.2f}**\n"
    text += f"   {trend_msg}\n   📊 {rsi_msg}\n"
    
    text += "ــــــــــــــــــــــــــــــــ\n"
    return text

# --- معالجة الأوامر ---

@bot.message_handler(commands=['start', 'help'])
def start(message):
    msg = "👋 **أهلاً بك في البوت المالي الذكي**\n\n"
    msg += "1️⃣ **التحويل والتحليل:**\nاكتب المبلغ والعملة (مثال: `100 دولار`)\n\n"
    msg += "2️⃣ **رادار الأسعار (جديد 📡):**\nاكتب 'تنبيه' + السعر + العملة.\n"
    msg += "• مثال: `تنبيه 3.60 دولار`\n(سينبهك البوت فوراً إذا وصل الدولار لهذا الرقم)."
    bot.reply_to(message, msg)

@bot.message_handler(func=lambda m: True)
def handle_message(message):
    text = message.text.lower()
    
    # --- منطق إضافة التنبيه ---
    if "تنبيه" in text or "alert" in text:
        try:
            # استخراج الرقم
            amount_str = ''.join(filter(lambda x: x.isdigit() or x == '.', text))
            target_price = float(amount_str)
            
            # استخراج العملة
            coin = "USD" # الافتراضي
            if "دينار" in text or "jod" in text: coin = "JOD"
            
            # جلب السعر الحالي لتحديد نوع التنبيه (صعود أم هبوط)
            data = get_live_market_data()
            if not data: 
                bot.reply_to(message, "⚠️ السوق مغلق حالياً، حاول لاحقاً.")
                return
                
            current_price = data[coin]['current']
            alert_type = 'below' if target_price < current_price else 'above'
            
            # الحفظ في الذاكرة
            chat_id = message.chat.id
            if chat_id not in user_alerts: user_alerts[chat_id] = []
            
            user_alerts[chat_id].append({'coin': coin, 'target': target_price, 'type': alert_type})
            
            condition_text = "ينزل تحت" if alert_type == 'below' else "يطلع فوق"
            bot.reply_to(message, f"✅ **تم تشغيل الرادار!**\nسأرسل لك رسالة فوراً عندما {condition_text} {data[coin]['name']} سعر **{target_price}** شيكل.")
            return
        except:
            bot.reply_to(message, "خطأ في الأمر. اكتب مثلاً: **تنبيه 3.65 دولار**")
            return

    # --- منطق التحويل العادي ---
    try:
        data = get_live_market_data()
        if not data:
            bot.reply_to(message, "⚠️ فشل في جلب البيانات.")
            return

        amount_str = ''.join(filter(lambda x: x.isdigit() or x == '.', text))
        if not amount_str:
            bot.reply_to(message, "اكتب المبلغ والعملة (مثال: 100 دولار) أو جرب ميزة التنبيه.")
            return
        amount = float(amount_str)
        
        curr_code = ""
        if "دولار" in text or "usd" in text: curr_code = "USD"
        elif "دينار" in text or "jod" in text: curr_code = "JOD"
        elif "شيكل" in text or "ils" in text: curr_code = "ILS"
        else:
            bot.reply_to(message, "حدد العملة (دولار، دينار، شيكل).")
            return

        report = f"💰 **محفظتك: {amount} {data[curr_code]['name']}**\nــــــــــــــــــــــــــــــــ\n"
        targets = [c for c in ["USD", "JOD", "ILS"] if c != curr_code]
        for target in targets: report += analyze_conversion(amount, curr_code, target, data)
        bot.reply_to(message, report)
    except: bot.reply_to(message, "حدث خطأ، تأكد من الرقم.")

# تشغيل
keep_alive()
bot.infinity_polling()
