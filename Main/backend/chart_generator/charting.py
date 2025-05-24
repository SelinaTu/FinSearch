import matplotlib
# Set Matplotlib backend to 'Agg'.
# 'Agg' is a non-interactive backend that renders plots to files (e.g., PNG).
# This is essential for running Matplotlib in headless environments like servers or Docker containers
# where a GUI display is not available. It prevents Matplotlib from trying to open a display window.
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
import numpy as np # For numerical operations, used in __main__ for sample data.
import os
from datetime import datetime
import logging # Added for logging

# Configure basic logging for the module.
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')
logger = logging.getLogger(__name__)

# Define the base directory for storing generated charts.
# This path is constructed relative to the current file's location.
# __file__ refers to this file: .../chart_generator/charting.py
# os.path.dirname(__file__) gives: .../chart_generator/
# os.path.join(os.path.dirname(__file__), '..') goes up one level to: .../backend/
# So, CHARTS_DIR points to: Main/backend/static/charts/
CHARTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'static', 'charts')

# Ensure the CHARTS_DIR exists when the module is loaded.
# This helps prevent errors if the directory is missing when a chart is generated.
if not os.path.exists(CHARTS_DIR):
    try:
        os.makedirs(CHARTS_DIR, exist_ok=True) # exist_ok=True prevents error if dir already exists.
        logger.info(f"Successfully created CHARTS_DIR at: {os.path.abspath(CHARTS_DIR)}")
    except OSError as e:
        logger.error(f"Error creating CHARTS_DIR at {os.path.abspath(CHARTS_DIR)}: {e}")
else:
    logger.info(f"CHARTS_DIR already exists at: {os.path.abspath(CHARTS_DIR)}")


def generate_simple_line_chart(data: list, title: str = 'Data Chart', 
                               xlabel: str = 'X-axis', ylabel: str = 'Y-axis', 
                               filename_prefix: str = 'chart') -> str | None:
    """
    Generates a simple line chart from a list of numerical data and saves it as a PNG file.

    The chart is saved into the directory defined by `CHARTS_DIR`. Filenames include a
    timestamp to ensure uniqueness. The function validates input data type and content.

    Args:
        data (list): A list of numerical values (integers or floats) to be plotted.
                     Example: `[10, 12, 15, 14, 17]`
        title (str, optional): The title of the chart. Defaults to 'Data Chart'.
        xlabel (str, optional): The label for the X-axis. Defaults to 'X-axis'.
        ylabel (str, optional): The label for the Y-axis. Defaults to 'Y-axis'.
        filename_prefix (str, optional): A prefix for the generated chart filename. 
                                         Defaults to 'chart'.

    Returns:
        str | None: The web-accessible path to the generated chart image 
                    (e.g., '/static/charts/chart_timestamp.png') if successful.
                    Returns `None` if chart generation fails due to invalid data,
                    empty data, or an internal Matplotlib error.
    """
    # Validate input data: must be a list containing only numbers.
    if not isinstance(data, list):
        logger.warning(f"Invalid data type for chart: Expected list, got {type(data)}. Title: '{title}'")
        return None
    if not all(isinstance(x, (int, float)) for x in data):
        logger.warning(f"Invalid data content for chart: All elements must be numbers. Title: '{title}'")
        return None
    if not data: # Check for empty list after type validation.
        logger.warning(f"Empty data provided for chart. Title: '{title}'")
        return None

    try:
        # Create a new Matplotlib figure and axes for the chart.
        # figsize is in inches.
        plt.figure(figsize=(8, 4)) # Adjusted for typical report/web display.
        
        # Plot the data with markers and a line.
        plt.plot(data, marker='o', linestyle='-')
        
        # Set chart title and axis labels.
        plt.title(title)
        plt.xlabel(xlabel)
        plt.ylabel(ylabel)
        
        # Add a grid for better readability.
        plt.grid(True)
        
        # Generate a unique filename using a timestamp to prevent overwrites.
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f") # High-precision timestamp.
        filename = f"{filename_prefix}_{timestamp}.png"
        
        # Construct the full, absolute path to save the chart file.
        # This uses the module-level CHARTS_DIR.
        filepath = os.path.abspath(os.path.join(CHARTS_DIR, filename))
        
        # Ensure the target directory exists (double-check, helpful if CHARTS_DIR was modified at runtime or deleted).
        # This is generally redundant if CHARTS_DIR is created reliably at module load, but adds robustness.
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        # Save the figure to the specified path.
        plt.savefig(filepath)
        
        # Close the figure to free up memory. This is crucial in server environments
        # to prevent memory leaks when generating many charts.
        plt.close() 
        
        # Construct the web-accessible path.
        # This path assumes that the 'static/' directory (which is Main/backend/static/)
        # is served at the URL root '/static/'.
        # So, a file at Main/backend/static/charts/filename.png becomes /static/charts/filename.png.
        web_path = f"/static/charts/{filename}" # Leading slash for root-relative URL.
        
        logger.info(f"Chart generated successfully: '{filepath}'. Web path: '{web_path}'")
        return web_path
        
    except Exception as e:
        # Log any other exceptions that occur during chart generation.
        logger.error(f"Error generating chart '{title}': {e}")
        import traceback
        # Print full traceback to server logs for detailed debugging.
        logger.error(traceback.format_exc()) 
        return None

if __name__ == '__main__':
    # This block executes when the script is run directly (e.g., python charting.py).
    # Useful for quick testing of the chart generation functionality.
    logger.info(f"--- Direct execution of charting.py for testing ---")
    logger.info(f"Charts will be saved in: {os.path.abspath(CHARTS_DIR)}")
    
    # Test case 1: Sample data
    sample_data_values = [np.random.randint(0, 10) for _ in range(10)] # Generate some random data.
    chart_path_1 = generate_simple_line_chart(sample_data_values, title="Sample Line Chart", 
                                             xlabel="Time Period", ylabel="Measurement")
    if chart_path_1:
        logger.info(f"Test chart 1 generated. Web path: {chart_path_1}")
    else:
        logger.warning("Failed to generate test chart 1.")

    # Test case 2: Empty data list
    chart_path_empty_data = generate_simple_line_chart([], title="Empty Data Chart")
    if not chart_path_empty_data:
        logger.info("Correctly handled empty data for chart generation (no chart generated).")
            
    # Test case 3: Invalid data (list of strings)
    chart_path_invalid_data = generate_simple_line_chart(["a", "b", 1], title="Invalid Data Chart")
    if not chart_path_invalid_data:
        logger.info("Correctly handled invalid data (list of non-numbers) for chart generation (no chart generated).")
    
    # Test case 4: Invalid data type (string instead of list)
    chart_path_non_list = generate_simple_line_chart("not a list", title="Non-List Input Chart")
    if not chart_path_non_list:
        logger.info("Correctly handled invalid data type (non-list) for chart generation (no chart generated).")

    # Test case 5: Single data point
    chart_path_single_point = generate_simple_line_chart([5], title="Single Data Point Chart")
    if chart_path_single_point:
        logger.info(f"Test chart for single data point generated. Web path: {chart_path_single_point}")
    else:
        logger.warning("Failed to generate test chart for single data point.")
    logger.info(f"--- End of charting.py direct test ---")
