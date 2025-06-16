from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
from scrapper import scrape_multiple_articles
from typing import List, Generator, Optional
from pydantic import BaseModel, Field, HttpUrl, ValidationError
import os
from dotenv import load_dotenv
import json
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory


load_dotenv()
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

chat = ChatGroq(api_key=GROQ_API_KEY, model_name="meta-llama/llama-4-scout-17b-16e-instruct")
chat_streaming = ChatGroq(api_key=GROQ_API_KEY, model_name="meta-llama/llama-4-scout-17b-16e-instruct", streaming=True)
memory = ConversationBufferMemory(return_messages=True)

qa_chain = ConversationChain(
    llm=chat,
    memory=memory,
    verbose=True,
)

class InvestmentSuggestion(BaseModel):
    """Investment recommendation with structured level and justification."""
    suggestion: str = Field(
        description="One of: Strong Buy, Weak Buy, Hold, Weak Sell, Strong Sell"
    )
    reason: str = Field(
        description="Detailed explanation justifying the investment recommendation"
    )


class KeyEvent(BaseModel):
    title: str = Field(description="A short headline describing the event")
    date: str = Field(description="The date of the event in a human-readable format")
    description: str = Field(description="A detailed explanation of what happened")
    entities_involved: List[str] = Field(description="List of key entities involved in the event")
    implications: str = Field(description="What impact or consequence this event has on the stock or market sentiment")

class StockAnalysis(BaseModel):
    stock_symbol: str
    summary:  str = Field(description="A brief summary of the news articles")
    key_events: List[KeyEvent]  # ⬅️ Use structured type instead of List[str]
    market_impact: str= Field(description="A brief one or two liner on the main market impact of the news")
    suggestion: InvestmentSuggestion


def summarize_stock_articles_structured(stock_name: str, urls: List[str]) -> StockAnalysis:
    """Scrape and analyze a list of article URLs using Groq, returning enhanced structured output."""
    articles_text = scrape_multiple_articles(urls)

    if not articles_text or len(articles_text.strip()) < 100:
        return StockAnalysis(
            stock_symbol=stock_name,
            summary="No valid content found in the provided URLs.",
            key_events=[],
            market_impact="Neutral impact due to lack of sufficient information.",
            suggestion=InvestmentSuggestion(
                suggestion="Hold",
                reason="Not enough data to support a confident decision."
            )
        )

    structured_llm = chat.with_structured_output(StockAnalysis)

    prompt = (
        f"You are a financial analyst specializing in the stock market. "
        f"Analyze the following news articles related to the stock **{stock_name}**. "
        f"Return a structured response with:\n"
        f"- A **concise summary** of the articles\n"
        f"- A list of **key events**: these must be descriptive and include details such as timelines, entities involved, and consequences\n"
        f"- A detailed **market impact** assessment: not just a label (positive/negative/mixed/neutral), but also explain *why* this impact is expected\n"
        f"- An **investment suggestion** as a JSON object with:\n"
        f"  - `suggestion`: one of [Strong Buy, Weak Buy, Hold, Weak Sell, Strong Sell]\n"
        f"  - `reason`: justification for this suggestion based on the article content\n\n"
        f"Article content:\n{articles_text}"
    )

    try:
        response = structured_llm.invoke([HumanMessage(content=prompt)])
        response.stock_symbol = stock_name
        return response
    except Exception as e:
        return StockAnalysis(
            stock_symbol=stock_name,
            summary=f"Error occurred during analysis: {str(e)}",
            key_events=[],
            market_impact="Neutral due to failure in processing.",
            suggestion=InvestmentSuggestion(
                suggestion="Hold",
                reason="Analysis failed due to internal error."
            )
        )

def summarize_stock_articles(stock_name, urls: list[str]) -> str:
    """Scrape and summarize a list of article URLs using Groq + Mixtral."""
    articles_text = scrape_multiple_articles(urls)

    if not articles_text or len(articles_text.strip()) < 100:
        return "No valid content found in the provided URLs."

    prompt = (
        f"You are a financial analyst specializing in the stock market. "
        f"Analyze the following news articles related to the stock **{stock_name}**. "
        f"Provide a concise summary highlighting how {stock_name} is impacted, including any relevant trends, events, or market sentiment.\n\n"
        f"{articles_text}"
    )

    response = chat.invoke([HumanMessage(content=prompt)])
    return response.content.strip()


class StockyBhaiAnswer(BaseModel):
    """Structured response from Stocky Bhai to a finance question."""

    answer: str = Field(
        description="Direct and confident answer in the style of Rocky Bhai (no narration or accent), focusing on clear, actionable advice for the Indian stock market."
    )

    youtube_links: Optional[List[HttpUrl]] = Field(
        default_factory=list,
        description="Optional list of **relevant and Indian stock market-focused** YouTube video links. Include only if it adds strong value."
    )

def ask_stocky_bhai_qa(query: str) -> StockyBhaiAnswer:
    prompt = (
        "You are Stocky Bhai — You are a roleplay version of KGF's Rocky Bhai. You are like his cousin brother with the same personality. "
        "You speak with the weight of experience. Every word matters. No soft talk, no sugarcoating. "
        "You only focus on the Indian stock market: NSE, BSE, SEBI rules, IPOs, Indian mutual funds, and real-world investing.\n\n"

        "When answering:\n"
        "- Speak like a man who’s already won — confident, blunt, and fearless.\n"
        "- Slightly detailed if needed, but punchy — each sentence should hit ike a hammer.\n"
        "- If a video is **highly relevant and Indian**, include the YouTube link(s) in `youtube_links`.\n"
        "- Never include foreign or generic content.\n\n"

        "Your response must be in **strict JSON**, like this:\n"
        "{\n"
        "  \"answer\": \"<your punchy response>\",\n"
        "  \"youtube_links\": [\"<link1>\", \"<link2>\"]\n"
        "}\n\n"

        f"User question: \"{query}\"\n\n"
        "Output ONLY the JSON. No markdown. No titles. No quotes. No prefix."
    )

    response = qa_chain.run(prompt)

    try:
        parsed = json.loads(response)
        return StockyBhaiAnswer(**parsed)
    except Exception as e:
        return StockyBhaiAnswer(
            answer="Sorry, couldn't parse the response.",
            youtube_links=[]
        )

# Example usage
if __name__ == "__main__":
    # stock_name = "Adani Green Energy Ltd"
    # urls = [
    #     "https://www.forbes.com/sites/daniellechemtob/2025/06/05/forbes-daily-new-flock-of-ai-surveillance-has-privacy-experts-worried/",
    #     "https://www.thehindubusinessline.com/companies/french-energy-giant-totalenergies-reaffirms-support-for-adani-greens-expansion-in-india/article69651184.ece"
    # ]
    #
    # result = summarize_stock_articles_structured(stock_name, urls)
    #
    # print(f"Stock: {result.stock_symbol}")
    # print(f"Summary: {result.summary}")
    # print(f"Market Impact: {result.market_impact}")
    # print(f"Key Events: {result.key_events}")
    # print(f"Suggestion: {result.suggestion}")
    # result = ask_stocky_bhai_qa('What is investing?')
    # print(result)
    pass
