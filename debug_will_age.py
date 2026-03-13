#!/usr/bin/env python3
import requests
import re

def test_will_age_change():
    print("=== Testing Will's Age Change from 4 to 6 ===")
    
    # First, check current state
    print("\n1. Current state:")
    response = requests.get('http://localhost:3112/settings')
    age_inputs = re.findall(r'name="person_age_(\d+)".*?value="([^"]*)"', response.text)
    for person_id, value in age_inputs:
        person_name = "test" if person_id == "1" else "Will"
        print(f"  {person_name} (Person {person_id}): '{value}'")
    
    # Check JSON file before change
    try:
        with open('person_ages.json', 'r') as f:
            print(f"  JSON before: {f.read().strip()}")
    except Exception as e:
        print(f"  Error reading JSON: {e}")
    
    # Try to change Will's age from 4 to 6
    print("\n2. Changing Will's age from 4 to 6:")
    age_data = {
        'save_ages': '1',
        'person_age_1': '8',  # Keep person 1 as is
        'person_age_2': '6',  # Change Will from 4 to 6
    }
    
    print(f"Posting data: {age_data}")
    post_response = requests.post('http://localhost:3112/settings', data=age_data)
    print(f"POST status: {post_response.status_code}")
    
    if "Ages saved successfully" in post_response.text:
        print("✓ Success message found in response")
    else:
        print("✗ Success message NOT found")
    
    # Check JSON file after POST
    try:
        with open('person_ages.json', 'r') as f:
            json_content = f.read().strip()
            print(f"  JSON after POST: {json_content}")
    except Exception as e:
        print(f"  Error reading JSON after POST: {e}")
    
    # Check what the browser shows immediately after POST
    print("\n3. Browser state after POST:")
    get_response = requests.get('http://localhost:3112/settings')
    age_inputs = re.findall(r'name="person_age_(\d+)".*?value="([^"]*)"', get_response.text)
    for person_id, value in age_inputs:
        person_name = "test" if person_id == "1" else "Will"
        expected = "8" if person_id == "1" else "6"
        status = "✓" if value == expected else "✗"
        print(f"  {person_name} (Person {person_id}): '{value}' {status} (expected: {expected})")
    
    # Test a different age to see if the issue is specific to certain numbers
    print("\n4. Testing with a different age (7):")
    age_data = {
        'save_ages': '1',
        'person_age_1': '8',  # Keep person 1 as is
        'person_age_2': '7',  # Try age 7 for Will
    }
    
    post_response = requests.post('http://localhost:3112/settings', data=age_data)
    
    # Check result
    get_response = requests.get('http://localhost:3112/settings')
    age_inputs = re.findall(r'name="person_age_(\d+)".*?value="([^"]*)"', get_response.text)
    for person_id, value in age_inputs:
        if person_id == "2":  # Will
            expected = "7"
            status = "✓" if value == expected else "✗"
            print(f"  Will's age after setting to 7: '{value}' {status} (expected: {expected})")

if __name__ == "__main__":
    test_will_age_change()