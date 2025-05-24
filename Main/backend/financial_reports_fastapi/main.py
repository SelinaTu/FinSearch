from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles # For serving static files like generated charts.
from datetime import datetime, timezone   # For timestamping reports.
import os                                 # For path manipulations (locating static directory).
import logging                            # For application-level logging.

# Import the core report generation function from the local 'report_generator' module.
# The '.' indicates a relative import from the same package.
from .report_generator import generate_hourly_financial_report 

# Configure basic logging for the application.
# This setup will apply to the Uvicorn server logs as well if not overridden.
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize the FastAPI application instance.
# This 'app' instance will be used by the Uvicorn server to handle incoming requests.
app = FastAPI(
    title="Financial Reports API",
    description="Provides an API for generating hourly financial reports and related functionalities.",
    version="1.0.0"
)

# --- Static Files Configuration ---
# This section configures the FastAPI application to serve static files, which is necessary
# for accessing generated charts via web URLs.

# Determine the absolute path to the 'static' directory located in 'Main/backend/static'.
# __file__ gives the path to the current file (e.g., .../financial_reports_fastapi/main.py).
# os.path.dirname(os.path.abspath(__file__)) gives the directory of the current file (.../financial_reports_fastapi/).
# The first os.path.dirname(...) goes up to .../financial_reports_fastapi/.
# The second os.path.dirname(...) goes up to .../backend/.
# Then, "static" is joined to form ".../backend/static".
static_files_dir = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
    "static"
)

# Ensure the static files directory exists. If not, create it.
# This is important because 'chart_generator/charting.py' saves charts into a subdirectory
# (static/charts), but the parent 'static' directory might not exist initially.
# Creating it here ensures that the StaticFiles mount target is valid.
if not os.path.exists(static_files_dir):
    try:
        os.makedirs(static_files_dir, exist_ok=True) # exist_ok=True prevents error if directory already exists.
        logger.info(f"Successfully created static files directory at: {static_files_dir}")
    except OSError as e:
        # Log an error if directory creation fails, as static files (like charts) might not be servable.
        logger.error(f"Error creating static directory {static_files_dir}: {e}. Static file serving may fail.")

# Mount the 'static_files_dir' to be accessible under the '/static' URL path.
# For example, a file at 'Main/backend/static/charts/mychart.png' will be available
# at 'http://<server_address>/static/charts/mychart.png'.
# The 'name="static"' allows referring to this mount in URL generation if needed (e.g., in templates).
app.mount("/static", StaticFiles(directory=static_files_dir), name="static")
logger.info(f"Static files are configured to be served from directory: '{os.path.abspath(static_files_dir)}' at URL path '/static'.")

# Optional: Check for the 'charts' subdirectory and log a warning if it's missing.
# This subdirectory is where 'charting.py' is expected to save generated charts.
charts_subdir_path = os.path.join(static_files_dir, "charts")
if not os.path.exists(charts_subdir_path):
    logger.warning(
        f"The 'charts' subdirectory ('{charts_subdir_path}') was not found within the static files directory. "
        "Charts will not be served until this directory is created (usually by chart_generator.py upon first chart generation)."
    )


# --- API Endpoints ---

@app.get("/")
def read_root():
    """
    Root endpoint for the API.
    Provides a simple welcome message indicating the API is operational.
    """
    logger.info("Root endpoint '/' accessed.")
    return {"message": "Financial Reports API is active."}

@app.get("/health")
def health_check():
    """
    Health check endpoint.
    Returns a status 'ok' if the API service is running. Useful for monitoring.
    """
    logger.info("Health check endpoint '/health' accessed.")
    return {"status": "ok"}

@app.get("/reports/hourly/")
def get_hourly_report():
    """
    Endpoint to generate and retrieve an hourly financial report.
    
    This endpoint triggers the `generate_hourly_financial_report` function from 
    `report_generator.py`, which uses a LangChain agent and various tools 
    (news, FX, RAG, charting) to compile the report.

    Returns:
        dict: A JSON response containing the report type, generation timestamp,
              and the report data (which can be a string or structured content
              including text and potentially paths to generated charts).
    """
    logger.info("Hourly report endpoint '/reports/hourly/' accessed. Initiating report generation.")
    # Call the core report generation logic.
    report_content = generate_hourly_financial_report()
    
    # Structure the response.
    response_payload = {
        "report_type": "hourly",
        "generated_at": datetime.now(timezone.utc).isoformat(), # ISO 8601 timestamp in UTC.
        "data": report_content # The actual report content from the generator.
    }
    logger.info(f"Hourly report generated. Report length (data part): {len(str(report_content))} characters.")
    return response_payload

# To run this FastAPI application locally (for development):
# Navigate to the 'Main/backend/financial_reports_fastapi/' directory in your terminal.
# Ensure all dependencies from 'requirements.txt' are installed in your environment.
# Set necessary environment variables (e.g., OPENAI_API_KEY, NEWSAPI_KEY, WANDB_API_KEY).
# Run the command: uvicorn main:app --reload --host 0.0.0.0 --port 8001
# '--reload' enables auto-reloading on code changes, useful for development.
# '--host 0.0.0.0' makes it accessible from outside the container/machine if needed.
# '--port 8001' specifies the port (can be changed).
