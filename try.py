import time
import subprocess
import sys
import tempfile
import os
import json
import base64
from anthropic import Anthropic
from dotenv import load_dotenv

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
    variables = {k: type(v).__name__ for k, v in notebook_globals.items() 
                if not k.startswith('__') and not callable(v)}
    return f"Available variables: {variables}" if variables else "No user variables defined yet"

def execute_python_code(code: str) -> dict:
    """Execute Python code in persistent environment (like Jupyter cells)"""
    global notebook_globals, cell_counter
    
    # Initialize environment if needed
    initialize_notebook_environment()
    
    # Increment cell counter
    cell_counter += 1
    
    try:
        # Add special notebook functions to the environment
        notebook_globals['show_vars'] = lambda: print(show_notebook_variables())
        notebook_globals['_cell_num'] = cell_counter
        
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
            "cell_number": cell_counter
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
            "cell_number": cell_counter
        }

# Define the code execution tool
code_execution_tool = {
    "name": "execute_python",
    "description": "Execute Python code in a persistent Jupyter-like environment. Variables persist between cells. Libraries available: pandas, numpy, matplotlib, requests, beautifulsoup4, scipy, seaborn. Use show_vars() to see available variables. For plots, save as base64 data URIs.",
    "input_schema": {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code to execute. Variables persist between executions like Jupyter cells. Use show_vars() to see current variables."
            }
        },
        "required": ["code"]
    }
}

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

queries = [
    """
Scrape the list of highest grossing films from Wikipedia. It is at the URL:
https://en.wikipedia.org/wiki/List_of_highest-grossing_films

Answer the following questions and respond with a JSON array of strings containing the answer.

1. How many $2 bn movies were released before 2020?
2. Which is the earliest film that grossed over $1.5 bn?
3. What's the correlation between the Rank and Peak?
4. Draw a scatterplot of Rank and Peak along with a dotted red regression line through it.
   Return as a base-64 encoded data URI, `"data:image/png;base64,iVBORw0KG..."` under 100,000 bytes.

IMPORTANT: 
- Use the execute_python tool to perform all analysis
- Your FINAL response should NOT repeat the answer in text
- Instead, execute a final code cell that prints ONLY the JSON array result
- The printed output from that final cell will be the official answer
- Do not write the JSON array in your text response - let the code output provide it
"""
,
 """
The Indian high court judgement dataset contains judgements from the Indian High Courts, downloaded from [ecourts website](https://judgments.ecourts.gov.in/). It contains judgments of 25 high courts, along with raw metadata (as .json) and structured metadata (as .parquet).

- 25 high courts
- ~16M judgments
- ~1TB of data

Structure of the data in the bucket:

- `data/pdf/year=2025/court=xyz/bench=xyz/judgment1.pdf,judgment2.pdf`
- `metadata/json/year=2025/court=xyz/bench=xyz/judgment1.json,judgment2.json`
- `metadata/parquet/year=2025/court=xyz/bench=xyz/metadata.parquet`
- `metadata/tar/year=2025/court=xyz/bench=xyz/metadata.tar.gz`
- `data/tar/year=2025/court=xyz/bench=xyz/pdfs.tar`

This DuckDB query counts the number of decisions in the dataset.

```sql
INSTALL httpfs; LOAD httpfs;
INSTALL parquet; LOAD parquet;

SELECT COUNT(*) FROM read_parquet('s3://indian-high-court-judgments/metadata/parquet/year=*/court=*/bench=*/metadata.parquet?s3_region=ap-south-1');
```

Here are the columns in the data:

| Column                 | Type    | Description                    |
| ---------------------- | ------- | ------------------------------ |
| `court_code`           | VARCHAR | Court identifier (e.g., 33~10) |
| `title`                | VARCHAR | Case title and parties         |
| `description`          | VARCHAR | Case description               |
| `judge`                | VARCHAR | Presiding judge(s)             |
| `pdf_link`             | VARCHAR | Link to judgment PDF           |
| `cnr`                  | VARCHAR | Case Number Register           |
| `date_of_registration` | VARCHAR | Registration date              |
| `decision_date`        | DATE    | Date of judgment               |
| `disposal_nature`      | VARCHAR | Case outcome                   |
| `court`                | VARCHAR | Court name                     |
| `raw_html`             | VARCHAR | Original HTML content          |
| `bench`                | VARCHAR | Bench identifier               |
| `year`                 | BIGINT  | Year partition                 |

Here is a sample row:

```json
{
  "court_code": "33~10",
  "title": "CRL MP(MD)/4399/2023 of Vinoth Vs The Inspector of Police",
  "description": "No.4399 of 2023 BEFORE THE MADURAI BENCH OF MADRAS HIGH COURT ( Criminal Jurisdiction ) Thursday, ...",
  "judge": "HONOURABLE  MR JUSTICE G.K. ILANTHIRAIYAN",
  "pdf_link": "court/cnrorders/mdubench/orders/HCMD010287762023_1_2023-03-16.pdf",
  "cnr": "HCMD010287762023",
  "date_of_registration": "14-03-2023",
  "decision_date": "2023-03-16",
  "disposal_nature": "DISMISSED",
  "court": "33_10",
  "raw_html": "<button type='button' role='link'..",
  "bench": "mdubench",
  "year": 2023
}
```
"""

,
"""
Answer the following questions and respond with a JSON object containing the answer.

```json
{
  "Which high court disposed the most cases from 2019 - 2022?": "...",
  "What's the regression slope of the date_of_registration - decision_date by year in the court=33_10?": "...",
  "Plot the year and # of days of delay from the above question as a scatterplot with a regression line. Encode as a base64 data URI under 100,000 characters": "data:image/webp:base64,..."
}
```
"""
]

query = queries[2]
start_time = time.time()

def run_query(query):


    # Start the conversation with tool support
    messages = [{"role": "user", "content": query}]

    print("🤖 Starting conversation with tool-enabled Claude...\n")

    # Loop until Claude provides final output without requesting tools
    conversation_active = True
    iteration_count = 0

    while conversation_active:
        iteration_count += 1
        print(f"\n{'='*60}")
        print(f"🔄 Conversation Iteration {iteration_count}")
        print(f"{'='*60}\n")
        
        # Send messages to Claude
        with client.messages.stream(
            model="claude-opus-4-20250514",
            max_tokens=32000,
            system="You are a helpful data analyst assistant. You can execute Python code to scrape data, perform analysis, and create visualizations. IMPORTANT: Your final answer must come ONLY from code execution output - do not write the JSON result in your text response. Execute a final code cell that prints the JSON array, and that printed output will be the official answer. When you have completed the analysis, execute one final cell that prints only the JSON result, then say 'Analysis complete' without repeating the answer.",
            messages=messages,
            tools=[code_execution_tool]
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
                messages.append({
                    "role": "assistant", 
                    "content": final_message.content
                })
                
                # Get all tool use requests
                tool_uses = [block for block in final_message.content if block.type == "tool_use"]
                
                # Prepare tool results
                tool_results = []
                
                # Execute each tool
                for tool_use in tool_uses:
                    if tool_use.name == "execute_python":
                        # Execute the code
                        result = execute_python_code(tool_use.input['code'])
                        
                        # Display like Jupyter notebook cell
                        print(f"\n📝 Cell [{result.get('cell_number', '?')}]:")
                        print(f"```python\n{tool_use.input['code']}\n```")
                        
                        if result['success']:
                            if result['stdout'].strip():
                                output = result['stdout'].strip()
                                print(f"\n📤 Output:")
                                
                                # Check if this looks like the final JSON answer
                                if (output.startswith('[') and output.endswith(']') and 
                                    output.count(',') >= 3):  # Likely the 4-element JSON array
                                    print("🎯 FINAL ANSWER:")
                                    print("=" * 50)
                                    print(output)
                                    print("=" * 50)
                                else:
                                    print(output)
                                    
                            if result['stderr'].strip():
                                print(f"\n⚠️  Warnings:")
                                print(result['stderr'])
                            print(f"✅ Cell [{result.get('cell_number', '?')}] executed successfully\n")
                        else:
                            print(f"\n❌ Cell [{result.get('cell_number', '?')}] failed:")
                            print(f"🚨 Error: {result['stderr']}\n")
                        
                        # Prepare tool result
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": json.dumps({
                                "stdout": result['stdout'],
                                "stderr": result['stderr'],
                                "success": result['success'],
                                "cell_number": result.get('cell_number', 0)
                            })
                        })
                
                # Add tool results to conversation
                if tool_results:
                    messages.append({
                        "role": "user",
                        "content": tool_results
                    })
                
                print(f"\n🔄 Continuing conversation (tool results sent to Claude)...")
                
            else:
                # Claude finished without requesting tools - conversation is complete
                print(f"\n\n🎯 Claude completed the analysis!")
                print(f"Stop reason: {final_message.stop_reason}")
                conversation_active = False
                
                # Add final message to conversation
                messages.append({
                    "role": "assistant", 
                    "content": final_message.content
                })
                
                # Try to parse the final response
                final_response = current_response
                print(f"\n{'='*60}")
                print("📋 FINAL RESPONSE:")
                print(f"{'='*60}")
                print(final_response)
                

    end_time = time.time()
    print(f"\n\n⏱️  Total time taken: {end_time - start_time:.2f} seconds")
    print(f"🔄 Total iterations: {iteration_count}")
    print(f"📝 Total cells executed: {cell_counter}")

    # Show final notebook state
    print(f"\n📊 Final notebook state:")
    print(show_notebook_variables())

    print(f"\n🎯 The final answer was provided through code execution output above.")
    return final_response



