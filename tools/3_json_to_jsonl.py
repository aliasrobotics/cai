"""
Convert JSON files to JSONL (JSON Lines) format.

This script converts JSON files containing either single objects or arrays of objects
into JSONL format, where each line contains a single valid JSON object.

Usage:
    Single file:
        JSON_FILE_PATH="path/to/file.json" python3 tools/3_json_to_jsonl.py
    
    Multiple files:
        for file in /path/to/json/files/*.json; do
            JSON_FILE_PATH="$file" python3 tools/3_json_to_jsonl.py
        done

Environment Variables:
    JSON_FILE_PATH: Path to the input JSON file (required)

Output:
    Creates a .jsonl file in the same directory as the input JSON file,
    with the same name but .jsonl extension.
    For example, if input is "/path/to/data.json", 
    output will be "/path/to/data.jsonl"

Example:
    If input is "/home/user/data.json", output will be "/home/user/data.jsonl"
    If input is "./data.json", output will be "./data.jsonl"
    If input is "data.json", output will be "data.jsonl"

Notes:
    - Handles both single JSON objects and arrays of objects
    - Each object in the output file will be on its own line
    - Preserves the original JSON structure of each object
    - The output .jsonl file is always created in the same directory as the input file
"""
import json
import sys
import os

def json_to_jsonl(input_file, output_file):
    # Read the JSON file
    with open(input_file, 'r') as f:
        data = json.load(f)
    
    # Write to JSONL file
    with open(output_file, 'w') as f:
        if isinstance(data, list):
            # If JSON contains a list of objects
            for item in data:
                f.write(json.dumps(item) + '\n')
        else:
            # If JSON contains a single object
            f.write(json.dumps(data) + '\n')

if __name__ == '__main__':
    # Get input JSON file path from environment variable
    json_file = os.getenv("JSON_FILE_PATH")
    if not json_file:
        print("JSON_FILE_PATH environment variable not set. Please set it to the path of your JSON file.")
        print("Example: export JSON_FILE_PATH=path/to/input.json")
        sys.exit(1)

    # Generate output JSONL path by replacing extension
    output_file = os.path.splitext(json_file)[0] + '.jsonl'
    
    try:
        json_to_jsonl(json_file, output_file)
        print(f"Successfully converted {json_file} to {output_file}")
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)