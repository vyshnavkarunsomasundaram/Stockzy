import requests
from bs4 import BeautifulSoup


def scrape_article(url: str) -> str:
    """Recursively extract the main text content from a news article URL."""
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers, timeout=10)

    if response.status_code != 200:
        raise Exception(f"Failed to fetch article. Status code: {response.status_code}")

    soup = BeautifulSoup(response.text, 'html.parser')

    # Try heuristically likely content containers
    candidates = soup.find_all(['article', 'main', 'div'], recursive=True)

    best_text = ''
    max_len = 0

    for candidate in candidates:
        paragraphs = candidate.find_all('p')
        content = ' '.join(p.get_text(strip=True) for p in paragraphs)
        if len(content) > max_len:
            best_text = content
            max_len = len(content)

        if max_len > 10000:  # Early exit if we already have rich content
            break

    # Fallback: if no good candidate found, get all <p> tags from entire page
    if len(best_text.strip()) < 10000:
        paragraphs = soup.find_all('p')
        best_text = ' '.join(p.get_text(strip=True) for p in paragraphs)

    return best_text.strip()

def scrape_multiple_articles(urls: list[str]) -> str:
    """Scrape and concatenate multiple news articles from a list of URLs."""
    combined_result = []

    for url in urls:
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code != 200:
                print(f"Skipping {url} - failed to fetch.")
                continue

            soup = BeautifulSoup(response.text, 'html.parser')

            # Extract title
            title = soup.title.string.strip() if soup.title else "Untitled Article"

            # Extract content using existing logic
            candidates = soup.find_all(['article', 'main', 'div'], recursive=True)

            best_text = ''
            max_len = 0

            for candidate in candidates:
                paragraphs = candidate.find_all('p')
                content = ' '.join(p.get_text(strip=True) for p in paragraphs)
                if len(content) > max_len:
                    best_text = content
                    max_len = len(content)

                if max_len > 10000:
                    break

            if len(best_text.strip()) < 1000:
                paragraphs = soup.find_all('p')
                best_text = ' '.join(p.get_text(strip=True) for p in paragraphs)

            combined_result.append(f"{title} - {best_text.strip()}")

        except Exception as e:
            print(f"Error processing {url}: {e}")
            continue

    return "\n\n".join(combined_result)

#article = scrape_article('https://www.thehindubusinessline.com/portfolio/tcs-infosys-wipro-hcltech-why-the-it-stocks-correction-gathers-no-moss/article69669369.ece')
#print(article)