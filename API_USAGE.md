# Data Analyst AI Agent API

## 🚀 **Quick Start**

### 1. Start the API Server

```bash
# Using the startup script
python start_api.py

# Or directly with uvicorn
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at: `http://localhost:8000`

### 2. Test the API

```bash
# Test health endpoint
curl http://localhost:8000/health

# Test main API with file upload
curl "http://localhost:8000/api/" -F "file=@question.txt"
```

### 3. Run the Test Suite

```bash
python test_api.py
```

## 📋 **API Endpoints**

### `POST /api/`
**Main analysis endpoint** - Upload a text file with your data analysis task

**Request:**
- Method: `POST`
- Content-Type: `multipart/form-data`
- Body: File upload with key `file`

**Example:**
```bash
curl "http://localhost:8000/api/" \
  -F "file=@question.txt" \
  -H "Accept: application/json"
```

**Response:**
- Content-Type: `application/json`
- Body: JSON array or object with analysis results

### `GET /`
**Root endpoint** - API information and capabilities

### `GET /health`
**Health check** - Simple status check

## 📝 **Sample Questions**

### Wikipedia Films Analysis
```text
Scrape the list of highest grossing films from Wikipedia. It is at the URL:
https://en.wikipedia.org/wiki/List_of_highest-grossing_films

Answer the following questions and respond with a JSON array of strings containing the answer.

1. How many $2 bn movies were released before 2020?
2. Which is the earliest film that grossed over $1.5 bn?
3. What's the correlation between the Rank and Peak?
4. Draw a scatterplot of Rank and Peak along with a dotted red regression line through it.
   Return as a base-64 encoded data URI under 100,000 bytes.
```

### Indian High Court Data Analysis
```text
The Indian high court judgement dataset contains judgements from the Indian High Courts.

Answer the following questions and respond with a JSON object containing the answer.

{
  "Which high court disposed the most cases from 2019 - 2022?": "...",
  "What's the regression slope of the date_of_registration - decision_date by year in the court=33_10?": "...",
  "Plot the year and # of days of delay as a scatterplot with regression line. Encode as base64 data URI": "..."
}
```

## 🎯 **How It Works**

1. **File Upload**: You upload a text file containing your data analysis question
2. **Claude Analysis**: The AI reads your question and plans the analysis approach
3. **Code Execution**: Claude writes and executes Python code in a Jupyter-like environment
4. **Persistent Context**: Variables persist between code cells (like Jupyter notebooks)
5. **Final Output**: The last code cell prints the JSON result, which becomes the API response

## 🔧 **Features**

- **Jupyter-like Execution**: Code runs in persistent environment with variable preservation
- **Auto-loop Processing**: Continues until Claude completes the full analysis
- **Code-Only Output**: Final answers come from code execution, not text duplication
- **Rich Libraries**: pandas, numpy, matplotlib, requests, BeautifulSoup, scipy, seaborn, duckdb
- **Data Visualization**: Base64-encoded charts and plots
- **Web Scraping**: Automatic data extraction from URLs
- **Statistical Analysis**: Correlations, regressions, and insights

## 📊 **Response Formats**

### JSON Array (for sequential questions)
```json
[1, "Titanic", 0.485782, "data:image/png;base64,iVBORw0KG..."]
```

### JSON Object (for named questions)
```json
{
  "Which high court disposed the most cases from 2019 - 2022?": "Madras High Court",
  "What's the regression slope...": 0.025,
  "Plot the year and # of days...": "data:image/webp;base64,UklGRv..."
}
```

## 🛠️ **Environment Setup**

1. **Install Dependencies:**
   ```bash
   pip install uv
   uv sync
   ```

2. **Set API Key:**
   ```bash
   echo "ANTHROPIC_API_KEY=your_key_here" > .env
   ```

3. **Optional Environment Variables:**
   ```bash
   HOST=0.0.0.0          # Server host (default: 0.0.0.0)
   PORT=8000             # Server port (default: 8000)
   RELOAD=true           # Auto-reload on changes (default: true)
   ```

## 🚀 **Deployment**

This API can be deployed to any platform supporting Python/Docker:

- **Railway/Render**: Direct GitHub deployment
- **Heroku**: Using included Dockerfile
- **AWS Lambda**: With Mangum adapter
- **Google Cloud Run**: Docker container deployment

The API automatically binds to `0.0.0.0:$PORT` for cloud deployment compatibility.

## 🧪 **Testing**

The `test_api.py` script provides comprehensive testing:

```bash
python test_api.py
```

This tests:
- Health endpoints
- Main analysis functionality
- Response format validation
- Error handling

## 💡 **Tips**

1. **Complex Analysis**: Break large questions into smaller, focused parts
2. **Data Format**: Specify exactly what JSON format you want in your question
3. **Visualizations**: Request base64 data URIs for images under 100KB
4. **Variable Inspection**: Use `show_vars()` in code to see available variables
5. **Timeout**: Complex analyses may take 2-5 minutes - be patient! 