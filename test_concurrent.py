#!/usr/bin/env python3
"""
Test script to verify the API can handle 3 concurrent requests
"""

import requests
import time
import threading
from concurrent.futures import ThreadPoolExecutor
import tempfile
import os

# Test data for different types of requests
test_questions = [
    """
    Scrape the Wikipedia page "List of highest-grossing films" and answer:
    1. What are the top 5 highest-grossing films of all time?
    2. What is the total gross revenue of these top 5 films?
    3. Which film has the highest worldwide gross?
    
    Return results as a JSON array with each answer as a separate object.
    """,
    
    """
    Create a simple analysis of the Fibonacci sequence:
    1. Generate the first 10 Fibonacci numbers
    2. Calculate the ratio between consecutive numbers
    3. Create a visualization showing the golden ratio convergence
    
    Return results as JSON array with the numbers and ratios.
    """,
    
    """
    Perform a basic statistical analysis:
    1. Generate 100 random numbers from a normal distribution
    2. Calculate mean, median, and standard deviation
    3. Create a histogram visualization
    
    Return results as JSON with the statistics.
    """
]

API_URL = "http://localhost:8000/api/"

def send_request(question_text, request_id):
    """Send a single request to the API"""
    start_time = time.time()
    
    try:
        # Create temporary file with the question
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(question_text)
            temp_file_path = f.name
        
        # Send request
        print(f"🚀 Request {request_id}: Starting...")
        with open(temp_file_path, 'rb') as f:
            files = {'file': (f'question_{request_id}.txt', f, 'text/plain')}
            response = requests.post(API_URL, files=files, timeout=300)  # 5-minute timeout
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Clean up temp file
        os.unlink(temp_file_path)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Request {request_id}: SUCCESS ({duration:.1f}s)")
            print(f"   Result type: {type(result)}")
            print(f"   Result length: {len(result) if isinstance(result, (list, dict)) else 'N/A'}")
            return {
                "request_id": request_id,
                "success": True,
                "duration": duration,
                "status_code": response.status_code,
                "result_type": type(result).__name__,
                "result_length": len(result) if isinstance(result, (list, dict)) else None
            }
        else:
            print(f"❌ Request {request_id}: FAILED ({duration:.1f}s) - Status: {response.status_code}")
            return {
                "request_id": request_id,
                "success": False,
                "duration": duration,
                "status_code": response.status_code,
                "error": response.text
            }
            
    except Exception as e:
        end_time = time.time()
        duration = end_time - start_time
        print(f"💥 Request {request_id}: ERROR ({duration:.1f}s) - {str(e)}")
        # Clean up temp file if it exists
        if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
        return {
            "request_id": request_id,
            "success": False,
            "duration": duration,
            "error": str(e)
        }

def test_concurrent_requests():
    """Test 3 concurrent requests to the API"""
    print("🧪 Testing concurrent request handling...")
    print(f"API URL: {API_URL}")
    print("=" * 60)
    
    # Test API availability first
    try:
        health_response = requests.get("http://localhost:8000/health", timeout=5)
        if health_response.status_code != 200:
            print("❌ API health check failed. Make sure the API is running on localhost:8000")
            return
        print("✅ API health check passed")
    except Exception as e:
        print(f"❌ API is not accessible: {e}")
        print("Make sure to start the API with: python api.py")
        return
    
    print("\n🚀 Starting 3 concurrent requests...\n")
    
    start_time = time.time()
    
    # Use ThreadPoolExecutor to send requests concurrently
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = []
        for i, question in enumerate(test_questions, 1):
            future = executor.submit(send_request, question, i)
            futures.append(future)
        
        # Wait for all requests to complete
        results = []
        for future in futures:
            try:
                result = future.result(timeout=310)  # 5 minutes + buffer
                results.append(result)
            except Exception as e:
                print(f"💥 Future failed: {e}")
                results.append({
                    "success": False,
                    "error": str(e)
                })
    
    end_time = time.time()
    total_duration = end_time - start_time
    
    print("\n" + "=" * 60)
    print("📊 CONCURRENT REQUEST TEST RESULTS")
    print("=" * 60)
    
    successful_requests = sum(1 for r in results if r.get("success", False))
    
    print(f"Total test duration: {total_duration:.1f} seconds")
    print(f"Successful requests: {successful_requests}/3")
    print(f"Success rate: {(successful_requests/3)*100:.1f}%")
    
    print("\nIndividual request results:")
    for result in results:
        status = "✅ SUCCESS" if result.get("success") else "❌ FAILED"
        duration = result.get("duration", 0)
        req_id = result.get("request_id", "?")
        print(f"  Request {req_id}: {status} ({duration:.1f}s)")
        
        if not result.get("success"):
            error = result.get("error", "Unknown error")
            print(f"    Error: {error}")
    
    # Verify requirements
    print(f"\n🎯 REQUIREMENT VERIFICATION:")
    print(f"✅ All requests completed within 5 minutes: {all(r.get('duration', 999) < 300 for r in results)}")
    print(f"✅ API handles concurrent requests: {successful_requests >= 2}")  # At least 2/3 should succeed
    print(f"✅ Proper JSON structure returned: {all(r.get('result_type') in ['list', 'dict'] for r in results if r.get('success'))}")

if __name__ == "__main__":
    test_concurrent_requests()