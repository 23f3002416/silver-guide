#!/usr/bin/env python3
"""
Python version of promptfoo evaluation for Data Analyst AI Agent
This script tests the API and provides scoring similar to promptfoo.
"""

import requests
import json
import time
import re
import sys
from typing import Dict, Any, List, Tuple

class APIEvaluator:
    def __init__(self, api_url: str = "http://localhost:8000/api/"):
        self.api_url = api_url
        self.total_score = 0
        self.max_score = 20
        self.results = []
    
    def test_api_health(self) -> bool:
        """Check if the API is running"""
        try:
            response = requests.get("http://localhost:8000/health", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def send_request(self, question_file: str = "question.txt") -> Tuple[bool, Any]:
        """Send request to API and get response"""
        try:
            with open(question_file, 'rb') as f:
                files = {'file': (question_file, f, 'text/plain')}
                
                print(f"📤 Sending request to {self.api_url}")
                print(f"📁 File: {question_file}")
                
                start_time = time.time()
                response = requests.post(self.api_url, files=files, timeout=300)
                end_time = time.time()
                
                print(f"⏱️  Request took: {end_time - start_time:.2f} seconds")
                print(f"📊 Status Code: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"✅ Response received: {type(result)}")
                    return True, result
                else:
                    print(f"❌ API Error: {response.status_code}")
                    print(f"Response: {response.text[:500]}...")
                    return False, response.text
                    
        except Exception as e:
            print(f"❌ Request failed: {e}")
            return False, str(e)
    
    def evaluate_structural_check(self, response: Any) -> Tuple[bool, str]:
        """Check if response is a 4-element JSON array"""
        try:
            if isinstance(response, list) and len(response) == 4:
                return True, "✅ Valid 4-element JSON array"
            else:
                return False, f"❌ Expected 4-element array, got {type(response)} with {len(response) if hasattr(response, '__len__') else 'unknown'} elements"
        except:
            return False, "❌ Invalid JSON structure"
    
    def evaluate_first_answer(self, response: Any) -> Tuple[bool, int, str]:
        """Check if first answer equals 1 (4 points)"""
        try:
            if isinstance(response, list) and len(response) >= 1:
                first_answer = response[0]
                if first_answer == 1:
                    return True, 4, f"✅ First answer is 1 (got: {first_answer})"
                else:
                    return False, 0, f"❌ First answer should be 1 (got: {first_answer})"
            else:
                return False, 0, "❌ Cannot access first element"
        except Exception as e:
            return False, 0, f"❌ Error evaluating first answer: {e}"
    
    def evaluate_second_answer(self, response: Any) -> Tuple[bool, int, str]:
        """Check if second answer contains 'Titanic' (4 points)"""
        try:
            if isinstance(response, list) and len(response) >= 2:
                second_answer = str(response[1])
                if re.search(r'titanic', second_answer, re.I):
                    return True, 4, f"✅ Second answer contains 'Titanic' (got: {second_answer})"
                else:
                    return False, 0, f"❌ Second answer should contain 'Titanic' (got: {second_answer})"
            else:
                return False, 0, "❌ Cannot access second element"
        except Exception as e:
            return False, 0, f"❌ Error evaluating second answer: {e}"
    
    def evaluate_third_answer(self, response: Any) -> Tuple[bool, int, str]:
        """Check if third answer is within ±0.001 of 0.485782 (4 points)"""
        try:
            if isinstance(response, list) and len(response) >= 3:
                third_answer = float(response[2])
                expected = 0.485782
                if abs(third_answer - expected) <= 0.001:
                    return True, 4, f"✅ Third answer within range (got: {third_answer}, expected: {expected})"
                else:
                    return False, 0, f"❌ Third answer out of range (got: {third_answer}, expected: {expected})"
            else:
                return False, 0, "❌ Cannot access third element"
        except Exception as e:
            return False, 0, f"❌ Error evaluating third answer: {e}"
    
    def evaluate_fourth_answer(self, response: Any) -> Tuple[bool, int, str]:
        """Check if fourth answer is a valid base64 data URI under 100KB (8 points)"""
        try:
            if isinstance(response, list) and len(response) >= 4:
                fourth_answer = str(response[3])
                
                # Check if it's a data URI
                is_data_uri = fourth_answer.startswith('data:image/')
                
                # Check size
                is_reasonable_size = len(fourth_answer) < 100000
                
                if is_data_uri and is_reasonable_size:
                    return True, 8, f"✅ Fourth answer is valid data URI ({len(fourth_answer)} chars)"
                elif not is_data_uri:
                    return False, 0, f"❌ Fourth answer is not a data URI (starts with: {fourth_answer[:50]}...)"
                else:
                    return False, 0, f"❌ Fourth answer too large ({len(fourth_answer)} chars, max 100000)"
            else:
                return False, 0, "❌ Cannot access fourth element"
        except Exception as e:
            return False, 0, f"❌ Error evaluating fourth answer: {e}"
    
    def run_evaluation(self, question_file: str = "question.txt") -> Dict[str, Any]:
        """Run complete evaluation"""
        print("🧪 Starting Data Analyst AI Agent Evaluation")
        print("=" * 60)
        
        # Check API health
        print("\n1️⃣ Checking API health...")
        if not self.test_api_health():
            return {
                "success": False,
                "error": "API is not running or not healthy",
                "score": 0,
                "max_score": self.max_score
            }
        print("✅ API is healthy")
        
        # Send request
        print("\n2️⃣ Sending evaluation request...")
        success, response = self.send_request(question_file)
        
        if not success:
            return {
                "success": False,
                "error": f"Request failed: {response}",
                "score": 0,
                "max_score": self.max_score
            }
        
        print(f"\n📋 Raw Response:")
        print(f"{json.dumps(response, indent=2)[:500]}...")
        
        # Structural check (no points, but must pass)
        print("\n3️⃣ Running evaluations...")
        structural_ok, structural_msg = self.evaluate_structural_check(response)
        print(f"📊 Structural Check: {structural_msg}")
        
        if not structural_ok:
            return {
                "success": False,
                "error": "Failed structural check",
                "details": structural_msg,
                "score": 0,
                "max_score": self.max_score
            }
        
        # Individual tests
        tests = [
            ("First Answer (==1)", self.evaluate_first_answer),
            ("Second Answer (contains 'Titanic')", self.evaluate_second_answer),
            ("Third Answer (correlation ≈0.485782)", self.evaluate_third_answer),
            ("Fourth Answer (valid data URI)", self.evaluate_fourth_answer)
        ]
        
        total_score = 0
        detailed_results = []
        
        for test_name, test_func in tests:
            passed, points, message = test_func(response)
            total_score += points
            
            detailed_results.append({
                "test": test_name,
                "passed": passed,
                "points": points,
                "message": message
            })
            
            print(f"🎯 {test_name}: {message} ({points} pts)")
        
        # Final results
        print("\n" + "=" * 60)
        print("📊 EVALUATION RESULTS")
        print("=" * 60)
        
        for result in detailed_results:
            status = "✅ PASS" if result["passed"] else "❌ FAIL"
            print(f"{status} {result['test']}: {result['points']} pts")
        
        print(f"\n🏆 TOTAL SCORE: {total_score}/{self.max_score} ({(total_score/self.max_score)*100:.1f}%)")
        
        if total_score == self.max_score:
            print("🎉 PERFECT SCORE! All tests passed!")
        elif total_score >= 16:
            print("🌟 Excellent! Almost perfect score!")
        elif total_score >= 12:
            print("👍 Good! Most tests passed!")
        elif total_score >= 8:
            print("⚠️  Needs improvement. Some tests failed.")
        else:
            print("❌ Significant issues found. Please check your implementation.")
        
        return {
            "success": True,
            "score": total_score,
            "max_score": self.max_score,
            "percentage": (total_score/self.max_score)*100,
            "detailed_results": detailed_results,
            "response": response
        }

def main():
    """Main execution function"""
    evaluator = APIEvaluator()
    
    # Check command line arguments
    question_file = "question.txt"
    if len(sys.argv) > 1:
        question_file = sys.argv[1]
    
    try:
        results = evaluator.run_evaluation(question_file)
        
        # Exit with appropriate code
        if results["success"] and results["score"] == results["max_score"]:
            sys.exit(0)  # Perfect score
        elif results["success"]:
            sys.exit(1)  # Partial score
        else:
            sys.exit(2)  # Failed
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Evaluation interrupted by user")
        sys.exit(3)
    except Exception as e:
        print(f"\n\n❌ Evaluation failed with error: {e}")
        sys.exit(4)

if __name__ == "__main__":
    main() 