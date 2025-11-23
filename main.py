# main.py
import os
import logging
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, CommandHandler
from handlers.commands import start, get_price_command, analyze_command

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

load_dotenv()

def main():
    token = os.getenv("TOKEN")
    if not token:
        print("🚨 HATA: .env dosyasında TOKEN bulunamadı!")
        return

    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("fiyat", get_price_command))
    app.add_handler(CommandHandler("analiz", analyze_command))

    print("✅ Bot başarıyla başlatıldı!")
    app.run_polling()

if __name__ == '__main__':
    main()
