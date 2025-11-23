import yfinance as yf

class MarketDataService:
    @staticmethod
    def get_stock_price(symbol: str):
        """
        Verilen sembol için anlık fiyatı getirir.
        Otomatik olarak .IS (Borsa İstanbul) uzantısı kontrolü yapar.
        """
        try:
            # Kullanıcı 'THYAO' yazarsa biz onu 'THYAO.IS' yaparız.
            # Eğer zaten '.IS' veya kripto (BTC-USD) girdiyse dokunmayız.
            clean_symbol = symbol.upper().strip()
            
            # Basit bir mantık: Eğer içinde nokta veya tire yoksa ve 
            # 5 karakterden kısaysa muhtemelen BIST hissesidir.
            if "." not in clean_symbol and "-" not in clean_symbol:
                search_symbol = f"{clean_symbol}.IS"
            else:
                search_symbol = clean_symbol

            # Yfinance üzerinden veriyi çek
            ticker = yf.Ticker(search_symbol)
            
            # Son 1 günlük veriyi al
            # fast_info bazen daha hızlıdır ama history daha güvenilirdir
            data = ticker.history(period="1d")

            if data.empty:
                return None
            
            # Son kapanış fiyatını al
            last_price = data['Close'].iloc[-1]
            
            return {
                "symbol": clean_symbol,
                "price": round(last_price, 2),
                "currency": ticker.info.get('currency', 'TRY')
            }

        except Exception as e:
            print(f"Hata oluştu ({symbol}): {e}")
            return None