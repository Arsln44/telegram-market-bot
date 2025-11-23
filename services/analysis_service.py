# services/analysis_service.py
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import MACD, SMAIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from ta.volume import OnBalanceVolumeIndicator

class AnalysisService:
    @staticmethod
    def _volatility_metrics(df: pd.DataFrame):
        """
        Basit volatilite ölçüleri:
        - pct_std: günlük (veya verilen timeframe) getiri standart sapması
        - atr: Average True Range (volatilite ölçümü)
        """
        res = {"pct_std": None, "atr": None}
        try:
            returns = df["Close"].pct_change().dropna()
            if len(returns) >= 2:
                res["pct_std"] = float(returns.std())

            # ATR (14)
            atr = AverageTrueRange(high=df["High"], low=df["Low"], close=df["Close"], window=14)
            res["atr"] = float(atr.average_true_range().iloc[-1])
        except Exception as e:
            print(f"[volatility_metrics] Hata: {e}")
        return res

    @staticmethod
    def calculate_technical_signals(df: pd.DataFrame, volatility_sensitive=True):
        """
        Hisse verisini analiz eder.
        volatility_sensitive: True ise volatilite yüksek olduğunda bant/RSI ağırlıklarını azaltır.
        Dönen veri: rsi, score, risk_label, details, obv_trend, volatility, stop_loss önerileri
        """
        if df is None or df.empty:
            return None

        try:
            # --- Indikatörler ---
            rsi_ind = RSIIndicator(close=df["Close"], window=14)
            current_rsi = float(rsi_ind.rsi().iloc[-1])

            macd_ind = MACD(close=df["Close"])
            current_macd = float(macd_ind.macd().iloc[-1])
            current_signal = float(macd_ind.macd_signal().iloc[-1])

            bb = BollingerBands(close=df["Close"], window=20, window_dev=2)
            bb_upper = float(bb.bollinger_hband().iloc[-1])
            bb_lower = float(bb.bollinger_lband().iloc[-1])
            bb_mid = float(bb.bollinger_mavg().iloc[-1])
            current_price = float(df["Close"].iloc[-1])

            obv_ind = OnBalanceVolumeIndicator(close=df["Close"], volume=df["Volume"])
            obv = obv_ind.on_balance_volume()
            obv_trend = "Nötr"
            if len(obv) >= 5:
                obv_trend = "Artıyor 🟢" if obv.iloc[-1] > obv.iloc[-5] else "Azalıyor 🔴"

            # Volatilite metrikleri
            vol = AnalysisService._volatility_metrics(df)
            pct_std = vol["pct_std"] or 0.0
            atr = vol["atr"] or 0.0

            # Basit volatilite derecelendirmesi
            vol_label = "Düşük"
            if pct_std > 0.03 or (atr and atr / current_price > 0.02):
                vol_label = "Yüksek"
            elif pct_std > 0.015:
                vol_label = "Orta"

            # --- PUANLAMA (parametrik ve volatiliteye duyarlı) ---
            score = 0
            details = []
            # Ağırlıklar (standart)
            weights = {
                "rsi": 2,
                "macd": 2,
                "bb": 3,
                "obv": 1
            }

            # Eğer volatilite yüksekse Bollinger ağırlığını azalt ve toplam skoru
            # temkinli yapmak için çarpan uygula
            volatility_multiplier = 1.0
            if volatility_sensitive and vol_label == "Yüksek":
                # yüksek volatilitede bant sinyallerine daha az güven -> bb ağırlığını düşür
                weights["bb"] = 1
                volatility_multiplier = 0.8
            elif volatility_sensitive and vol_label == "Orta":
                weights["bb"] = 2
                volatility_multiplier = 0.95

            # RSI
            if current_rsi < 30:
                score += int(weights["rsi"] * 1)
                details.append("RSI: Dip Bölge (Fırsat)")
            elif current_rsi > 70:
                score -= int(weights["rsi"] * 1)
                details.append("RSI: Tepe Bölge (Risk)")

            # MACD
            if current_macd > current_signal:
                score += int(weights["macd"] * 1)
                details.append("MACD: Al Sinyali")
            else:
                score -= int(weights["macd"] * 1)
                details.append("MACD: Sat Sinyali")

            # Bollinger band
            if current_price < bb_lower:
                score += int(weights["bb"] * 2)
                details.append("BB: Alt Bandı Kırdı (Tepki Gelebilir)")
            elif current_price > bb_upper:
                score -= int(weights["bb"] * 1)
                details.append("BB: Üst Bantta (Yorgunluk)")

            # OBV
            if "Artıyor" in obv_trend:
                score += int(weights["obv"] * 1)
            else:
                score -= int(weights["obv"] * 1)

            # Volatiliteye göre skoru yumuşat
            score = int(round(score * volatility_multiplier))

            # Etiketleme (esnek eşikler)
            risk_label = "NÖTR"
            if score >= 4:
                risk_label = "GÜÇLÜ AL 🚀"
            elif 1 <= score < 4:
                risk_label = "AL (Zayıf) 📈"
            elif -3 <= score < 1:
                risk_label = "SAT (Zayıf) 📉"
            elif score < -3:
                risk_label = "GÜÇLÜ SAT 🛑"

            # Stop-loss / Take-profit önerisi (ATR tabanlı)
            stop_loss = None
            take_profit = None
            if atr and current_price:
                # Basit öneri: AL için stop = price - 2*ATR, TP = price + 3*ATR
                stop_loss = round(current_price - 2 * atr, 4)
                take_profit = round(current_price + 3 * atr, 4)

            return {
                "rsi": round(current_rsi, 2),
                "score": score,
                "risk_label": risk_label,
                "details": details,
                "obv_trend": obv_trend,
                "volatility": {"label": vol_label, "pct_std": round(pct_std, 5), "atr": round(atr, 6)},
                "stop_loss": stop_loss,
                "take_profit": take_profit
            }

        except Exception as e:
            print(f"[calculate_technical_signals] Analiz Hatası: {e}")
            return None

    @staticmethod
    def analyze_market_health(df: pd.DataFrame):
        """
        Piyasa yönü (SMA50 / SMA200) kontrolü. Eksik veri durumuna toleranslı.
        """
        if df is None or df.empty:
            return "Veri Yok", "Nötr"

        try:
            # Eğer 200 günlük veri yoksa mevcut length'e göre fallback yap
            length = len(df)
            window50 = 50 if length >= 50 else max(5, int(length / 4))
            window200 = 200 if length >= 200 else max(window50 + 1, int(length / 2))

            sma50 = SMAIndicator(close=df["Close"], window=window50).sma_indicator().iloc[-1]
            sma200 = SMAIndicator(close=df["Close"], window=window200).sma_indicator().iloc[-1]
            current_price = float(df["Close"].iloc[-1])

            status = "Nötr"
            trend_desc = ""

            if current_price > sma200:
                if current_price > sma50:
                    status = "POZİTİF (Boğa) 🐂"
                    trend_desc = "Piyasa yükseliş trendinde. Alımlar destekleniyor."
                else:
                    status = "DÜZELTME ⚠️"
                    trend_desc = "Ana trend yukarı ama kısa vade zayıf."
            else:
                if current_price < sma50:
                    status = "NEGATİF (Ayı) 🐻"
                    trend_desc = "Piyasa düşüş trendinde. Riskler çok yüksek."
                else:
                    status = "TEPKİ YÜKSELİŞİ 🤞"
                    trend_desc = "Düşüş trendinde tepki veriyor. Dikkatli olunmalı."

            return status, trend_desc

        except Exception as e:
            print(f"[analyze_market_health] Hata: {e}")
            return "Hata", "Hesaplanamadı"
