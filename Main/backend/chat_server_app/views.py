import json
import os
import csv
# import random # 'random' module was imported but not used. Removed.
from datetime import datetime
from django.views.decorators.csrf import csrf_exempt # For disabling CSRF protection on specific views.
from django.http import JsonResponse # Django's JSON response class.
from datascraper import datascraper as ds # Alias for brevity.
from datascraper import create_embeddings as ce # Alias for brevity.
# from django.shortcuts import render # 'render' was imported but not used.
# from django.http import HttpResponse # 'HttpResponse' was imported but not used.

# --- Path Adjustments and Module Imports ---
import sys
import logging # Added for logging within this module.

# Configure basic logging for this Django app's views.
# This helps in debugging and monitoring the application's behavior.
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')


# Attempt to import the 'news_and_fx' module from the 'data_providers' package.
# This section includes path adjustments and mock fallbacks for robustness,
# especially if the Django environment isn't fully configured or when running parts standalone.
try:
    # Standard Django way to import from another app/module if 'data_providers' is a Python package
    # accessible via PYTHONPATH (which Django usually manages).
    from data_providers import news_and_fx
    logger.info("Successfully imported 'news_and_fx' from 'data_providers'.")
except ImportError:
    # If direct import fails, try adjusting sys.path.
    # This assumes 'chat_server_app' and 'data_providers' are sibling directories under 'backend'.
    # __file__ is .../chat_server_app/views.py
    # os.path.dirname(__file__) is .../chat_server_app/
    # os.path.join(os.path.dirname(__file__), '..') is .../backend/
    backend_dir_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if backend_dir_path not in sys.path:
        sys.path.insert(0, backend_dir_path) # Add 'backend/' to path for broader imports.
        logger.info(f"Added '{backend_dir_path}' to sys.path for module discovery.")
    try:
        from data_providers import news_and_fx
        logger.info("Successfully imported 'news_and_fx' after sys.path adjustment.")
    except ImportError as e_import:
        # If import still fails after path adjustment, use mock objects.
        # This allows the server to run but with mocked functionality for these services.
        logger.critical(f"CRITICAL FAILURE: Could not import 'news_and_fx'. Activating MOCK services. Error: {e_import}")
        def mock_fetch_financial_news(query="default", page_size=5): 
            logger.warning(f"MOCK news_and_fx.fetch_financial_news called with query: {query}")
            return []
        def mock_fetch_fx_exchange_rates(pairs=None): 
            logger.warning(f"MOCK news_and_fx.fetch_fx_exchange_rates called with pairs: {pairs}")
            return {}
        news_and_fx = type('obj', (object,), { # Create a mock object with the required functions.
            'fetch_financial_news': mock_fetch_financial_news,
            'fetch_fx_exchange_rates': mock_fetch_fx_exchange_rates
        })

# --- Constants ---
# Define path for the question log CSV file, relative to this views.py file.
QUESTION_LOG_PATH = os.path.join(os.path.dirname(__file__), 'questionLog.csv')

# Define path for the preferred URLs text file.
# This path assumes 'preferred_urls.txt' is within the 'datascraper' directory,
# and 'datascraper' is a sibling to 'chat_server_app' under 'backend'.
PREFERRED_URLS_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), # .../chat_server_app/
    '..',                                      # .../backend/
    'datascraper',                             # .../backend/datascraper/
    'preferred_urls.txt'                       # .../backend/datascraper/preferred_urls.txt
)
logger.info(f"Path for preferred URLs file set to: {PREFERRED_URLS_FILE}")


# --- Global State (Message List) ---
# This global list stores the conversation history for the chat.
# IMPORTANT: Using a global variable for `message_list` makes the chat state shared across
# all users and requests to this Django worker process. This is NOT SUITABLE for production
# environments with multiple users. In a production scenario, conversation history should be
# managed per user session (e.g., using Django sessions, a database, or a cache like Redis).
# For the current scope, it's maintained as a simple global list.
message_list = [
    {"role": "system", # Initial system message to set the assistant's persona.
     "content": "You are a helpful financial assistant. Always answer questions to the best of your ability."}
]
logger.info("Global 'message_list' initialized with a system prompt.")

# --- Helper Functions ---

def _ensure_log_file_exists():
    """
    Ensures that the CSV log file for interactions exists, creating it with headers if not.
    Uses UTF-8 encoding for broader character support.
    """
    if not os.path.isfile(QUESTION_LOG_PATH):
        try:
            with open(QUESTION_LOG_PATH, 'w', newline='', encoding='utf-8') as log_file:
                writer = csv.writer(log_file)
                # Define headers for the CSV log file.
                writer.writerow(['Button_Type', 'Current_URL', 'Question', 'Date', 'Time', 'Response_Preview'])
            logger.info(f"Created interaction log file: {QUESTION_LOG_PATH}")
        except IOError as e:
            logger.error(f"Failed to create interaction log file at {QUESTION_LOG_PATH}: {e}")


def _log_interaction(button_type: str, current_url: str, question: str, response: str = None):
    """
    Logs interaction details (button type, URL, question, response preview) to a CSV file.
    Includes timestamp (date and time). Ensures UTF-8 encoding and basic CSV sanitization.

    Args:
        button_type (str): Identifier for the type of interaction (e.g., 'chat_news', 'clear').
        current_url (str): The URL from which the request originated, if applicable.
        question (str): The question or action initiated by the user.
        response (str, optional): The response generated by the system. Only a preview is logged.
    """
    _ensure_log_file_exists() # Make sure the log file is ready.
    
    now = datetime.now()
    date_str = now.strftime('%Y-%m-%d')
    time_str = now.strftime('%H:%M:%S')
    
    # Truncate response for preview to keep log concise.
    response_preview = str(response)[:50] if response else "N/A" 
    
    # Basic sanitization for CSV: escape double quotes by doubling them.
    def sanitize_csv_field(field_text: str) -> str:
        return str(field_text).replace('"', '""')

    # Sanitize all fields before writing to CSV.
    button_type_s = sanitize_csv_field(button_type)
    current_url_s = sanitize_csv_field(current_url)
    question_s = sanitize_csv_field(question)
    response_preview_s = sanitize_csv_field(response_preview)

    try:
        with open(QUESTION_LOG_PATH, 'a', newline='', encoding='utf-8') as log_file:
            writer = csv.writer(log_file)
            writer.writerow([button_type_s, current_url_s, question_s, date_str, time_str, response_preview_s])
    except IOError as e:
        logger.error(f"Error writing to interaction log file {QUESTION_LOG_PATH}: {e}")

# --- Django Views ---

@csrf_exempt # Disable CSRF protection for this view, common for simple API endpoints.
def add_webtext(request):
    """
    View to add text content from a webpage (presumably scraped by the frontend)
    to the global `message_list`. This text is then used as context for the LLM.

    Expects a POST request with a JSON body containing 'textContent' and 'currentUrl'.
    """
    if request.method != 'POST':
        logger.warning(f"add_webtext: Received non-POST request method: {request.method}")
        return JsonResponse({'error': 'Invalid request method; use POST.'}, status=405)
    
    try:
        body_data = json.loads(request.body)
        text_content = body_data.get('textContent', '')
        current_url = body_data.get('currentUrl', 'N/A') # Get URL, default to N/A if not provided.
        
        if not text_content:
            logger.warning("add_webtext: No 'textContent' provided in POST request.")
            return JsonResponse({"error": "No textContent provided."}, status=400)
        
        # Append the scraped web content to the message_list as user context.
        # Prepending the source URL to the content for clarity in the conversation history.
        message_list.append({
            "role": "user", # Content is treated as if the user provided it.
            "content": f"Context from webpage {current_url}:\n{text_content}"
        })
        logger.info(f"add_webtext: Added web content from URL: {current_url} (length: {len(text_content)} chars).")
        
        _log_interaction(button_clicked="add_webtext_context", current_url=current_url, 
                         question=f"Added web content snippet: {text_content[:50]}...")
        
        return JsonResponse({"resp": "Text content added successfully to conversation context."})
    except json.JSONDecodeError:
        logger.error("add_webtext: Invalid JSON received in POST request body.")
        return JsonResponse({"error": "Invalid JSON format in request body."}, status=400)
    except Exception as e:
        logger.error(f"add_webtext: Unexpected error: {e}")
        return JsonResponse({"error": f"An unexpected error occurred: {e}"}, status=500)


def chat_response(request):
    """
    Handles chat requests, routing to different data sources based on 'data_type' parameter.
    Supports fetching news, FX rates, or interacting with RAG/general LLM.

    GET Parameters:
        question (str): The user's query.
        data_type (str, optional): Specifies the type of data requested.
                                   'news': Fetches financial news.
                                   'fx': Fetches FX exchange rates.
                                   'rag' (default): Uses RAG or general LLM.
        use_rag (str, optional): 'true' or 'false'. For 'rag' data_type, determines if RAG is used.
        models (str, optional): Comma-separated list of LLM models (for 'rag' data_type if not using specific service).
        current_url (str, optional): URL of the page where the chat is initiated.
    """
    question = request.GET.get('question', '')
    data_type = request.GET.get('data_type', 'rag').lower() # Default to 'rag', convert to lowercase.
    use_rag_str = request.GET.get('use_rag', 'false').lower()
    current_url = request.GET.get('current_url', 'N/A')
    
    logger.info(f"chat_response: Received request - data_type='{data_type}', question='{question[:50]}...', use_rag='{use_rag_str}'")

    responses = {} # Dictionary to hold responses from different services/models.
    log_button_action = f"chat_{data_type}" # Base for logging interaction type.

    if data_type == 'news':
        # Fetch financial news using the news_and_fx module.
        news_query = question if question else "latest financial news OR stock market OR economy"
        logger.info(f"chat_response (news): Fetching news with query: '{news_query}'")
        articles = news_and_fx.fetch_financial_news(query=news_query, page_size=10) # Fetch up to 10 articles.
        
        if articles:
            # Format articles into a string for the response.
            formatted_news_items = [
                f"Title: {a.get('title', 'N/A')}\nDescription: {a.get('description', 'N/A')}\n"
                f"Source: {a.get('source', 'N/A')} (Published: {a.get('published_at', 'N/A')})\nURL: {a.get('url', 'N/A')}"
                for a in articles # Format all fetched articles for direct display.
            ]
            responses['NewsService'] = "\n\n".join(formatted_news_items)
        else:
            # Handle cases where no articles are found or NEWSAPI_KEY is missing/invalid.
            responses['NewsService'] = "No news articles found or an error occurred. Ensure NEWSAPI_KEY is correctly set if real news is expected."
        
        _log_interaction(log_button_action, current_url, question, responses['NewsService'][:50])

    elif data_type == 'fx':
        # Fetch FX exchange rates.
        logger.info("chat_response (fx): Fetching FX rates.")
        rates = news_and_fx.fetch_fx_exchange_rates() # Uses default pairs from news_and_fx.
        
        if rates:
            formatted_rates_str = "\n".join([f"{pair}: {rate_text}" for pair, rate_text in rates.items()])
            responses['FXService'] = formatted_rates_str
        else:
            responses['FXService'] = "Could not fetch FX rates at this time. The service might be temporarily unavailable."
            
        _log_interaction(log_button_action, current_url, question, responses['FXService'][:50])

    else: # Default case: 'rag' or any other data_type, handled by RAG or general LLM.
        selected_llm_models_str = request.GET.get('models', 'gpt-4o') # Default to gpt-4o.
        llm_models_list = selected_llm_models_str.split(',')
        # For simplicity, use the first model in the list if multiple are provided for this default path.
        model_to_use = llm_models_list[0].strip() if llm_models_list else 'gpt-4o'
        
        logger.info(f"chat_response (rag/general): Using LLM '{model_to_use}'. use_rag='{use_rag_str}'.")

        # Determine if RAG should be used based on 'use_rag' parameter.
        if use_rag_str == 'true':
            log_button_action = "chat_rag_llm"
            # Call RAG system (from datascraper.ds). Pass a copy of message_list if it's modified by the function.
            responses[model_to_use] = ds.create_rag_response(question, message_list.copy(), model_to_use)
        else:
            log_button_action = "chat_general_llm"
            # Call general LLM response (from datascraper.ds).
            responses[model_to_use] = ds.create_response(question, message_list.copy(), model_to_use)
        
        response_text_for_log = responses.get(model_to_use, "No LLM response generated.")
        _log_interaction(log_button_action, current_url, question, response_text_for_log[:50] if response_text_for_log else "N/A")

    return JsonResponse({'resp': responses}) # Return all collected responses.


@csrf_exempt
def adv_response(request):
    """
    Handles "advanced" chat requests, typically involving more complex RAG or LLM interactions.
    (Note: The distinction between this and `chat_response` with `use_rag='true'` might need clarification
     or this endpoint could be merged/refactored if functionality overlaps significantly.)
    """
    question = request.GET.get('question', '')
    selected_models = request.GET.get('models', 'gpt-4o') # Default LLM model.
    models = selected_models.split(',')
    use_rag = request.GET.get('use_rag', 'false').lower() == 'true' # Check if RAG is specifically requested for advanced.
    current_url = request.GET.get('current_url', 'N/A')
    
    logger.info(f"adv_response: Received request - question='{question[:50]}...', use_rag='{use_rag}'")
    responses = {}
    
    for model_name in models:
        # Ensure message_list is copied if ds.create_rag_advanced_response or ds.create_advanced_response modifies it.
        if use_rag: # If RAG is explicitly part of the advanced response.
            responses[model_name] = ds.create_rag_advanced_response(question, message_list.copy(), model_name)
        else: # General advanced response without RAG (might involve web search if implemented in ds.create_advanced_response).
            responses[model_name] = ds.create_advanced_response(question, message_list.copy(), model_name)
    
    first_response_preview = next(iter(responses.values()), "No advanced response")[:50]
    _log_interaction(f"advanced_chat_{'rag' if use_rag else 'general'}", current_url, question, first_response_preview)
    
    return JsonResponse({'resp': responses})


@csrf_exempt
def clear(request):
    """
    Clears the global `message_list`, resetting the conversation history.
    Restores the initial system prompt.
    """
    global message_list # Indicate that we are modifying the global variable.
    message_list = [
        {"role": "system", 
         "content": "You are a helpful financial assistant. Always answer questions to the best of your ability."}
    ]
    logger.info("Global 'message_list' has been cleared and reset.")
    
    current_url = request.GET.get('current_url', 'N/A') # Get URL if provided, for logging context.
    _log_interaction("clear_chat_history", current_url, "User cleared message history.")
    
    return JsonResponse({'resp': 'Message list cleared successfully.'})


@csrf_exempt
def get_sources(request):
    """
    Retrieves data sources used by the `datascraper` module for a given query.
    (Note: The effectiveness of this depends on how `ds.get_sources` is implemented,
     particularly if it relies on state from a previous call to `create_advanced_response`.)
    """
    query = request.GET.get('query', '') # The query for which sources are requested.
    logger.info(f"get_sources: Request for sources related to query: '{query[:50]}...'")
    
    sources = ds.get_sources(query) # Call the datascraper function.
    
    current_url = request.GET.get('current_url', 'N/A')
    _log_interaction("get_sources_request", current_url, f"Source lookup for query: {query[:50]}...")
    
    return JsonResponse({'resp': sources})


@csrf_exempt
def get_logo(request):
    """
    Fetches a website's logo (favicon) given its URL.
    Uses `ds.get_website_icon` from the datascraper module.
    """
    url_to_fetch_logo = request.GET.get('url', '')
    if not url_to_fetch_logo:
        logger.warning("get_logo: 'url' parameter is missing.")
        return JsonResponse({'error': 'URL parameter is required.'}, status=400)
    
    logger.info(f"get_logo: Request to fetch logo for URL: {url_to_fetch_logo}")
    try:
        logo_source_url = ds.get_website_icon(url_to_fetch_logo)
        if logo_source_url:
            return JsonResponse({'resp': logo_source_url})
        else:
            logger.info(f"get_logo: No icon found for URL: {url_to_fetch_logo}")
            return JsonResponse({'resp': 'No icon found for the provided URL.'}) # Return a clear message, not an error status for "not found".
    except Exception as e:
        logger.error(f"get_logo: Error fetching icon for URL {url_to_fetch_logo}: {e}")
        return JsonResponse({'error': f'An error occurred while fetching the icon: {str(e)}'}, status=500)


def log_question(request): # Legacy endpoint.
    """
    Legacy endpoint for logging questions. Redirects to the new `_log_interaction` helper.
    Consider marking for deprecation or removing if no longer actively used by front-end.
    """
    question = request.GET.get('question', '')
    button_clicked_type = request.GET.get('button', 'legacy_log') # Default type if not specified.
    current_url = request.GET.get('current_url', 'N/A')
    
    logger.info(f"log_question (legacy): Received log request - button='{button_clicked_type}', question='{question[:50]}...'")
    if question and button_clicked_type and current_url: # Ensure essential info is present.
        _log_interaction(button_clicked_type, current_url, question, "N/A (legacy log entry)")
    
    return JsonResponse({'status': 'success (legacy log handled)'})


def get_preferred_urls(request):
    """
    Retrieves the list of user-preferred URLs from the `PREFERRED_URLS_FILE`.
    """
    logger.info(f"get_preferred_urls: Request to fetch preferred URLs from: {PREFERRED_URLS_FILE}")
    urls_list = []
    if os.path.exists(PREFERRED_URLS_FILE):
        try:
            with open(PREFERRED_URLS_FILE, 'r', encoding='utf-8') as file:
                urls_list = [line.strip() for line in file.readlines() if line.strip()] # Read non-empty lines.
            logger.info(f"get_preferred_urls: Found {len(urls_list)} preferred URLs.")
        except IOError as e:
            logger.error(f"get_preferred_urls: Error reading preferred URLs file {PREFERRED_URLS_FILE}: {e}")
    else:
        logger.warning(f"get_preferred_urls: Preferred URLs file not found at {PREFERRED_URLS_FILE}.")

    return JsonResponse({'urls': urls_list})


@csrf_exempt
def add_preferred_url(request):
    """
    Adds a new URL to the `PREFERRED_URLS_FILE`.
    Expects a POST request with a JSON body containing the 'url'.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            new_url_to_add = data.get('url')
        except json.JSONDecodeError:
            logger.warning("add_preferred_url: Invalid JSON in request body.")
            return JsonResponse({'status': 'failed', 'error': 'Invalid JSON format.'}, status=400)

        if new_url_to_add:
            logger.info(f"add_preferred_url: Attempting to add URL: {new_url_to_add}")
            current_urls = []
            if os.path.exists(PREFERRED_URLS_FILE):
                try:
                    with open(PREFERRED_URLS_FILE, 'r', encoding='utf-8') as file:
                        current_urls = [line.strip() for line in file.readlines()]
                except IOError as e:
                    logger.error(f"add_preferred_url: Error reading existing preferred URLs file {PREFERRED_URLS_FILE}: {e}")
                    # Proceed with caution or return error, depending on desired behavior.
            
            if new_url_to_add in current_urls:
                logger.info(f"add_preferred_url: URL '{new_url_to_add}' already exists in preferred list.")
                return JsonResponse({'status': 'exists', 'message': 'URL already in preferred list.'})
            
            try:
                with open(PREFERRED_URLS_FILE, 'a', encoding='utf-8') as file: # Append mode.
                    file.write(new_url_to_add + '\n')
                logger.info(f"add_preferred_url: Successfully added URL '{new_url_to_add}' to preferred list.")
                _log_interaction("add_preferred_url", new_url_to_add, f"Added new preferred URL: {new_url_to_add}")
                return JsonResponse({'status': 'success', 'message': 'URL added to preferred list.'})
            except IOError as e:
                logger.error(f"add_preferred_url: Error writing to preferred URLs file {PREFERRED_URLS_FILE}: {e}")
                return JsonResponse({'status': 'failed', 'error': f'Could not write to preferred URLs file: {e}'}, status=500)
    
    logger.warning(f"add_preferred_url: Failed request - method {request.method} or missing URL.")
    return JsonResponse({'status': 'failed', 'error': 'Invalid request method or missing URL in JSON body.'}, status=400)


@csrf_exempt
def folder_path(request):
    """
    Handles the upload of a JSON file containing file paths and content for RAG embedding.
    This JSON data is passed to `create_embeddings.upload_folder` (aliased as `ce.upload_folder`).

    Expects a POST request with 'json_data' as a file upload.
    """
    if request.method == 'POST':
        logger.info("folder_path: Received POST request for RAG document upload.")
        try:
            # Check if 'json_data' file is part of the uploaded files.
            if 'json_data' not in request.FILES:
                logger.warning("folder_path: No file part named 'json_data' in POST request.")
                return JsonResponse({'error': 'No file part named "json_data" found in the request.'}, status=400)
            
            uploaded_file = request.FILES['json_data']
            logger.info(f"folder_path: Received file: {uploaded_file.name} (size: {uploaded_file.size} bytes).")
            
            # Read content from the uploaded file.
            json_file_content = uploaded_file.read()
            if not json_file_content:
                logger.warning(f"folder_path: Uploaded file '{uploaded_file.name}' is empty.")
                return JsonResponse({'error': 'The uploaded JSON file is empty.'}, status=400)

            try:
                # Parse the file content as JSON.
                json_data_parsed = json.loads(json_file_content)
            except json.JSONDecodeError as e_json_decode:
                logger.error(f"folder_path: Invalid JSON format in uploaded file '{uploaded_file.name}'. Error: {e_json_decode}")
                return JsonResponse({'error': f'Invalid JSON format: {str(e_json_decode)}'}, status=400)

            # Call the RAG embedding creation function.
            # `ce.upload_folder` is expected to handle the logic of processing these files,
            # creating embeddings, and setting up the FAISS index.
            logger.info(f"folder_path: Calling create_embeddings.upload_folder with parsed JSON data.")
            response_data_from_ce, status_code_from_ce = ce.upload_folder(json_data_parsed)
            
            logger.info(f"folder_path: Response from ce.upload_folder: {response_data_from_ce}, Status: {status_code_from_ce}")
            return JsonResponse(response_data_from_ce, status=status_code_from_ce)

        except Exception as e_unexpected:
            # Catch any other unexpected errors during processing.
            logger.error(f"folder_path: Unexpected error during file upload processing: {e_unexpected}")
            import traceback
            logger.error(traceback.format_exc()) # Log full traceback for debugging.
            return JsonResponse({'error': f'An unexpected server error occurred: {str(e_unexpected)}'}, status=500)
    else:
        logger.warning(f"folder_path: Received non-POST request method: {request.method}")
        return JsonResponse({'error': 'Only POST requests are allowed for this endpoint.'}, status=405)
