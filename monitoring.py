import os
import requests
import schedule
import time
from datetime import datetime
from dotenv import load_dotenv
from pysnmp.hlapi import *

# Load environment variables from ".env"
load_dotenv()
PROMETHEUS_URL = os.environ.get('PROMETHEUS_URL')
# Replace with your SNMP agent details
COMMUNITY  = os.environ.get('COMMUNITY')
PDU_IP     = os.environ.get('PDU_IP')
POWER_OID  = os.environ.get('POWER_OID')
ENERGY_OID = os.environ.get('ENERGY_OID')

def fetch_metrics():
    timestamp = datetime.now().strftime('%Y/%m/%d %H:%M:%S')
    print(timestamp)
    # Query Nodes
    node_response = requests.get(PROMETHEUS_URL, params={'query': 'kube_node_info'}).json()
    node_list     = [node['metric']['node'] for node in node_response['data']['result']]
    node_json     = {node:0 for node in node_list}

    # Query CPU Utilization
    cpu_usage_percentage = '100 - (avg by (node) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)'
    cpu_usage_percentage_response = requests.get(PROMETHEUS_URL, params={'query': cpu_usage_percentage}).json()
    cpu_usage_percentage_json = {result['metric']['node']: round(float(result['value'][1]),2) for result in cpu_usage_percentage_response['data']['result']}
    print("CPU Utilization (%):")
    print(cpu_usage_percentage_json)
    print("===========================")

    cpu_reserve_core = 'sum by (node) (kube_pod_container_resource_requests{resource="cpu"})'
    cpu_reserve_core_response = requests.get(PROMETHEUS_URL, params={'query': cpu_reserve_core}).json()
    cpu_reserve_core_json = node_json
    cpu_reserve_core_json.update({result['metric']['node']: round(float(result['value'][1]), 2) for result in cpu_reserve_core_response['data']['result']})
    print("CPU Reservation (Cores):")
    print(cpu_reserve_core_json)
    print("===========================")

    # Query Memory Utilization
    mem_usage_percentage = '100 - ((node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100)'
    mem_usage_percentage_response = requests.get(PROMETHEUS_URL, params={'query': mem_usage_percentage}).json()
    mem_usage_percentage_json = {result['metric']['node']: round(float(result['value'][1]),2) for result in mem_usage_percentage_response['data']['result']}
    print("Memory Utilization (%):")
    print(mem_usage_percentage_json)
    print("===========================")

    mem_reserve_core = 'sum by (node) (kube_pod_container_resource_requests{resource="memory"}) / 1e9'
    mem_reserve_core_response = requests.get(PROMETHEUS_URL, params={'query': mem_reserve_core}).json()
    mem_reserve_core_json = node_json
    mem_reserve_core_json.update({result['metric']['node']: round(float(result['value'][1]),2) for result in mem_reserve_core_response['data']['result']})
    print("Memory Reservation (GiB):")
    print(mem_reserve_core_json)
    print("===========================")

def snmp_get(community, ip, oid, port=161):
    error_indication, error_status, error_index, var_binds = next(
        getCmd(
            SnmpEngine(),
            CommunityData(community),
            UdpTransportTarget((ip, port)),
            ContextData(),
            ObjectType(ObjectIdentity(oid))
        )
    )

    if error_indication:
        print(f"Error: {error_indication}")
    elif error_status:
        print(f"Error Status: {error_status.prettyPrint()}")
    else:
        for var_bind in var_binds:
            print(f"{var_bind.prettyPrint()}")

# Schedule the job every minute
schedule.every(1).minutes.do(fetch_metrics)
fetch_metrics()
snmp_get(COMMUNITY, PDU_IP, POWER_OID)
snmp_get(COMMUNITY, PDU_IP, ENERGY_OID)
while True:
    schedule.run_pending()
    snmp_get(COMMUNITY, PDU_IP, POWER_OID)
    snmp_get(COMMUNITY, PDU_IP, ENERGY_OID)
    time.sleep(1)

