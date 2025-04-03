#!/usr/bin/env python3
"""
Test script to verify the template loading functionality
"""

import os
import sys
from pathlib import Path

# Add the project root to sys.path
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))

# Import the template loading function
from cai.util import get_template_content, load_prompt_template

def test_template_loading():
    """Test that templates can be loaded correctly"""
    print("Testing template loading...")
    
    # Test getting raw template content
    try:
        content = get_template_content("prompts/system_bug_bounter.md")
        print(f"Successfully loaded raw template content: {content[:50]}...")
    except Exception as e:
        print(f"Error loading raw template: {str(e)}")
        
    # Test loading and rendering a template
    try:
        rendered = load_prompt_template("prompts/system_bug_bounter.md")
        print(f"Successfully loaded and rendered template: {rendered[:50]}...")
    except Exception as e:
        print(f"Error rendering template: {str(e)}")
    
    # Test with 'cai/' prefix in the path
    try:
        content = get_template_content("cai/prompts/system_bug_bounter.md")
        print(f"Successfully loaded template with 'cai/' prefix: {content[:50]}...")
    except Exception as e:
        print(f"Error loading template with 'cai/' prefix: {str(e)}")
    
    # Test rendering with 'cai/' prefix in the path
    try:
        rendered = load_prompt_template("cai/prompts/system_bug_bounter.md")
        print(f"Successfully rendered template with 'cai/' prefix: {rendered[:50]}...")
    except Exception as e:
        print(f"Error rendering template with 'cai/' prefix: {str(e)}")
        
    # Test from a different directory
    try:
        os.chdir('/tmp')
        content = get_template_content("prompts/system_bug_bounter.md")
        print(f"Successfully loaded template from different directory: {content[:50]}...")
    except Exception as e:
        print(f"Error loading template from different directory: {str(e)}")
    
    # Return to original directory
    os.chdir(project_root)
        
    print("Template loading tests completed.")

if __name__ == "__main__":
    test_template_loading() 