import unittest
from unittest.mock import patch
import os
import sys
from fastapi.testclient import TestClient

# Adjust path for imports
current_dir = os.path.dirname(os.path.abspath(__file__)) # tests directory
module_dir = os.path.dirname(current_dir) # financial_reports_fastapi directory
backend_dir = os.path.dirname(module_dir) # backend directory
# Add backend_dir to sys.path to allow FastAPI to find modules like 'datascraper', 'data_providers' etc.
# if they are imported by 'financial_reports_fastapi.main' or its dependencies.
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir) 
# Add module_dir for direct imports from financial_reports_fastapi
if module_dir not in sys.path:
    sys.path.insert(0, module_dir)


# Import the FastAPI app from main.py
# Must be imported after sys.path modifications
from financial_reports_fastapi.main import app 

class TestMainApi(unittest.TestCase):
    def setUp(self):
        # It's important that the app instance used by TestClient
        # is the one from financial_reports_fastapi.main
        # and that all its dependencies (like report_generator) can be resolved.
        self.client = TestClient(app)

    def test_read_root(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"message": "Financial Reports API"})

    def test_health_check(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    @patch('financial_reports_fastapi.main.generate_hourly_financial_report')
    def test_get_hourly_report_success(self, mock_generate_report):
        mock_generate_report.return_value = "This is a mock financial report."
        
        response = self.client.get("/reports/hourly/")
        self.assertEqual(response.status_code, 200)
        json_response = response.json()
        self.assertEqual(json_response["report_type"], "hourly")
        self.assertEqual(json_response["data"], "This is a mock financial report.")
        self.assertIn("generated_at", json_response)
        mock_generate_report.assert_called_once()

    @patch('financial_reports_fastapi.main.generate_hourly_financial_report')
    def test_get_hourly_report_generator_error(self, mock_generate_report):
        mock_generate_report.return_value = "Error generating report: Test Error"
        
        response = self.client.get("/reports/hourly/")
        self.assertEqual(response.status_code, 200) # The endpoint itself should still succeed
        json_response = response.json()
        self.assertEqual(json_response["data"], "Error generating report: Test Error")
        mock_generate_report.assert_called_once()
            
    # Test for static file serving (optional, as it depends on files existing)
    # This test relies on the static mount setup in main.py and
    # the actual existence of a file.
    # For a robust test, we might need to create a dummy file in the static dir during test setup.
    # Example: Main/backend/static/test_static.txt
    # @classmethod
    # def setUpClass(cls):
    #     # Create a dummy static file for testing
    #     static_dir_in_main_py = os.path.join(backend_dir, "static") # Path used in main.py for StaticFiles
    #     os.makedirs(static_dir_in_main_py, exist_ok=True)
    #     cls.dummy_static_file_path = os.path.join(static_dir_in_main_py, "test_static.txt")
    #     with open(cls.dummy_static_file_path, "w") as f:
    #         f.write("Test static content.")

    # @classmethod
    # def tearDownClass(cls):
    #     # Clean up the dummy static file
    #     if os.path.exists(cls.dummy_static_file_path):
    #         os.remove(cls.dummy_static_file_path)

    # def test_static_file_access(self):
    #     # Ensure the TestClient is initialized with an app that has static files mounted.
    #     # The app from financial_reports_fastapi.main should have this if main.py is correct.
    #     response = self.client.get("/static/test_static.txt") # Path relative to static mount
    #     if response.status_code == 404:
    #         # This might happen if the static directory in main.py is not correctly resolved
    #         # during testing, or if the dummy file setup failed.
    #         # Print the path used by main.py for StaticFiles for debugging
    #         # This requires accessing app.mounts or similar, which can be complex.
    #         # For now, log a warning if 404.
    #         print("Warning: Static file test_static.txt not found. Check static mount in main.py and test setup.")
    #         # Try to access the charts directory as a basic check
    #         response_charts = self.client.get("/static/charts/") # Should give 404 if no index.html, but proves mount
    #         print(f"Access to /static/charts/ returned: {response_charts.status_code}")


    #     self.assertEqual(response.status_code, 200, f"Failed to get static file. Content: {response.text}")
    #     self.assertEqual(response.text, "Test static content.")


if __name__ == '__main__':
    unittest.main()
