#!/usr/bin/env python3
# PR‑tracker: counts Copilot / Codex PRs and saves data to CSV.
# Tracks merged PRs (not just approved ones)
# deps: requests

import csv
import datetime as dt
import os
import re
import time
from pathlib import Path
import requests

# GitHub API headers with authentication
def get_headers():
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "PR-Watcher"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers

# Languages to track
LANGUAGES = [
    'all',  # All languages combined (no language filter)
    'javascript', 'typescript', 'python', 'java', 'ruby', 'go', 'php', 
    'c%23', 'c%2B%2B', 'rust', 'f%23'
]

# Agent search patterns
AGENTS = {
    'copilot': {
        'total': 'is:pr+head:copilot/',
        'merged': 'is:pr+head:copilot/+is:merged'
    },
    'codex': {
        'total': 'is:pr+head:codex/',
        'merged': 'is:pr+head:codex/+is:merged'
    },
    'cursor': {
        'total': 'is:pr+head:cursor/',
        'merged': 'is:pr+head:cursor/+is:merged'
    },
    'devin': {
        'total': 'is:pr+author:devin-ai-integration[bot]',
        'merged': 'is:pr+author:devin-ai-integration[bot]+is:merged'
    },
    'codegen': {
        'total': 'is:pr+author:codegen-sh[bot]',
        'merged': 'is:pr+author:codegen-sh[bot]+is:merged'
    }
}


def make_github_request(url, headers, max_retries=3):
    """Make a GitHub API request with rate limiting and retry logic."""
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                return response
            elif response.status_code == 403:
                # Rate limit exceeded
                print(f"    Rate limit hit (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    # Wait longer on each retry (exponential backoff)
                    wait_time = 60 * (2 ** attempt)  # 60s, 120s, 240s
                    print(f"    Waiting {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"    Max retries reached, giving up")
                    return response
            else:
                # Other error, don't retry
                print(f"    Request failed with {response.status_code}: {response.text}")
                return response
                
        except Exception as e:
            print(f"    Request exception (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(10)  # Wait 10 seconds before retry
                continue
            else:
                raise
    
    return None


def collect_data():
    """Collect PR data for all languages and agents from GitHub API."""
    headers = get_headers()
    data = {}
    timestamp = dt.datetime.now(dt.UTC).strftime("%Y-%m-%d %H:%M:%S")
    
    print(f"Collecting data at {timestamp}")
    print("Note: Adding delays between requests to respect GitHub rate limits...")
    
    # Collect data for each language-agent combination
    for language_idx, language in enumerate(LANGUAGES):
        print(f"Processing language {language_idx + 1}/{len(LANGUAGES)}: {language}")
        lang_data = {}
        
        for agent_idx, (agent, patterns) in enumerate(AGENTS.items()):
            try:
                # Add delay between requests to avoid rate limiting
                if agent_idx > 0:  # Don't sleep before the first agent
                    print(f"    Sleeping 2 seconds between requests...")
                    time.sleep(2)
                
                # Get total PRs
                if language == 'all':
                    # For "all" languages, don't include language filter
                    total_query = patterns['total']
                else:
                    # For specific languages, include language filter
                    total_query = f"language:{language}+{patterns['total']}"
                print(f"    Querying total: {total_query}")
                
                total_response = make_github_request(
                    f"https://api.github.com/search/issues?q={total_query}",
                    headers
                )
                
                if total_response is None or total_response.status_code != 200:
                    print(f"    Total query failed")
                    lang_data[f"{agent}_total"] = 0
                    lang_data[f"{agent}_merged"] = 0
                    continue
                
                total_count = total_response.json()["total_count"]
                
                # Small delay between total and merged queries
                time.sleep(1)
                
                # Get merged PRs
                if language == 'all':
                    # For "all" languages, don't include language filter
                    merged_query = patterns['merged']
                else:
                    # For specific languages, include language filter
                    merged_query = f"language:{language}+{patterns['merged']}"
                print(f"    Querying merged: {merged_query}")
                
                merged_response = make_github_request(
                    f"https://api.github.com/search/issues?q={merged_query}",
                    headers
                )
                
                if merged_response is None or merged_response.status_code != 200:
                    print(f"    Merged query failed")
                    lang_data[f"{agent}_total"] = total_count
                    lang_data[f"{agent}_merged"] = 0
                    continue
                
                merged_count = merged_response.json()["total_count"]
                
                lang_data[f"{agent}_total"] = total_count
                lang_data[f"{agent}_merged"] = merged_count
                
                print(f"  ✓ {agent}: {total_count} total, {merged_count} merged")
                
            except Exception as e:
                print(f"  ✗ Error collecting {agent} data for {language}: {e}")
                lang_data[f"{agent}_total"] = 0
                lang_data[f"{agent}_merged"] = 0
        
        data[language] = lang_data
        
        # Add a longer delay between languages to be extra safe
        if language_idx < len(LANGUAGES) - 1:  # Don't sleep after the last language
            print(f"  Sleeping 5 seconds before next language...")
            time.sleep(5)
    
    # Save to CSV
    csv_file = Path("data.csv")
    save_to_csv(data, timestamp, csv_file)
    
    return csv_file


def save_to_csv(data, timestamp, csv_file):
    """Save collected data to CSV file."""
    # Prepare CSV headers
    headers = ["timestamp", "language"]
    for agent in AGENTS.keys():
        headers.extend([f"{agent}_total", f"{agent}_merged"])
    
    # Check if file exists
    is_new_file = not csv_file.exists()
    
    with csv_file.open("a", newline="") as f:
        writer = csv.writer(f)
        
        # Write headers if new file
        if is_new_file:
            writer.writerow(headers)
        
        # Write data for each language
        for language, lang_data in data.items():
            row = [timestamp, language]
            for agent in AGENTS.keys():
                row.extend([lang_data[f"{agent}_total"], lang_data[f"{agent}_merged"]])
            writer.writerow(row)


def update_html_with_latest_data():
    """Update the HTML file with the latest statistics from the chart data."""
    # The HTML will be updated by JavaScript automatically when chart-data.json loads
    # This is a placeholder for any additional HTML updates needed
    html_file = Path("docs/index.html")
    if not html_file.exists():
        print("HTML file not found, skipping HTML update")
        return

    # Update the last updated timestamp in the HTML
    html_content = html_file.read_text()

    # Get current timestamp in the format used in the HTML
    now = dt.datetime.now(dt.UTC)
    timestamp_str = now.strftime("%B %d, %Y %H:%M UTC")

    # Update the timestamp in the HTML
    updated_html = re.sub(
        r'<span id="last-updated">[^<]*</span>',
        f'<span id="last-updated">{timestamp_str}</span>',
        html_content,
    )

    html_file.write_text(updated_html)
    print(f"Updated HTML timestamp to: {timestamp_str}")


if __name__ == "__main__":
    collect_data()
    update_html_with_latest_data()
    print("Data collection complete. To generate chart, run generate_chart.py")
