from django.test import TestCase, Client
from unittest.mock import patch, MagicMock, mock_open
import json
import os
import sys
from io import BytesIO # For creating in-memory file for upload test

# Path adjustments for imports if necessary:
# For Django tests, usually, the project structure and manage.py handle path setups.
# However, ensuring 'backend' is on the path can help if direct imports of sibling modules
# (like data_providers or datascraper) are done within the app being tested,
# and those modules are not installed as packages.
# backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
# if backend_dir not in sys.path:
#    sys.path.insert(0, backend_dir)

class ChatServerAppViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        # To ensure test isolation for views.message_list (if it's module-level global):
        # Option 1: Patch views.message_list before each test that might modify it.
        # Option 2: Call the /clear endpoint if available and reliable.
        # Option 3: Refactor views.message_list to be instance-based or session-based (ideal).
        # For this test suite, we'll assume that if message_list is modified,
        # subsequent tests might be affected if not handled.
        # A simple way to reset it if it's a global list in views.py:
        try:
            from chat_server_app import views
            views.message_list = [
                {"role": "system", "content": "You are a helpful financial assistant. Always answer questions to the best of your ability."}
            ]
        except ImportError:
            pass # If views cannot be imported here, rely on endpoint behavior or patching.


    @patch('chat_server_app.views.news_and_fx.fetch_financial_news')
    def test_chat_response_data_type_news(self, mock_fetch_news):
        mock_fetch_news.return_value = [
            {"title": "Test News", "description": "News description", "source": "Test Source", "published_at": "2023-01-01", "url": "http://example.com"}
        ]
        response = self.client.get('/get_chat_response/', {'data_type': 'news', 'question': 'latest news'})
        self.assertEqual(response.status_code, 200)
        json_response = response.json()
        self.assertIn('NewsService', json_response['resp'])
        self.assertIn("Title: Test News", json_response['resp']['NewsService'])
        mock_fetch_news.assert_called_once()

    @patch('chat_server_app.views.news_and_fx.fetch_fx_exchange_rates')
    def test_chat_response_data_type_fx(self, mock_fetch_fx):
        mock_fetch_fx.return_value = {"EUR/USD": "1.0900", "USD/JPY": "150.0000"}
        response = self.client.get('/get_chat_response/', {'data_type': 'fx'}) 
        self.assertEqual(response.status_code, 200)
        json_response = response.json()
        self.assertIn('FXService', json_response['resp'])
        self.assertIn("EUR/USD: 1.0900", json_response['resp']['FXService'])
        mock_fetch_fx.assert_called_once()

    @patch('chat_server_app.views.ds.create_rag_response') 
    def test_chat_response_data_type_rag(self, mock_create_rag_response):
        mock_create_rag_response.return_value = "Mocked RAG response for your query."
        # The view logic defaults to 'gpt-4o' if 'models' param is not split or first entry.
        model_key_in_response = 'gpt-4o' 

        response = self.client.get('/get_chat_response/', {'data_type': 'rag', 'question': 'What is inflation?', 'use_rag': 'true', 'models': model_key_in_response})
        self.assertEqual(response.status_code, 200)
        json_response = response.json()
        self.assertIn(model_key_in_response, json_response['resp'])
        self.assertEqual(json_response['resp'][model_key_in_response], "Mocked RAG response for your query.")
        mock_create_rag_response.assert_called_once()

    @patch('chat_server_app.views.ds.create_response') 
    def test_chat_response_data_type_general_no_rag(self, mock_create_response):
        mock_create_response.return_value = "Mocked general LLM response."
        model_key_in_response = 'gpt-4o'

        response = self.client.get('/get_chat_response/', {'data_type': 'rag', 'question': 'Hello', 'use_rag': 'false', 'models': model_key_in_response})
        self.assertEqual(response.status_code, 200)
        json_response = response.json()
        self.assertIn(model_key_in_response, json_response['resp'])
        self.assertEqual(json_response['resp'][model_key_in_response], "Mocked general LLM response.")
        mock_create_response.assert_called_once()
            
    @patch('chat_server_app.views.ce.upload_folder') 
    def test_folder_path_post_success(self, mock_upload_folder):
        mock_upload_folder.return_value = ({"message": "Files processed"}, 200)
        
        dummy_json_data = {"filePaths": [{"name": "doc1.txt", "content": "Hello world"}]}
        dummy_file_content = json.dumps(dummy_json_data).encode('utf-8')
        
        dummy_file = BytesIO(dummy_file_content)
        dummy_file.name = 'test.json' 
        
        # Use the correct URL for folder_path, assuming it's mapped to '/api/folder_path' in urls.py
        # If your urls.py maps it differently, this needs to change.
        # Based on typical Django REST patterns, it might be /api/folder_path or just /folder_path
        # The prompt doesn't specify urls.py, so assuming a common pattern or the one used in HTML.
        # Let's assume '/api/folder_path' is the correct one from a hypothetical urls.py
        response = self.client.post('/api/folder_path/', {'json_data': dummy_file}) # Added trailing slash
        
        self.assertEqual(response.status_code, 200)
        json_response = response.json()
        self.assertEqual(json_response.get("message"), "Files processed")
        mock_upload_folder.assert_called_once()

    @patch('chat_server_app.views.os.path.exists', return_value=True) # Mock os.path.exists
    @patch('chat_server_app.views.open', new_callable=mock_open, read_data="http://example.com\nhttp://another.com")
    def test_get_preferred_urls(self, mock_file_open, mock_path_exists):
        # Patch the PREFERRED_URLS_FILE constant within the views module for this test's scope
        # This ensures the test uses a predictable path, regardless of views.py's actual constant value.
        with patch('chat_server_app.views.PREFERRED_URLS_FILE', 'dummy_preferred_urls.txt'):
            response = self.client.get('/api/get_preferred_urls/') # Added trailing slash
            self.assertEqual(response.status_code, 200)
            json_response = response.json()
            self.assertEqual(json_response['urls'], ["http://example.com", "http://another.com"])
            # Assert that os.path.exists was called with the patched path
            mock_path_exists.assert_called_with('dummy_preferred_urls.txt')
            # Assert that open was called with the patched path
            mock_file_open.assert_called_with('dummy_preferred_urls.txt', 'r', encoding='utf-8')

    def test_clear_message_list(self):
        # Add a message first to see if clear works
        from chat_server_app import views # Import views to access message_list
        views.message_list.append({"role": "user", "content": "Test message to be cleared."})
        self.assertTrue(len(views.message_list) > 1) # System prompt + test message

        response = self.client.get('/clear_chat_history/') # Assuming this is the URL for clear view
        self.assertEqual(response.status_code, 200)
        json_response = response.json()
        self.assertEqual(json_response['resp'], 'Message list cleared successfully')
        
        # Check if message_list in views module is actually reset
        self.assertEqual(len(views.message_list), 1) # Only system prompt should remain
        self.assertEqual(views.message_list[0]['role'], 'system')


# Note: Ensure that the URLs used in client.get() and client.post() match
# the actual URL patterns defined in chat_server_app/urls.py.
# For example, '/get_chat_response/', '/api/folder_path/', etc.
# These tests assume certain URL naming conventions.
# If Django settings (DJANGO_SETTINGS_MODULE) are not automatically configured
# by the test runner environment, they might need to be set.
# (e.g., os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'your_project.settings'))
# However, 'manage.py test' usually handles this.
