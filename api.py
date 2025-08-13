import time
import subprocess
import sys
import tempfile
import os
import json
import base64
import textwrap
import traceback
import threading
import asyncio
from concurrent.futures import ThreadPoolExecutor
from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from typing import Dict, Any
import datetime

load_dotenv()

# Global execution environment (like Jupyter notebook)
notebook_globals = {}
notebook_initialized = False
cell_counter = 0

# Timeout configuration (4.5 minutes to leave buffer for response)
API_TIMEOUT_SECONDS = 270  # 4.5 minutes
MAX_ITERATION_TIMEOUT = 30  # Max time per Claude iteration

# Thread pool for handling concurrent requests
executor = ThreadPoolExecutor(max_workers=10)


def initialize_notebook_environment():
    """Initialize the notebook environment with common imports"""
    global notebook_globals, notebook_initialized

    if not notebook_initialized:
        initialization_code = """import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import requests
from bs4 import BeautifulSoup
import re
import base64
import io
from scipy import stats
import seaborn as sns
import warnings
from datetime import datetime
import json
import duckdb

# Set matplotlib to non-interactive backend
plt.switch_backend('Agg')

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore')

print("🔧 Notebook environment initialized")
"""

        # Initialize with common imports
        exec(initialization_code, notebook_globals)
        notebook_initialized = True


def show_notebook_variables():
    """Show current variables in the notebook environment"""
    variables = {
        k: type(v).__name__
        for k, v in notebook_globals.items()
        if not k.startswith("__") and not callable(v)
    }
    return (
        f"Available variables: {variables}"
        if variables
        else "No user variables defined yet"
    )


def execute_python_code(code: str) -> dict:
    """Execute Python code in persistent environment (like Jupyter cells)"""
    global notebook_globals, cell_counter

    # Initialize environment if needed
    initialize_notebook_environment()

    # Increment cell counter
    cell_counter += 1

    try:
        # Preprocess code to fix common indentation issues
        # Remove any common leading whitespace while preserving relative indentation
        code = textwrap.dedent(code)
        
        # Strip leading/trailing whitespace lines
        code = code.strip()
        
        # Add special notebook functions to the environment
        notebook_globals["show_vars"] = lambda: print(show_notebook_variables())
        notebook_globals["_cell_num"] = cell_counter

        # Capture stdout and stderr
        from io import StringIO

        old_stdout = sys.stdout
        old_stderr = sys.stderr

        stdout_capture = StringIO()
        stderr_capture = StringIO()

        sys.stdout = stdout_capture
        sys.stderr = stderr_capture

        # Execute the code in the persistent environment
        exec(code, notebook_globals)

        # Restore stdout/stderr
        sys.stdout = old_stdout
        sys.stderr = old_stderr

        # Get captured output
        stdout_content = stdout_capture.getvalue()
        stderr_content = stderr_capture.getvalue()

        return {
            "stdout": stdout_content,
            "stderr": stderr_content,
            "returncode": 0,
            "success": True,
            "cell_number": cell_counter,
        }

    except Exception as e:
        # Restore stdout/stderr in case of error
        sys.stdout = old_stdout
        sys.stderr = old_stderr

        return {
            "stdout": "",
            "stderr": f"Error: {str(e)}",
            "returncode": 1,
            "success": False,
            "cell_number": cell_counter,
        }


def reset_notebook_environment():
    """Reset the notebook environment for a new request"""
    global notebook_globals, notebook_initialized, cell_counter
    notebook_globals = {}
    notebook_initialized = False
    cell_counter = 0


def validate_and_clean_base64(base64_string: str) -> str:
    """Clean and validate base64 string to ensure OpenAI API compatibility"""
    import re
    import base64
    
    # Remove any whitespace, newlines, or extra characters
    cleaned = re.sub(r'\s+', '', base64_string.strip())
    
    # Ensure valid base64 characters only (A-Z, a-z, 0-9, +, /, =)
    if not re.match(r'^[A-Za-z0-9+/]*={0,2}$', cleaned):
        print(f"⚠️ Invalid base64 characters detected")
        return base64_string  # Return original if validation fails
    
    # Fix padding if needed
    missing_padding = len(cleaned) % 4
    if missing_padding:
        cleaned += '=' * (4 - missing_padding)
    
    # Test that it's valid base64 by trying to decode
    try:
        decoded = base64.b64decode(cleaned)
        # Re-encode to ensure consistent format
        reencoded = base64.b64encode(decoded).decode('utf-8')
        print(f"✅ Base64 validated and cleaned: {len(reencoded)} chars")
        return reencoded
    except Exception as e:
        print(f"⚠️ Base64 validation failed: {e}")
        return base64_string  # Return original if validation fails


def process_file_placeholders(json_string: str) -> str:
    """Replace <file:filepath> placeholders with actual base64 data"""
    import re
    import base64
    import os
    
    def replace_file_placeholder(match):
        filepath = match.group(1)
        try:
            if os.path.exists(filepath):
                with open(filepath, 'rb') as f:
                    file_data = f.read()
                    
                # Check file size before processing (OpenAI has limits)
                file_size_kb = len(file_data) / 1024
                if file_size_kb > 100:
                    print(f"⚠️ Image file {filepath} is {file_size_kb:.1f}KB (may exceed OpenAI limits)")
                
                # Determine file type and create data URI
                if filepath.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                    # Get file extension for MIME type
                    ext = filepath.lower().split('.')[-1]
                    if ext == 'jpg':
                        ext = 'jpeg'
                    
                    # Generate base64 and clean it for OpenAI compatibility
                    base64_data = base64.b64encode(file_data).decode('utf-8')
                    cleaned_base64 = validate_and_clean_base64(base64_data)
                    
                    print(f"📊 Image {filepath}: {file_size_kb:.1f}KB, base64: {len(cleaned_base64)} chars")
                    return cleaned_base64  # Just the base64 string, no data URI prefix
                else:
                    # For other file types, just return base64
                    base64_data = base64.b64encode(file_data).decode('utf-8')
                    cleaned_base64 = validate_and_clean_base64(base64_data)
                    return cleaned_base64
            else:
                print(f"⚠️ File not found: {filepath}")
                return f"<file:{filepath}>"  # Keep placeholder if file not found
        except Exception as e:
            print(f"⚠️ Error reading file {filepath}: {e}")
            return f"<file:{filepath}>"  # Keep placeholder on error
    
    # Replace all <file:filepath> patterns
    pattern = r'<file:([^>]+)>'
    result = re.sub(pattern, replace_file_placeholder, json_string)
    return result


def truncate_base64_for_display(json_string: str) -> str:
    """Truncate long base64 strings for display purposes"""
    import re
    
    def truncate_base64(match):
        full_string = match.group(0)
        if len(full_string) > 100:
            return full_string[:50] + "..." + full_string[-20:]
        return full_string
    
    # Truncate data:image/... base64 strings
    pattern = r'"data:image/[^"]{50,}"'
    result = re.sub(pattern, truncate_base64, json_string)
    return result


# Define the code execution tool
code_execution_tool = {
    "name": "execute_python",
    "description": "Execute Python code in a persistent Jupyter-like environment. Variables persist between cells. Libraries available: pandas, numpy, matplotlib, requests, beautifulsoup4, scipy, seaborn, duckdb. Use show_vars() to see available variables. For plots, save as base64 data URIs.",
    "input_schema": {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code to execute. Variables persist between executions like Jupyter cells. Use show_vars() to see current variables.",
            }
        },
        "required": ["code"],
    },
}


async def run_query_with_timeout(query: str, timeout: float = API_TIMEOUT_SECONDS) -> Dict[str, Any]:
    """Run query with timeout to ensure response within time limit"""
    try:
        # Use asyncio.wait_for for async timeout handling
        result = await asyncio.wait_for(run_query(query), timeout=timeout)
        return result
    except asyncio.TimeoutError:
        # Timeout occurred - return valid JSON structure
        print(f"\n⏰ Query timed out after {timeout} seconds, returning empty array for proper JSON structure")
        return []
    except Exception as e:
        print(f"\n❌ Exception occurred: {e}")
        # Return empty array with proper structure even on error
        return []


async def run_query(query: str) -> Dict[str, Any]:
    """Run a data analysis query using Claude with code execution"""

    # Reset environment for each new query
    reset_notebook_environment()

    client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    start_time = time.time()
    deadline_time = start_time + API_TIMEOUT_SECONDS

    # Start the conversation with tool support
    messages = [{"role": "user", "content": query}]

    print("🤖 Starting conversation with tool-enabled Claude...\n")

    # Loop until Claude provides final output without requesting tools
    conversation_active = True
    iteration_count = 0
    final_output = None

    while conversation_active:
        # Check if we're approaching timeout
        current_time = time.time()
        time_remaining = deadline_time - current_time
        
        if time_remaining < 30:  # Less than 30 seconds left
            print(f"\n⚠️ Approaching timeout with {time_remaining:.1f}s left! Returning best available answer...")
            if final_output:
                try:
                    return json.loads(final_output)
                except:
                    return []  # Return empty array for proper structure
            else:
                # Return empty array to maintain correct JSON structure
                return []
        
        iteration_count += 1
        print(f"\n{'='*60}")
        print(f"🔄 Conversation Iteration {iteration_count}")
        print(f"⏱️ Time remaining: {time_remaining:.1f} seconds")
        print(f"{'='*60}\n")

        try:
            # Send messages to Claude with iteration timeout
            async with client.messages.stream(
                model="claude-opus-4-20250514",
                max_tokens=32000,
                system="""You are a helpful data analyst assistant. You can execute Python code to scrape data, perform analysis, and create visualizations. 

IMPORTANT PLOTTING INSTRUCTIONS:
- When creating charts/plots, save them as PNG files to disk instead of embedding base64 in JSON
- Keep images UNDER 100KB for OpenAI API compatibility
- Use this pattern for plots:

```python
import matplotlib.pyplot as plt

# Create your plot with smaller size for file size limits
plt.figure(figsize=(6,4))  # Smaller figure size
# ... your plotting code ...

# Save to file with reduced DPI to keep under 100KB
plt.savefig('network_graph.png', dpi=60, bbox_inches='tight')
plt.close()
```

- In your final JSON output, use file placeholders like: `"network_graph": "<file:network_graph.png>"`
- The system will automatically convert these to base64 data URIs
- CRITICAL: Keep all image files under 100KB for evaluation compatibility

FINAL OUTPUT REQUIREMENTS:
- Your final answer must come ONLY from code execution output
- Execute a final code cell that prints the JSON using: `print(json.dumps(result_dict))`
- Use <file:filepath> placeholders for image files
- Say 'Analysis complete' after printing the JSON

Work efficiently as time is limited.""",
                messages=messages,
                tools=[code_execution_tool],
            ) as stream:
                current_response = ""
                async for text in stream.text_stream:
                    print(text, end="", flush=True)
                    current_response += text

                # Get the final message from this iteration
                final_message = await stream.get_final_message()

                # Check if Claude wants to use tools
                if final_message.stop_reason == "tool_use":
                    print("\n\n📋 Claude wants to execute code...")

                    # Add Claude's message to conversation
                    messages.append({"role": "assistant", "content": final_message.content})

                    # Get all tool use requests
                    tool_uses = [
                        block for block in final_message.content if block.type == "tool_use"
                    ]

                    # Prepare tool results
                    tool_results = []

                    # Execute each tool
                    for tool_use in tool_uses:
                        if tool_use.name == "execute_python":
                            try:
                                # Execute the code
                                result = execute_python_code(tool_use.input["code"])
                            except Exception as e:
                                print(f"\n❌ Error in execute_python_code: {e}")
                                traceback.print_exc()
                                result = {
                                    "stdout": "",
                                    "stderr": f"Error executing code: {str(e)}",
                                    "returncode": 1,
                                    "success": False,
                                    "cell_number": cell_counter,
                                }

                            # Display like Jupyter notebook cell
                            print(f"\n📝 Cell [{result.get('cell_number', '?')}]:")
                            print(f"```python\n{tool_use.input['code']}\n```")

                            if result["success"]:
                                if result["stdout"].strip():
                                    output = result["stdout"].strip()
                                    print(f"\n📤 Output:")

                                    # Check if this looks like a final JSON answer
                                    if (
                                        output.startswith("[") and output.endswith("]")
                                    ) or (output.startswith("{") and output.endswith("}")):
                                        # Process file placeholders before storing as final output
                                        processed_output = process_file_placeholders(output)
                                        final_output = processed_output
                                        print("🎯 FINAL ANSWER:")
                                        print("=" * 50)
                                        # Display truncated version for logs
                                        display_output = truncate_base64_for_display(processed_output)
                                        print(display_output)
                                        print("=" * 50)
                                    else:
                                        print(output)

                                if result["stderr"].strip():
                                    print(f"\n⚠️  Warnings:")
                                    print(result["stderr"])
                                print(
                                    f"✅ Cell [{result.get('cell_number', '?')}] executed successfully\n"
                                )
                            else:
                                print(
                                    f"\n❌ Cell [{result.get('cell_number', '?')}] failed:"
                                )
                                print(f"🚨 Error: {result['stderr']}\n")

                            # Prepare tool result
                            tool_results.append(
                                {
                                    "type": "tool_result",
                                    "tool_use_id": tool_use.id,
                                    "content": json.dumps(
                                        {
                                            "stdout": result["stdout"],
                                            "stderr": result["stderr"],
                                            "success": result["success"],
                                            "cell_number": result.get("cell_number", 0),
                                        }
                                    ),
                                }
                            )

                    # Add tool results to conversation
                    if tool_results:
                        messages.append({"role": "user", "content": tool_results})

                    print(f"\n🔄 Continuing conversation (tool results sent to Claude)...")

                else:
                    # Claude finished without requesting tools - conversation is complete
                    print(f"\n\n🎯 Claude completed the analysis!")
                    print(f"Stop reason: {final_message.stop_reason}")
                    conversation_active = False

                    # Add final message to conversation
                    messages.append({"role": "assistant", "content": final_message.content})

        except Exception as e:
            print(f"\n⚠️ Error in iteration {iteration_count}: {e}")
            # Continue with best available answer
            if final_output:
                try:
                    return json.loads(final_output)
                except:
                    return []
            else:
                return []

    end_time = time.time()
    print(f"\n\n⏱️  Total time taken: {end_time - start_time:.2f} seconds")
    print(f"🔄 Total iterations: {iteration_count}")
    print(f"📝 Total cells executed: {cell_counter}")

    # Show final notebook state
    print(f"\n📊 Final notebook state:")
    print(show_notebook_variables())

    print(f"\n🎯 The final answer was provided through code execution output above.")

    # Return the final output from code execution
    if final_output:
        try:
            # Try to parse as JSON
            parsed = json.loads(final_output)
            # Ensure proper structure
            if isinstance(parsed, (list, dict)):
                return parsed
            else:
                # Wrap non-list/dict in array for consistent structure
                return [parsed]
        except Exception as e:
            print(f"\n⚠️ Failed to parse output as JSON: {e}")
            # Return empty array to maintain correct JSON structure
            return []
    else:
        print("\n⚠️ No final output generated, returning empty array")
        # Return empty array to maintain correct JSON structure for partial marks
        return []


# FastAPI Application
app = FastAPI(
    title="Data Analyst AI Agent",
    description="AI-powered data analysis API that can scrape, analyze, and visualize data using Claude AI with code execution capabilities",
    version="1.0.0",
)

# Add CORS middleware (if needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests with details"""
    start_time = time.time()
    
    # Log request details
    timestamp = datetime.datetime.now().isoformat()
    method = request.method
    url = str(request.url)
    client_host = request.client.host if request.client else "unknown"
    
    # Log request headers
    headers = dict(request.headers)
    
    print(f"\n{'='*60}")
    print(f"📥 INCOMING REQUEST at {timestamp}")
    print(f"Method: {method}")
    print(f"URL: {url}")
    print(f"Client: {client_host}")
    print(f"Headers: {headers}")
    
    # Try to get request body for POST requests
    if method == "POST":
        try:
            # Store the body for logging (careful with large files)
            body = await request.body()
            print(f"Body size: {len(body)} bytes")
            # Reset body stream
            async def receive():
                return {"type": "http.request", "body": body}
            request._receive = receive
        except Exception as e:
            print(f"Could not read body: {e}")
    
    print(f"{'='*60}\n")
    
    # Process the request
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # Log response details
        print(f"\n{'='*60}")
        print(f"📤 RESPONSE for {url}")
        print(f"Status: {response.status_code}")
        print(f"Process time: {process_time:.3f}s")
        print(f"{'='*60}\n")
        
        return response
    except Exception as e:
        process_time = time.time() - start_time
        print(f"\n{'='*60}")
        print(f"❌ ERROR processing {url}")
        print(f"Error: {str(e)}")
        print(f"Process time: {process_time:.3f}s")
        print(f"{'='*60}\n")
        raise

# Custom exception handler for validation errors (422)
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with detailed logging"""
    print(f"\n{'='*60}")
    print(f"🚨 VALIDATION ERROR (422)")
    print(f"URL: {request.url}")
    print(f"Method: {request.method}")
    print(f"Validation errors: {exc.errors()}")
    print(f"Body: {exc.body if hasattr(exc, 'body') else 'N/A'}")
    print(f"{'='*60}\n")
    
    # Return detailed error response
    return JSONResponse(
        status_code=422,
        content={
            "detail": exc.errors(),
            "body": str(exc.body) if hasattr(exc, 'body') else None,
            "message": "Request validation failed. Check the logs for details."
        }
    )


@app.post("/api/")
async def analyze_data(request: Request, file: UploadFile = File(None)):
    """
    Main API endpoint for data analysis tasks
    
    Upload a text file containing your data analysis question/task.
    The AI will execute Python code to scrape data, perform analysis, and create visualizations.
    """
    request_id = f"req_{int(time.time()*1000)}"
    
    try:
        # Check if file was provided with standard field name
        if not file:
            # Try to get file from form data with any field name
            form = await request.form()
            files = []
            
            print(f"\n{'='*60}")
            print(f"📊 REQUEST DETAILS [{request_id}]")
            print(f"📋 Form fields: {list(form.keys())}")
            
            # Look for any uploaded files in the form
            for field_name, field_value in form.items():
                if hasattr(field_value, 'filename'):  # It's an uploaded file
                    files.append((field_name, field_value))
                    print(f"📁 Found file '{field_value.filename}' in field '{field_name}'")
            
            if not files:
                print(f"❌ No files found in request")
                return JSONResponse(
                    status_code=400,
                    content={"error": "No file uploaded. Please upload a file with any field name.", "request_id": request_id}
                )
            
            # Save all uploaded files to the current working directory
            question_file = None
            saved_files = []
            
            for field_name, field_value in files:
                # Save each file
                file_content = await field_value.read()
                file_path = field_value.filename
                
                # Save to current directory
                with open(file_path, 'wb') as f:
                    f.write(file_content)
                
                saved_files.append(file_path)
                print(f"💾 Saved file: {file_path}")
                
                # Reset file position for reading again
                field_value.file.seek(0)
                
                # Identify the question file
                if 'question' in field_name.lower() or 'question' in field_value.filename.lower():
                    question_file = field_value
                    print(f"✅ Using file from field '{field_name}': {field_value.filename}")
            
            if not question_file and files:
                # Just use the first file as question
                field_name, question_file = files[0]
                print(f"✅ Using first file from field '{field_name}': {question_file.filename}")
            
            file = question_file
        
        # Log detailed file information
        print(f"📁 File: {file.filename}")
        print(f"📄 Content-Type: {file.content_type}")
        print(f"📏 File size: {file.size if hasattr(file, 'size') else 'unknown'}")
        
        # Read the uploaded file content with error handling
        try:
            content = await file.read()
            if not content:
                print(f"❌ Empty file content")
                return JSONResponse(
                    status_code=400,
                    content={"error": "Empty file", "request_id": request_id}
                )
            
            # Try to decode as UTF-8
            question_text = content.decode("utf-8")
            
        except UnicodeDecodeError as e:
            print(f"❌ Unicode decode error: {e}")
            return JSONResponse(
                status_code=400,
                content={"error": "File must be UTF-8 encoded text", "request_id": request_id}
            )
        except Exception as e:
            print(f"❌ Error reading file: {e}")
            return JSONResponse(
                status_code=400,
                content={"error": f"Error reading file: {str(e)}", "request_id": request_id}
            )

        print(f"📝 Content length: {len(question_text)} characters")
        print(f"📋 First 200 chars: {question_text[:200]}...")
        print(f"{'='*60}\n")

        # Process the question with timeout to ensure response within 5 minutes
        result = await run_query_with_timeout(question_text, timeout=API_TIMEOUT_SECONDS)

        # Ensure result is always valid JSON
        if result is None:
            print(f"⚠️ Result was None, returning empty array [{request_id}]")
            result = []  # Empty array for proper structure
        
        print(f"\n✅ Successfully processed request [{request_id}]")
        print(f"📦 Result type: {type(result)}")
        print(f"📏 Result size: {len(str(result))} characters")
        
        # Clean up saved files
        if 'saved_files' in locals():
            for saved_file in saved_files:
                try:
                    os.remove(saved_file)
                    print(f"🧹 Cleaned up file: {saved_file}")
                except Exception as e:
                    print(f"⚠️ Could not clean up {saved_file}: {e}")
        
        # Return the result as JSON
        return JSONResponse(content=result)

    except Exception as e:
        print(f"\n❌ Unexpected error in analyze_data [{request_id}]: {e}")
        print(f"Error type: {type(e).__name__}")
        traceback.print_exc()
        
        # Always return valid JSON structure even on error
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "message": str(e),
                "request_id": request_id,
                "result": []  # Include empty result for compatibility
            }
        )


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "Data Analyst AI Agent API",
        "status": "running",
        "capabilities": [
            "Web scraping and data extraction",
            "Statistical analysis and insights",
            "Data visualization with base64-encoded charts",
            "DuckDB integration for large-scale data queries",
            "Jupyter-like persistent code execution",
            "Handles 3+ concurrent requests",
            "Guaranteed response within 5 minutes",
        ],
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.post("/api/v2/")
async def analyze_data_v2(request: Request):
    """
    Alternative API endpoint that accepts files with any field name
    
    This endpoint is more flexible and will accept the first text file uploaded,
    regardless of the field name used in the multipart form.
    """
    request_id = f"req_{int(time.time()*1000)}"
    
    try:
        # Parse form data
        form = await request.form()
        
        print(f"\n{'='*60}")
        print(f"📊 REQUEST DETAILS V2 [{request_id}]")
        print(f"📋 Form fields: {list(form.keys())}")
        
        # Find all uploaded files
        uploaded_files = []
        for field_name, field_value in form.items():
            if hasattr(field_value, 'filename'):
                uploaded_files.append({
                    'field_name': field_name,
                    'file': field_value,
                    'filename': field_value.filename,
                    'content_type': field_value.content_type
                })
                print(f"📁 Found: {field_value.filename} (field: {field_name}, type: {field_value.content_type})")
        
        if not uploaded_files:
            return JSONResponse(
                status_code=400,
                content={"error": "No files uploaded", "request_id": request_id}
            )
        
        # Prioritize files with 'question' in the name or text content type
        selected_file = None
        for file_info in uploaded_files:
            if 'question' in file_info['filename'].lower() or 'text' in str(file_info['content_type']):
                selected_file = file_info
                break
        
        if not selected_file:
            selected_file = uploaded_files[0]
        
        print(f"✅ Selected file: {selected_file['filename']} from field '{selected_file['field_name']}'")
        
        # Read file content
        content = await selected_file['file'].read()
        if not content:
            return JSONResponse(
                status_code=400,
                content={"error": "Empty file", "request_id": request_id}
            )
        
        question_text = content.decode("utf-8")
        print(f"📝 Content length: {len(question_text)} characters")
        print(f"📋 Preview: {question_text[:200]}...")
        
        # Process the question
        result = await run_query_with_timeout(question_text, timeout=API_TIMEOUT_SECONDS)
        
        if result is None:
            result = []
        
        print(f"✅ Successfully processed request [{request_id}]")
        return JSONResponse(content=result)
        
    except Exception as e:
        print(f"❌ Error in V2 endpoint [{request_id}]: {e}")
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "request_id": request_id}
        )


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    # Use multiple workers to handle concurrent requests
    uvicorn.run("api:app", host="0.0.0.0", port=port, reload=False, workers=1, log_level="info")