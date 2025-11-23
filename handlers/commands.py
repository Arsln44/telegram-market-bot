from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from services.market_data import MarketDataService
from services.analysis_service import AnalysisService

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ /start komutu geldiğinde çalışır """
    user_first_name = update.effective_user.first_name
    
    await update.message.reply_text(
        f"Selam {user_first_name}! 👋\n"
        "Ben Borsa Takip Asistanı.\n\n"
        "📊 **Kullanabileceğin Komutlar:**\n\n"
        "1️⃣ **Fiyat Sorgulama:**\n"
        "`/fiyat <KOD>` -> Anlık fiyatı getirir.\n"
        "Örn: `/fiyat THYAO`\n\n"
        "2️⃣ **Teknik Analiz (RSI):**\n"
        "`/analiz <KOD>` -> Al/Sat sinyal durumunu ölçer.\n"
        "Örn: `/analiz ASELS`\n\n"
        "Kripto paralar için: `/analiz BTC-USD` gibi kullanabilirsin.",
        parse_mode=ParseMode.MARKDOWN
    )

async def get_price_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ /fiyat <SEMBOL> komutunu işler """
    
    # Kullanıcı sadece /fiyat yazıp hisse adı yazmadıysa uyar
    if not context.args:
        await update.message.reply_text("⚠️ Lütfen bir hisse kodu girin.\nÖrn: `/fiyat GARAN`", parse_mode=ParseMode.MARKDOWN)
        return

    symbol = context.args[0] # İlk parametreyi al
    
    # Kullanıcıya "işlem yapılıyor" mesajı at (UX için önemli)
    wait_msg = await update.message.reply_text(f"🔍 *{symbol.upper()}* verileri çekiliyor...", parse_mode=ParseMode.MARKDOWN)

    # Servisi çağır (Bloke etmemesi için burada basit çağırıyoruz, 
    # ileride daha complex işlemlerde thread kullanacağız)
    result = MarketDataService.get_stock_price(symbol)

    if result:
        message = (
            f"📈 *{result['symbol']}*\n"
            f"💰 Fiyat: `{result['price']} {result['currency']}`"
        )
        # Bekleme mesajını silmek yerine editle (Daha profesyonel durur)
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id, 
            message_id=wait_msg.message_id, 
            text=message, 
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id, 
            message_id=wait_msg.message_id, 
            text=f"❌ *{symbol}* bulunamadı veya veri çekilemedi.",
            parse_mode=ParseMode.MARKDOWN
        )

async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ /analiz <SEMBOL> komutunu işler """
    
    if not context.args:
        await update.message.reply_text("⚠️ Lütfen hisse kodu girin.\nÖrn: `/analiz THYAO`", parse_mode=ParseMode.MARKDOWN)
        return

    symbol = context.args[0]
    wait_msg = await update.message.reply_text(f"⚙️ *{symbol.upper()}* teknik analizi yapılıyor...", parse_mode=ParseMode.MARKDOWN)

    # 1. Adım: Veriyi Çek
    df = MarketDataService.get_historical_data(symbol)
    
    if df is None:
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id, 
            message_id=wait_msg.message_id, 
            text="❌ Yeterli veri bulunamadı.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # 2. Adım: Analiz Et
    rsi_result = AnalysisService.calculate_rsi(df)
    
    # Anlık fiyatı da alalım ki rapor tam olsun
    price_info = MarketDataService.get_stock_price(symbol)

    if rsi_result and price_info:
        message = (
            f"📊 **Teknik Analiz Raporu: {price_info['symbol']}**\n\n"
            f"💰 **Fiyat:** {price_info['price']} {price_info['currency']}\n"
            f"📉 **RSI (14):** `{rsi_result['value']}`\n"
            f"b **Sinyal:** {rsi_result['signal']}\n\n"
            "_Not: Bu bir yatırım tavsiyesi değildir._"
        )
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id, 
            message_id=wait_msg.message_id, 
            text=message, 
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id, 
            message_id=wait_msg.message_id, 
            text="❌ Analiz sırasında bir hata oluştu.",
            parse_mode=ParseMode.MARKDOWN
        )