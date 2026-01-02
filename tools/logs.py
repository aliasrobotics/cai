"""
This script is used to create a web-based logs analysis dashboard.

It allows you to visualize the logs in different ways and see the PyPI download statistics.

Usage:
    # Show all logs
    python tools/web_logs.py <(cat ./logs.txt)
    
    # Show last 10 logs and enable map
    python tools/web_logs.py --enable-map <(tail -n 10 ./logs.txt)

Ideas for further improvements:
- Re-generate the log heatmap with only top 20 IPs
- Create a map with the top 20 IPs
- Dive into the logs
"""

import matplotlib
matplotlib.use('Agg')

from flask import Flask, render_template, request
from functools import wraps
import pandas as pd
import matplotlib.pyplot as plt
import io
import base64
from datetime import datetime, timedelta
import os
import folium
import requests
import argparse
from typing import Dict, Optional
import numpy as np
import re
from collections import defaultdict
import time

app = Flask(__name__)

# Rate limiting configuration
class RateLimiter:
    """Rate limiter to prevent DoS attacks on API endpoints."""
    
    def __init__(self, requests_per_minute=10, requests_per_hour=50, requests_per_day=200):
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.requests_per_day = requests_per_day
        self.request_history = defaultdict(list)
    
    def is_rate_limited(self, client_id):
        """Check if a client has exceeded rate limits."""
        current_time = time.time()
        
        # Clean old requests
        self.request_history[client_id] = [
            req_time for req_time in self.request_history[client_id]
            if current_time - req_time < 86400  # Keep last 24 hours
        ]
        
        # Check minute limit (60 seconds)
        minute_requests = [r for r in self.request_history[client_id] if current_time - r < 60]
        if len(minute_requests) >= self.requests_per_minute:
            return True
        
        # Check hour limit (3600 seconds)
        hour_requests = [r for r in self.request_history[client_id] if current_time - r < 3600]
        if len(hour_requests) >= self.requests_per_hour:
            return True
        
        # Check day limit (86400 seconds)
        day_requests = [r for r in self.request_history[client_id] if current_time - r < 86400]
        if len(day_requests) >= self.requests_per_day:
            return True
        
        # Record this request
        self.request_history[client_id].append(current_time)
        return False

# Initialize rate limiter
rate_limiter = RateLimiter(
    requests_per_minute=10,
    requests_per_hour=50,
    requests_per_day=200
)

def apply_rate_limit():
    """Apply rate limiting to the current request."""
    client_ip = request.remote_addr
    if rate_limiter.is_rate_limited(client_ip):
        return "Rate limit exceeded. Please try again later.", 429
    return None

# Configuration for enabled visualizations
class Config:
    def __init__(self):
        self.enable_map = False  # Default to disabled
        self.enable_daily_logs = True
        self.enable_system_dist = True
        self.enable_user_activity = True
        
    @classmethod
    def from_args(cls, args):
        config = cls()
        # Handle map options - disable takes precedence
        if hasattr(args, 'disable_map') and args.disable_map:
            config.enable_map = False
        elif hasattr(args, 'enable_map') and args.enable_map:
            config.enable_map = True
            
        if hasattr(args, 'disable_daily'):
            config.enable_daily_logs = not args.disable_daily
        if hasattr(args, 'disable_system'):
            config.enable_system_dist = not args.disable_system
        if hasattr(args, 'disable_users'):
            config.enable_user_activity = not args.disable_users
        return config

# Visualization components
class Visualizations:
    def __init__(self, df: pd.DataFrame, config: Config):
        self.df = df
        self.config = config
        
    def create_daily_logs(self) -> Optional[str]:
        if not self.config.enable_daily_logs:
            return None
            
        plt.figure(figsize=(12, 6))
        daily_counts = self.df.set_index('timestamp').resample('D').size()
        daily_counts.index = daily_counts.index.strftime('%Y-%m-%d')  # Format the index to 'yyyy-mm-dd'
        
        # Plot bar chart for daily counts
        ax = daily_counts.plot(kind='bar', color='skyblue', label='Daily Count')
        
        # Plot line chart for cumulative counts
        cumulative_counts = daily_counts.cumsum()
        total_cumulative_count = cumulative_counts.iloc[-1]  # Get the total cumulative count
        cumulative_counts.plot(kind='line', color='orange', secondary_y=True, ax=ax, label=f'Cumulative Count (Total: {total_cumulative_count})')
        
        # Add vertical red line on 2025-04-09
        if '2025-04-09' in daily_counts.index:
            red_line_index = daily_counts.index.get_loc('2025-04-09')
            ax.axvline(x=red_line_index, color='red', linestyle='--', 
                      label='Public Release v0.3.11')
            
            # Add grey-ish background to all elements prior to the red line
            ax.axvspan(0, red_line_index, color='grey', alpha=0.3)

        # Add vertical blue line on 2025-05-30
        if '2025-05-30' in daily_counts.index:
            green_line_index = daily_counts.index.get_loc('2025-05-30')
            ax.axvline(x=green_line_index, color='green', linestyle='--', 
                      label='"CAIv0.4.0" and "alias0" releases')

        # Add vertical yellow line on 2025-04-01
        if '2025-04-01' in daily_counts.index:
            yellow_line_index = daily_counts.index.get_loc('2025-04-01')
            ax.axvline(x=yellow_line_index, color='yellow', linestyle='--', label='Professional Bug Bounty Test')
        
        # Set titles and labels
        ax.set_title('Number of Logs by Day')
        ax.set_xlabel('Date')
        ax.set_ylabel('Number of Logs')
        ax.right_ax.set_ylabel('Cumulative Count')
        ax.set_xticklabels(daily_counts.index, rotation=45)
        
        # Add legends
        ax.legend(loc='upper left')
        ax.right_ax.legend(loc='upper right')
        
        plt.tight_layout()
        return self._get_plot_base64()

    def create_system_distribution(self) -> Optional[str]:
        if not self.config.enable_system_dist:
            return None
            
        plt.figure(figsize=(10, 6))
        system_map = {
            'linux': 'Linux', 
            'darwin': 'Darwin', 
            'windows': 'Windows',
            'microsoft': 'Windows',
            'wsl': 'Windows'
        }
        self.df['system_grouped'] = self.df['system'].map(system_map).fillna('Other')
        system_counts = self.df['system_grouped'].value_counts()
        system_counts.plot(kind='bar')
        plt.title('Total Number of Logs per System')
        plt.xlabel('System')
        plt.ylabel('Number of Logs')
        plt.tight_layout()
        return self._get_plot_base64()

    def create_user_activity(self) -> Optional[str]:
        if not self.config.enable_user_activity:
            return None

        plt.figure(figsize=(12, 6))
        user_counts = self.df['username'].value_counts().head(50)
        total_unique_users = self.df['username'].nunique()
        ax = user_counts.plot(kind='bar')
        plt.title(f'Top 50 Most Active Users (out of {total_unique_users} different users)')
        plt.xlabel('Username')
        plt.ylabel('Number of Logs')
        plt.xticks(rotation=45)

        # Add the actual number on top of each bar
        for i, count in enumerate(user_counts):
            ax.text(i, count, str(count), ha='center', va='bottom')

        plt.tight_layout()
        return self._get_plot_base64()

    def create_map(self) -> Optional[str]:
        if not self.config.enable_map:
            return None
            
        m = folium.Map(location=[40, -3], zoom_start=4)
        for _, row in self.df.iterrows():
            location = get_location(row['ip_address'])
            folium.Marker(
                location,
                popup=f"{row['username']} ({row['ip_address']})<br>{row['timestamp']}",
                tooltip=row['username'],
            ).add_to(m)
        return m._repr_html_()

    def create_ip_date_heatmap(self) -> Optional[str]:
        # Only create if there are valid IPs (not 'disabled')
        df = self.df[self.df['ip_address'] != 'disabled'].copy()
        if df.empty:
            return None
        # Use only date part for columns now
        df['date'] = df['timestamp'].dt.strftime('%Y-%m-%d')
        # Pivot: rows=ip, columns=date, values=count
        pivot = df.pivot_table(index='ip_address', columns='date', values='size', aggfunc='count', fill_value=0)
        if pivot.empty:
            return None
        # Order IPs by total logs (descending)
        ip_order = pivot.sum(axis=1).sort_values(ascending=True).index.tolist()
        pivot = pivot.loc[ip_order]
        # Get human-readable locations for each IP
        ip_labels = []
        #
        # TODO: note API limits
        # for ip in pivot.index:
        #     loc = self._get_ip_location_label(ip)
        #     ip_labels.append(f"{ip} ({loc})")
        #
        for ip in pivot.index:
            ip_labels.append(ip)
        plt.figure(figsize=(max(6, 0.5 * len(pivot.columns)), min(20, 1 + 0.5 * len(pivot.index))))
        ax = plt.gca()
        im = ax.imshow(pivot.values, aspect='auto', cmap='YlOrRd', origin='lower')
        plt.colorbar(im, ax=ax, label='Number of Logs')
        ax.set_xticks(range(len(pivot.columns)))
        ax.set_xticklabels(pivot.columns, rotation=90, fontsize=8)
        ax.set_yticks(range(len(ip_labels)))
        ax.set_yticklabels(ip_labels, fontsize=8)
        plt.title('Log Heatmap: Number of Logs per IP Address and Date')
        plt.xlabel('Date')
        plt.ylabel('IP Address (Location)')
        plt.tight_layout()
        return self._get_plot_base64()

    def _get_ip_location_label(self, ip: str) -> str:
        # Try to get city/country from ip-api.com
        if ip in ("127.0.0.1", "localhost"):
            return "Vitoria, Spain"
        try:
            response = requests.get(f"http://ip-api.com/json/{ip}", timeout=5)
            data = response.json()
            if response.status_code == 200 and data.get("status") == "success":
                city = data.get("city", "")
                country = data.get("country", "")
                if city and country:
                    return f"{city}, {country}"
                elif country:
                    return country
        except Exception:
            pass
        # Fallback to lat/lon
        try:
            lat, lon = get_location(ip)
            return f"{lat:.2f},{lon:.2f}"
        except Exception:
            return "Unknown"

    def _get_plot_base64(self) -> str:
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        buf.seek(0)
        plot_data = base64.b64encode(buf.getvalue()).decode()
        plt.close()
        return plot_data

def parse_logs(file_path, parse_ips=False):
    logs = []
    # Regex patterns for the three formats
    # 1. Old: ...-cai_20250405_091537_root_linux_6.10.14-linuxkit_81_38_188_36.jsonl
    old_pattern = re.compile(r"cai_(\d{8})_(\d{6})_([^_]+)_([^_]+)_([^_]+)_(\d+)_(\d+)_(\d+)_(\d+)\.jsonl$")
    # 2. New: uuid_cai_uuid_20250426_054313_root_linux_6.12.13-amd64_177_91_253_204.jsonl
    new_pattern = re.compile(r"([\w-]+)_cai_([\w-]+)_(\d{8})_(\d{6})_([^_]+)_([^_]+)_([^_]+)_([\d]+)_([\d]+)_([\d]+)_([\d]+)\.jsonl$")
    # 3. Intermediate: logs/sessions/uuid/intermediate_20250422_222021.jsonl
    intermediate_pattern = re.compile(r"intermediate_(\d{8})_(\d{6})\.jsonl$")

    with open(file_path, 'r') as file:
        for line in file:
            try:
                parts = line.strip().split(None, 2)
                if len(parts) != 3:
                    continue
                size = parts[2].split()[0]
                filename = parts[2].split()[1] if len(parts[2].split()) > 1 else parts[2]

                # --- Old and New format ---
                if 'cai_' in filename:
                    # Try new format first
                    m_new = new_pattern.search(filename)
                    if m_new:
                        # uuid_cai_uuid_YYYYMMDD_HHMMSS_user_system_version_ip.jsonl
                        # Groups: 3=date, 4=time, 5=username, 6=system, 7=version, 8-11=ip
                        date_str = m_new.group(3)
                        time_str = m_new.group(4)
                        ts = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]} {time_str[:2]}:{time_str[2:4]}:{time_str[4:]}"
                        username = m_new.group(5)
                        system = m_new.group(6).lower()
                        version = m_new.group(7)
                        if 'microsoft' in system or 'wsl' in version.lower():
                            system = 'windows'
                        if parse_ips:
                            ip_address = '.'.join([m_new.group(8), m_new.group(9), m_new.group(10), m_new.group(11)])
                        else:
                            ip_address = 'disabled'
                        logs.append([ts, size, ip_address, system, username])
                        continue
                    # Try old format
                    m_old = old_pattern.search(filename)
                    if m_old:
                        # Groups: 1=date, 2=time, 3=username, 4=system, 5=version, 6-9=ip
                        date_str = m_old.group(1)
                        time_str = m_old.group(2)
                        ts = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]} {time_str[:2]}:{time_str[2:4]}:{time_str[4:]}"
                        username = m_old.group(3)
                        system = m_old.group(4).lower()
                        version = m_old.group(5)
                        if 'microsoft' in system or 'wsl' in version.lower():
                            system = 'windows'
                        if parse_ips:
                            ip_address = '.'.join([m_old.group(6), m_old.group(7), m_old.group(8), m_old.group(9)])
                        else:
                            ip_address = 'disabled'
                        logs.append([ts, size, ip_address, system, username])
                        continue
                # --- Intermediate format ---
                m_inter = intermediate_pattern.search(filename)
                if m_inter:
                    # Only date is relevant
                    date_str = m_inter.group(1)
                    time_str = m_inter.group(2)
                    # Compose a timestamp from the extracted date/time
                    ts = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]} {time_str[:2]}:{time_str[2:4]}:{time_str[4:]}"
                    logs.append([ts, size, 'disabled', 'unknown', 'unknown'])
                    continue
                # If none matched, skip
                continue
            except Exception as e:
                print(f"Error parsing line: {line.strip()} -> {e}")
                continue
    return logs

def get_location(ip):
    if ip in ("127.0.0.1", "localhost"):
        return 42.85, -2.67  # Vitoria

    # API 1: ip-api.com
    try:
        response = requests.get(f"http://ip-api.com/json/{ip}", timeout=5)
        data = response.json()
        if response.status_code == 200 and data.get("status") == "success":
            return data["lat"], data["lon"]
    except Exception:
        pass

    # API 2: ipinfo.io
    try:
        response = requests.get(f"https://ipinfo.io/{ip}/json", timeout=5)
        data = response.json()
        if response.status_code == 200 and "loc" in data:
            lat, lon = map(float, data["loc"].split(","))
            return lat, lon
    except Exception:
        pass

    # API 3: ipwho.is
    try:
        response = requests.get(f"https://ipwho.is/{ip}", timeout=5)
        data = response.json()
        if response.status_code == 200 and data.get("success") is True:
            return data["latitude"], data["longitude"]
    except Exception:
        pass

    # Fallback
    return 42.85, -2.67

def get_overall_stats():
    """Fetch overall download statistics for cai-framework"""
    url = "https://pypistats.org/api/packages/cai-framework/overall"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error fetching overall stats: {response.status_code}")
        return None

def get_system_stats():
    """Fetch system-specific download statistics for cai-framework"""
    url = "https://pypistats.org/api/packages/cai-framework/system"
    response = requests.get(url) 
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error fetching system stats: {response.status_code}")
        return None

def create_pypi_plot():
    # Get the data
    overall_stats = get_overall_stats()
    system_stats = get_system_stats()
    
    if not overall_stats or not system_stats:
        print("Error: Could not fetch PyPI statistics")
        return None, None
    
    # Create a figure with custom layout
    plt.figure(figsize=(15, 8))
    
    # Convert data to DataFrames
    df_overall = pd.DataFrame(overall_stats['data'])
    df_system = pd.DataFrame(system_stats['data'])
    
    # Filter for downloads without mirrors (matches website reporting)
    df_overall_no_mirrors = df_overall[df_overall['category'] == 'without_mirrors']
    without_mirrors_total = df_overall_no_mirrors['downloads'].sum()
    
    # Process the data
    daily_downloads = df_overall_no_mirrors.groupby('date')['downloads'].sum().reset_index()
    daily_downloads['date'] = pd.to_datetime(daily_downloads['date'])
    # Add cumulative downloads
    daily_downloads['cumulative_downloads'] = daily_downloads['downloads'].cumsum()
    
    # Get release date (first date in the dataset)
    release_date = daily_downloads['date'].min()
    
    # Calculate system percentages for each day
    system_pivot = df_system.pivot(index='date', columns='category', values='downloads')
    system_pivot.index = pd.to_datetime(system_pivot.index)
    system_pivot = system_pivot.fillna(0)
    
    # Keep track of the total downloads per system for the legend
    system_totals = system_pivot.sum()
    
    # Create main plot with two y-axes
    ax1 = plt.subplot(111)
    ax2 = ax1.twinx()  # Create a second y-axis sharing the same x-axis
    
    # Plot total cumulative downloads on the left axis
    ax1.plot(daily_downloads['date'], daily_downloads['cumulative_downloads'], 
               linewidth=3, color='black', label=f'Total Downloads (without mirrors): {without_mirrors_total:,}')
    
    # Define color mapping for systems
    color_map = {
        'Darwin': '#1E88E5',  # Blue
        'Linux': '#FB8C00',   # Orange
        'Windows': '#43A047',  # Green
        'null': '#E53935'     # Red
    }
    
    # Plot system distribution on the right axis
    bottom = np.zeros(len(system_pivot))
    
    # Ensure specific order of systems
    desired_order = ['Darwin', 'Linux', 'Windows', 'null']
    for col in desired_order:
        if col in system_pivot.columns:
            ax2.bar(system_pivot.index, system_pivot[col], 
                      bottom=bottom, label=col, color=color_map[col], 
                      alpha=0.5, width=0.8)
            bottom += system_pivot[col]
    
    # Add release date annotation
    ax1.axvline(x=release_date, color='#E53935', linestyle='--', alpha=0.7)
    ax1.annotate('Release Date', 
                xy=(release_date, ax1.get_ylim()[1]),
                xytext=(10, 10), textcoords='offset points',
                color='#E53935', fontsize=10,
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec='#E53935', alpha=0.8))
    
    # Set the x-ticks to be at each date in the dataset
    ax1.set_xticks(system_pivot.index)
    ax1.set_xticklabels([date.strftime('%Y-%m-%d') for date in system_pivot.index], 
                       rotation=45, fontsize=10, ha='right')
    
    # Add padding between x-axis and the date labels
    ax1.tick_params(axis='x', which='major', pad=10)
    
    ax1.set_title('CAI Framework Download Statistics', fontsize=14, pad=20)
    ax1.set_ylabel('Total Cumulative Downloads', fontsize=14, color='black')
    ax2.set_ylabel('Daily Downloads by System', fontsize=14, color='black')
    ax1.set_xlabel('Date', fontsize=14)
    
    # Set grid and tick parameters
    ax1.grid(True, linestyle='--', alpha=0.7)
    ax1.tick_params(axis='y', colors='black')
    ax2.tick_params(axis='y', colors='black')
    
    # Add legend with combined information
    handles1, labels1 = ax1.get_legend_handles_labels()
    handles2, labels2 = [], []
    
    # Add bars to legend in the desired order with correct colors
    for col in desired_order:
        if col in system_pivot.columns:
            # Create a proxy artist with the correct color
            proxy = plt.Rectangle((0, 0), 1, 1, fc=color_map[col], alpha=0.5)
            handles2.append(proxy)
            # Calculate percentage of both system total and overall total
            system_percentage = (system_totals[col] / system_totals.sum()) * 100
            website_percentage = (system_totals[col] / without_mirrors_total) * 100
            labels2.append(f'{col} ({int(system_totals[col]):,} total, {system_percentage:.1f}%)')
    
    # Create legend with updated colors
    ax1.legend(handles1 + handles2, labels1 + labels2, 
              title='Operating Systems',
              bbox_to_anchor=(1.05, 1), loc='upper left',
              fontsize=12, title_fontsize=14)
    
    plt.tight_layout()
    
    # Create a BytesIO buffer for the image
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=300)
    plt.close()
    
    # Encode the image to base64 string
    buf.seek(0)
    image_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    
    # Prepare statistics for the template
    stats = {
        'total_downloads': without_mirrors_total,
        'latest_downloads': daily_downloads.iloc[-1]['downloads'] if not daily_downloads.empty else 0,
        'first_date': daily_downloads['date'].min().strftime('%Y-%m-%d') if not daily_downloads.empty else 'N/A',
        'last_date': daily_downloads['date'].max().strftime('%Y-%m-%d') if not daily_downloads.empty else 'N/A',
        'system_totals': {col: int(system_totals[col]) for col in system_totals.index if col in system_pivot.columns},
        'system_percentages': {col: (system_totals[col] / system_totals.sum()) * 100 
                              for col in system_totals.index if col in system_pivot.columns}
    }
    
    return f'data:image/png;base64,{image_base64}', stats

@app.route('/')
def index():
    # Apply rate limiting
    rate_limit_response = apply_rate_limit()
    if rate_limit_response:
        return rate_limit_response
    
    # Get log file path from app config
    log_file = app.config['LOG_FILE']
    
    # Parse logs
    logs = parse_logs(log_file, parse_ips=True)
    if not logs:
        return f"No logs were parsed. Please check if the file {log_file} exists and contains valid log entries."
    
    df = pd.DataFrame(logs, columns=['timestamp', 'size', 'ip_address', 'system', 'username'])
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Create visualizations
    viz = Visualizations(df, app.config['VIZ_CONFIG'])
    
    # Only create enabled visualizations
    visualizations = {
        'logs_by_day': viz.create_daily_logs(),
        'logs_by_system': viz.create_system_distribution(),
        'active_users': viz.create_user_activity(),
        'ip_date_heatmap': viz.create_ip_date_heatmap(),
        'config': app.config['VIZ_CONFIG']
    }
    
    # Only create map if enabled
    if app.config['VIZ_CONFIG'].enable_map:
        visualizations['map_html'] = viz.create_map()
    
    # Generate PyPI plot
    pypi_plot, pypi_stats = create_pypi_plot()
    visualizations['pypi_plot'] = pypi_plot
    visualizations['pypi_stats'] = pypi_stats
    
    return render_template('logs.html', **visualizations)

@app.route('/pypi-stats')
def pypi_stats():
    # Apply rate limiting
    rate_limit_response = apply_rate_limit()
    if rate_limit_response:
        return rate_limit_response
    
    # Generate PyPI plot
    pypi_plot, stats = create_pypi_plot()
    
    return render_template('pypi_stats.html',
                          pypi_plot=pypi_plot,
                          stats=stats)

def parse_args():
    parser = argparse.ArgumentParser(description='Web-based log analysis dashboard')
    parser.add_argument('log_file', nargs='?', default='/tmp/logs.txt',
                      help='Path to the log file (default: /tmp/logs.txt)')
    
    # Map control group
    map_group = parser.add_mutually_exclusive_group()
    map_group.add_argument('--enable-map', action='store_true',
                      help='Enable the geographic distribution map (default: disabled)')
    map_group.add_argument('--disable-map', action='store_true',
                      help='Disable the geographic distribution map (takes precedence)')
    
    parser.add_argument('--disable-daily', action='store_true',
                      help='Disable the daily logs chart')
    parser.add_argument('--disable-system', action='store_true',
                      help='Disable the system distribution chart')
    parser.add_argument('--disable-users', action='store_true',
                      help='Disable the user activity chart')
    parser.add_argument('--port', type=int, default=5001,
                      help='Port to run the server on (default: 5001)')
    return parser.parse_args()

def main():
    args = parse_args()
    
    # Ensure the log file exists
    if not os.path.exists(args.log_file):
        print(f"Error: {args.log_file} not found!")
        exit(1)
    
    # Configure the application
    app.config['LOG_FILE'] = args.log_file
    app.config['VIZ_CONFIG'] = Config.from_args(args)
    
    print(f"Starting web server on http://localhost:{args.port}")
    print(f"Using log file: {args.log_file}")
    app.run(host='0.0.0.0', port=args.port, debug=True)

if __name__ == '__main__':
    main()
