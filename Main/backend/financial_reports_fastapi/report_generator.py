import os
import sys
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain.tools import tool
import json # For formatting dicts/lists to string if needed for tool outputs
import time # For W&B: performance timing
import wandb # For W&B: metrics logging
import logging # Added for logging

# Configure basic logging for the module.
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Path Adjustments for Module Imports ---
# This section ensures that sibling directories (datascraper, data_providers, chart_generator)
# within the 'backend' parent directory are discoverable by Python's import system.
# __file__ is .../financial_reports_fastapi/report_generator.py
current_module_dir = os.path.dirname(os.path.abspath(__file__)) # .../financial_reports_fastapi/
backend_parent_dir = os.path.dirname(current_module_dir)      # .../backend/

# Add 'backend_parent_dir' to sys.path if it's not already there.
# This allows imports like 'from datascraper import ...', etc.
if backend_parent_dir not in sys.path:
    sys.path.append(backend_parent_dir)
    logger.info(f"Added '{backend_parent_dir}' to sys.path for broader module access.")

# --- Mock Fallbacks for Critical Imports ---
# These try-except blocks attempt to import necessary modules. If an import fails
# (e.g., due to missing dependencies or incorrect paths in some environments),
# mock versions of the required functions/classes are created. This allows
# the application to load and potentially run with reduced functionality,
# rather than crashing outright. It's particularly useful for testing or
# if some external services are temporarily unavailable or not configured.

try:
    from datascraper import cdm_rag 
except ImportError as e_rag:
    logger.error(f"Failed to import cdm_rag from datascraper: {e_rag}. Using MOCK RAG function.")
    def get_rag_response_mock(question, model_name="o1-preview"):
        return f"Mock RAG response for '{question}' (cdm_rag could not be imported)."
    cdm_rag = type('obj', (object,), {'get_rag_response' : get_rag_response_mock})

try:
    from data_providers import news_and_fx
except ImportError as e_news_fx:
    logger.error(f"Failed to import news_and_fx from data_providers: {e_news_fx}. Using MOCK news/FX functions.")
    def mock_fetch_financial_news(query="default", page_size=5): 
        return [{"title": "Mock News: Service Unavailable", "description": "News fetching is mocked due to import error.", "source":"Mock System", "published_at":"Now", "url":"mockurl.com"}]
    def mock_fetch_fx_exchange_rates(pairs=None): 
        return {"EUR/USD": "N/A (mocked)", "USD/JPY": "N/A (mocked)"}
    news_and_fx = type('obj', (object,), {
        'fetch_financial_news': mock_fetch_financial_news,
        'fetch_fx_exchange_rates': mock_fetch_fx_exchange_rates
    })

try:
    from chart_generator.charting import generate_simple_line_chart
except ImportError as e_chart:
    logger.error(f"Failed to import generate_simple_line_chart from chart_generator: {e_chart}. Using MOCK chart function.")
    def mock_generate_simple_line_chart(data, title="Mock Chart", xlabel="X", ylabel="Y", filename_prefix="mock_chart"):
        logger.info(f"Mock chart generation called for title: '{title}' (charting module import failed).")
        return "/static/charts/mock_chart_unavailable.png" # Placeholder path
    generate_simple_line_chart = mock_generate_simple_line_chart


# --- LangChain Tools Definition ---
# These tools are exposed to the LangChain agent, allowing it to interact with
# external data sources (RAG, news, FX) and internal capabilities (charting).

@tool
def get_financial_data_tool(query: str, model_name: str = "o1-preview") -> str:
    """
    Queries a Retrieval-Augmented Generation (RAG) system with access to a general 
    knowledge base of uploaded financial documents. Use this tool for broader financial 
    context, historical data analysis, or specific queries about document contents 
    not covered by real-time news or FX rate tools.
    The 'model_name' parameter is for the RAG system's internal LLM, not the primary agent.
    """
    logger.info(f"Tool 'get_financial_data_tool' called with query: '{query}', RAG model: '{model_name}'")
    response = cdm_rag.get_rag_response(question=query, model_name=model_name)
    # Ensure the response is a string for the LangChain agent.
    return json.dumps(response) if not isinstance(response, str) else response

@tool
def fetch_news_tool(query: str = "latest financial news OR stock market OR economy OR interest rates OR forex OR currency", page_size: int = 7) -> str:
    """
    Fetches recent financial news articles based on a natural language query.
    Useful for understanding current events affecting markets or specific financial entities.
    Returns a formatted string of news items, including title, description, source, and publication date.
    Default query covers general financial topics. page_size limits number of articles (default 7).
    """
    logger.info(f"Tool 'fetch_news_tool' called with query: '{query}', page_size: {page_size}")
    articles = news_and_fx.fetch_financial_news(query=query, page_size=page_size)
    if not articles: 
        return "No relevant news articles found for the query."
    # Format news articles into a single string for the LLM.
    # Limiting to a few articles (e.g., first 5 if many are returned by the API) for context window management.
    formatted_news_list = [
        f"Title: {a.get('title', 'N/A')}\nDescription: {a.get('description', 'N/A')}\nSource: {a.get('source', 'N/A')} ({a.get('published_at', 'N/A')})\nURL: {a.get('url', 'N/A')}"
        for a in articles[:5] 
    ]
    return "\n\n".join(formatted_news_list) if formatted_news_list else "No news articles found or an error occurred."

@tool
def fetch_fx_rates_tool() -> str:
    """
    Fetches current foreign exchange (FX) rates for a predefined list of major currency pairs.
    Provides a snapshot of current FX market conditions.
    Returns a string detailing each currency pair and its exchange rate.
    """
    logger.info("Tool 'fetch_fx_rates_tool' called.")
    rates = news_and_fx.fetch_fx_exchange_rates() # Uses default pairs defined in news_and_fx module.
    if not rates: 
        return "Could not fetch current FX rates."
    # Format rates into a single string.
    return "\n".join([f"{pair}: {rate}" for pair, rate in rates.items()])

@tool
def generate_chart_tool(data: list[float], title: str = "Data Visualization", xlabel: str = "Index", ylabel: str = "Value") -> str:
    """
    Generates a simple line chart from a list of numerical data points.
    Use this tool to visualize trends or time series data relevant to the financial report.
    Args:
        data (list[float]): A list of numbers (integers or floats) to plot. Example: [10.1, 12.5, 11.0, 15.3].
        title (str, optional): The title for the chart. Defaults to "Data Visualization".
        xlabel (str, optional): Label for the X-axis. Defaults to "Index".
        ylabel (str, optional): Label for the Y-axis. Defaults to "Value".
    Returns:
        str: The web-accessible path to the generated chart image (e.g., '/static/charts/chart_timestamp.png') 
             if successful, or an error message if chart generation failed (e.g., due to invalid data).
    """
    logger.info(f"Tool 'generate_chart_tool' called with title: '{title}', data length: {len(data) if isinstance(data, list) else 'N/A'}")
    # Input validation for the data parameter.
    if not isinstance(data, list) or not data:
        return "Error: Input data for chart must be a non-empty list of numerical values."
    
    processed_data = []
    try:
        # Ensure all data points are convertible to float for plotting.
        processed_data = [float(x) for x in data]
    except (ValueError, TypeError) as e:
        return f"Error: Chart data must consist of numbers. Invalid element found. Details: {e}"

    if not processed_data: # Should be caught by the first check, but as a safeguard.
        return "Error: Chart data is empty or became empty after processing."

    # Call the actual chart generation function.
    chart_path = generate_simple_line_chart(data=processed_data, title=title, xlabel=xlabel, ylabel=ylabel)
    
    if chart_path:
        logger.info(f"Chart generated by 'generate_chart_tool'. Web path: {chart_path}")
        # The returned path (e.g., /static/charts/...) is directly usable in HTML if static files are served.
        return chart_path 
    else:
        logger.error("Chart generation failed within 'generate_simple_line_chart' function.")
        return "Error: Failed to generate chart. The chart generation function did not return a valid path."


def generate_hourly_financial_report() -> str:
    """
    Generates an hourly financial report by orchestrating a LangChain agent
    with tools for data fetching (news, FX, RAG) and visualization (charts).
    Logs metrics to Weights & Biases if WANDB_API_KEY is configured.

    Returns:
        str: The generated financial report string, or an error message if generation fails.
    """
    wandb_run = None # Initialize wandb_run to None.
    start_time = time.time() # Record start time for performance monitoring.
    log_data_for_wandb = {"input_query": "Hourly financial report generation request", "llm_model_used": "gpt-4o"}

    # --- API Key and W&B Initialization ---
    # Check for presence of necessary API keys. These are critical for core functionality
    # and for meaningful W&B logging.
    wandb_api_key_present = bool(os.getenv("WANDB_API_KEY"))
    openai_api_key_present = bool(os.getenv("OPENAI_API_KEY"))
    newsapi_key_present = bool(os.getenv("NEWSAPI_KEY")) # news_and_fx.py handles its absence gracefully.
    
    # Determine if mock functions are in use for external services.
    is_mock_news_active = hasattr(news_and_fx, 'fetch_financial_news') and news_and_fx.fetch_financial_news.__name__ == 'mock_fetch_financial_news'
    
    # W&B should only be initialized if its API key is present and core dependencies (OpenAI LLM) are available.
    # NewsAPI is non-critical if mocked, but if not mocked, its key should be present for a full-featured run.
    can_attempt_wandb_init = wandb_api_key_present and openai_api_key_present and (newsapi_key_present or is_mock_news_active)

    if can_attempt_wandb_init:
        try:
            wandb_run = wandb.init(
                project="financial_reports_service_v2", # Descriptive project name
                reinit=True, # Allows calling wandb.init() multiple times in the same process.
                config={ # Static configuration for this run type.
                    "llm_model": "gpt-4o", 
                    "report_type": "hourly_automated",
                    "agent_tools_available": [t.name for t in tools_list] # Defined below
                }
            )
            logger.info(f"W&B initialized successfully for report generation. Run ID: {wandb_run.id}")
        except Exception as e_wandb_init:
            logger.error(f"Error initializing W&B: {e_wandb_init}. W&B logging will be disabled for this run.")
            wandb_run = None # Ensure wandb_run is None if initialization fails.
    else:
        # Log reasons for not initializing W&B.
        missing_keys_info = []
        if not wandb_api_key_present: missing_keys_info.append("WANDB_API_KEY")
        if not openai_api_key_present: missing_keys_info.append("OPENAI_API_KEY")
        if not newsapi_key_present and not is_mock_news_active: missing_keys_info.append("NEWSAPI_KEY (and news service is not mocked)")
        logger.warning(f"W&B logging disabled due to missing API keys or incomplete setup: {', '.join(missing_keys_info)}.")

    # --- Critical Pre-check for OpenAI API Key ---
    if not openai_api_key_present:
        error_msg_critical = "CRITICAL ERROR: OPENAI_API_KEY is not found. LLM agent cannot operate."
        logger.critical(error_msg_critical)
        # If W&B run was started (e.g. WANDB_API_KEY was present but OPENAI_API_KEY was not), log failure.
        if wandb_run:
            log_data_for_wandb.update({"agent_success": False, "error_message": error_msg_critical, "report_generation_duration_seconds": time.time() - start_time})
            try: wandb_run.log(log_data_for_wandb); wandb_run.finish()
            except Exception as e_wb_log: logger.error(f"Error logging critical failure to W&B: {e_wb_log}")
        return error_msg_critical # Exit early as agent cannot function.

    # --- LangChain Agent Setup ---
    llm = ChatOpenAI(model="gpt-4o", temperature=0.7) # Using a capable OpenAI model.
    tools_list = [ # Define the list of tools available to the agent.
        get_financial_data_tool, 
        fetch_news_tool, 
        fetch_fx_rates_tool,
        generate_chart_tool
    ]

    # Define the system prompt for the LangChain agent.
    # This prompt guides the agent on its role, available tools, and expected output format.
    system_message_prompt = (
        "You are a highly skilled financial analyst. Your primary task is to generate a concise and informative "
        "hourly financial report. Utilize the available tools to gather real-time and historical data. "
        "Available Tools:\n"
        "- 'fetch_news_tool': Use for the latest financial news. Query broadly (e.g., 'global financial highlights') or specifically.\n"
        "- 'fetch_fx_rates_tool': Use for current FX rates of major currency pairs.\n"
        "- 'generate_chart_tool': Use to visualize numerical data series (e.g., trends from news, analysis, or FX rates if you have a series). "
        "  Input data as a list of numbers (e.g., [10.2, 10.5, 10.3]). The tool returns a path to the chart image. "
        "  If a chart is relevant and generated, mention its creation and include the image path (e.g., '/static/charts/chart_name.png') in your report.\n"
        "- 'get_financial_data_tool': Use for querying an existing knowledge base of financial documents for broader context or historical data.\n\n"
        "Report Structure: Synthesize information covering key market movements, significant economic news, "
        "FX rate updates, visualized data trends (if charts are generated), and a brief outlook. "
        "Be factual and concise."
    )
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", system_message_prompt),
        ("human", "{input}"), # Placeholder for the user's (or system's) primary query.
        ("placeholder", "{agent_scratchpad}"), # For agent's intermediate steps.
    ])
    
    # Create the LangChain agent and agent executor.
    agent = create_tool_calling_agent(llm, tools_list, prompt_template)
    # handle_parsing_errors=True can help make the agent more resilient to occasional LLM output format issues.
    agent_executor = AgentExecutor(agent=agent, tools=tools_list, verbose=True, handle_parsing_errors=True)

    # Define the primary query for the financial report.
    report_generation_query = (
        "Generate a comprehensive hourly financial report. Fetch the latest news and FX rates. "
        "If you identify any numerical data series suitable for visualization (e.g., a trend from news or analysis), "
        "generate a chart for it. Also, consult the general financial knowledge base if needed for supplementary context."
    )
    log_data_for_wandb["input_query"] = report_generation_query # Update W&B log with actual query
    
    try:
        # Invoke the agent to generate the report.
        response = agent_executor.invoke({"input": report_generation_query})
        generated_output = response.get("output", "Error: No output received from financial report agent.")
        
        # Log success metrics to W&B if initialized.
        log_data_for_wandb.update({
            "report_generation_duration_seconds": time.time() - start_time,
            "report_length_chars": len(generated_output),
            "agent_success": True,
            "final_report_content_snippet": generated_output[:200] # Log a snippet
        })
        return generated_output
        
    except Exception as e_agent:
        # Handle exceptions during agent execution.
        duration_on_error = time.time() - start_time
        error_message_detail = str(e_agent)
        logger.error(f"LangChain agent execution failed: {error_message_detail}")
        
        # Log failure metrics to W&B.
        log_data_for_wandb.update({
            "report_generation_duration_seconds": duration_on_error,
            "agent_success": False,
            "error_message": error_message_detail
        })
        
        # Construct a user-friendly error message.
        # Specific check for OpenAI API key errors, which are common.
        if "OPENAI_API_KEY" in error_message_detail or "api_key" in error_message_detail.lower() or "AuthenticationError" in error_message_detail:
             return "Error generating report: Critical issue with OpenAI API Key (missing or invalid)."
        return f"Error: Financial report generation failed due to an agent execution error: {error_message_detail}"
        
    finally:
        # Ensure W&B run is finished if it was started.
        if wandb_run:
            try:
                # Add final tool usage summary if possible (complex for general agent)
                # For now, available_tools is logged at init.
                # If specific tools were called, that would require deeper LangChain callback integration.
                log_data_for_wandb["final_status_notes"] = "Run completed."
                
                wandb_run.log(log_data_for_wandb)
                wandb_run.finish()
                logger.info(f"W&B data logged and run finished. Run ID: {wandb_run.id}")
            except Exception as e_wandb_finish:
                logger.error(f"Error during W&B final logging/finish: {e_wandb_finish}")

if __name__ == '__main__':
    # This block allows direct execution of the script for testing purposes.
    logger.info("--- Direct execution of report_generator.py for testing ---")
    
    # Print status of required API keys for easier debugging when run directly.
    logger.info(f"Environment WANDB_API_KEY set: {bool(os.getenv('WANDB_API_KEY'))}")
    logger.info(f"Environment OPENAI_API_KEY set: {bool(os.getenv('OPENAI_API_KEY'))}")
    logger.info(f"Environment NEWSAPI_KEY set: {bool(os.getenv('NEWSAPI_KEY'))}")
    
    # Check if mock functions are active (useful for diagnosing import issues).
    logger.info(f"Using mock news: {hasattr(news_and_fx, 'fetch_financial_news') and news_and_fx.fetch_financial_news.__name__ == 'mock_fetch_financial_news'}")
    logger.info(f"Using mock FX: {hasattr(news_and_fx, 'fetch_fx_exchange_rates') and news_and_fx.fetch_fx_exchange_rates.__name__ == 'mock_fetch_fx_exchange_rates'}")
    logger.info(f"Using mock chart: {generate_simple_line_chart.__name__ == 'mock_generate_simple_line_chart'}")
    
    logger.info("\nAttempting to generate a sample financial report (this may take some time)...")
    financial_report = generate_hourly_financial_report()
    
    print("\n--- Generated Financial Report (Direct Execution) ---")
    print(financial_report)
    print("-------------------------------------------------------")
    logger.info("--- End of report_generator.py direct test ---")
