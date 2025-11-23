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
    if not context.args:
        await update.message.reply_text("⚠️ Örn: `/analiz THYAO 1h`", parse_mode=ParseMode.MARKDOWN)
        return

    symbol = context.args[0].upper()
    interval = context.args[1] if len(context.args) > 1 else "1d"
    
    # 1. Macro Periyodu Belirle
    macro_interval = MarketDataService.get_macro_interval(interval)
    
    wait_msg = await update.message.reply_text(
        f"🔍 *{symbol}* analiz ediliyor...\n"
        f"⏱️ Periyot: {interval} | 🌍 Trend: {macro_interval}", 
        parse_mode=ParseMode.MARKDOWN
    )

    # Period ayarlamaları (Veri çekme optimizasyonu)
    # yfinance period formatları: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
    period_mapping = {
        "1m": "5d", "5m": "5d", "15m": "1mo", "30m": "1mo",
        "1h": "6mo", "4h": "1y", "1d": "2y", "1wk": "5y"
    }
    period = period_mapping.get(interval, "1y")
    macro_period = period_mapping.get(macro_interval, "2y")

    # 2. Verileri Çek (Parallel yapılabilir ama şimdilik sıralı yeterli)
    stock_df = MarketDataService.get_historical_data(symbol, period=period, interval=interval)
    macro_df = MarketDataService.get_historical_data(symbol, period=macro_period, interval=macro_interval)

    if stock_df is None:
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=wait_msg.message_id, text="❌ Veri alınamadı.")
        return

    # 3. Analizi Başlat (Macro veriyi de gönderiyoruz)
    analysis = AnalysisService.calculate_technical_signals(stock_df, macro_df=macro_df)
    price_info = MarketDataService.get_stock_price(symbol)

    if analysis and price_info:
        # Detay listesini madde imiyle birleştir
        details_text = "\n".join([f"• {d}" for d in analysis['details']]) if analysis['details'] else "• Belirgin sinyal yok."
        
        # Divergence Mesajı (Varsa)
        div_msg = ""
        if analysis['divergence']['label']:
            div_msg = f"\n📢 *UYUMSUZLUK VAR:*\nSinyal: `{analysis['divergence']['label']}`\nDurum: _{analysis['divergence']['desc']}_\n"

        supp = analysis['levels']['support']
        res = analysis['levels']['resistance']
        levels_txt = f"🛡️ Destek: `{supp}`\n🚧 Direnç: `{res}`" if supp else "Hesaplanamadı"

        message = (
            f"📊 *{price_info['symbol']} ANALİZ RAPORU* ({interval})\n"
            f"💰 Fiyat: `{price_info['price']} {price_info['currency']}`\n"
            f"🏆 Skor: `{analysis['score']}` | Sinyal: *{analysis['risk_label']}*\n\n"
            
            f"🌍 *GENEL TREND ({macro_interval}):*\n"
            f"Yön: `{analysis['mtf']['label']}`\n"
            f"{div_msg}\n"
            
            f"🏗️ *FİYAT YAPISI (50 Mum):*\n"
            f"{levels_txt}\n\n"
            
            f"📐 *TEKNİK GÖSTERGELER:*\n"
            f"RSI: `{analysis['rsi']}`\n"
            f"Hacim Trendi: `{analysis['obv_trend']}`\n\n"
            
            f"📋 *DETAYLAR:*\n{details_text}\n\n"
            
            f"🛡️ *PLAN (ATR):*\n"
            f"🛑 Stop: `{analysis['stop_loss']}`\n"
            f"🎯 Hedef: `{analysis['take_profit']}`\n"
        )
        
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=wait_msg.message_id, text=message, parse_mode=ParseMode.MARKDOWN)
    else:
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=wait_msg.message_id, text="❌ Analiz hatası.")