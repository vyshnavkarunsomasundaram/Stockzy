# TODO: FIX NSE DATA FETCHING ISSUES - Blocked for ticker tape and top gainers and losrers
import streamlit as st
import yfinance as yf
import plotly.graph_objs as go
from datetime import datetime, timedelta
import pandas as pd
from news_api_handler import fetch_query_news, fetch_today_news
from llm_handler import summarize_stock_articles, summarize_stock_articles_structured, ask_stocky_bhai_qa
import pandas as pd
import requests
from nsepython import nse_get_top_gainers, nse_get_top_losers, nse_get_index_quote, nse_index, nsefetch
from components import TickerTape

# Page config
st.set_page_config(page_title="Stockzy", page_icon="📈", layout="wide")

# Initialize session states
if 'tracked_stocks' not in st.session_state:
    st.session_state.tracked_stocks = []

if 'portfolio' not in st.session_state:
    st.session_state.portfolio = {}

if 'nse_positions-data' not in st.session_state:
    st.session_state.nse_positions_data = {}

# Time period options
period_options = {
    "1 Day": ("1d", "5m"),
    "1 Month": ("1mo", "1h"),
    "3 Months": ("3mo", "1d"),
    "6 Months": ("6mo", "1d"),
    "1 Year": ("1y", "1d"),
    "3 Years": ("3y", "1wk")
}


@st.cache_data(ttl=300)
def get_nse_positions_data():
    try:
        positions = nsefetch('https://www.nseindia.com/api/equity-stockIndices?index=SECURITIES%20IN%20F%26O')
        df = pd.DataFrame(positions['data'])
    except Exception as e:
        print(f"Error fetching NSE positions: {e}")
        df = pd.DataFrame()  # return empty DataFrame on failure
    return df

st.session_state.nse_positions_data = get_nse_positions_data()

@st.cache_data(ttl=300)  # Cache for 5 minutes = 300 seconds
def get_indices_summary(index_names):
    summaries = []
    for name in index_names:
        try:
            data = nse_get_index_quote(name)
            summaries.append({
                "Index": data["indexName"],
                "Value": data["last"],
                "% Change": data["percChange"]
            })
        except Exception as e:
            summaries.append({
                "Index": name,
                "Value": "Error",
                "% Change": str(e)
            })
    return pd.DataFrame(summaries)


@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_top_nse_gainers_losers(top_k=5):
    """
    Returns:
        tuple: (top_k_gainers, top_k_losers)
        Each is a list of dicts with fields like 'symbol', 'ltp', 'pChange', etc.
    """
    try:
        top_gainers = nse_get_top_gainers()
        if not isinstance(top_gainers, list):
            top_gainers = []
    except Exception as e:
        #st.warning(f"Error fetching top gainers: {e}")
        top_gainers = []

    try:
        top_losers = nse_get_top_losers()
        if not isinstance(top_losers, list):
            top_losers = []
    except Exception as e:
        #st.warning(f"Error fetching top losers: {e}")
        top_losers = []

    return top_gainers[:top_k], top_losers[:top_k]


@st.cache_data(ttl=300)
def get_commodity_prices():
    # Global commodity tickers (USD)
    commodities = {
        "Gold": "GC=F",
        "Silver": "SI=F",
        "Crude Oil": "CL=F",
        "Natural Gas": "NG=F"
    }

    # USD → INR exchange rate ticker
    fx = yf.Ticker("INR=X")
    fx_price = fx.info.get("regularMarketPrice", None)

    data = []
    for name, symbol in commodities.items():
        ticker = yf.Ticker(symbol)
        info = ticker.info

        usd_current = info.get("regularMarketPrice")
        usd_prev = info.get("regularMarketPreviousClose")

        if fx_price and usd_current and usd_prev:
            inr_current = usd_current * fx_price
            inr_prev = usd_prev * fx_price
            change = inr_current - inr_prev
            percent_change = (change / inr_prev) * 100 if inr_prev != 0 else None
        else:
            inr_current = inr_prev = change = percent_change = None

        data.append({
            "Commodity": name,
            "Current Price": round(inr_current, 2) if inr_current else None,
            "Previous Close (₹)": round(inr_prev, 2) if inr_prev else None,
            "Change (₹)": round(change, 2) if change else None,
            "Change (%)": round(percent_change, 2) if percent_change else None
        })

    return pd.DataFrame(data)



def get_stock_price(symbol):
    """Get current stock price"""
    try:
        stock = yf.Ticker(symbol)
        data = stock.history(period="1d")
        if not data.empty:
            return data['Close'].iloc[-1]
        return None
    except:
        return None


def validate_stock(symbol):
    """Validate if stock exists"""
    try:
        stock = yf.Ticker(symbol)
        info = stock.info
        return info and 'symbol' in info
    except:
        return False


def add_stock_to_portfolio(symbol, quantity, avg_price, test=False):
    if test or (portfolio_stock and quantity > 0 and avg_price > 0):
        full_symbol = symbol + ".NS"
        if validate_stock(full_symbol):
            if full_symbol in st.session_state.portfolio:
                # Update existing holding
                existing = st.session_state.portfolio[full_symbol]
                total_qty = existing['quantity'] + quantity
                total_investment = (existing['quantity'] * existing['avg_price']) + (quantity * avg_price)
                new_avg_price = total_investment / total_qty

                st.session_state.portfolio[full_symbol] = {
                    'quantity': total_qty,
                    'avg_price': new_avg_price
                }
                st.success(f"Updated {symbol}: {total_qty} shares at avg ₹{new_avg_price:.2f}")
            else:
                # Add new holding
                st.session_state.portfolio[full_symbol] = {
                    'quantity': quantity,
                    'avg_price': avg_price
                }
                st.success(f"Added {symbol}: {quantity} shares at ₹{avg_price}")
            st.rerun()
        else:
            st.error(f"Stock {symbol} not found on NSE")


# TEST STOCK ADDITION - TODO: REMOVE AFTER DB INTEGRATION
# Add TCS stock only if it's not already in the portfolio
# if "TCS.NS" not in st.session_state.portfolio:
#     add_stock_to_portfolio("TCS", quantity=1, avg_price=3000, test=True)

@st.cache_data(ttl=300)
def get_nse_indices_data(top_k=20):
    """
    Returns the top 20 NSE indices by current value (`last`) with relevant details:
    indexName, indexOrder, indexType, last, percChange.

    Ensures all rows are complete (no NaN values).
    """
    df = nse_index()

    # Select only required columns
    df_cleaned = df[['indexName', 'indexOrder', 'indexType', 'last', 'percChange']].copy()

    # Remove commas and convert to numeric
    df_cleaned['last'] = pd.to_numeric(df_cleaned['last'].astype(str).str.replace(',', ''), errors='coerce')
    df_cleaned['percChange'] = pd.to_numeric(df_cleaned['percChange'].astype(str).str.replace(',', ''), errors='coerce')

    # Drop any rows with NaNs in any column
    df_cleaned.dropna(inplace=True)

    # Sort by 'last' in descending order and return top 20
    df_cleaned = df_cleaned.sort_values(by='last', ascending=False).head(top_k)

    return df_cleaned.reset_index(drop=True)

# Only render ticker tape if positions data has been fetched sucessfully
if len(st.session_state.nse_positions_data)>0:
    TickerTape.ticker_tape_component(st.session_state.nse_positions_data)

# App title
left, right = st.columns([6, 1])  # wider left column for title, narrower right for button

with left:
    st.title("Stockzy")

with right:
    # Inject custom CSS to vertically center content
    st.markdown("""
        <style>
        .vertical-center {
            display: flex;
            align-items: center;
            justify-content: flex-end;
            height: 100%;
        }
        </style>
        <div class="vertical-center">
    """, unsafe_allow_html=True)

    with st.popover("Ask Stocky Bhai", use_container_width=False):
        img_col, inp_col = st.columns([1, 5])
        with img_col:
            st.image("res/images/stocky_bhai.png", use_container_width=True)
        with inp_col:
            question = st.text_input("Ask Stocky Bhai Something...", key="stocky_input")

            if question:
                with st.spinner("Stocky Bhai is thinking..."):
                    response = ask_stocky_bhai_qa(question)
                    st.markdown(f"**🧠 Stocky Bhai Says:**\n\n{response.answer}")

    # Close the div tag
    st.markdown("</div>", unsafe_allow_html=True)

# Initialize active tab in session state
if 'active_tab' not in st.session_state:
    st.session_state.active_tab = "feed"


# Create tabs with callback to track active tab
def set_active_tab():
    # This is a workaround to detect tab changes
    pass


# Tab selection
col1,  col2, col3, col4, col5 = st.columns(5)
with col1:
    if st.button("🌐 Feed", type="primary" if st.session_state.active_tab == "feed" else "secondary",
                 use_container_width=True):
        st.session_state.active_tab = "feed"
        st.rerun()
with col2:
    if st.button("🔍 Research", type="primary" if st.session_state.active_tab == "research" else "secondary",
                 use_container_width=True):
        st.session_state.active_tab = "research"
        st.rerun()
with col3:
    if st.button("📊 Stock Tracker", type="primary" if st.session_state.active_tab == "tracker" else "secondary",
                 use_container_width=True):
        st.session_state.active_tab = "tracker"
        st.rerun()
with col4:
    if st.button("💼 My Portfolio", type="primary" if st.session_state.active_tab == "portfolio" else "secondary",
                 use_container_width=True):
        st.session_state.active_tab = "portfolio"
        st.rerun()
with col5:
    if st.button("💵 Market", type="primary" if st.session_state.active_tab == "market" else "secondary",
                 use_container_width=True):
        st.session_state.active_tab = "market"
        st.rerun()

st.divider()

# Conditional Sidebar based on active tab
with st.sidebar:
    if st.session_state.active_tab == 'feed':
        # INDICES SUMMARY
        st.subheader('📊 Indices Snapshot')
        indices = ['NIFTY 50', 'NIFTY IT', 'INDIA VIX']
        indices_summary = get_indices_summary(indices)

        # Create columns dynamically based on the number of indices
        cols = st.columns(len(indices))

        # Iterate through each index and corresponding column
        for idx, (i, row) in enumerate(indices_summary.iterrows()):
            with cols[idx]:
                with st.container(border=True):
                    # Smaller font for index name
                    st.markdown(f"<div style='font-size: 12px; font-weight: 600'>{row['Index']}</div>",
                                unsafe_allow_html=True)

                    # Determine color based on % change value
                    try:
                        change_value = float(row['% Change'])
                        value_color = 'green' if change_value >= 0 else 'red'
                    except:
                        value_color = 'black'  # fallback if % Change is not a number

                    # Smaller font for value with color
                    st.markdown(
                        f"<div style='font-size: 16px; font-weight: bold; color: {value_color}'>{row['Value']}</div>",
                        unsafe_allow_html=True
                    )

                    # Smaller font for % change
                    st.markdown(
                        f"<div style='color: grey; font-size: 12px'>{row['% Change']}%</div>",
                        unsafe_allow_html=True
                    )


        # TOP GAINERS AND LOSERS
        gainers, losers = get_top_nse_gainers_losers()
        if len(gainers)>0:
            st.subheader("📈 Top Gainers & Losers 📉")
            # Only render if gainers is non empty - otherwise get_top_gainers_losers() has failed
            # Select only the required columns
            columns_to_display = {
                'symbol': 'Stock',
                'open': 'Open',
                'lastPrice': 'Curr.',
                'pChange': '% Change'
            }

            gainers_display = gainers[['symbol', 'open', 'lastPrice', 'pChange']].rename(columns=columns_to_display)
            losers_display = losers[['symbol', 'open', 'lastPrice', 'pChange']].rename(columns=columns_to_display)

            st.markdown("**🔼 Top 5 Gainers**")
            st.dataframe(gainers_display.set_index(gainers_display.columns[0]))

            st.markdown("**🔽 Top 5 Losers**")
            st.dataframe(losers_display.set_index(losers_display.columns[0]))

        # else:
        #     st.warning("Couldn't fetch gainers/losers at the moment.")

        # COMMODITIES SNAPSHOT - TODO: Not getting Indian Prices for now - so feature is revoked
        # st.subheader('🪙 Commodities Snapshot')
        #
        # commodities_data = get_commodity_prices()
        #
        # # Create columns dynamically based on number of commodities
        # cols = st.columns(len(commodities_data))
        #
        # for idx, (_, row) in enumerate(commodities_data.iterrows()):
        #     with cols[idx]:
        #         with st.container(border=True):
        #             # Commodity Name
        #             st.markdown(f"""
        #             <div style='
        #                 font-size: 12px;
        #                 font-weight: 600;
        #                 min-height: 32px;
        #                 line-height: 16px;
        #                 overflow-wrap: break-word;
        #             '>
        #                 {row['Commodity']}
        #             </div>
        #             """, unsafe_allow_html=True)
        #
        #             # Color code based on price change
        #             try:
        #                 change_value = float(row['Change (%)'])
        #                 value_color = 'green' if change_value >= 0 else 'red'
        #             except:
        #                 value_color = 'black'
        #
        #             # Current Price
        #             st.markdown(
        #                 f"<div style='font-size: 16px; font-weight: bold; color: {value_color}'>{row['Current Price']}</div>",
        #                 unsafe_allow_html=True
        #             )
        #
        #             # % Change
        #             st.markdown(
        #                 f"<div style='color: grey; font-size: 12px'>{row['Change (%)']:.2f}%</div>",
        #                 unsafe_allow_html=True
        #             )

    if st.session_state.active_tab == "tracker":
        st.header("📊 Stock Tracker Controls")

        # Add stock section
        st.subheader("Add Indian Stock")
        new_stock = st.text_input("Enter NSE Symbol (e.g., TCS, RELIANCE)", key="tracker_input")
        if st.button("➕ Add to Tracker", type="primary", key="add_tracker"):
            if new_stock:
                symbol = new_stock.upper().strip()
                if symbol:
                    full_symbol = symbol + ".NS"
                    if full_symbol not in st.session_state.tracked_stocks:
                        if validate_stock(full_symbol):
                            st.session_state.tracked_stocks.append(full_symbol)
                            st.success(f"Added {symbol}")
                            st.rerun()
                        else:
                            st.error(f"Stock {symbol} not found on NSE")
                    else:
                        st.warning(f"{symbol} is already being tracked")

        st.divider()

        # Time period selection
        st.subheader("⏰ Time Period")
        selected_period = st.radio("Select duration", list(period_options.keys()), index=2, key="tracker_period")

        st.divider()

        # Remove stocks section
        if st.session_state.tracked_stocks:
            st.subheader("🗑️ Remove Stocks")
            stocks_to_display = [stock.replace('.NS', '') for stock in st.session_state.tracked_stocks]

            for i, (display_name, full_symbol) in enumerate(zip(stocks_to_display, st.session_state.tracked_stocks)):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(display_name)
                with col2:
                    if st.button("❌", key=f"remove_tracker_{i}", help=f"Remove {display_name}"):
                        st.session_state.tracked_stocks.remove(full_symbol)
                        st.rerun()

    elif st.session_state.active_tab == "portfolio":
        st.header("💼 Portfolio Controls")

        # Add stock to portfolio
        st.subheader("Add Stock to Portfolio")
        portfolio_stock = st.text_input("Enter NSE Symbol", key="portfolio_input")
        quantity = st.number_input("Quantity", min_value=1, value=1, key="quantity")
        avg_price = st.number_input("Average Buy Price (₹)", min_value=0.01, value=100.0, step=0.01, key="avg_price")

        if st.button("➕ Add to Portfolio", type="primary", key="add_portfolio"):
            add_stock_to_portfolio(portfolio_stock.upper().strip(), quantity, avg_price)

        st.divider()

        # Portfolio time period
        st.subheader("⏰ Time Period")
        portfolio_period = st.radio("Select duration", list(period_options.keys()), index=2, key="portfolio_period")

        st.divider()

        # Remove from portfolio
        if st.session_state.portfolio:
            st.subheader("🗑️ Manage Holdings")
            for i, (symbol, holding) in enumerate(st.session_state.portfolio.items()):
                stock_name = symbol.replace('.NS', '')
                st.write(f"**{stock_name}**")
                st.write(f"Qty: {holding['quantity']} @ ₹{holding['avg_price']:.2f}")
                if st.button("❌ Remove", key=f"remove_portfolio_{i}"):
                    del st.session_state.portfolio[symbol]
                    st.rerun()
                st.write("---")

# ============= CONTENT BASED ON ACTIVE TAB =============
if st.session_state.active_tab == "feed":
    st.subheader("📢 Today’s Top Stock News")

    news_items = fetch_today_news()
    fallback_image = "res/images/stocky_bhai_news.png"

    if news_items:
        cols = st.columns(4)
        urls = []

        for idx, article in enumerate(news_items):
            with cols[idx % 4]:
                # Get the image URL from the article
                image_url = article.get('urlToImage', '')

                # Check if it's a valid URL (starts with http) and not a known broken format (like .webp)
                if not image_url or 'webp' in image_url or not image_url.startswith("http"):
                    image_url = None

                # Try to use remote image, else fallback to local file and encode to base64
                if image_url:
                    img_tag = f"""<img src="{image_url}" 
                                    alt="News Image"
                                    style="width: 100%; height: 200px; object-fit: cover; border-radius: 8px; margin-bottom: 12px;">"""
                else:
                    # Load and encode local fallback image to base64
                    import base64

                    with open(fallback_image, "rb") as f:
                        encoded = base64.b64encode(f.read()).decode()
                        img_tag = f"""<img src="data:image/png;base64,{encoded}" 
                                        alt="Fallback Image"
                                        style="width: 100%; height: 200px; object-fit: cover; border-radius: 8px; margin-bottom: 12px;">"""

                # Now inject HTML
                st.markdown(f"""
                <div style="background-color: #2d2d2d; border-radius: 12px; padding: 16px; margin-bottom: 20px;">
                    <a href="{article['url']}" target="_blank" style="text-decoration: none;">
                        {img_tag}
                        <div style="color: #FFFFFF; font-size: 18px; font-weight: bold; margin-bottom: 10px;">
                            {article['title']}
                        </div>
                        <div style="color: white; font-size: 14px; margin-bottom: 10px;">
                            {article.get('description', 'No description available')[:100]}...
                        </div>
                        <div style="display: flex; justify-content: space-between; align-items: center; color: #cccccc; font-size: 12px; margin-top: 8px;">
                            <span>{article['publishedAt'][:10]}</span>
                            <span>{article['source']}</span>
                        </div>
                    </a>
                </div>
                """, unsafe_allow_html=True)

if st.session_state.active_tab == "research":
    st.subheader("🔍 Stock Analyzer")

    col1, col2 = st.columns([4, 1])  # Wider input, smaller button
    with col1:
        query = st.text_input("Enter a search topic (e.g., Reliance, Sensex, IT Stocks)",
                              value="", key="news_query", label_visibility='collapsed')

    summarize_triggered = False
    with col2:
        if st.button("Summarize", type='primary'):
            summarize_triggered = True

    if query:
        news_results = fetch_query_news(query, page_size=16)

        if news_results:
            cols = st.columns(4)

            urls = []  # Collect URLs here
            for idx, article in enumerate(news_results):
                urls.append(article['url'])  # Collect URL

                with cols[idx % 4]:
                    st.markdown(f"""
                    <div style="background-color: #2d2d2d; border-radius: 12px; padding: 16px; margin-bottom: 20px;">
                        <a href="{article['url']}" target="_blank" style="text-decoration: none;">
                            <img src="{article.get('urlToImage', '')}" alt="News Image"
                                 style="width: 100%; height: 200px; object-fit: cover; border-radius: 8px; margin-bottom: 12px;">
                            <div style="color: #FFFFFF; font-size: 18px; font-weight: bold; margin-bottom: 10px;">
                                        {article['title']}
                            </div>
                            <div style="color: white; font-size: 14px; margin-bottom: 10px;">
                                {article.get('description', 'No description available')[:100]}...
                            </div>
                            <div style="display: flex; justify-content: space-between; align-items: center; color: #cccccc; font-size: 12px; margin-top: 8px;">
                                <span>{article['publishedAt'][:10]}</span>
                                <span>{article['source']}</span>
                            </div>
                        </a>
                    </div>
                    """, unsafe_allow_html=True)

            if summarize_triggered and urls:
                summary = summarize_stock_articles_structured(query, urls)

                # Summary
                st.markdown("#### 📝 Summary")
                st.markdown(summary.summary)

                # Key Events
                st.markdown("### 📌 Key Events")
                for i, event in enumerate(summary.key_events):
                    # Generate smaller entity chips with dark gray background and blue text linking to Wikipedia
                    entities_html = ' '.join([
                        f'<a href="https://en.wikipedia.org/wiki/{entity.replace(" ", "_")}" target="_blank" '
                        f'style="text-decoration:none; background:#3a3a3a; color:#ffffff; '
                        f'padding:1px 5px; margin:1px; font-size:10px; border-radius:4px; display:inline-block;">{entity}</a>'
                        for entity in event.entities_involved
                    ])

                    # Combine description + implication
                    combined_text = f"{event.description}. {event.implications}"

                    # Final formatted event block
                    event_html = f"""
                    <div style="margin-bottom:1.2rem;">
                        <div style="font-weight:700; font-size:16px;">{i + 1}. {event.title}</div>
                        <div style="margin-top:4px; font-size:14px; line-height:1.4;">{combined_text}</div>
                        <div style="margin-top:6px;">{entities_html}</div>
                    </div>
                    """

                    st.markdown(event_html, unsafe_allow_html=True)

                # Market Impact
                st.markdown("#### 📉 Market Impact")
                st.markdown(summary.market_impact)

                # Suggestion
                color_map = {
                    "Strong Sell": "#ff4d4d",  # Red
                    "Weak Sell": "#ff9900",  # Orange
                    "Hold": "#ffd700",  # Yellow
                    "Weak Buy": "#90ee90",  # Light Green
                    "Strong Buy": "#228B22"  # Dark Green
                }

                suggestion_text = summary.suggestion.suggestion
                suggestion_color = color_map.get(suggestion_text, "#cccccc")

                st.markdown("#### 💡 Investment Suggestion")
                st.markdown(
                    f"<div style='font-size: 24px; font-weight: bold; color: {suggestion_color};'>"
                    f"Recommendation: {suggestion_text}</div>",
                    unsafe_allow_html=True
                )
                st.markdown(f"**Reason:** {summary.suggestion.reason}")

if st.session_state.active_tab == "tracker":
    # Tracker content
    if not st.session_state.tracked_stocks:
        st.info("👈 Add NSE stocks using the sidebar to start tracking.")
        st.markdown("""
        ### Popular Indian Stocks to try:
        - **TCS** - Tata Consultancy Services
        - **RELIANCE** - Reliance Industries
        - **HDFCBANK** - HDFC Bank
        - **INFY** - Infosys
        - **ICICIBANK** - ICICI Bank
        - **BHARTIARTL** - Bharti Airtel
        - **ITC** - ITC Limited
        - **KOTAKBANK** - Kotak Mahindra Bank
        """)
    else:
        # Get the selected period from the correct variable
        selected_period = st.session_state.get('tracker_period', '3 Months')

        st.subheader(f"📈 Tracking {len(st.session_state.tracked_stocks)} Stock(s) - {selected_period}")

        # Display tracker charts
        cols = st.columns(2) if len(st.session_state.tracked_stocks) > 1 else [st.container()]

        for idx, stock_symbol in enumerate(st.session_state.tracked_stocks):
            container = cols[idx % 2] if len(cols) > 1 else cols[0]

            with container:
                stock_name = stock_symbol.replace('.NS', '')

                try:
                    period, interval = period_options[selected_period]
                    stock = yf.Ticker(stock_symbol)
                    data = stock.history(period=period, interval=interval)

                    if data.empty:
                        st.warning(f"📊 No data available for {stock_name}")
                        continue

                    current_price = data['Close'].iloc[-1]
                    prev_price = data['Close'].iloc[0]
                    price_change = current_price - prev_price
                    price_change_pct = (price_change / prev_price) * 100

                    # Stock info header
                    col1, col2, col3 = st.columns([2, 1, 1])
                    with col1:
                        st.markdown(f"### 📈 {stock_name}")
                    with col2:
                        st.metric("Current Price", f"₹{current_price:.2f}")
                    with col3:
                        st.metric("Change", f"₹{price_change:.2f}", f"{price_change_pct:.2f}%")

                    # Create chart
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=data.index,
                        y=data['Close'],
                        mode='lines',
                        name=f'{stock_name} Price',
                        line=dict(
                            color='#1f77b4' if price_change >= 0 else '#d62728',
                            width=2
                        )
                    ))

                    fig.update_layout(
                        title=f"{stock_name} - {selected_period} Performance",
                        xaxis_title="Date/Time",
                        yaxis_title="Price (₹)",
                        height=400,
                        showlegend=False
                    )

                    st.plotly_chart(fig, use_container_width=True)

                except Exception as e:
                    st.error(f"❌ Error loading data for {stock_name}: {str(e)}")

elif st.session_state.active_tab == "portfolio":
    # Portfolio content
    if not st.session_state.portfolio:
        st.info("👈 Add stocks to your portfolio using the sidebar to start tracking your investments.")
        st.markdown("""
        ### How to use Portfolio:
        1. **Add stocks** you own with quantity and average buy price
        2. **View performance** with real-time profit/loss calculations
        3. **Track returns** across different time periods
        4. **Monitor** your total portfolio value and performance
        """)
    else:
        st.subheader(f"💼 My Portfolio - {len(st.session_state.portfolio)} Holdings")

        # Collect current prices and calculate metrics
        portfolio_data = []
        total_invested = 0
        total_current_value = 0

        for symbol, holding in st.session_state.portfolio.items():
            current_price = get_stock_price(symbol)
            if current_price:
                stock_name = symbol.replace('.NS', '')
                invested = holding['quantity'] * holding['avg_price']
                current_value = holding['quantity'] * current_price
                pnl = current_value - invested
                pnl_pct = (pnl / invested) * 100

                portfolio_data.append({
                    'Stock': stock_name,
                    'Quantity': holding['quantity'],
                    'Avg Price': holding['avg_price'],
                    'Current Price': current_price,
                    'Invested': invested,
                    'Current Value': current_value,
                    'P&L': pnl,
                    'P&L %': pnl_pct,
                    'Symbol': symbol
                })

                total_invested += invested
                total_current_value += current_value

        if portfolio_data:
            # Portfolio Summary Cards
            total_pnl = total_current_value - total_invested
            total_pnl_pct = (total_pnl / total_invested) * 100 if total_invested > 0 else 0

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("💰 Total Invested", f"₹{total_invested:,.2f}")
            with col2:
                st.metric("📈 Current Value", f"₹{total_current_value:,.2f}")
            with col3:
                st.metric("💵 Total P&L", f"₹{total_pnl:,.2f}", f"{total_pnl_pct:.2f}%")
            with col4:
                daily_return = 0  # Calculate daily return if needed
                st.metric("📊 Daily Return", f"₹{daily_return:,.2f}")

            st.divider()

            # Individual Stock Performance
            st.subheader("📊 Individual Stock Performance")

            cols = st.columns(2) if len(portfolio_data) > 1 else [st.container()]

            for idx, stock_data in enumerate(portfolio_data):
                container = cols[idx % 2] if len(cols) > 1 else cols[0]

                with container:
                    # Stock header with key metrics
                    st.markdown(f"### 📈 {stock_data['Stock']}")

                    metric_col1, metric_col2, metric_col3 = st.columns(3)
                    with metric_col1:
                        st.metric("Holdings", f"{stock_data['Quantity']} shares")
                    with metric_col2:
                        st.metric("Current Price", f"₹{stock_data['Current Price']:.2f}")
                    with metric_col3:
                        st.metric("P&L", f"₹{stock_data['P&L']:,.2f}", f"{stock_data['P&L %']:.2f}%")

                    # Stock chart
                    try:
                        period, interval = period_options[portfolio_period]
                        stock = yf.Ticker(stock_data['Symbol'])
                        data = stock.history(period=period, interval=interval)

                        if not data.empty:
                            fig = go.Figure()

                            # Add price line
                            fig.add_trace(go.Scatter(
                                x=data.index,
                                y=data['Close'],
                                mode='lines',
                                name='Price',
                                line=dict(color='#1f77b4', width=2)
                            ))

                            # Add average price line
                            fig.add_hline(
                                y=stock_data['Avg Price'],
                                line_dash="dash",
                                line_color="red",
                                annotation_text=f"Avg Buy: ₹{stock_data['Avg Price']:.2f}"
                            )

                            fig.update_layout(
                                title=f"{stock_data['Stock']} vs Your Average Price",
                                xaxis_title="Date/Time",
                                yaxis_title="Price (₹)",
                                height=400,
                                showlegend=False
                            )

                            st.plotly_chart(fig, use_container_width=True)

                    except Exception as e:
                        st.error(f"Error loading chart for {stock_data['Stock']}")

            st.divider()

            # Portfolio Summary Table
            st.subheader("📋 Portfolio Summary Table")

            df = pd.DataFrame(portfolio_data)
            df_display = df[
                ['Stock', 'Quantity', 'Avg Price', 'Current Price', 'Invested', 'Current Value', 'P&L', 'P&L %']].copy()

            # Format currency columns
            df_display['Avg Price'] = df_display['Avg Price'].apply(lambda x: f"₹{x:.2f}")
            df_display['Current Price'] = df_display['Current Price'].apply(lambda x: f"₹{x:.2f}")
            df_display['Invested'] = df_display['Invested'].apply(lambda x: f"₹{x:,.2f}")
            df_display['Current Value'] = df_display['Current Value'].apply(lambda x: f"₹{x:,.2f}")
            df_display['P&L'] = df_display['P&L'].apply(lambda x: f"₹{x:,.2f}")
            df_display['P&L %'] = df_display['P&L %'].apply(lambda x: f"{x:.2f}%")

            st.dataframe(df_display, use_container_width=True, hide_index=True)

            # Overall Portfolio Stats
            st.subheader("📊 Overall Portfolio Statistics")

            stats_col1, stats_col2 = st.columns(2)

            with stats_col1:
                st.markdown("**Investment Summary:**")
                st.write(f"• Total Stocks: {len(portfolio_data)}")
                st.write(f"• Total Invested: ₹{total_invested:,.2f}")
                st.write(f"• Current Portfolio Value: ₹{total_current_value:,.2f}")

            with stats_col2:
                st.markdown("**Performance Summary:**")
                st.write(f"• Total P&L: ₹{total_pnl:,.2f}")
                st.write(f"• Total Return: {total_pnl_pct:.2f}%")
                best_performer = max(portfolio_data, key=lambda x: x['P&L %'])
                worst_performer = min(portfolio_data, key=lambda x: x['P&L %'])
                st.write(f"• Best Performer: {best_performer['Stock']} ({best_performer['P&L %']:.2f}%)")
                st.write(f"• Worst Performer: {worst_performer['Stock']} ({worst_performer['P&L %']:.2f}%)")

if st.session_state.active_tab == "market":
    def get_gradient_color(perc):
        clamp = 5
        perc = max(-clamp, min(clamp, perc))  # Clamp between -5% and +5%
        if perc >= 0:
            green_intensity = int(255 * min(1, perc / clamp))
            return f"rgb({255 - green_intensity}, 255, {255 - green_intensity})"
        else:
            red_intensity = int(255 * min(1, -perc / clamp))
            return f"rgb(255, {255 - red_intensity}, {255 - red_intensity})"

    st.title('📊 Indices Heatmap')
    df = get_nse_indices_data()

    INDEX_CARDS_PER_ROW = 5
    # Display grid
    cols = st.columns(INDEX_CARDS_PER_ROW)  # 3 cards per row
    for i, row in df.iterrows():
        with cols[i % INDEX_CARDS_PER_ROW]:
            bg_color = get_gradient_color(row['percChange'])
            st.markdown(f"""
                <div style="border: 1px solid #ccc; border-radius: 10px; padding: 10px; margin: 5px;
                            background: {bg_color}; color: #000;">
                    <h5 style="margin-bottom: 2px;">{row['indexName']}</h5>
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div style="font-size: 18px;"><b>{row['last']}</b></div>
                        <div style="font-size: 18px;"><b>{row['percChange']}%</b></div>
                    </div>
                </div>
            """, unsafe_allow_html=True)


# Footer
st.divider()
st.markdown("""
<div style='text-align: center; color: #666; font-size: 0.8em;'>
    📊 Data provided by Yahoo Finance | 🇮🇳 NSE stocks only | 💼 Portfolio tracking with real-time P&L
</div>
""", unsafe_allow_html=True)
