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
    node_json     = {node:0 for node in node_list}
    prometheus_result['node_list'] = node_list

    # Query CPU Utilization
    cpu_usage_percentage = '100 - (avg by (node) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)'
    cpu_usage_percentage_response = requests.get(PROMETHEUS_URL, params={'query': cpu_usage_percentage}).json()
    cpu_usage_percentage_json = {result['metric']['node']: round(float(result['value'][1]),2) for result in cpu_usage_percentage_response['data']['result']}
    prometheus_result['cpu_usage_percentage'] = cpu_usage_percentage_json

    cpu_reserve = 'sum by (node) (kube_pod_container_resource_requests{resource="cpu"})'
    cpu_reserve_response = requests.get(PROMETHEUS_URL, params={'query': cpu_reserve}).json()
    cpu_reserve_json = node_json
    cpu_reserve_json.update({result['metric']['node']: round(float(result['value'][1]), 2) for result in cpu_reserve_response['data']['result']})
    prometheus_result['cpu_reserve'] = cpu_reserve_json

    # Query Memory Utilization
    mem_usage_percentage = '100 - ((node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100)'
    mem_usage_percentage_response = requests.get(PROMETHEUS_URL, params={'query': mem_usage_percentage}).json()
    mem_usage_percentage_json = {result['metric']['node']: round(float(result['value'][1]),2) for result in mem_usage_percentage_response['data']['result']}
    prometheus_result['mem_usage_percentage'] = mem_usage_percentage_json

    mem_reserve = 'sum by (node) (kube_pod_container_resource_requests{resource="memory"}) / 1e9'
    mem_reserve_response = requests.get(PROMETHEUS_URL, params={'query': mem_reserve}).json()
    mem_reserve_json = node_json
    mem_reserve_json.update({result['metric']['node']: round(float(result['value'][1]),2) for result in mem_reserve_response['data']['result']})
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
        return result

def monitor_cluster():
    timestamp = datetime.now().strftime('%Y/%m/%d %H:%M:%S')
    prometheus_result = prometheus_get()
    power_pdu = snmp_get(PDU_IP, COMMUNITY, POWER_OID)
    energy_pdu = snmp_get(PDU_IP, COMMUNITY, ENERGY_OID)
    monitor_result = {'timestamp':timestamp, **prometheus_result, **power_pdu, **energy_pdu}
    print(monitor_result)
    return monitor_result

# Schedule the job every minute
schedule.every(1).minutes.do(monitor_cluster)
#print(monitor_cluster())
while True:
    schedule.run_pending()
    time.sleep(1)

