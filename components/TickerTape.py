import streamlit as st
import pandas as pd


def ticker_tape_component(df: pd.DataFrame):
    """
    Renders a ticker tape in Streamlit from a DataFrame with columns: 'symbol', 'lastPrice', 'pChange'
    """
    ticker_items = []
    print(df[:10])
    for _, stock in df.iterrows():
        price = f"₹{float(stock['lastPrice']):.2f}"
        pchange = f"{'+' if stock['pChange'] >= 0 else ''}{stock['pChange']:.2f}%"
        color_class = "green" if stock['pChange'] >= 0 else "red"

        ticker_items.append(
            f'<span class="{color_class}">{stock["symbol"]} {price} {pchange}</span>'
        )

    ticker_text = " • ".join(ticker_items)
    full_ticker = (ticker_text + " • ") * 4  # Duplicate for infinite feel

    html = f"""
    <style>
        .ticker-tape {{
            width: 100%;
            height: 40px;
            background: #000000;
            border-top: 2px solid #FFD700;
            border-bottom: 2px solid #FFD700;
            overflow: hidden;
            position: relative;
            display: flex;
            align-items: center;
        }}

        .red {{
            color: #FF4C4C;
        }}

        .green {{
            color: #00FF00;
        }}

        .ticker-content {{
            white-space: nowrap;
            animation: scroll-left 1200s linear infinite;
            font-family: 'Arial', sans-serif;
            font-size: 14px;
            font-weight: bold;
            color: #FFD700;
            letter-spacing: 1px;
            line-height: 40px;
        }}

        @keyframes scroll-left {{
            0% {{ transform: translateX(0%); }}
            100% {{ transform: translateX(-100%); }}
        }}

        .ticker-tape:hover .ticker-content {{
            animation-play-state: paused;
        }}
    </style>

    <div class="ticker-tape">
        <div class="ticker-content">
            {full_ticker}
        </div>
    </div>
    """

    st.markdown(html, unsafe_allow_html=True)


# Sample usage
if __name__ == "__main__":
    st.set_page_config(page_title="Ticker Tape Component", layout="wide")

    # Sample stock data
    data = [
        {"symbol": "MANAPPURAM", "lastPrice": 279.8, "pChange": 3.32},
        {"symbol": "MAXHEALTH", "lastPrice": 1236.5, "pChange": 2.85},
        {"symbol": "ICICIGI", "lastPrice": 1847.2, "pChange": -1.24},
        {"symbol": "RELIANCE", "lastPrice": 2456.3, "pChange": 1.67},
        {"symbol": "TCS", "lastPrice": 3789.45, "pChange": -0.89},
        {"symbol": "INFY", "lastPrice": 1542.8, "pChange": 2.14},
        {"symbol": "HDFCBANK", "lastPrice": 1678.9, "pChange": 0.76},
        {"symbol": "ICICIBANK", "lastPrice": 1234.5, "pChange": -0.45}
    ]

    df = pd.DataFrame(data)
    ticker_tape_component(df)
    st.markdown("<br>", unsafe_allow_html=True)
    st.write("📈 **Stock Ticker Tape** - Symbol • Price • Change% - Hover to pause scrolling")
