#!/bin/bash

# Test script to verify API works with curl (simulating the testing environment)

API_URL="http://localhost:8000/api/"
echo "🧪 Testing API with curl commands..."
echo "API URL: $API_URL"
echo "=" $(printf "%0.s=" {1..60})

# Function to send a curl request
send_curl_request() {
    local file_path=$1
    local request_id=$2
    
    echo "🚀 Request $request_id: Starting with file $file_path..."
    
    start_time=$(date +%s)
    response=$(curl -s -w "\n%{http_code}\n%{time_total}" \
        -X POST \
        -F "file=@$file_path" \
        "$API_URL" 2>/dev/null)
    
    # Parse response (last 2 lines are status code and time)
    status_code=$(echo "$response" | tail -n 2 | head -n 1)
    time_total=$(echo "$response" | tail -n 1)
    json_response=$(echo "$response" | head -n -2)
    
    if [ "$status_code" = "200" ]; then
        echo "✅ Request $request_id: SUCCESS (${time_total}s)"
        echo "   Response: $json_response"
    else
        echo "❌ Request $request_id: FAILED (${time_total}s) - Status: $status_code"
        echo "   Response: $json_response"
    fi
    echo ""
}

# Test API health first
echo "🏥 Checking API health..."
health_response=$(curl -s -w "%{http_code}" http://localhost:8000/health 2>/dev/null)
health_status=$(echo "$health_response" | tail -c 4)

if [ "$health_status" = "200" ]; then
    echo "✅ API health check passed"
else
    echo "❌ API health check failed. Make sure the API is running on localhost:8000"
    echo "Start the API with: python api.py"
    exit 1
fi

echo ""
echo "🚀 Sending sequential test requests..."
echo ""

# Send test requests sequentially
send_curl_request "test_question1.txt" 1
send_curl_request "test_question2.txt" 2  
send_curl_request "test_question3.txt" 3

echo "=" $(printf "%0.s=" {1..60})
echo "✅ All curl tests completed!"
echo ""
echo "To test concurrent requests, run: python test_concurrent.py"