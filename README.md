# Data Analyst Agent API

An AI-powered data analysis API that can scrape, analyze, and visualize data using Claude AI.

## Features

- Web scraping and data extraction
- Statistical analysis and insights
- Data visualization with base64-encoded charts
- DuckDB integration for large-scale data queries
- Support for various data formats

## Setup

1. Clone the repository:
```bash
git clone <your-repo-url>
cd td_proj_2
```

2. Set up environment variables:
```bash
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

3. Install dependencies using uv:
```bash
pip install uv
uv sync
```

## Running the API

### Local Development

```bash
uv run python -m src.main
```

The API will be available at `http://localhost:8000`

### Using Docker

```bash
docker build -t data-analyst-agent .
docker run -p 8000:8000 -e ANTHROPIC_API_KEY=your_key data-analyst-agent
```

## API Usage

Send a POST request to `/api/` with a text file containing your analysis question:

```bash
curl "http://localhost:8000/api/" -F "file=@question.txt"
```

## Testing

Run tests with:
```bash
uv run pytest tests/
```

Test the API endpoint:
```bash
uv run python test_api.py
```

## Deployment

The application can be deployed to any platform that supports Docker or Python applications:

- **Heroku**: Use the included Dockerfile
- **AWS Lambda**: Use FastAPI with Mangum
- **Google Cloud Run**: Deploy the Docker container
- **Railway/Render**: Direct deployment from GitHub

## License

MIT