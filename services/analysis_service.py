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
        if df is None or df.empty: return None

        try:
            # --- 1. Veri Hazırlığı ---
            current_row = df.iloc[-1]
            current_price = float(current_row["Close"])
            
            # İndikatörler
            rsi = float(RSIIndicator(close=df["Close"], window=14).rsi().iloc[-1])
            
            macd_ind = MACD(close=df["Close"])
            macd = float(macd_ind.macd().iloc[-1])
            signal = float(macd_ind.macd_signal().iloc[-1])
            
            bb = BollingerBands(close=df["Close"], window=20, window_dev=2)
            bb_lower = float(bb.bollinger_lband().iloc[-1])
            bb_upper = float(bb.bollinger_hband().iloc[-1])
            
            atr = float(AverageTrueRange(high=df["High"], low=df["Low"], close=df["Close"], window=14).average_true_range().iloc[-1])
            sma50 = SMAIndicator(close=df["Close"], window=50).sma_indicator().iloc[-1]
            
            obv_ind = OnBalanceVolumeIndicator(close=df["Close"], volume=df["Volume"])
            obv_curr = obv_ind.on_balance_volume().iloc[-1]
            obv_prev = obv_ind.on_balance_volume().iloc[-5]
            obv_trend = "Artıyor 🟢" if obv_curr > obv_prev else "Azalıyor 🔴"

            # --- 2. Özel Analizler ---
            # a) Divergence
            div_label, div_desc = AnalysisService.detect_rsi_divergence(df)
            # b) MTF
            mtf_label, mtf_desc = "Yok", "-"
            if macro_df is not None:
                mtf_label, mtf_desc = AnalysisService.calculate_mtf_trend(macro_df)
            # c) Levels
            supp, res = AnalysisService._calculate_support_resistance(df)
            # d) Mean Reversion
            mr_status = AnalysisService._check_mean_reversion(current_price, sma50)
            # e) YENİ: Whale & Candle
            whale_signal = AnalysisService._detect_whale_volume(df)
            candle_pattern = AnalysisService._analyze_candlestick_pattern(current_row)

            # --- 3. Puanlama Motoru ---
            score = 0
            details = []
            
            # RSI
            if rsi < 30: score += 2; details.append("RSI: Aşırı Satım (Dip)")
            elif rsi > 70: score -= 2; details.append("RSI: Aşırı Alım (Tepe)")
            
            # MACD
            if macd > signal: score += 1
            else: score -= 1
            
            # Bollinger
            if current_price < bb_lower: score += 2; details.append("BB: Alt Bant Delindi")
            
            # Yapısal Seviyeler
            if supp and abs(current_price - supp)/current_price < 0.02:
                score += 2; details.append("YAPI: Desteğe Yakın 🛡️")
            elif res and abs(current_price - res)/current_price < 0.02:
                score -= 2; details.append("YAPI: Dirence Yakın 🚧")
                
            # Uyumsuzluk
            if div_label:
                score += 3 if "Yükseliş" in div_label else -3
                details.append(f"🔥 {div_label}")

            # YENİ: Balina Etkisi
            if whale_signal:
                # Eğer fiyat artıyorsa ve hacim yüksekse -> Güçlü Al
                if current_price > df["Open"].iloc[-1]:
                    score += 2
                    details.append(f"🐋 HACİM: {whale_signal} (Yükseliş Destekli)")
                else:
                    score -= 2
                    details.append(f"🐋 HACİM: {whale_signal} (Satış Baskısı)")

            # YENİ: Mum Formasyonu (Pinbar)
            if candle_pattern:
                if "ÇEKİÇ" in candle_pattern: # Bullish
                    score += 3 # Dönüş formasyonları güçlüdür
                    details.append(f"🕯️ {candle_pattern}")
                elif "SATIŞ" in candle_pattern: # Bearish
                    score -= 3
                    details.append(f"🕯️ {candle_pattern}")

            # MTF Trend
            if "YÜKSELİŞ" in mtf_label and score > 0: score += 1
            elif "DÜŞÜŞ" in mtf_label and score < 0: score -= 1

            # Etiketleme
            risk_label = "NÖTR"
            if score >= 6: risk_label = "GÜÇLÜ AL 🚀" # Eşik yükseldi çünkü çok faktör var
            elif score >= 2: risk_label = "AL 📈"
            elif score <= -6: risk_label = "GÜÇLÜ SAT 🛑"
            elif score <= -2: risk_label = "SAT 📉"

            return {
                "score": score,
                "risk_label": risk_label,
                "rsi": round(rsi, 2),
                "details": details,
                "obv_trend": obv_trend,
                "stop_loss": round(current_price - 2 * atr, 4),
                "take_profit": round(current_price + 3 * atr, 4),
                "divergence": {"label": div_label, "desc": div_desc},
                "mtf": {"label": mtf_label, "desc": mtf_desc},
                "levels": {"support": supp, "resistance": res},
                "whale": whale_signal,      # Yeni Veri
                "candle": candle_pattern    # Yeni Veri
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
        
    @staticmethod
    def _calculate_support_resistance(df: pd.DataFrame):
        """
        Son 50 mumdaki en yüksek ve en düşük seviyeleri (Basit Destek/Direnç) bulur.
        """
        if len(df) < 50:
            return None, None
        
        # Son 50 mumluk pencere (Güncel mum hariç)
        subset = df.iloc[-51:-1]
        resistance = float(subset["High"].max())
        support = float(subset["Low"].min())
        
        return support, resistance

    @staticmethod
    def _check_mean_reversion(current_price, sma50):
        """
        Fiyatın 50 ortalamadan ne kadar uzaklaştığını ölçer.
        Aşırı sapma varsa 'Mean Reversion' (Ortalamaya Dönüş) ihtimali artar.
        """
        if not sma50: return None
        
        diff_pct = (current_price - sma50) / sma50
        
        # %15'ten fazla sapma varsa uyarı (Kripto/BIST için genelleme)
        if diff_pct > 0.15:
            return "Aşırı Pahalı (Düzeltme Riski) ⚠️"
        elif diff_pct < -0.15:
            return "Aşırı Ucuz (Tepki Gelebilir) 🛒"
        return None
    
    @staticmethod
    def _detect_whale_volume(df: pd.DataFrame):
        """
        Son mumdaki hacmi, ortalama hacimle kıyaslar.
        """
        if len(df) < 20: return None
        
        current_vol = df["Volume"].iloc[-1]
        avg_vol = df["Volume"].iloc[-21:-1].mean() # Son mum hariç ortalama
        
        if avg_vol == 0: return None
        
        ratio = current_vol / avg_vol
        
        if ratio >= 3.0:
            return "ULTRA YÜKSEK (Balina 🐋)"
        elif ratio >= 2.0:
            return "YÜKSEK (Dikkat) 🔥"
        return None

    @staticmethod
    def _analyze_candlestick_pattern(row):
        """
        Tek mum formasyonu analizi (Pinbar / Rejection).
        Stop avı ve dönüşleri yakalar.
        """
        open_p = row["Open"]
        close_p = row["Close"]
        high_p = row["High"]
        low_p = row["Low"]
        
        body = abs(close_p - open_p)
        upper_wick = high_p - max(open_p, close_p)
        lower_wick = min(open_p, close_p) - low_p
        
        # Gövde çok küçükse (Doji ihtimali) fitil hassasiyetini artır
        min_body = max(body, 0.0001) 
        
        # Bullish Pinbar (Aşağıdan Reddedilme / Stop Avı)
        # Alt fitil, gövdenin en az 2 katı olmalı ve üst fitilden uzun olmalı
        if lower_wick > (2 * min_body) and lower_wick > (1.5 * upper_wick):
            return "ÇEKİÇ / DİP OLUŞUMU (Bullish Pinbar) 🔨"
            
        # Bearish Pinbar (Yukarıdan Reddedilme / Satış Baskısı)
        # Üst fitil, gövdenin en az 2 katı olmalı
        if upper_wick > (2 * min_body) and upper_wick > (1.5 * lower_wick):
            return "TERS ÇEKİÇ / SATIŞ BASKISI (Bearish Pinbar) 📌"
            
        return None
