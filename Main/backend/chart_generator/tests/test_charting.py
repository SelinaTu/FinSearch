import unittest
import os
import sys
import shutil # For cleaning up generated chart files
import glob # For finding generated files with timestamp

# Adjust path to import module from parent directory
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir) # chart_generator directory
backend_dir = os.path.dirname(parent_dir) # backend directory
# Ensure 'backend_dir' is added to sys.path if not already there
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from chart_generator import charting

class TestCharting(unittest.TestCase):
    # Use a dedicated test output directory within chart_generator/tests/ for clarity
    # This directory will be created and cleaned up by tests.
    # It's relative to the test file itself.
    CHART_TEST_DIR_RELATIVE = 'test_charts_output' 
    CHART_TEST_DIR_ABSOLUTE = os.path.abspath(os.path.join(current_dir, CHART_TEST_DIR_RELATIVE))


    @classmethod
    def setUpClass(cls):
        # Ensure the test chart directory exists and is clean
        if os.path.exists(cls.CHART_TEST_DIR_ABSOLUTE):
            shutil.rmtree(cls.CHART_TEST_DIR_ABSOLUTE)
        os.makedirs(cls.CHART_TEST_DIR_ABSOLUTE, exist_ok=True)
        
        # Override the CHARTS_DIR in the charting module to point to our test directory
        # This is crucial for tests to not interfere with actual chart generation paths
        # and to have a predictable location for verifying output.
        cls.original_charts_dir = charting.CHARTS_DIR # Store original to restore later
        charting.CHARTS_DIR = cls.CHART_TEST_DIR_ABSOLUTE
        print(f"Overrode charting.CHARTS_DIR to: {charting.CHARTS_DIR}")


    @classmethod
    def tearDownClass(cls):
        # Clean up the test chart directory
        if os.path.exists(cls.CHART_TEST_DIR_ABSOLUTE):
            shutil.rmtree(cls.CHART_TEST_DIR_ABSOLUTE)
        
        # Restore original CHARTS_DIR
        charting.CHARTS_DIR = cls.original_charts_dir
        print(f"Restored charting.CHARTS_DIR to: {charting.CHARTS_DIR}")


    def test_generate_simple_line_chart_success(self):
        data = [1, 5, 3, 6, 2, 7]
        filename_prefix = "test_chart_success"
        
        # Call the function that now uses the overridden CHARTS_DIR
        web_path = charting.generate_simple_line_chart(data, title="Test Chart", filename_prefix=filename_prefix)
        
        self.assertIsNotNone(web_path)
        # The web_path is expected to be like "/static/charts/test_chart_success_timestamp.png"
        # but since we overrode CHARTS_DIR to an absolute path for testing,
        # the logic in charting.py creating web_path needs care.
        # charting.py: web_path = f"static/charts/{filename}"
        # If CHARTS_DIR is absolute, os.path.join(CHARTS_DIR, filename) is absolute.
        # The web_path construction in charting.py needs to be robust or this test needs to adapt.
        
        # Let's verify the file exists on disk first using the prefix and overridden directory
        # List files in the CHART_TEST_DIR_ABSOLUTE that match the prefix
        matching_files = glob.glob(os.path.join(self.CHART_TEST_DIR_ABSOLUTE, f"{filename_prefix}_*.png"))
        self.assertTrue(len(matching_files) == 1, f"Expected one chart file with prefix '{filename_prefix}', found {len(matching_files)}")
        self.assertTrue(os.path.exists(matching_files[0]))

        # Verify the returned web_path structure.
        # The current charting.py generate_simple_line_chart returns f"/static/charts/{filename}"
        # This is hardcoded. For testing, it might be better if charting.py used a base web path
        # that could also be overridden, or if it returned a full disk path for testing.
        # Given the current implementation, we check against the hardcoded structure.
        # The filename part of web_path should match the actual filename on disk.
        actual_filename_on_disk = os.path.basename(matching_files[0])
        self.assertEqual(web_path, f"/static/charts/{actual_filename_on_disk}")


    def test_generate_simple_line_chart_empty_data(self):
        web_path = charting.generate_simple_line_chart([], title="Empty Data")
        self.assertIsNone(web_path)

    def test_generate_simple_line_chart_invalid_data_type(self):
        # Test with data that is not a list of numbers
        web_path = charting.generate_simple_line_chart(["a", "b", "c"], title="Invalid Data Type")
        self.assertIsNone(web_path)
            
    def test_generate_simple_line_chart_non_list_input(self):
        # Test with input that is not a list at all
        web_path = charting.generate_simple_line_chart("this is not a list", title="Non List Input")
        self.assertIsNone(web_path)

    def test_generate_simple_line_chart_single_point_data(self):
        data = [42]
        filename_prefix = "test_chart_single_point"
        web_path = charting.generate_simple_line_chart(data, title="Single Point Test", filename_prefix=filename_prefix)
        self.assertIsNotNone(web_path)
        matching_files = glob.glob(os.path.join(self.CHART_TEST_DIR_ABSOLUTE, f"{filename_prefix}_*.png"))
        self.assertTrue(len(matching_files) == 1)
        actual_filename_on_disk = os.path.basename(matching_files[0])
        self.assertEqual(web_path, f"/static/charts/{actual_filename_on_disk}")


if __name__ == '__main__':
    unittest.main()
