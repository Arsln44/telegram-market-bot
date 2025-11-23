# handlers/commands.py
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from services.market_data import MarketDataService
from services.analysis_service import AnalysisService

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_first_name = update.effective_user.first_name
    await update.message.reply_text(
        f"Selam {user_first_name}! 👋\n"
        "Borsa Takip Asistanı hazırım.\n\n"
        "📊 Komutlar:\n"
        "`/fiyat <KOD>` -> Anlık fiyat\n"
        "`/analiz <KOD> [<interval>]` -> Teknik analiz. Interval örn: 1d, 1h, 15m\n"
        "Örn: `/analiz THYAO 1d` veya `/analiz BTC-USD 60m`",
        parse_mode=ParseMode.MARKDOWN
    )

async def get_price_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Lütfen bir hisse kodu girin.\nÖrn: `/fiyat GARAN`", parse_mode=ParseMode.MARKDOWN)
        return

    symbol = context.args[0]
    wait_msg = await update.message.reply_text(f"🔍 *{symbol.upper()}* verileri çekiliyor...", parse_mode=ParseMode.MARKDOWN)

    result = MarketDataService.get_stock_price(symbol)

    if result:
        message = (
            f"📈 *{result['symbol']}*\n"
            f"💰 Fiyat: `{result['price']} {result['currency']}`"
        )
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=wait_msg.message_id, text=message, parse_mode=ParseMode.MARKDOWN)
    else:
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=wait_msg.message_id, text=f"❌ *{symbol}* bulunamadı veya veri çekilemedi.", parse_mode=ParseMode.MARKDOWN)

async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /analiz <SYMBOL> [<interval>]
    interval örnekleri: 1d (günlük, default), 1h (60m), 15m (15m), 5m
    """
    if not context.args:
        await update.message.reply_text("⚠️ Örn: `/analiz THYAO 1d` veya `/analiz BTC-USD 60m`", parse_mode=ParseMode.MARKDOWN)
        return

    symbol = context.args[0].upper()
    interval = "1d"  # default
    if len(context.args) > 1:
        interval = context.args[1]

    # Basit interval -> yf interval dönüşümü (kendi ihtiyacına göre genişlet)
    # yfinance expects interval like "1d", "60m", "15m"
    yf_interval = interval
    # Period seçimi: interval'e göre mantıklı bir period seçelim
    if yf_interval.endswith("m"):
        # intraday => 30 günlük geçmiş yeterli olabilir
        period = "30d"
    elif yf_interval.endswith("h"):
        period = "90d"
    else:
        period = "1y"

    wait_msg = await update.message.reply_text(f"🔍 *{symbol}* analiz ediliyor ({yf_interval})...", parse_mode=ParseMode.MARKDOWN)

    # Hisse verisi
    stock_df = MarketDataService.get_historical_data(symbol, period=period, interval=yf_interval)

    # Endeks/piyasa için konjonktür (BIST 100 veya BTC)
    is_crypto = "-" in symbol or "USD" in symbol
    market_index_symbol = "BTC-USD" if is_crypto else "XU100.IS"
    market_name = "BITCOIN" if is_crypto else "BIST 100"
    market_df = MarketDataService.get_historical_data(market_index_symbol, period=period, interval=yf_interval)

    if stock_df is None:
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=wait_msg.message_id, text="❌ Hisse verisi çekilemedi veya yetersiz veri.")
        return

    stock_analysis = AnalysisService.calculate_technical_signals(stock_df, volatility_sensitive=True)
    market_status, market_comment = AnalysisService.analyze_market_health(market_df)
    price_info = MarketDataService.get_stock_price(symbol)

    if stock_analysis and price_info:
        details_text = "\n".join([f"• {item}" for item in stock_analysis["details"]])
        vol = stock_analysis["volatility"]
        market_emoji = "✅" if "POZİTİF" in market_status else "⚠️"

        # Risk uyarıları
        extra_warn = ""
        if vol["label"] == "Yüksek":
            extra_warn = "\n⚠️ *Volatilite yüksek!* Bant sinyallerine daha az güven. Yakından izle."

        # Stop-loss bilgisi
        sl = stock_analysis.get("stop_loss")
        tp = stock_analysis.get("take_profit")
        sl_text = f"\nStop-loss önerisi: `{sl}`" if sl else ""
        tp_text = f" / Take-profit: `{tp}`" if tp else ""

        message = (
            f"📊 *{price_info['symbol']} ANALİZ RAPORU* ({yf_interval})\n"
            f"💰 Fiyat: `{price_info['price']} {price_info['currency']}`\n\n"
            f"🌍 *PİYASA ORTAMI ({market_name}):*\n"
            f"Durum: `{market_status}`\n"
            f"Yorum: _{market_comment}_\n\n"
            f"🔍 *HİSSE TEKNİK GÖRÜNÜMÜ:*\n"
            f"Skor: `{stock_analysis['score']} `\n"
            f"Sinyal: *{stock_analysis['risk_label']}*\n"
            f"📈 RSI: `{stock_analysis['rsi']}`\n"
            f"📊 Hacim Trendi: `{stock_analysis['obv_trend']}`\n"
            f"📉 Volatilite: `{vol['label']}` (std: `{vol['pct_std']}`, ATR: `{vol['atr']}`)\n\n"
            f"*Detaylar:*\n{details_text}"
            f"{extra_warn}\n\n"
            f"{sl_text}{tp_text}\n\n"
            f"_Not: Bu bir yatırım tavsiyesi değildir. Stop-loss ATR tabanlı öneridir, pozisyon boyutunu piyasa koşullarına göre ayarla._"
        )

        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=wait_msg.message_id, text=message, parse_mode=ParseMode.MARKDOWN)
    else:
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=wait_msg.message_id, text="❌ Analiz yapılamadı veya eksik veri.")
