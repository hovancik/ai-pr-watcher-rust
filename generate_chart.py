#!/usr/bin/env python3
"""
Generate chart-data.json from collected CSV data for the HTML dashboard.
This script reads the historical data from data.csv and creates the format
expected by the interactive chart in index.html.
"""

import csv
import json
import datetime as dt
from pathlib import Path
from collections import defaultdict


def read_csv_data(csv_file):
    """Read and parse CSV data into structured format."""
    if not csv_file.exists():
        print("No CSV data file found. Run collect_data.py first.")
        return None
    
    data_by_date = defaultdict(lambda: defaultdict(dict))
    
    with csv_file.open('r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            timestamp = row['timestamp']
            language = row['language']
            
            # Parse timestamp to get date for daily grouping
            try:
                date_obj = dt.datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
                date_key = date_obj.strftime("%Y-%m-%d")  # Daily grouping
            except ValueError:
                continue
            
            # Store agent data for this language and date
            agents_data = {}
            for agent in ['copilot', 'codex', 'cursor', 'devin', 'codegen']:
                total_key = f"{agent}_total"
                merged_key = f"{agent}_merged"
                
                if total_key in row and merged_key in row:
                    total = int(row[total_key]) if row[total_key] else 0
                    merged = int(row[merged_key]) if row[merged_key] else 0
                    success_rate = (merged / total * 100) if total > 0 else 0
                    
                    agents_data[agent] = {
                        'volume': total,
                        'success': success_rate
                    }
            
            data_by_date[date_key][language] = agents_data
    
    return data_by_date


def generate_chart_data(data_by_date):
    """Convert CSV data into Chart.js format."""
    if not data_by_date:
        return None
    
    # Get sorted time labels (actual dates from data)
    time_labels = sorted(data_by_date.keys(), key=lambda x: dt.datetime.strptime(x, "%Y-%m-%d"))
    
    # Keep only the last 30 days of data (or all data if less than 30 days)
    if len(time_labels) > 30:
        time_labels = time_labels[-30:]
    
    # Convert to more readable format for display
    display_labels = []
    for date_str in time_labels:
        date_obj = dt.datetime.strptime(date_str, "%Y-%m-%d")
        display_labels.append(date_obj.strftime("%b %d"))  # "Jun 20" format
    
    languages = ['all', 'javascript', 'typescript', 'python', 'java', 'ruby', 'go', 'php', 'c%23', 'c%2B%2B', 'rust', 'f%23']
    agents = ['copilot', 'codex', 'cursor', 'devin', 'codegen']
    
    colors = {
        'copilot': '#87ceeb',
        'codex': '#ff6b6b',
        'cursor': '#9b59b6',
        'devin': '#52c41a',
        'codegen': '#daa520'
    }
    
    datasets = []
    
    # Generate datasets for all languages (including 'all')
    for language in languages:
        for agent in agents:
            # Volume data (bars)
            volume_data = []
            success_data = []
            
            for time_label in time_labels:
                if (time_label in data_by_date and 
                    language in data_by_date[time_label] and 
                    agent in data_by_date[time_label][language]):
                    
                    agent_data = data_by_date[time_label][language][agent]
                    volume_data.append(agent_data['volume'])
                    success_data.append(agent_data['success'])
                else:
                    # No data for this time period - use null to create gaps
                    volume_data.append(None)
                    success_data.append(None)
            
            # Determine if this should be hidden by default
            is_hidden = language != 'all'  # Show 'all' by default, hide individual languages
            
            # Create volume dataset (bar)
            datasets.append({
                'label': f'{language.replace("%23", "#").replace("%2B%2B", "++").title()} {agent.title()} Volume',
                'data': volume_data,
                'backgroundColor': colors[agent] + '80',  # Semi-transparent
                'borderColor': colors[agent],
                'borderWidth': 1,
                'type': 'bar',
                'yAxisID': 'y',
                'language': language,
                'agent': agent,
                'hidden': is_hidden
            })
            
            # Create success rate dataset (line)
            datasets.append({
                'label': f'{language.replace("%23", "#").replace("%2B%2B", "++").title()} {agent.title()} Success %',
                'data': success_data,
                'backgroundColor': colors[agent],
                'borderColor': colors[agent],
                'borderWidth': 2,
                'fill': False,
                'type': 'line',
                'yAxisID': 'y1',
                'language': language,
                'agent': agent,
                'pointRadius': 3,
                'hidden': is_hidden
            })
    
    return {
        'labels': display_labels,  # Use the formatted display labels
        'datasets': datasets
    }


def main():
    """Main function to generate chart data."""
    csv_file = Path("data.csv")
    output_file = Path("docs/chart-data.json")
    
    print("Reading CSV data...")
    data_by_date = read_csv_data(csv_file)
    
    if not data_by_date:
        print("No data available. Exiting.")
        return
    
    print("Generating chart data...")
    chart_data = generate_chart_data(data_by_date)
    
    if not chart_data:
        print("Failed to generate chart data.")
        return
    
    # Ensure docs directory exists
    output_file.parent.mkdir(exist_ok=True)
    
    # Write chart data to JSON file
    with output_file.open('w') as f:
        json.dump(chart_data, f, indent=2)
    
    print(f"Chart data generated successfully: {output_file}")
    print(f"Generated data for {len(chart_data['labels'])} time periods")
    print(f"Generated {len(chart_data['datasets'])} datasets")


if __name__ == "__main__":
    main()
