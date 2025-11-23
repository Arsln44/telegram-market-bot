# services/market_data.py
import yfinance as yf

class MarketDataService:
    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        """Sembolü normalize eder (.IS kontrolü)."""
        clean = symbol.upper().strip()
        # Eğer kullanıcı BTC-USD veya başka global sembol verdi ise dokunma
        if "." in clean or "-" in clean:
            return clean
        # Türkiye piyasası için .IS ekle
        if len(clean) <= 5:
            return f"{clean}.IS"
        return clean

    @staticmethod
    def get_stock_price(symbol: str):
        """
        Anlık (son kapanış veya intraday) fiyat çeker.
        Basit: history ile son kapanışı döndürür.
        """
        try:
            search_symbol = MarketDataService._normalize_symbol(symbol)
            ticker = yf.Ticker(search_symbol)

            # Önce fast_info deneyebiliriz (daha hızlı) ama garanti için history
            data = ticker.history(period="1d", interval="1m")
            if data.empty:
                # fallback: 5 günlük kapanışlardan sonunu al
                data = ticker.history(period="5d")
                if data.empty:
                    return None

            # Son fiyat (en son close/last)
            if "Close" in data.columns:
                last_price = data["Close"].iloc[-1]
            else:
                return None

            # Currency bilgisi .info'dan gelmeye çalışılır; yoksa None
            currency = None
            try:
                currency = ticker.info.get("currency")  # bazen hata çıkartır
            except Exception:
                currency = None

            return {
                "symbol": symbol.upper().strip(),
                "price": round(float(last_price), 2),
                "currency": currency or "Unknown"
            }

        except Exception as e:
            # TODO: logging kullan
            print(f"[MarketDataService.get_stock_price] Hata: {e}")
            return None

    @staticmethod
    def get_historical_data(symbol: str, period="1mo", interval="1d"):
        """
        Geçmiş veri çek. period ve interval parametreleri esnek.
        Örn: period="1y", interval="1d" veya period="30d", interval="60m"
        """
        try:
            search_symbol = MarketDataService._normalize_symbol(symbol)
            ticker = yf.Ticker(search_symbol)

            data = ticker.history(period=period, interval=interval)
            if data.empty:
                return None

            # Basit validasyon: Close kolonu yoksa hata
            if "Close" not in data.columns:
                return None

            return data

        except Exception as e:
            print(f"[MarketDataService.get_historical_data] Hata: {e}")
            return None
        
    @staticmethod
    def get_macro_interval(micro_interval: str) -> str:
        """
        Seçilen zaman dilimine göre bir üst (trend) zaman dilimini belirler.
        MTF Analizi için kritiktir.
        """
        mapping = {
            "1m": "15m",
            "5m": "15m",
            "15m": "1h",
            "30m": "4h",
            "60m": "1d",
            "1h": "1d",
            "4h": "1wk",
            "1d": "1wk",
            "1wk": "1mo"
        }
        return mapping.get(micro_interval, "1d")
