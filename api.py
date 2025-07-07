import time
import subprocess
import sys
import tempfile
import os
import json
import base64
from anthropic import Anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
from typing import Dict, Any

load_dotenv()

# Global execution environment (like Jupyter notebook)
notebook_globals = {}
notebook_initialized = False
cell_counter = 0


def initialize_notebook_environment():
    """Initialize the notebook environment with common imports"""
    global notebook_globals, notebook_initialized

    if not notebook_initialized:
        initialization_code = """
            import sys
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


def run_query(query: str) -> Dict[str, Any]:
    """Run a data analysis query using Claude with code execution"""

    # Reset environment for each new query
    reset_notebook_environment()

    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    start_time = time.time()

    # Start the conversation with tool support
    messages = [{"role": "user", "content": query}]

    print("🤖 Starting conversation with tool-enabled Claude...\n")

    # Loop until Claude provides final output without requesting tools
    conversation_active = True
    iteration_count = 0
    final_response = ""
    final_output = None

    while conversation_active:
        iteration_count += 1
        print(f"\n{'='*60}")
        print(f"🔄 Conversation Iteration {iteration_count}")
        print(f"{'='*60}\n")

        # Send messages to Claude
        with client.messages.stream(
            model="claude-opus-4-20250514",
            max_tokens=32000,
            system="You are a helpful data analyst assistant. You can execute Python code to scrape data, perform analysis, and create visualizations. IMPORTANT: Your final answer must come ONLY from code execution output - do not write the JSON result in your text response. Execute a final code cell that prints the JSON array/object, and that printed output will be the official answer. When you have completed the analysis, execute one final cell that prints only the JSON result, then say 'Analysis complete' without repeating the answer.",
            messages=messages,
            tools=[code_execution_tool],
        ) as stream:
            current_response = ""
            for text in stream.text_stream:
                print(text, end="", flush=True)
                current_response += text

            # Get the final message from this iteration
            final_message = stream.get_final_message()

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
                        # Execute the code
                        result = execute_python_code(tool_use.input["code"])

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
                                    final_output = output
                                    print("🎯 FINAL ANSWER:")
                                    print("=" * 50)
                                    print(output)
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

                final_response = current_response

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
            return json.loads(final_output)
        except:
            # If not valid JSON, return as string
            return {"result": final_output}
    else:
        return {"error": "No final output generated", "claude_response": final_response}


# FastAPI Application
app = FastAPI(
    title="Data Analyst AI Agent",
    description="AI-powered data analysis API that can scrape, analyze, and visualize data using Claude AI with code execution capabilities",
    version="1.0.0",
)


@app.post("/api/")
async def analyze_data(file: UploadFile = File(...)):
    """
    Main API endpoint for data analysis tasks

    Upload a text file containing your data analysis question/task.
    The AI will execute Python code to scrape data, perform analysis, and create visualizations.
    """
    try:
        # Read the uploaded file content
        content = await file.read()
        question_text = content.decode("utf-8")

        print(f"\n🔍 Received analysis request:")
        print(f"📁 File: {file.filename}")
        print(f"📝 Content length: {len(question_text)} characters")
        print(f"{'='*60}")

        # Process the question using our notebook-style execution
        result = run_query(question_text)

        # Return the result as JSON
        return JSONResponse(content=result)

    except Exception as e:
        print(f"❌ Error processing request: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
        ],
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("api:app", host="0.0.0.0", port=port, reload=True, log_level="info")
