import pandas as pd
from ta.momentum import RSIIndicator

class AnalysisService:
    @staticmethod
    def calculate_rsi(df: pd.DataFrame, window=14):
        """
        Verilen veri seti üzerinde RSI hesaplar.
        RSI < 30 : Aşırı Satım (Alım Fırsatı Olabilir)
        RSI > 70 : Aşırı Alım (Düşüş Riski Olabilir)
        """
        try:
            # Kütüphaneyi kullanarak RSI hesapla
            rsi_indicator = RSIIndicator(close=df["Close"], window=window)
            df["rsi"] = rsi_indicator.rsi()
            
            # Son günkü RSI değerini al
            current_rsi = df["rsi"].iloc[-1]
            
            # Yorumla
            signal = "Nötr 😐"
            if current_rsi < 30:
                signal = "🟢 AŞIRI SATIM (Dip Bölgesi)"
            elif current_rsi > 70:
                signal = "🔴 AŞIRI ALIM (Tepe Bölgesi)"
            elif 30 <= current_rsi < 45:
                signal = "Alım Bölgesine Yakın"
            elif 55 < current_rsi <= 70:
                signal = "Satım Bölgesine Yakın"

            return {
                "value": round(current_rsi, 2),
                "signal": signal
            }
        except Exception as e:
            print(f"Analiz Hatası: {e}")
            return None