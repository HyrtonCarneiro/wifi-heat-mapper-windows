import ctypes
from ctypes import wintypes
import logging
from wifi_heat_mapper.oui_db import get_vendor

logger = logging.getLogger(__name__)

# Define constants
WLAN_API_VERSION_2_0 = 2
ERROR_SUCCESS = 0

# WLAN constants
wlan_interface_state_not_ready = 0
wlan_interface_state_connected = 1
wlan_interface_state_ad_hoc_network_formed = 2
wlan_interface_state_disconnecting = 3
wlan_interface_state_disconnected = 4
wlan_interface_state_associating = 5
wlan_interface_state_discovering = 6
wlan_interface_state_authenticating = 7

# Structure definitions
class WLAN_INTERFACE_INFO(ctypes.Structure):
    _fields_ = [
        ("InterfaceGuid", ctypes.c_byte * 16),
        ("strInterfaceDescription", ctypes.c_wchar * 256),
        ("isState", ctypes.c_uint)
    ]

class WLAN_INTERFACE_INFO_LIST(ctypes.Structure):
    _fields_ = [
        ("dwNumberOfItems", wintypes.DWORD),
        ("dwIndex", wintypes.DWORD),
        ("InterfaceInfo", WLAN_INTERFACE_INFO * 1) # Variable length
    ]

class DOT11_SSID(ctypes.Structure):
    _fields_ = [
        ("uSSIDLength", wintypes.ULONG),
        ("ucSSID", ctypes.c_ubyte * 32)
    ]

class WLAN_BSS_ENTRY(ctypes.Structure):
    _fields_ = [
        ("dot11Ssid", DOT11_SSID),
        ("uPhyId", wintypes.ULONG),
        ("dot11Bssid", ctypes.c_ubyte * 6),
        ("dot11BssType", ctypes.c_uint),
        ("dot11BssPhyType", ctypes.c_uint),
        ("lRssi", ctypes.c_long),
        ("uLinkQuality", wintypes.ULONG),
        ("bInRegDomain", wintypes.BOOLEAN),
        ("usBeaconPeriod", wintypes.USHORT),
        ("ullTimestamp", ctypes.c_ulonglong),
        ("ullHostTimestamp", ctypes.c_ulonglong),
        ("usCapabilityInformation", wintypes.USHORT),
        ("ulChCenterFrequency", wintypes.ULONG),
        ("wlanRateSet", ctypes.c_byte * 256), # WLAN_RATE_SET: ULONG(4) + USHORT[126](252) = 256 bytes
        ("ulIeOffset", wintypes.ULONG),
        ("ulIeSize", wintypes.ULONG)
    ]

class WLAN_BSS_LIST(ctypes.Structure):
    _fields_ = [
        ("dwTotalSize", wintypes.DWORD),
        ("dwNumberOfItems", wintypes.DWORD),
        ("wlanBssEntries", WLAN_BSS_ENTRY * 1) # Variable length
    ]

class WLAN_CONNECTION_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("isState", ctypes.c_uint),
        ("wlanConnectionMode", ctypes.c_uint),
        ("strProfileName", ctypes.c_wchar * 256),
        ("wlanAssociationAttributes", ctypes.c_byte * 100), # Simplification, we just need BSSID
        ("wlanSecurityAttributes", ctypes.c_byte * 100)
    ]

# Need accurate ASSOCIATION_ATTRIBUTES to get BSSID of current connection
class WLAN_ASSOCIATION_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("dot11Ssid", DOT11_SSID),
        ("dot11BssType", ctypes.c_uint),
        ("dot11Bssid", ctypes.c_ubyte * 6),
        ("dot11PhyType", ctypes.c_uint),
        ("uDot11PhyIndex", wintypes.ULONG),
        ("wlanSignalQuality", wintypes.ULONG),
        ("ulRxRate", wintypes.ULONG),
        ("ulTxRate", wintypes.ULONG)
    ]

class WLAN_CONNECTION_ATTRIBUTES_REAL(ctypes.Structure):
    _fields_ = [
        ("isState", ctypes.c_uint),
        ("wlanConnectionMode", ctypes.c_uint),
        ("strProfileName", ctypes.c_wchar * 256),
        ("wlanAssociationAttributes", WLAN_ASSOCIATION_ATTRIBUTES),
        ("wlanSecurityAttributes", ctypes.c_byte * 100) # Unneeded for us
    ]

def get_phy_type_name(phy_type_id):
    phy_types = {
        1: "DSSS",
        2: "FHSS",
        3: "IR Baseband",
        4: "802.11a",
        5: "802.11b",
        6: "802.11g",
        7: "802.11n",
        8: "802.11ac",
        9: "802.11ad",
        10: "802.11ax",
        11: "802.11be"
    }
    return phy_types.get(phy_type_id, f"Unknown ({phy_type_id})")

def get_wlanapi():
    try:
        wlanapi = ctypes.windll.wlanapi
        logger.debug("wlanapi.dll carregada com sucesso.")
        return wlanapi
    except OSError as e:
        logger.warning("Falha ao carregar wlanapi.dll: %s. O serviço Wi-Fi pode estar desabilitado.", e)
        return None
    except Exception as e:
        logger.error("Erro inesperado ao carregar wlanapi.dll: %s", e)
        return None

def open_handle(wlanapi):
    negotiated_version = wintypes.DWORD()
    client_handle = wintypes.HANDLE()
    result = wlanapi.WlanOpenHandle(
        WLAN_API_VERSION_2_0, None, ctypes.byref(negotiated_version), ctypes.byref(client_handle)
    )
    if result != ERROR_SUCCESS:
        logger.error("WlanOpenHandle falhou com código %d. "
                     "Verifique se o serviço 'WLAN AutoConfig' (wlansvc) está ativo.", result)
        return None
    logger.debug("WlanOpenHandle OK. Versão negociada: %d", negotiated_version.value)
    return client_handle

def close_handle(wlanapi, client_handle):
    wlanapi.WlanCloseHandle(client_handle, None)

def get_interfaces(wlanapi, client_handle):
    p_interface_list = ctypes.POINTER(WLAN_INTERFACE_INFO_LIST)()
    result = wlanapi.WlanEnumInterfaces(
        client_handle, None, ctypes.byref(p_interface_list)
    )
    if result != ERROR_SUCCESS:
        logger.error("WlanEnumInterfaces falhou com código %d.", result)
        return []
    
    interfaces = []
    num_items = p_interface_list.contents.dwNumberOfItems
    logger.debug("Encontradas %d interface(s) Wi-Fi.", num_items)
    
    info_array = ctypes.cast(
        ctypes.byref(p_interface_list.contents.InterfaceInfo),
        ctypes.POINTER(WLAN_INTERFACE_INFO * num_items)
    ).contents
    
    for i in range(num_items):
        info = info_array[i]
        guid_bytes = bytes(info.InterfaceGuid)
        desc = info.strInterfaceDescription
        state = info.isState
        logger.debug("  Interface %d: '%s' | Estado: %d", i, desc, state)
        interfaces.append({
            'guid': guid_bytes,
            'description': desc,
            'state': state
        })
    
    wlanapi.WlanFreeMemory(p_interface_list)
    return interfaces

def get_current_connection(wlanapi, client_handle, guid_bytes):
    p_data = ctypes.c_void_p()
    data_size = wintypes.DWORD()
    
    result = wlanapi.WlanQueryInterface(
        client_handle,
        ctypes.c_buffer(guid_bytes),
        7,  # wlan_intf_opcode_current_connection
        None,
        ctypes.byref(data_size),
        ctypes.byref(p_data),
        None
    )
    
    if result != ERROR_SUCCESS:
        logger.error("WlanQueryInterface falhou com código %d. "
                     "A interface pode estar desconectada.", result)
        return None
        
    conn_attrs = ctypes.cast(p_data, ctypes.POINTER(WLAN_CONNECTION_ATTRIBUTES_REAL)).contents
    
    bssid_bytes = bytes(conn_attrs.wlanAssociationAttributes.dot11Bssid)
    bssid_str = ':'.join(['{:02x}'.format(b) for b in bssid_bytes])
    
    ssid_len = conn_attrs.wlanAssociationAttributes.dot11Ssid.uSSIDLength
    ssid_bytes = bytes(conn_attrs.wlanAssociationAttributes.dot11Ssid.ucSSID[:ssid_len])
    try:
        ssid_str = ssid_bytes.decode('utf-8')
    except:
        ssid_str = ssid_bytes.decode('ascii', errors='ignore')
        
    wlanapi.WlanFreeMemory(p_data)
    
    return {
        'bssid': bssid_str,
        'ssid': ssid_str
    }

def get_bss_list(wlanapi, client_handle, guid_bytes):
    p_bss_list = ctypes.POINTER(WLAN_BSS_LIST)()
    
    result = wlanapi.WlanGetNetworkBssList(
        client_handle,
        ctypes.c_buffer(guid_bytes),
        None, # dot11Ssid
        0, # dot11BssType
        False, # bSecurityEnabled
        None, # pReserved
        ctypes.byref(p_bss_list)
    )
    
    if result != ERROR_SUCCESS:
        return []
        
    bss_entries = []
    num_items = p_bss_list.contents.dwNumberOfItems
    
    # Need to iterate carefully due to variable size structures.
    # WlanGetNetworkBssList returns contiguous array if we only look at fixed fields,
    # but the IE offsets make it tricky if we need IEs. Fortunately, we don't.
    # We can cast to array.
    entry_array = ctypes.cast(
        ctypes.byref(p_bss_list.contents.wlanBssEntries),
        ctypes.POINTER(WLAN_BSS_ENTRY * num_items)
    ).contents
    
    for i in range(num_items):
        entry = entry_array[i]
        bssid_bytes = bytes(entry.dot11Bssid)
        bssid_str = ':'.join(['{:02x}'.format(b) for b in bssid_bytes])
        
        ssid_len = entry.dot11Ssid.uSSIDLength
        ssid_bytes = bytes(entry.dot11Ssid.ucSSID[:ssid_len])
        try:
            ssid_str = ssid_bytes.decode('utf-8')
        except:
            ssid_str = ssid_bytes.decode('ascii', errors='ignore')
            
        freq_mhz = entry.ulChCenterFrequency // 1000
        
        # Approximate channel from freq
        channel = 0
        if freq_mhz >= 2412 and freq_mhz <= 2484:
            channel = (freq_mhz - 2407) // 5
            if freq_mhz == 2484:
                channel = 14
        elif freq_mhz >= 5000:
            channel = (freq_mhz - 5000) // 5
            
        is_secure = bool(entry.usCapabilityInformation & 0x0010)
        
        bss_type_id = entry.dot11BssType
        bss_type_str = "Infrastructure" if bss_type_id == 1 else ("Ad-Hoc" if bss_type_id == 2 else f"Unknown ({bss_type_id})")
        beacon_period = entry.usBeaconPeriod
        
        # Safely parse BSS Load from IEs
        bss_load_station_count = 0
        bss_load_channel_utilization = 0.0
        
        try:
            if entry.ulIeSize > 0:
                ie_ptr = ctypes.cast(ctypes.addressof(entry) + entry.ulIeOffset, ctypes.POINTER(ctypes.c_ubyte * entry.ulIeSize))
                ie_bytes = bytes(ie_ptr.contents)
                idx = 0
                while idx < len(ie_bytes):
                    if idx + 1 >= len(ie_bytes): break
                    ie_id = ie_bytes[idx]
                    ie_len = ie_bytes[idx+1]
                    if idx + 2 + ie_len > len(ie_bytes): break
                    
                    if ie_id == 11 and ie_len == 5: # BSS Load Element
                        data = ie_bytes[idx+2 : idx+2+ie_len]
                        bss_load_station_count = int.from_bytes(data[0:2], byteorder='little')
                        chan_util_raw = data[2]
                        bss_load_channel_utilization = round((chan_util_raw / 255.0) * 100.0, 1)
                        break
                    idx += 2 + ie_len
        except Exception as e:
            logger.debug(f"Erro no parse de IE (BSS Load) para {bssid_str}: {e}")

        bss_entries.append({
            'bssid': bssid_str,
            'ssid': ssid_str,
            'rssi': entry.lRssi,
            'channel': channel,
            'frequency': freq_mhz,
            'phy_type': get_phy_type_name(entry.dot11BssPhyType),
            'is_secure': is_secure,
            'bss_type': bss_type_str,
            'beacon_period': beacon_period,
            'bss_load_station_count': bss_load_station_count,
            'bss_load_channel_utilization': bss_load_channel_utilization,
            'vendor': get_vendor(bssid_str)
        })
        
    wlanapi.WlanFreeMemory(p_bss_list)
    return bss_entries


def get_wifi_metrics_windows(interface_name="Wi-Fi"):
    """
    Get metrics for the CURRENTLY CONNECTED network.
    """
    wlanapi = get_wlanapi()
    if not wlanapi:
        return None
    
    handle = open_handle(wlanapi)
    if not handle:
        # Fallback to netsh if handle fails
        from wifi_heat_mapper.misc import get_wifi_metrics_netsh
        return get_wifi_metrics_netsh(interface_name)
    
    try:
        interfaces = get_interfaces(wlanapi, handle)
        if not interfaces:
            return None
        
        target_guid = None
        for intf in interfaces:
            if interface_name.lower() in intf['description'].lower():
                target_guid = intf['guid']
                break
        if not target_guid:
            target_guid = interfaces[0]['guid']
            
        p_attributes = ctypes.POINTER(WLAN_CONNECTION_ATTRIBUTES_REAL)()
        data_size = wintypes.DWORD()
        
        result = wlanapi.WlanQueryInterface(
            handle, ctypes.byref(ctypes.create_string_buffer(target_guid)),
            7, # wlan_intf_opcode_current_connection
            None, ctypes.byref(data_size), ctypes.byref(p_attributes), None
        )
        
        if result != ERROR_SUCCESS:
            return None
            
        attr = p_attributes.contents.wlanAssociationAttributes
        ssid_len = attr.dot11Ssid.uSSIDLength
        ssid_bytes = bytes(attr.dot11Ssid.ucSSID[:ssid_len])
        try:
            ssid = ssid_bytes.decode('utf-8')
        except:
            ssid = ssid_bytes.decode('cp1252', errors='replace')
            
        bssid = ":".join([f"{b:02x}" for b in attr.dot11Bssid])
        
        # To get frequency/channel, we need the BSS list
        bss_list = get_bss_list(wlanapi, handle, target_guid)
        freq = 0
        channel = 0
        for bss in bss_list:
            if bss['bssid'].lower() == bssid.lower():
                freq = bss['frequency']
                channel = bss['channel']
                break
        
        signal_strength = attr.wlanSignalQuality # 0-100
        # Convert quality 0-100 to approximate dBm (-100 to -50)
        rssi = (signal_strength / 2) - 100
        
        wlanapi.WlanFreeMemory(p_attributes)
        
        return {
            'ssid_mac': bssid,
            'ssid': ssid,
            'signal_strength': int(rssi),
            'channel': channel,
            'channel_frequency': freq,
            'phy_type': get_phy_type_name(attr.dot11PhyType)
        }
        
    except Exception as e:
        logger.exception("Erro ao obter métricas WLAN: %s", e)
    finally:
        close_handle(wlanapi, handle)
        
    return None


def scan_all_networks(interface_name="Wi-Fi"):
    """Scan all visible Wi-Fi networks and return their metrics."""
    logger.info("Escaneando todas as redes Wi-Fi visíveis...")
    wlanapi = get_wlanapi()
    if not wlanapi:
        logger.warning("wlanapi indisponível para scan.")
        return []

    handle = open_handle(wlanapi)
    if not handle:
        logger.warning("Não foi possível abrir handle WLAN para scan.")
        return []

    try:
        interfaces = get_interfaces(wlanapi, handle)
        if not interfaces:
            logger.warning("Nenhuma interface Wi-Fi encontrada para scan.")
            return []

        # Find the target interface (prefer matching name, fallback to first)
        target_guid = None
        for intf in interfaces:
            if interface_name.lower() in intf['description'].lower():
                target_guid = intf['guid']
                break
        if not target_guid:
            target_guid = interfaces[0]['guid']
        # Força um scan ativo no Windows para descobrir o máximo de redes possível (estilo Acrylic)
        try:
            wlanapi.WlanScan(handle, ctypes.byref(ctypes.create_string_buffer(target_guid)), None, None, None)
            import time
            time.sleep(1.0) # Tempo para a placa atualizar os resultados
        except:
            pass
            
        bss_list = get_bss_list(wlanapi, handle, target_guid)
        logger.info("BSS scan retornou %d entradas.", len(bss_list))

        # Group by SSID, keeping all APs
        networks = {}
        for bss in bss_list:
            ssid = bss['ssid']
            if not ssid:  # Skip hidden/empty SSIDs
                continue
            if ssid not in networks:
                networks[ssid] = []
            networks[ssid].append({
                'ssid': ssid,
                'ssid_mac': bss['bssid'],
                'signal_strength': bss['rssi'],
                'channel': bss['channel'],
                'channel_frequency': bss['frequency'],
                'phy_type': bss['phy_type'],
                'is_secure': bss.get('is_secure', False),
                'bss_type': bss.get('bss_type', 'Unknown'),
                'beacon_period': bss.get('beacon_period', 100),
                'bss_load_station_count': bss.get('bss_load_station_count', 0),
                'bss_load_channel_utilization': bss.get('bss_load_channel_utilization', 0.0),
                'vendor': bss.get('vendor', 'Unknown')
            })

        # For each SSID, pick the AP with the best (highest) RSSI
        result = []
        for ssid, entries in networks.items():
            best = max(entries, key=lambda x: x['signal_strength']).copy()
            best['ap_count'] = len(entries)
            # Store all BSSIDs for triangulation later
            best['all_aps'] = entries
            result.append(best)

        # Sort by signal strength (strongest first)
        result.sort(key=lambda x: x['signal_strength'], reverse=True)
        logger.info("Encontradas %d redes únicas.", len(result))
        return result

    except Exception as e:
        logger.exception("Erro ao escanear redes: %s", e)
        return []
    finally:
        close_handle(wlanapi, handle)


if __name__ == "__main__":
    print(get_wifi_metrics_windows("Wi-Fi"))
    print("--- All networks ---")
    for net in scan_all_networks():
        print(f"  {net['ssid']:30s} | {net['phy_type']:15s} | {net['signal_strength']:4d} dBm | Ch {net['channel']:3d} | APs: {net['ap_count']}")
