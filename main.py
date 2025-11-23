import os
import logging
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, CommandHandler
from handlers.commands import start, get_price_command

# Loglama ayarları (Hata ayıklamak için)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# .env dosyasını yükle
load_dotenv()

def main():
    token = os.getenv("TOKEN")
    
    if not token:
        print("🚨 HATA: .env dosyasında TELEGRAM_TOKEN bulunamadı!")
        return

    # Bot uygulamasını oluştur
    app = ApplicationBuilder().token(token).build()

    # Komutları ekle
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("fiyat", get_price_command))

    print("✅ Bot başarıyla başlatıldı! Telegram'a gidip test edebilirsin.")
    
    # Botu sürekli çalışır halde tut
    app.run_polling()

if __name__ == '__main__':
    main()