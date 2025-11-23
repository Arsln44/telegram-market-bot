# services/ai_service.py
import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

class AIService:
    @staticmethod
    def generate_market_comment(symbol: str, analysis_data: dict):
        """
        Teknik verileri Google Gemini API'ye gönderir ve yorum alır.
        """
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("[AIService] Hata: GEMINI_API_KEY bulunamadı.")
            return None

        try:
            # Gemini Konfigürasyonu
            genai.configure(api_key=api_key)
            
            # DÜZELTME: Senin listendeki en uygun modeli seçtik:
            model = genai.GenerativeModel('gemini-2.5-flash')

            # Verileri Metne Dök
            technical_summary = (
                f"Hisse: {symbol}\n"
                f"Fiyat: {analysis_data.get('price', 'Bilinmiyor')}\n"
                f"Skor: {analysis_data['score']} / Sinyal: {analysis_data['risk_label']}\n"
                f"RSI: {analysis_data['rsi']}\n"
                f"Trend: {analysis_data['mtf']['label']}\n"
                f"Uyumsuzluk: {analysis_data['divergence']['label'] or 'Yok'}\n"
                f"Formasyon: {analysis_data['candle'] or 'Yok'}\n"
                f"Balina Hacmi: {analysis_data['whale'] or 'Yok'}\n"
                f"R/R Oranı: {analysis_data['risk_data']['rr_ratio']}\n"
            )

            prompt = (
                "Sen deneyimli bir borsa uzmanısın. Aşağıdaki teknik verilere dayanarak "
                "kullanıcıya 2-3 cümlelik, samimi, net ve yatırım tavsiyesi vermeden (YTD) "
                "bir piyasa yorumu yap. Sayıları tekrar etme, ne anlama geldiklerini yorumla. "
                "Eğer riskli bir durum varsa uyar.\n\n"
                f"VERİLER:\n{technical_summary}"
            )

            # İsteği Gönder
            response = model.generate_content(prompt)
            
            # Cevabı Dön
            return response.text.strip()

        except Exception as e:
            print(f"[AIService] Gemini Hatası: {e}")
            return None