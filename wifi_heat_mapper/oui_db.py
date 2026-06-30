def get_vendor(mac_address):
    """
    Identifica o fabricante do roteador com base no OUI (3 primeiros bytes do MAC).
    Focado nos fabricantes corporativos e domésticos mais comuns para uso offline.
    """
    if not mac_address or len(mac_address) < 8:
        return "Unknown"
        
    oui = mac_address[:8].lower()
    
    mapping = {
        # Cisco
        "00:14:1b": "Cisco", "00:40:96": "Cisco", "00:00:0c": "Cisco",
        "00:23:cd": "Cisco", "00:25:9c": "Cisco", "c8:f9:f9": "Cisco",
        "00:3a:9a": "Cisco", "04:62:73": "Cisco", "08:1f:f3": "Cisco",
        "f4:0f:1b": "Cisco", "64:9e:f3": "Cisco", "e8:40:40": "Cisco",
        "70:db:98": "Cisco", "00:1d:e5": "Cisco", "cc:d8:1f": "Cisco",
        
        # Aruba Networks
        "d8:c7:c8": "Aruba", "00:0b:86": "Aruba", "00:1a:1e": "Aruba",
        "04:bd:88": "Aruba", "20:4c:03": "Aruba", "24:fd:0d": "Aruba",
        "40:e3:d6": "Aruba", "9c:1c:12": "Aruba", "f0:5c:19": "Aruba",
        "b0:5a:da": "Aruba", "70:3a:0e": "Aruba", "a0:f8:49": "Aruba",
        "f4:aa:af": "Aruba", "14:18:77": "Aruba", "cc:eb:ae": "Aruba",
        
        # Ubiquiti
        "04:18:d6": "Ubiquiti", "18:e8:29": "Ubiquiti", "44:d9:e7": "Ubiquiti",
        "fc:ec:da": "Ubiquiti", "e0:63:da": "Ubiquiti", "f0:9f:c2": "Ubiquiti",
        "b4:fb:e4": "Ubiquiti", "00:27:22": "Ubiquiti", "80:2a:a8": "Ubiquiti",
        "68:d7:9a": "Ubiquiti", "60:22:32": "Ubiquiti", "24:a4:3c": "Ubiquiti",
        "78:8a:20": "Ubiquiti", "74:83:c2": "Ubiquiti", "14:58:d0": "Ubiquiti",

        # TP-Link
        "f4:f2:6d": "TP-Link", "e8:94:f6": "TP-Link", "c0:c9:e3": "TP-Link",
        "18:a6:f7": "TP-Link", "00:0a:eb": "TP-Link", "0c:80:63": "TP-Link",
        "50:c7:bf": "TP-Link", "7c:8b:ca": "TP-Link", "ac:84:c6": "TP-Link",
        "30:b5:c2": "TP-Link", "c4:6e:1f": "TP-Link", "5c:a6:e6": "TP-Link",
        
        # Intelbras
        "00:1e:e3": "Intelbras", "c4:a8:1d": "Intelbras", "00:1a:3f": "Intelbras",
        "84:5b:12": "Intelbras", "a8:2c:5c": "Intelbras", "e0:05:21": "Intelbras",
        "a4:2b:b0": "Intelbras", "40:f2:01": "Intelbras", "04:df:69": "Intelbras",
        "7c:c3:a1": "Intelbras", "80:7f:8f": "Intelbras", "b8:b4:cb": "Intelbras",
        
        # D-Link
        "00:22:a1": "D-Link", "f8:e9:03": "D-Link", "00:24:01": "D-Link",
        "c8:d3:a3": "D-Link", "14:d6:4d": "D-Link", "1c:7e:e5": "D-Link",
        
        # Huawei
        "00:25:9e": "Huawei", "00:1e:10": "Huawei", "20:0b:c7": "Huawei",
        "00:e0:fc": "Huawei", "10:1b:54": "Huawei", "10:47:80": "Huawei",
        "cc:a2:23": "Huawei", "80:38:bc": "Huawei", "88:53:d4": "Huawei",
        
        # Ruckus
        "84:d4:7e": "Ruckus", "00:1f:41": "Ruckus", "24:f5:a2": "Ruckus",
        "74:83:c2": "Ruckus", "74:9d:dc": "Ruckus", "9c:05:d6": "Ruckus",
        "e4:81:84": "Ruckus", "00:14:f4": "Ruckus", "d4:20:b0": "Ruckus",
        
        # Aerohive / Extreme
        "00:17:3f": "Aerohive", "08:ea:44": "Aerohive", "34:cd:6d": "Aerohive",
        
        # Meraki
        "00:18:0a": "Meraki", "e0:55:3d": "Meraki", "88:15:44": "Meraki",
        
        # Motorola / Zebra
        "18:1b:eb": "Motorola", "00:15:70": "Motorola", "00:24:e3": "Motorola",
        "00:0e:8f": "Zebra", "48:5a:3f": "Zebra", "80:cf:41": "Zebra",
        
        # Linksys / Belkin
        "00:0c:41": "Linksys", "c8:b3:73": "Linksys", "20:aa:4b": "Linksys",
        
        # Apple (Often used for Mobile Hotspots)
        "c8:bc:c8": "Apple", "e4:ce:8f": "Apple", "00:23:12": "Apple",
        "28:e0:2c": "Apple", "70:a2:b3": "Apple", "04:f7:e4": "Apple",
        
        # Samsung (Often used for Mobile Hotspots)
        "d8:fc:93": "Samsung", "bc:e6:3f": "Samsung", "cc:07:ab": "Samsung",
        "00:15:99": "Samsung", "fc:c1:13": "Samsung", "44:f4:77": "Samsung"
    }
    
    return mapping.get(oui, "Unknown")
