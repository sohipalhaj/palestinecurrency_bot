import telebot
import yfinance as yf
from statistics import mean
from flask import Flask
from threading import Thread
import time
import os

# --- 1. إعدادات السيرفر (عشان Render ما يطفيه) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is running on Render!"

def run():
    # Render بيعطينا بورت خاص، لازم نستخدمه
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- 2. إعدادات البوت ---
TOKEN = "8582182426:AAFs7YFRu4yK5HbIS2eYALuNxoF6mbEnH4Q"
bot = telebot.TeleBot(TOKEN)
COMMISSION_PCT = 0.008 

# --- دوال جلب البيانات والتحليل ---
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
    rsi_desc = ""
    if rsi >= 70: rsi_desc = "🔥 السعر مرتفع جداً (غالي)."
    elif rsi <= 30: rsi_desc = "💎 السعر منخفض (لقطة)."
    else: rsi_desc = "⚖️ السعر مستقر."
    avg_price = mean(history[-7:])
    trend_desc = ""
    if current < avg_price: trend_desc = f"📉 {coin_name} **في انخفاض** مقابل {my_coin_name}."
    elif current > avg_price: trend_desc = f"📈 {coin_name} **في ارتفاع** مقابل {my_coin_name}."
    else: trend_desc = f"➖ {coin_name} **سعره ثابت** مقابل {my_coin_name}."
    return rsi_desc, trend_desc

def analyze_conversion(amount, from_curr, to_curr, market_data):
    rate_from = market_data[from_curr]["current"]
    rate_to = market_data[to_curr]["current"]
    if from_curr == "ILS": exchange_rate = 1 / rate_to
    elif to_curr == "ILS": exchange_rate = rate_from 
    else: exchange_rate = rate_from / rate_to
    shop_rate = exchange_rate * (1 - COMMISSION_PCT)
    net_hand_val = amount * shop_rate
    
    if to_curr == "ILS":
        analyze_val, analyze_hist = rate_from, market_data[from_curr]["history"]
        coin_label, base_label = market_data[from_curr]["name"], market_data[to_curr]["name"]
    elif from_curr == "ILS":
        analyze_val, analyze_hist = rate_to, market_data[to_curr]["history"]
        coin_label, base_label = market_data[to_curr]["name"], market_data[from_curr]["name"]
    else:
        analyze_val = exchange_rate
        hist_from, hist_to = market_data[from_curr]["history"], market_data[to_curr]["history"]
        analyze_hist = [h_f / h_t for h_f, h_t in zip(hist_from, hist_to)]
        coin_label, base_label = market_data[to_curr]["name"], market_data[from_curr]["name"]

    rsi_msg, trend_msg = interpret_indicators(analyze_val, analyze_hist, coin_label, base_label)
    text = f"🔹 **التحويل لـ {market_data[to_curr]['name']}**\n"
    text += f"   🌐 السعر العالمي: {exchange_rate:.4f}\n"
    text += f"   🏪 سعر الصراف المتوقع: {shop_rate:.4f}\n"
    text += f"   💵 **الصافي بيدك: {net_hand_val:.2f}**\n"
    text += f"   {trend_msg}\n   📊 **وضع السوق:** {rsi_msg}\n"
    
    if not ({from_curr, to_curr} == {"USD", "JOD"}):
        avg_hist = mean(analyze_hist)
        if analyze_val < avg_hist: text += f"\n💡 **فرصة:** السعر الحالي ({analyze_val:.2f}) أقل من المعدل.\n"
    text += "ــــــــــــــــــــــــــــــــ\n"
    return text

# --- تشغيل البوت ---
@bot.message_handler(func=lambda m: True)
def handle_message(message):
    text = message.text.lower()
    try:
        market_data = get_live_market_data()
        if not market_data:
            bot.reply_to(message, "⚠️ فشل في جلب البيانات.")
            return
        amount_str = ''.join(filter(lambda x: x.isdigit() or x == '.', text))
        if not amount_str:
            bot.reply_to(message, "اكتب المبلغ والعملة (مثال: 100 دولار)")
            return
        amount = float(amount_str)
        curr_code = ""
        if "دولار" in text or "usd" in text: curr_code = "USD"
        elif "دينار" in text or "jod" in text: curr_code = "JOD"
        elif "شيكل" in text or "ils" in text: curr_code = "ILS"
        else:
            bot.reply_to(message, "حدد العملة (دولار، دينار، شيكل).")
            return
        report = f"💰 **محفظتك: {amount} {market_data[curr_code]['name']}**\nــــــــــــــــــــــــــــــــ\n"
        targets = [c for c in ["USD", "JOD", "ILS"] if c != curr_code]
        for target in targets: report += analyze_conversion(amount, curr_code, target, market_data)
        bot.reply_to(message, report)
    except: bot.reply_to(message, "حدث خطأ، تأكد من الرقم.")

# تشغيل السيرفر والبوت
keep_alive()
bot.infinity_polling()
