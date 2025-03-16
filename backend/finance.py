import yfinance as yf
import logging

# ✅ Predefined Dictionary of Famous Companies and Their Tickers

def fetch_financial_data(company_name):
    COMPANY_TICKERS = {
        "apple": "AAPL",
        "google": "GOOGL",
        "alphabet": "GOOGL",
        "openai": "MSFT",  # OpenAI is funded by Microsoft, which is publicly traded
        "tesla": "TSLA",
        "tesla, inc.": "TSLA",
        "bmw": "BMW.DE",  # BMW's ticker in German market
        "ford": "F",
        "microsoft": "MSFT",
        "amazon": "AMZN",
        "meta": "META",  # Formerly Facebook
        "nvidia": "NVDA",
        "netflix": "NFLX"
    }

    try:
        # ✅ Convert input company name to lowercase and match with predefined tickers
        company_key = company_name.lower()
        ticker_symbol = COMPANY_TICKERS.get(company_key)

        if not ticker_symbol:
            logging.error(f"❌ No ticker found for {company_name}")
            return {"stock_price": "N/A", "revenue": "N/A"}

        stock = yf.Ticker(ticker_symbol)

        # ✅ Fetch stock price
        stock_price = stock.history(period="1d")
        current_price = round(stock_price["Close"].iloc[-1], 2) if not stock_price.empty else "N/A"

        # ✅ Fetch revenue (try `financials` and `income_stmt`)
        revenue = "N/A"
        if not stock.financials.empty and "Total Revenue" in stock.financials.index:
            revenue = stock.financials.loc["Total Revenue"].iloc[0]
        elif not stock.income_stmt.empty and "Total Revenue" in stock.income_stmt.index:
            revenue = stock.income_stmt.loc["Total Revenue"].iloc[0]

        return {
            "company_name": company_name.capitalize(),
            "stock_ticker": ticker_symbol,
            "stock_price": f"${current_price}" if current_price != "N/A" else "N/A",
            "revenue": f"${revenue:,}" if revenue != "N/A" else "N/A"
        }

    except Exception as e:
        logging.error(f"❌ Error fetching financial data for {company_name}: {str(e)}")
        return {"stock_price": "N/A", "revenue": "N/A"}

# Test the function
print(fetch_financial_data("tesla, Inc."))
