# services/analysis_service.py
import pandas as pd
import numpy as np
from ta.momentum import RSIIndicator
from ta.trend import MACD, SMAIndicator, EMAIndicator
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
    def _get_peaks_troughs(series, window=3):
        """
        Veri serisindeki yerel tepe (peaks) ve dipleri (troughs) bulur.
        window: Sağında ve solunda kaç mumun daha düşük/yüksek olması gerektiği.
        Titiz analiz için window=2 veya 3 idealdir.
        """
        peaks = []
        troughs = []
        
        # Son 'window' kadar veri henüz teyit edilmediği için işlenmez.
        # Bu yüzden range(window, len - window)
        for i in range(window, len(series) - window):
            current = series.iloc[i]
            
            # Tepe Kontrolü
            is_peak = all(current > series.iloc[i-w] for w in range(1, window+1)) and \
                      all(current > series.iloc[i+w] for w in range(1, window+1))
            if is_peak:
                peaks.append((series.index[i], current, i)) # (Tarih, Değer, Index)
                
            # Dip Kontrolü
            is_trough = all(current < series.iloc[i-w] for w in range(1, window+1)) and \
                        all(current < series.iloc[i+w] for w in range(1, window+1))
            if is_trough:
                troughs.append((series.index[i], current, i))
                
        return peaks, troughs

    @staticmethod
    def detect_rsi_divergence(df: pd.DataFrame):
        """
        Fiyat ve RSI arasındaki uyumsuzlukları (Divergence) tespit eder.
        Dönüş: (Label, Açıklama) örn: ('POZİTİF UYUMSUZLUK', 'Fiyat düşerken RSI yükseliyor')
        """
        if len(df) < 20: return None, None

        # RSI Hesapla
        rsi_series = RSIIndicator(close=df["Close"], window=14).rsi()
        
        # Fiyat (Low/High) ve RSI için tepe/dip bul (Window=2 kullanıyoruz ki yakın dönüşleri yakalayalım)
        price_peaks, price_troughs = AnalysisService._get_peaks_troughs(df["Close"], window=2)
        rsi_peaks, rsi_troughs = AnalysisService._get_peaks_troughs(rsi_series, window=2)

        # En az 2 dip veya tepe lazım
        if len(price_troughs) < 2 or len(rsi_troughs) < 2:
            return None, None

        # --- BULLISH (Pozitif) DIVERGENCE KONTROLÜ ---
        # Fiyatın son iki dibi: Son dip, önceki dipten DAHA AŞAĞIDA (Lower Low)
        # RSI'ın son iki dibi: Son dip, önceki dipten DAHA YUKARIDA (Higher Low)
        
        # Son tespit edilen dipleri al
        last_p_trough = price_troughs[-1] 
        prev_p_trough = price_troughs[-2]
        
        last_r_trough = rsi_troughs[-1]
        prev_r_trough = rsi_troughs[-2]

        # Zaman indekslerinin yakın olması lazım (Senkronizasyon kontrolü)
        # Yani fiyat dibi ile RSI dibi arasında çok büyük zaman farkı olmamalı (örn: +-3 bar tolerans)
        idx_diff = abs(last_p_trough[2] - last_r_trough[2])
        
        if idx_diff <= 3:
            # Mantık Kontrolü
            price_lower_low = last_p_trough[1] < prev_p_trough[1]
            rsi_higher_low = last_r_trough[1] > prev_r_trough[1]
            
            if price_lower_low and rsi_higher_low:
                return "PU (Yükseliş Sinyali) 🐂", "Fiyat yeni dip yaparken RSI yükseliyor (Trend Dönüşü)."

        # --- BEARISH (Negatif) DIVERGENCE KONTROLÜ ---
        # Fiyatın son iki tepesi: Son tepe DAHA YUKARIDA (Higher High)
        # RSI'ın son iki tepesi: Son tepe DAHA AŞAĞIDA (Lower High)
        
        if len(price_peaks) < 2 or len(rsi_peaks) < 2:
            return None, None

        last_p_peak = price_peaks[-1]
        prev_p_peak = price_peaks[-2]
        last_r_peak = rsi_peaks[-1]
        prev_r_peak = rsi_peaks[-2]
        
        idx_diff_peak = abs(last_p_peak[2] - last_r_peak[2])
        
        if idx_diff_peak <= 3:
            price_higher_high = last_p_peak[1] > prev_p_peak[1]
            rsi_lower_high = last_r_peak[1] < prev_r_peak[1]
            
            if price_higher_high and rsi_lower_high:
                return "NU (Düşüş Sinyali) 🐻", "Fiyat yükselirken RSI düşüyor (Güç Kaybı)."

        return None, None

    @staticmethod
    def calculate_mtf_trend(macro_df: pd.DataFrame):
        """
        Üst zaman dilimindeki (Macro) trendi analiz eder.
        EMA 50 ve RSI referans alınır.
        """
        if macro_df is None or macro_df.empty:
            return "Veri Yok", "Nötr"
            
        try:
            current_close = macro_df["Close"].iloc[-1]
            # EMA 50
            ema50 = EMAIndicator(close=macro_df["Close"], window=50).ema_indicator().iloc[-1]
            # RSI
            rsi = RSIIndicator(close=macro_df["Close"], window=14).rsi().iloc[-1]
            
            trend = "Nötr"
            color = "⚪"
            
            if current_close > ema50:
                if rsi > 50:
                    trend = "YÜKSELİŞ (Güçlü)"
                    color = "🟢"
                else:
                    trend = "YÜKSELİŞ (Zayıf)"
                    color = "🟢"
            else:
                if rsi < 50:
                    trend = "DÜŞÜŞ (Güçlü)"
                    color = "🔴"
                else:
                    trend = "DÜŞÜŞ (Zayıf)"
                    color = "🔴"
                    
            return f"{trend} {color}", f"Fiyat EMA50 {'üstünde' if current_close > ema50 else 'altında'}, RSI: {round(rsi,1)}"
            
        except Exception:
            return "Hata", "-"

    # --- ANA ANALİZ FONKSİYONU (GÜNCELLENDİ) ---
    
    @staticmethod
    def calculate_technical_signals(df: pd.DataFrame, macro_df: pd.DataFrame = None):
        """
        Artık hem mevcut df hem de macro_df (üst periyot) alıyor.
        """
        if df is None or df.empty:
            return None

        try:
            # 1. Temel İndikatörler
            rsi_ind = RSIIndicator(close=df["Close"], window=14)
            current_rsi = float(rsi_ind.rsi().iloc[-1])

            macd_ind = MACD(close=df["Close"])
            current_macd = float(macd_ind.macd().iloc[-1])
            current_signal = float(macd_ind.macd_signal().iloc[-1])

            bb = BollingerBands(close=df["Close"], window=20, window_dev=2)
            bb_upper = float(bb.bollinger_hband().iloc[-1])
            bb_lower = float(bb.bollinger_lband().iloc[-1])

            obv_ind = OnBalanceVolumeIndicator(close=df["Close"], volume=df["Volume"])
            obv = obv_ind.on_balance_volume()
            obv_trend = "Nötr"
            if len(obv) >= 5:
                obv_trend = "Artıyor 🟢" if obv.iloc[-1] > obv.iloc[-5] else "Azalıyor 🔴"

            atr = AverageTrueRange(high=df["High"], low=df["Low"], close=df["Close"], window=14).average_true_range().iloc[-1]

            # 2. Yeni Özellik: DIVERGENCE Tespiti
            div_label, div_desc = AnalysisService.detect_rsi_divergence(df)
            
            # 3. Yeni Özellik: MTF Trend Analizi
            mtf_label, mtf_desc = "Yok", "-"
            if macro_df is not None:
                mtf_label, mtf_desc = AnalysisService.calculate_mtf_trend(macro_df)

            # --- PUANLAMA SİSTEMİ (Revize Edildi) ---
            score = 0
            details = []
            
            # RSI
            if current_rsi < 30: 
                score += 2
                details.append("RSI: Dip Bölge (30 altı)")
            elif current_rsi > 70: 
                score -= 2
                details.append("RSI: Tepe Bölge (70 üstü)")
                
            # MACD
            if current_macd > current_signal:
                score += 1
                details.append("MACD: Pozitif Kesişim")
            else:
                score -= 1
            
            # Bollinger
            current_price = df["Close"].iloc[-1]
            if current_price < bb_lower:
                score += 2
                details.append("BB: Alt Bandı Deldi (Tepki Beklentisi)")
            elif current_price > bb_upper:
                score -= 1
            
            # Divergence (Büyük Puan Etkisi)
            if div_label:
                if "Yükseliş" in div_label:
                    score += 3  # Uyumsuzluk güçlü sinyaldir
                    details.append(f"🔥 {div_label}")
                elif "Düşüş" in div_label:
                    score -= 3
                    details.append(f"⚠️ {div_label}")

            # MTF Trend Onayı (Trend yönünde isek puan artır)
            if "YÜKSELİŞ" in mtf_label and score > 0:
                score += 1
                details.append("MTF: Büyük Resim Yükselişi Destekliyor")
            elif "DÜŞÜŞ" in mtf_label and score < 0:
                score -= 1
                details.append("MTF: Büyük Resim Düşüşü Destekliyor")

            # Etiketleme
            risk_label = "NÖTR"
            if score >= 5: risk_label = "GÜÇLÜ AL 🚀"
            elif score >= 2: risk_label = "AL 📈"
            elif score <= -5: risk_label = "GÜÇLÜ SAT 🛑"
            elif score <= -2: risk_label = "SAT 📉"

            return {
                "score": score,
                "risk_label": risk_label,
                "rsi": round(current_rsi, 2),
                "details": details,
                "obv_trend": obv_trend,
                "stop_loss": round(current_price - 2 * atr, 4),
                "take_profit": round(current_price + 3 * atr, 4),
                "divergence": {"label": div_label, "desc": div_desc},
                "mtf": {"label": mtf_label, "desc": mtf_desc}
            }

        except Exception as e:
            print(f"Analiz Hatası: {e}")
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
