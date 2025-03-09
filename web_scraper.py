#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import csv
import time
import sys

def scrape_website(url):
    """
    Scrape a website and extract relevant information
    """
    try:
        # Add a user agent to avoid being blocked
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Send a GET request to the URL
        response = requests.get(url, headers=headers, timeout=10)
        
        # Check if the request was successful
        if response.status_code == 200:
            print(f"Successfully connected to {url}")
            # Parse the HTML content
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract information
            # Example: Get all headings
            headings = soup.find_all(['h1', 'h2', 'h3'])
            print(f"Found {len(headings)} headings")
            
            # Example: Get all links
            links = soup.find_all('a', href=True)
            print(f"Found {len(links)} links")
            
            # Example: Get all paragraphs
            paragraphs = soup.find_all('p')
            print(f"Found {len(paragraphs)} paragraphs")
            
            # Save data to CSV
            save_to_csv(headings, links, paragraphs)
            
            return True
        else:
            print(f"Failed to retrieve the page. Status code: {response.status_code}")
            return False
    
    except requests.exceptions.RequestException as e:
        print(f"Error during request: {e}")
        return False
    except Exception as e:
        print(f"An error occurred: {e}")
        return False

def save_to_csv(headings, links, paragraphs):
    """
    Save the scraped data to a CSV file
    """
    try:
        # Save headings
        with open('headings.csv', 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['Heading', 'Text'])
            for heading in headings:
                writer.writerow([heading.name, heading.text.strip()])
        
        # Save links
        with open('links.csv', 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['Text', 'URL'])
            for link in links:
                writer.writerow([link.text.strip(), link['href']])
        
        # Save paragraphs
        with open('paragraphs.csv', 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['Paragraph'])
            for p in paragraphs:
                writer.writerow([p.text.strip()])
        
        print("Data saved to CSV files")
    
    except Exception as e:
        print(f"Error saving to CSV: {e}")

def main():
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = input("Enter the URL to scrape (e.g., https://example.com): ")
    
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    print(f"Starting to scrape {url}...")
    scrape_website(url)
    print("Scraping completed!")

if __name__ == "__main__":
    main()
