import streamlit as st
import requests

# FastAPI backend URL
API_URL = "http://127.0.0.1:8000/get_compdata"

st.set_page_config(page_title="Company Research Assistant", layout="wide")
st.title("AI-Powered Company Research Assistant")

# Input field for company name
company_name = st.text_input("Enter Company Name:")

if st.button("Search"):
    if company_name.strip():
        with st.spinner("Fetching data..."):
            response = requests.post(API_URL, json={"company_name": company_name})
            
            if response.status_code == 200:
                data = response.json()
                
                # Display Overview
                st.subheader(f"📌 Company details : {data['company_name']}")
                st.write(f"**Headquarters:** {data['overview']['headquarters']}")
                st.write(f"**Website:** {data['overview']['website']}")
                st.write(f"**Industry:** {data['overview']['industry']}")
                st.write(f"**CEO:** {data['overview']['ceo']}")
                st.write(f"**Founded:** {data['overview']['founded']}")
                st.write(f"**Employees:** {data['overview']['employees']}")
                st.write(f"**Competitors:** {data['overview']['competitors']}")
                
                # Display Recent News
                st.subheader("📰 Recent News")
                for news in data.get("recent_news", []):
                    st.write(f"- **{news['headline']}** ({news['source']}, {news['date']})")
                
                st.subheader("💰 Financials about the company")
                st.write(f"**Stock Price:** ${data['financials']['stock_price']}")
                st.write(f"**Revenue:** ${data['financials']['revenue']}")

                # Display Twitter Sentiment
                st.subheader("📊 Twitter Sentiment Analysis")
                sentiment = data.get("twitter_sentiment", {}).get("scores", {})
                st.write(f"**Positive Tweets:** {sentiment.get('positive', 0)}")
                st.write(f"**Negative Tweets:** {sentiment.get('negative', 0)}")
                st.write(f"**Neutral Tweets:** {sentiment.get('neutral', 0)}")

                # ✅ Show Actual Tweets with Sentiment
                tweets = data.get("twitter_sentiment", {}).get("tweets", [])
                if tweets:
                    st.subheader("🐦 Recent Tweets related to the company")
                    for tweet in tweets:
                        sentiment_emoji = "😊" if tweet["sentiment"] == "positive" else "😡" if tweet["sentiment"] == "negative" else "😐"
                        st.write(f"{sentiment_emoji} **{tweet['sentiment'].capitalize()}**: {tweet['text']}")
                else:
                    st.write("No recent tweets found.")
            else:
                st.error("Failed to fetch data. Please try again later.")
    else:
        st.warning("Please enter a valid company name.")
