# services/chart_service.py
import io
import mplfinance as mpf
import pandas as pd

class ChartService:
    @staticmethod
    def create_chart(df: pd.DataFrame, symbol: str, support=None, resistance=None):
        """
        Verilen DF'den mum grafiği oluşturur ve ByteIO (resim dosyası) olarak döner.
        """
        try:
            # Son 60 mumu al (Grafik çok sıkışık olmasın)
            plot_df = df.iloc[-60:].copy()
            
            # --- Stil Ayarları ---
            # Yahoo tarzı, koyu tema
            mc = mpf.make_marketcolors(up='#00ff00', down='#ff0000', inherit=True)
            s = mpf.make_mpf_style(base_mpf_style='nightclouds', marketcolors=mc)
            
            # --- Ekstra Çizgiler (AddPlots) ---
            add_plots = []
            
            # 1. SMA 50 (Sarı Çizgi)
            # plot_df uzunluğunda bir SMA serisi hesapla veya var olanı kes
            if len(df) >= 50:
                sma50 = df['Close'].rolling(window=50).mean().iloc[-60:]
                add_plots.append(
                    mpf.make_addplot(sma50, color='yellow', width=1.5, label='SMA 50')
                )
            
            # 2. Destek / Direnç Çizgileri (Yatay)
            # Hline (Horizontal Line) mantığı mplfinance'da hlines parametresi ile verilir
            h_lines = []
            h_colors = []
            
            if support:
                h_lines.append(support)
                h_colors.append('cyan') # Destek Mavi
            
            if resistance:
                h_lines.append(resistance)
                h_colors.append('orange') # Direnç Turuncu

            # --- Çizim İşlemi ---
            buf = io.BytesIO()
            
            mpf.plot(
                plot_df,
                type='candle',
                style=s,
                title=f"\n{symbol} Analiz Grafigi",
                ylabel='Fiyat',
                ylabel_lower='Hacim',
                volume=True,
                addplot=add_plots,
                hlines=dict(hlines=h_lines, colors=h_colors, linestyle='-.', linewidths=1.0),
                savefig=dict(fname=buf, dpi=100, bbox_inches='tight'),
                figscale=1.2
            )
            
            buf.seek(0)
            return buf
            
        except Exception as e:
            print(f"[ChartService] Grafik Hatası: {e}")
            return None