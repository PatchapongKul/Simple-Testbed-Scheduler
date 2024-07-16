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

# Define the OID to description mapping
OID_TO_DESCRIPTION = {
    POWER_OID: 'Power',
    ENERGY_OID: 'Energy'
}

def prometheus_get(debug=False):
    prometheus_result = dict()
    # Query Nodes
    node_response = requests.get(PROMETHEUS_URL, params={'query': 'kube_node_info'}).json()
    node_list     = [node['metric']['node'] for node in node_response['data']['result']]
    prometheus_result['cluster_node_list'] = node_list

    # Query CPU Utilization
    cpu_usage_percentage = '100 - (avg by (node) (rate(node_cpu_seconds_total{mode="idle"}[2m])) * 100)'
    cpu_usage_percentage_response = requests.get(PROMETHEUS_URL, params={'query': cpu_usage_percentage}).json()
    cpu_usage_percentage_json = {result['metric']['node']: round(float(result['value'][1]),2) for result in cpu_usage_percentage_response['data']['result']}
    prometheus_result['cpu_usage_percentage'] = cpu_usage_percentage_json

    active_node_list = list(cpu_usage_percentage_json.keys())
    active_node_json = {node:0 for node in active_node_list}
    node_status = {node: True if node in active_node_list else False for node in node_list}
    prometheus_result['node_status'] = node_status

    cpu_reserve = 'sum by (node) (kube_pod_container_resource_requests{resource="cpu"})'
    cpu_reserve_response = requests.get(PROMETHEUS_URL, params={'query': cpu_reserve}).json()
    cpu_reserve_json = active_node_json.copy()
    for result in cpu_reserve_response['data']['result']:
        if len(result['metric']) > 0:
            node = result['metric']['node']
            value = round(float(result['value'][1]), 2)
            cpu_reserve_json[node] = value
    prometheus_result['cpu_reserve'] = cpu_reserve_json

    # Query Memory Utilization
    mem_usage_percentage = '100 - ((node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100)'
    mem_usage_percentage_response = requests.get(PROMETHEUS_URL, params={'query': mem_usage_percentage}).json()
    mem_usage_percentage_json = {result['metric']['node']: round(float(result['value'][1]),2) for result in mem_usage_percentage_response['data']['result']}
    prometheus_result['mem_usage_percentage'] = mem_usage_percentage_json

    mem_reserve = 'sum by (node) (kube_pod_container_resource_requests{resource="memory"}) / 1e9'
    mem_reserve_response = requests.get(PROMETHEUS_URL, params={'query': mem_reserve}).json()
    mem_reserve_json = active_node_json.copy()
    for result in mem_reserve_response['data']['result']:
        if len(result['metric']) > 0:
            node = result['metric']['node']
            value = round(float(result['value'][1]), 2)
            mem_reserve_json[node] = value

    prometheus_result['mem_reserve'] = mem_reserve_json

    # Print Result
    if debug:
        print("CPU Utilization (%):")
        print(cpu_usage_percentage_json)
        print("===========================")
        print("CPU Reservation (Cores):")
        print(cpu_reserve_json)
        print("===========================")
        print("Memory Utilization (%):")
        print(mem_usage_percentage_json)
        print("===========================")
        print("Memory Reservation (GiB):")
        print(mem_reserve_json)
        print("===========================")

    return prometheus_result

def snmp_get(target, community, oid, port=161):
    """
    Perform an SNMP GET operation.

    :param target: The target device IP address or hostname.
    :param community: The SNMP community string.
    :param oid: The OID to query.
    :param port: The SNMP port number (default is 161).
    :return: The result of the SNMP GET operation.
    """
    iterator = getCmd(
        SnmpEngine(),
        CommunityData(community, mpModel=0),  # mpModel=0 means SNMPv1, for SNMPv2 use mpModel=1
        UdpTransportTarget((target, port)),
        ContextData(),
        ObjectType(ObjectIdentity(oid))
    )

    error_indication, error_status, error_index, var_binds = next(iterator)

    if error_indication:
        print(f"Error: {error_indication}")
        return None
    elif error_status:
        print(f"Error: {error_status.prettyPrint()} at {error_index and var_binds[int(error_index) - 1][0] or '?'}")
        return None
    else:
        result = {}
        for var_bind in var_binds:
            oid_str = str(var_bind[0])
            description = OID_TO_DESCRIPTION[oid_str]
            result[description] = int(var_bind[1].prettyPrint())
            if description == 'Power':  result[description] *= 10
            if description == 'Energy': result[description] /= 10
        return result

def delete_completed_task():
    time_completed_task = 'kube_pod_completion_time - kube_pod_start_time'
    time_completed_task_response = requests.get(PROMETHEUS_URL, params={'query': time_completed_task}).json()
    print(time_completed_task_response['data']['result'][0]['metric']['pod'])

def monitor_cluster(report=True):
    timestamp = datetime.now().strftime('%Y/%m/%d %H:%M:%S')
    prometheus_result = prometheus_get()
    power_pdu = snmp_get(PDU_IP, COMMUNITY, POWER_OID)
    energy_pdu = snmp_get(PDU_IP, COMMUNITY, ENERGY_OID)
    monitor_result = {'timestamp':timestamp, **prometheus_result, **power_pdu, **energy_pdu}
    if report:
        # Determine the maximum key length for alignment
        max_key_length = max(len(key) for key in monitor_result.keys())

        # Print each key-value pair with alignment
        for key in monitor_result.keys():
            print(f"{key.ljust(max_key_length)}\t{monitor_result[key]}")
        print("-------------------------------------------------------------------------")
    delete_completed_task()
    return monitor_result

# Schedule the job every minute
schedule.every(5).seconds.do(monitor_cluster)
monitor_cluster()
while True:
    schedule.run_pending()
    time.sleep(1)

