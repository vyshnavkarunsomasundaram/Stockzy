from newsapi import NewsApiClient
from dotenv import load_dotenv
import os
from datetime import datetime

# Load API Key
load_dotenv()
news_api_key = os.getenv("NEWS_API_KEY")
print("Loaded API Key:", news_api_key)

# Initialize News API client
api = NewsApiClient(api_key=news_api_key)

# Get today's date in YYYY-MM-DD format
today = datetime.today().strftime('%Y-%m-%d')

# Fetch today's Indian stock market news
all_articles = api.get_everything(
    q='Stock Market News Today in India ',
    language='en',
    page_size=6,
)

print(all_articles)

# Print headlines only
for article in all_articles['articles']:
    print(f"📰 {article['title']}")
