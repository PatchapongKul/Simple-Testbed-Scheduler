import os
import time
import schedule
from dotenv import load_dotenv
from pysnmp.hlapi import *

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

energy_W_min = 0

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
    
def power_monitor(energy_W_min):
    power_pdu = snmp_get(PDU_IP, COMMUNITY, POWER_OID)
    energy_W_min += power_pdu['Power'] / 60
    print(energy_W_min)

# Schedule the job every second
schedule.every(1).seconds.do(power_monitor(energy_W_min))
power_monitor(energy_W_min)
while True:
    schedule.run_pending()
    time.sleep(1)