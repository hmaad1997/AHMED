"""
Test script for the API endpoints
Run this after starting the server to verify everything works
"""

import requests
from pathlib import Path
import json


API_BASE = "http://localhost:8000"


def test_health_check():
    """Test the health check endpoint"""
    print("\n" + "="*60)
    print("TEST 1: Health Check")
    print("="*60)
    
    try:
        response = requests.get(f"{API_BASE}/health")
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Failed: {str(e)}")
        return False


def test_list_reciters():
    """Test listing all reciters"""
    print("\n" + "="*60)
    print("TEST 2: List Reciters")
    print("="*60)
    
    try:
        response = requests.get(f"{API_BASE}/list-reciters")
        print(f"Status: {response.status_code}")
        
        data = response.json()
        print(f"Total Reciters: {data['total_reciters']}")
        
        if data['reciters']:
            print("\nFirst 3 reciters:")
            for reciter in data['reciters'][:3]:
                print(f"  - {reciter['name']} ({reciter['name_english']})")
        
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Failed: {str(e)}")
        return False


def test_identify_reciter(audio_file_path: str):
    """Test reciter identification with an audio file"""
    print("\n" + "="*60)
    print("TEST 3: Identify Reciter")
    print("="*60)
    
    audio_path = Path(audio_file_path)
    
    if not audio_path.exists():
        print(f"❌ Audio file not found: {audio_file_path}")
        print("\nTo test this endpoint:")
        print("  1. Record a short audio clip (5-10 seconds) of Quran recitation")
        print("  2. Save it as a WAV or MP3 file")
        print("  3. Run: python test_api.py <path_to_audio_file>")
        return False
    
    try:
        print(f"Uploading: {audio_path.name}")
        
        with open(audio_path, 'rb') as f:
            files = {'audio_file': (audio_path.name, f, 'audio/wav')}
            response = requests.post(f"{API_BASE}/identify-reciter", files=files)
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n✓ Identified Reciter:")
            print(f"  Name: {data['reciter_name']}")
            print(f"  English: {data['reciter_name_english']}")
            print(f"  Confidence: {data['confidence']:.2%}")
            print(f"  Country: {data['country']}")
            print(f"  Style: {data['recitation_style']}")
            print(f"  Similarity Score: {data['similarity_score']:.4f}")
        else:
            print(f"Response: {response.json()}")
        
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Failed: {str(e)}")
        return False


def test_stats():
    """Test stats endpoint"""
    print("\n" + "="*60)
    print("TEST 4: Database Stats")
    print("="*60)
    
    try:
        response = requests.get(f"{API_BASE}/stats")
        print(f"Status: {response.status_code}")
        print(f"Stats: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Failed: {str(e)}")
        return False


def main():
    """Run all tests"""
    import sys
    
    print("="*60)
    print("QURAN RECITER ID - API TESTS")
    print("="*60)
    print("\nMake sure the server is running:")
    print("  python run_server.py")
    print()
    
    # Run tests
    results = []
    
    results.append(("Health Check", test_health_check()))
    results.append(("Stats", test_stats()))
    results.append(("List Reciters", test_list_reciters()))
    
    # Test identification if audio file provided
    if len(sys.argv) > 1:
        audio_file = sys.argv[1]
        results.append(("Identify Reciter", test_identify_reciter(audio_file)))
    else:
        print("\n" + "="*60)
        print("TEST 3: Identify Reciter - SKIPPED")
        print("="*60)
        print("Provide an audio file to test identification:")
        print("  python test_api.py <path_to_audio_file.wav>")
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    for test_name, passed in results:
        status = "✓ PASSED" if passed else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    total_passed = sum(1 for _, passed in results if passed)
    print(f"\nTotal: {total_passed}/{len(results)} tests passed")


if __name__ == "__main__":
    main()
