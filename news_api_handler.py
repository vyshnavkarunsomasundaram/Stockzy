# news_api_handler.py
import os
from datetime import datetime
from dotenv import load_dotenv
from newsapi import NewsApiClient

# Load environment variables from .env file
load_dotenv()

# Initialize the News API client
_api_key = os.getenv("NEWS_API_KEY")
if not _api_key:
    raise EnvironmentError("NEWS_API_KEY not found in .env file")

_news_api = NewsApiClient(api_key=_api_key)


def fetch_query_news(query: str, page_size: int = 10) -> list:
    """
    Fetch the most relevant and unique news articles for a given query using NewsAPI.

    Deduplicates based on the first 20 characters of the article title.

    Parameters:
    - query (str): Search keyword.
    - page_size (int): Number of articles to fetch. Max 100.

    Returns:
    - List of dictionaries containing 'title', 'description', 'url', 'publishedAt', 'urlToImage', and 'source'
    """
    # Append 'STOCKS' to search handler - TODO: Remove later
    query += ' Stocks'
    try:
        response = _news_api.get_everything(
            q=query,
            language='en',
            sort_by='relevancy',
            page_size=page_size,
        )
        articles = response.get('articles', [])

        seen_title_prefixes = set()
        unique_articles = []

        for article in articles:
            title = article.get('title', '').strip()
            title_key = title[:20].lower()  # First 20 characters, lowercased

            if title and title_key not in seen_title_prefixes:
                seen_title_prefixes.add(title_key)
                unique_articles.append({
                    'title': title,
                    'description': article.get('description', 'No Description'),
                    'url': article.get('url', ''),
                    'publishedAt': article.get('publishedAt', ''),
                    'urlToImage': article.get('urlToImage', ''),
                    'source': article.get('source', {}).get('name', 'Unknown'),
                })

        return unique_articles[:5]

    except Exception as e:
        print(f"[ERROR] Failed to fetch news: {e}")
        return []

def fetch_today_news(page_size: int = 8) -> list:
    """
    Fetch today's top Indian stock market news articles using NewsAPI.

    Deduplicates based on the first 20 characters of the article title.

    Parameters:
    - page_size (int): Number of articles to fetch. Max 100.

    Returns:
    - List of dictionaries containing 'title', 'description', 'url', 'publishedAt', 'urlToImage', and 'source'
    """
    today = datetime.now().strftime("%Y-%m-%d")

    try:
        response = _news_api.get_everything(
            q="Indian Stock Market OR Sensex OR Bombay Stock Exchange OR BSE OR NSE OR Indian Investments",
            language="en",
            sort_by="relevancy",
            page_size=page_size,
        )

        articles = response.get("articles", [])

        seen_title_prefixes = set()
        unique_articles = []

        for article in articles:
            title = article.get("title", "").strip()
            title_key = title[:20].lower()

            if title and title_key not in seen_title_prefixes:
                seen_title_prefixes.add(title_key)
                unique_articles.append({
                    "title": title,
                    "description": article.get("description", "No Description"),
                    "url": article.get("url", ""),
                    "publishedAt": article.get("publishedAt", ""),
                    "urlToImage": article.get("urlToImage", ""),
                    "source": article.get("source", {}).get("name", "Unknown"),
                })

        return unique_articles

    except Exception as e:
        print(f"[ERROR] Failed to fetch today’s news: {e}")
        return []


print(fetch_today_news())