from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.exceptions import OutputParserException
from langchain_community.document_loaders import WebBaseLoader
import os
import re
import logging
import requests
import json
from bs4 import BeautifulSoup, SoupStrainer
import tweepy
from textblob import TextBlob
import yfinance as yf

logging.basicConfig(level=logging.INFO)

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Load API keys
groq_api_key = os.getenv("GROQ_API_KEY")
newsapi_key = os.getenv("NEWSAPI_KEY")
twitter_api_key = os.getenv("TWITTER_API_KEY")
twitter_api_secret_key = os.getenv("TWITTER_API_SECRET_KEY")
twitter_access_token = os.getenv("TWITTER_ACCESS_TOKEN")
twitter_access_token_secret = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")

# Validate API keys
if not all([groq_api_key, newsapi_key, twitter_api_key, twitter_api_secret_key, twitter_access_token, twitter_access_token_secret]):
    raise ValueError("Missing API keys in environment variables.")

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic request model
class CompanyRequest(BaseModel):
    company_name: str

# Language model handler
class Chain:
    def __init__(self):
        self.llm = ChatGroq(
            temperature=0,
            groq_api_key=groq_api_key,
            model_name="llama-3.3-70b-versatile"
        )
    
    def extract_compdata(self, cleaned_text):
        prompt_extract = PromptTemplate.from_template(
        """
        ### SCRAPED TEXT FROM WEBSITE
        {page_data1}
        
        ### INSTRUCTION:
        Extract company details from the scraped text , if any information is null search it yourself and provide relevant information and return a JSON object with:
        - company_name
        - website
        - headquarters
        - industry
        - employee_count
        - ceo
        - founded
        - competitors
        
        **Ensure the response is a valid JSON object, without any extra text or formatting like Markdown.**
        """
        )
        chain = prompt_extract | self.llm
        response = chain.invoke(input={'page_data1': cleaned_text})

        logging.info(f"LLM Response: {response}")  # Debugging
        
        try:
            return JsonOutputParser().parse(response.content)
        except OutputParserException:
            raise HTTPException(status_code=400, detail="Unable to parse company data.")

    def fetch_news(self, company_name):
        url = f"https://newsapi.org/v2/everything?q={company_name}&apiKey={newsapi_key}"
        response = requests.get(url)

        if response.status_code == 200:
            news_data = response.json()
            articles = news_data.get("articles", [])[:5]
            return [{"headline": a["title"], "source": a["source"]["name"], "date": a["publishedAt"]} for a in articles]

        return []


def get_twitter_client():
    try:
        # ✅ Use Twitter API v2 Client (Preferred for recent tweets)
        client = tweepy.Client(
            bearer_token=os.getenv("TWITTER_BEARER_TOKEN"),
            consumer_key=os.getenv("TWITTER_API_KEY"),
            consumer_secret=os.getenv("TWITTER_API_SECRET_KEY"),
            access_token=os.getenv("TWITTER_ACCESS_TOKEN"),
            access_token_secret=os.getenv("TWITTER_ACCESS_TOKEN_SECRET"),
            wait_on_rate_limit=True
        )
        logging.info("✅ Successfully authenticated Twitter API client")
        return client
    except Exception as e:
        logging.error(f"❌ Twitter API Authentication Failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Error authenticating with Twitter API.")

# Fetch Twitter sentiment
def fetch_twitter_sentiment(company_name):
    client = get_twitter_client()

    try:
        # ✅ Fetch recent tweets related to the company (max 10)
        response = client.search_recent_tweets(
            query=company_name, 
            tweet_fields=["text", "created_at"], 
            max_results=10
        )

        if not response.data:
            logging.warning(f"⚠️ No tweets found for {company_name}")
            return {"sentiment_scores": {"positive": 0, "negative": 0, "neutral": 0}, "tweets": []}

        tweet_texts = [tweet.text for tweet in response.data]
        sentiments = []
        tweet_data = []

        for text in tweet_texts:
            blob = TextBlob(text)
            sentiment = (
                "positive" if blob.sentiment.polarity > 0 
                else "negative" if blob.sentiment.polarity < 0 
                else "neutral"
            )
            sentiments.append(sentiment)
            tweet_data.append({"text": text, "sentiment": sentiment})  # ✅ Store each tweet with its sentiment

        sentiment_score = {
            "positive": sentiments.count("positive"),
            "negative": sentiments.count("negative"),
            "neutral": sentiments.count("neutral")
        }

        logging.info(f"✅ Twitter Sentiment Analysis: {sentiment_score}")

        return {
            "sentiment_scores": sentiment_score,
            "tweets": tweet_data  # ✅ Return tweet texts with their sentiment
        }

    except tweepy.TweepyException as e:
        logging.error(f"❌ Error fetching tweets: {e}")
        raise HTTPException(status_code=400, detail=f"Error fetching tweets: {str(e)}")
    
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
            "revenue": f"${revenue:,}" if revenue != "N/A" else "N/A",
        }

    except Exception as e:
        logging.error(f"❌ Error fetching financial data for {company_name}: {str(e)}")
        return {"stock_price": "N/A", "revenue": "N/A"}
    
# Clean extracted text
def clean_text(text):
    text = re.sub(r'<[^>]*?>', '', text)
    text = re.sub(r'http[s]?://[^\s]+', '', text)
    text = re.sub(r'[^a-zA-Z0-9 ]', '', text)
    text = re.sub(r'\s{2,}', ' ', text).strip()
    return text

chain = Chain()

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.post("/get_compdata")
def process_company(data: CompanyRequest):
    company_name = data.company_name
    search_url = f"https://en.wikipedia.org/wiki/{company_name}"
    
    # Validate Wikipedia page
    wiki_response = requests.get(search_url)
    if wiki_response.status_code != 200:
        raise HTTPException(status_code=404, detail="Wikipedia page not found")

    # Load data
    loader = WebBaseLoader(search_url)
    scraped_docs = loader.load()
    
    scraped_text = " ".join([doc.page_content for doc in scraped_docs]) if scraped_docs else ""

    if not scraped_text.strip():
        raise HTTPException(status_code=404, detail="Infobox not found on Wikipedia page")

    # Clean extracted text
    cleaned_text = clean_text(scraped_text)
    cleaned_text_snippet = cleaned_text[:len(cleaned_text) // 10]  # Extract 10% of content for efficiency

    logging.info(f"Extracted Text Snippet: {cleaned_text_snippet[:500]}")  # Log first 500 chars

    # ✅ Extract structured company details
    try:
        company_details = chain.extract_compdata(cleaned_text_snippet)
    except HTTPException as e:
        logging.error(f"Company Data Extraction Failed: {e.detail}")
        raise HTTPException(status_code=400, detail="Failed to extract company details.")

    # ✅ Fetch additional data
    news = chain.fetch_news(company_name)
    twitter_data = fetch_twitter_sentiment(company_name)  # ✅ Get tweets + sentiment scores
    financial_data = fetch_financial_data(company_name)  # ✅ Get stock, revenue, funding rounds

    # ✅ Ensure FastAPI returns a **clean JSON response**
    response_json = {
        "company_name": company_details.get("company_name", company_name),
        "overview": {
            "headquarters": company_details.get("headquarters", "N/A"),
            "website": company_details.get("website", "N/A"),
            "industry": company_details.get("industry", "N/A"),
            "ceo": company_details.get("ceo", "N/A"),
            "founded": company_details.get("founded", "N/A"),
            "employees": company_details.get("employee_count", "N/A"),
            "competitors": company_details.get("competitors", "N/A")
        },
        "recent_news": news,
        "twitter_sentiment": {
            "scores": twitter_data["sentiment_scores"],  # ✅ Sentiment counts
            "tweets": twitter_data["tweets"]  # ✅ Actual tweets
        },
        "financials": {
            "stock_price": financial_data["stock_price"],
            "revenue": financial_data["revenue"]
        }
    }

    logging.info(f"Final API Response: {json.dumps(response_json, indent=4)}")  # Debugging

    return response_json

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
