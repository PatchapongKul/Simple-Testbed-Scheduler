import os
import requests
import schedule
import time
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from ".env"
load_dotenv()
PROMETHEUS_URL = os.environ.get('PROMETHEUS_URL')

def fetch_metrics():
    timestamp = datetime.now().strftime('%Y/%m/%d %H:%M:%S')
    print(timestamp)
    # Query CPU Utilization
    cpu_query = '100 - (avg by (node) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)'
    cpu_response = requests.get(PROMETHEUS_URL, params={'query': cpu_query}).json()
    cpu_json = {result['metric']['node']: result['value'][1] for result in cpu_response['data']['result']}
    print(cpu_json)
    print("===========================")
    # Query Memory Utilization
    mem_query = '100 - ((node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100)'
    mem_response = requests.get(PROMETHEUS_URL, params={'query': mem_query}).json()
    mem_json = {result['metric']['node']: result['value'][1] for result in mem_response['data']['result']}
    print(mem_json)
    print("===========================")
    # # Save the results
    # with open(f'/path/to/save/cpu_metrics_{timestamp}.json', 'w') as f:
    #     f.write(f'Timestamp: {timestamp}\n')
    #     f.write(f'{cpu_response}\n')

    # with open(f'/path/to/save/mem_metrics_{timestamp}.json', 'w') as f:
    #     f.write(f'Timestamp: {timestamp}\n')
    #     f.write(f'{mem_response}\n')

# Schedule the job every minute
schedule.every(1).minutes.do(fetch_metrics)
# fetch_metrics()
while True:
    schedule.run_pending()
    time.sleep(1)