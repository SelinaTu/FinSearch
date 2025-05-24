import os
import datetime
import requests
import logging

# Determine the path to the .env file, assuming it's in the 'backend/' directory.
# __file__ is .../data_providers/news_and_fx.py
# os.path.dirname(__file__) is .../data_providers/
# The .env file is expected one level up, in 'backend/'.
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env') 
from dotenv import load_dotenv
load_dotenv(dotenv_path) # Load .env file from the calculated path.

# Retrieve NewsAPI key from environment variables.
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")

# Configure basic logging for the module.
# This will use the root logger configuration if already set, or default to basicConfig.
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')
logger = logging.getLogger(__name__) # Get a logger specific to this module.

def fetch_financial_news(query: str = "forex OR foreign exchange OR currency OR stock market OR economy",
                         page_size: int = 30) -> list:
    """
    Fetches recent financial news articles from NewsAPI based on a specified query.

    This function queries the NewsAPI's 'everything' endpoint, focusing on articles
    published in English within the last 30 hours, sorted by relevancy.
    It processes the response to extract key information for each article.

    Args:
        query (str, optional): The search query for news articles. 
                               Defaults to a broad financial topics query.
        page_size (int, optional): The number of articles to request from the API. 
                                   Defaults to 30. Max is typically 100 for NewsAPI.

    Returns:
        list: A list of dictionaries, where each dictionary represents a news article
              and contains keys like 'title', 'description', 'source', 
              'published_at', and 'url'. Returns an empty list if the NEWSAPI_KEY 
              is not configured, or if an API error or network issue occurs.
    """
    if not NEWSAPI_KEY:
        logger.warning("NEWSAPI_KEY not found in environment variables. Cannot fetch news.")
        return [] # Return empty list if API key is missing.

    # Define time window for news fetching: from 30 hours ago to now.
    now_utc = datetime.datetime.utcnow()
    from_time_utc = now_utc - datetime.timedelta(hours=30)

    try:
        # Make GET request to NewsAPI.
        response = requests.get(
            "https://newsapi.org/v2/everything",
            params={
                "q": query,
                "from": from_time_utc.isoformat() + "Z", # Format time to ISO 8601 with Z for UTC.
                "to": now_utc.isoformat() + "Z",
                "pageSize": page_size,
                "language": "en",         # Filter for English articles.
                "sortBy": "relevancy",    # Order articles by relevance to the query.
                "apiKey": NEWSAPI_KEY     # Pass the API key.
            },
            timeout=10 # Set a 10-second timeout for the request.
        )
        response.raise_for_status() # Raise an HTTPError for bad responses (4XX or 5XX).
        
        articles_data = response.json().get('articles', [])
        
        # Process articles to extract relevant fields and filter out those without descriptions.
        processed_articles = [
            {
                "title": article.get("title"),
                "description": article.get("description"),
                "source": article.get("source", {}).get("name"), # Safely access nested source name.
                "published_at": article.get("publishedAt"),
                "url": article.get("url")
            }
            for article in articles_data if article.get("description") # Ensure articles have a description.
        ]
        
        logger.info(f"Fetched {len(processed_articles)} articles from NewsAPI for query: '{query}'.")
        return processed_articles
        
    except requests.exceptions.Timeout:
        logger.error("Timeout occurred while fetching news from NewsAPI.")
        return [] # Return empty list on timeout.
    except requests.exceptions.RequestException as e:
        # Handle other network-related errors (e.g., DNS failure, connection error).
        logger.error(f"Error fetching news from NewsAPI: {e}")
        return []
    except Exception as e:
        # Catch any other unexpected errors during the process.
        logger.error(f"An unexpected error occurred while fetching financial news: {e}")
        return []

def fetch_fx_exchange_rates(pairs: list = None) -> dict:
    """
    Fetches current FX conversion rates for specified currency pairs using api.exchangerate.host.

    This function queries the public API at api.exchangerate.host, which does not
    require an API key. It iterates through a list of currency pairs (e.g., "EUR/USD")
    and retrieves the conversion rate for each.

    Args:
        pairs (list, optional): A list of currency pairs to fetch rates for, 
                                formatted as "FROM/TO" (e.g., ["EUR/USD", "USD/JPY"]).
                                Defaults to a predefined list of common pairs.

    Returns:
        dict: A dictionary where keys are the currency pairs (str) and values are 
              their corresponding exchange rates (str, formatted to 4 decimal places)
              or an error message string (e.g., "N/A (API error: ...)") if fetching failed for a pair.
    """
    if pairs is None:
        # Default currency pairs if none are provided.
        pairs = ["EUR/USD", "USD/MXN", "USD/CNH", "USD/INR", "USD/THB"]
    
    rates_data = {} # Dictionary to store fetched rates.
    base_url = "https://api.exchangerate.host/convert" # API endpoint.
    
    for p in pairs:
        try:
            # Split the pair string (e.g., "EUR/USD") into from_currency and to_currency.
            from_currency, to_currency = p.split('/')
            params = {"from": from_currency, "to": to_currency, "amount": 1} # Request conversion for 1 unit.
            
            response = requests.get(base_url, params=params, timeout=5) # 5-second timeout.
            response.raise_for_status() # Raise HTTPError for bad responses.
            resp_json = response.json()
            
            # Check if API call was successful and 'result' (the rate) is present.
            if resp_json.get('success') and 'result' in resp_json:
                result_rate = resp_json.get('result')
                if isinstance(result_rate, (int, float)):
                    rates_data[p] = f"{result_rate:.4f}" # Format rate to 4 decimal places.
                else:
                    logger.warning(f"Unexpected result type for pair {p}: {result_rate}")
                    rates_data[p] = "N/A (unexpected result type)"
            else:
                # API call was not successful, or 'result' is missing. Log and store error info.
                error_info = resp_json.get('error', {}) # Default to empty dict if 'error' key is missing
                error_message_detail = error_info.get('info', 'Unknown API error') if isinstance(error_info, dict) else str(error_info)
                logger.warning(f"Failed to fetch FX rate for {p} from API. Error: {error_message_detail}")
                rates_data[p] = f"N/A (API error: {error_message_detail})"
                
        except requests.exceptions.Timeout:
            logger.error(f"Timeout occurred while fetching FX rate for {p}.")
            rates_data[p] = "N/A (request timed out)"
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error fetching FX rate for {p}: {e}")
            rates_data[p] = "N/A (request failed)"
        except ValueError:
            # Handles errors from p.split('/') if pair format is incorrect.
            logger.error(f"Invalid currency pair format: {p}. Expected format 'FROM/TO'.")
            rates_data[p] = "N/A (invalid pair)"
        except Exception as e:
            # Catch any other unexpected errors for a specific pair.
            logger.error(f"An unexpected error occurred while fetching rate for {p}: {e}")
            rates_data[p] = "N/A (unexpected error)"
    
    logger.info(f"Fetched FX rates: {rates_data}")
    return rates_data


if __name__ == '__main__':
    # This block is for direct testing of the module's functions.
    # It demonstrates how to use the functions and prints their output.
    print("--- Testing news_and_fx.py directly ---")
    
    print("\nTesting news fetching (NEWSAPI_KEY must be set in .env or environment):")
    news_articles = fetch_financial_news(page_size=3) # Request fewer articles for testing.
    if news_articles:
        for i, article in enumerate(news_articles): # Iterate through all fetched articles for this test
            print(f"  News {i+1}: {article.get('title', 'N/A')}")
            print(f"    Desc: {article.get('description', 'N/A')[:100] if article.get('description') else 'N/A'}...")
            print(f"    Source: {article.get('source', 'N/A')} @ {article.get('published_at', 'N/A')}")
    else:
        print("  No news fetched. This might be due to a missing NEWSAPI_KEY, network issues, or API errors. Check logs for details.")

    print("\nTesting FX rate fetching:")
    exchange_rates = fetch_fx_exchange_rates(pairs=["USD/EUR", "GBP/JPY", "AUD/USD", "INVALIDPAIR"]) # Test with a mix of pairs
    if exchange_rates:
        for pair, rate in exchange_rates.items():
            print(f"  {pair}: {rate}")
    else:
        print("  No FX rates fetched. Check logs for details.")
    print("--- End of news_and_fx.py direct test ---")
