from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from services.market_data import MarketDataService

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ /start komutu geldiğinde çalışır """
    user_first_name = update.effective_user.first_name
    await update.message.reply_text(
        f"Selam {user_first_name}! 👋\n"
        "Ben Borsa Takip Asistanı.\n\n"
        "Hisse fiyatı sorgulamak için:\n"
        "`/fiyat <HISSE_KODU>` yazabilirsin.\n\n"
        "Örnekler:\n"
        "👉 /fiyat THYAO\n"
        "👉 /fiyat ASELS\n"
        "👉 /fiyat BTC-USD",
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