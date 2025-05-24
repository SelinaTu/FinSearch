import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import datetime
import requests # Import requests for requests.exceptions.HTTPError

# Adjust path to import module from parent directory
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir) # data_providers directory
backend_dir = os.path.dirname(parent_dir) # backend directory
# Ensure 'backend_dir' is added to sys.path if not already there,
# to allow 'from data_providers import news_and_fx'
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from data_providers import news_and_fx

class TestNewsAndFx(unittest.TestCase):

    @patch('data_providers.news_and_fx.requests.get')
    def test_fetch_financial_news_success(self, mock_get):
        # Mock NewsAPI response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "articles": [
                {"title": "Test News 1", "description": "Desc 1", "source": {"name": "Source1"}, "publishedAt": "2023-01-01T12:00:00Z", "url": "http://example.com/news1"},
                {"title": "Test News 2", "description": "Desc 2", "source": {"name": "Source2"}, "publishedAt": "2023-01-01T13:00:00Z", "url": "http://example.com/news2"},
            ]
        }
        mock_get.return_value = mock_response
        
        # Temporarily set NEWSAPI_KEY for the test
        original_newsapi_key = news_and_fx.NEWSAPI_KEY
        news_and_fx.NEWSAPI_KEY = "test_key" # Ensure the module uses this mocked key
        
        articles = news_and_fx.fetch_financial_news(query="test query", page_size=2)
        
        self.assertEqual(len(articles), 2)
        self.assertEqual(articles[0]['title'], "Test News 1")
        mock_get.assert_called_once() # Verify requests.get was called
        
        # Restore original NEWSAPI_KEY
        news_and_fx.NEWSAPI_KEY = original_newsapi_key

    @patch('data_providers.news_and_fx.requests.get')
    def test_fetch_financial_news_api_error(self, mock_get):
        mock_response = MagicMock()
        # Simulate an HTTP error, e.g., 500
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("API Error")
        mock_get.return_value = mock_response

        original_newsapi_key = news_and_fx.NEWSAPI_KEY
        news_and_fx.NEWSAPI_KEY = "test_key"
        articles = news_and_fx.fetch_financial_news()
        self.assertEqual(len(articles), 0) # Expect empty list on API error
        news_and_fx.NEWSAPI_KEY = original_newsapi_key

    def test_fetch_financial_news_no_api_key(self):
        original_newsapi_key = news_and_fx.NEWSAPI_KEY
        news_and_fx.NEWSAPI_KEY = None # Simulate missing API key
        articles = news_and_fx.fetch_financial_news()
        self.assertEqual(len(articles), 0) # Expect empty list if key is None
        news_and_fx.NEWSAPI_KEY = original_newsapi_key

    @patch('data_providers.news_and_fx.requests.get')
    def test_fetch_fx_exchange_rates_success(self, mock_get):
        mock_response_eur_usd = MagicMock()
        mock_response_eur_usd.status_code = 200
        mock_response_eur_usd.json.return_value = {"success": True, "result": 1.08} # API uses 'result'
        
        mock_response_usd_jpy = MagicMock()
        mock_response_usd_jpy.status_code = 200
        mock_response_usd_jpy.json.return_value = {"success": True, "result": 150.50}

        # Configure side_effect to return different mocks for sequential calls
        mock_get.side_effect = [mock_response_eur_usd, mock_response_usd_jpy]
        
        rates = news_and_fx.fetch_fx_exchange_rates(pairs=["EUR/USD", "USD/JPY"])
        
        self.assertEqual(len(rates), 2)
        self.assertEqual(rates["EUR/USD"], "1.0800") # Ensure formatting to 4 decimal places
        self.assertEqual(rates["USD/JPY"], "150.5000")
        self.assertEqual(mock_get.call_count, 2)

    @patch('data_providers.news_and_fx.requests.get')
    def test_fetch_fx_exchange_rates_api_error(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 500 # Simulate server error
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("API Error")
        mock_get.return_value = mock_response # This mock will be used for all calls in this test
        
        rates = news_and_fx.fetch_fx_exchange_rates(pairs=["EUR/USD", "USD/JPY"]) # Test with multiple pairs
        self.assertEqual(rates["EUR/USD"], "N/A (request failed)")
        self.assertEqual(rates["USD/JPY"], "N/A (request failed)")
        self.assertEqual(mock_get.call_count, 2) # Called for each pair


    @patch('data_providers.news_and_fx.requests.get')
    def test_fetch_fx_exchange_rates_api_returns_error_in_json(self, mock_get):
        mock_response_eur_usd = MagicMock()
        mock_response_eur_usd.status_code = 200 # API call itself is successful
        mock_response_eur_usd.json.return_value = {"success": False, "error": {"info": "Invalid currency."}}
        
        mock_get.return_value = mock_response_eur_usd
        
        rates = news_and_fx.fetch_fx_exchange_rates(pairs=["EUR/INVALID"])
        self.assertTrue("N/A (API error: Invalid currency.)" in rates["EUR/INVALID"])


    def test_fetch_fx_exchange_rates_invalid_pair_format(self):
        rates = news_and_fx.fetch_fx_exchange_rates(pairs=["EURUSD"]) # Invalid format
        self.assertEqual(rates["EURUSD"], "N/A (invalid pair)")

if __name__ == '__main__':
    unittest.main()
