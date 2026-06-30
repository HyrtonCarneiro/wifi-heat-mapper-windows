from wifi_heat_mapper.debugger import log_arguments
import subprocess
from shutil import which
import re
import socket
import json
import os
import logging
import psutil
from wifi_heat_mapper.windows_wlan import get_wifi_metrics_windows


class TColor:
    BLACK = "\u001b[30;1m"
    RED = "\u001b[31;1m"
    GREEN = "\u001b[32;1m"
    YELLOW = "\u001b[33;1m"
    BLUE = "\u001b[34;1m"
    MAGENTA = "\u001b[35;1m"
    CYAN = "\u001b[36;1m"
    WHITE = "\u001b[37;1m"
    RESET = "\u001b[0m"
    UNDERLINE = "\u001b[4m"





class suppress_stdout_stderr(object):
    # https://stackoverflow.com/questions/11130156/suppress-stdout-stderr-print-from-python-functions
    '''
    A context manager for doing a "deep suppression" of stdout and stderr in
    Python, i.e. will suppress all print, even if the print originates in a
    compiled C/Fortran sub-function.
       This will not suppress raised exceptions, since exceptions are printed
    to stderr just before a script exits, and after the context manager has
    exited (at least, I think that is why it lets exceptions through).

    '''
    def __init__(self):
        # Open a pair of null files
        self.null_fds = [os.open(os.devnull, os.O_RDWR) for x in range(2)]
        # Save the actual stdout (1) and stderr (2) file descriptors.
        # Guard against missing descriptors in windowed mode
        self.save_fds = []
        try:
            self.save_fds.append(os.dup(1))
        except:
            self.save_fds.append(None)
        try:
            self.save_fds.append(os.dup(2))
        except:
            self.save_fds.append(None)

    def __enter__(self):
        # Assign the null pointers to stdout and stderr if descriptors exist.
        if self.save_fds[0] is not None: os.dup2(self.null_fds[0], 1)
        if self.save_fds[1] is not None: os.dup2(self.null_fds[1], 2)

    def __exit__(self, *_):
        # Re-assign the real stdout/stderr back if they were valid
        if self.save_fds[0] is not None: os.dup2(self.save_fds[0], 1)
        if self.save_fds[1] is not None: os.dup2(self.save_fds[1], 2)
        # Close all file descriptors
        for fd in self.null_fds:
            os.close(fd)
        for fd in self.save_fds:
            if fd is not None: os.close(fd)


HUMAN_BYTE_SIZE = [
    (1 << 60, "EiB"),
    (1 << 50, "PiB"),
    (1 << 40, "TiB"),
    (1 << 30, "GiB"),
    (1 << 20, "MiB"),
    (1 << 10, "KiB"),
    (1, "Byte")
]


class ParseError(Exception):
    pass


class ExternalError(Exception):
    pass


def check_application(name):
    """Check if application is available in the
    current environment.

    Args:
        name (str): application (or executable) name.

    Returns:
        bool : True if application is available,
        False if not available.
    """
    return which(name) is not None


def get_application_output(command, shell=False, timeout=None):
    """Run a command and get the output.

    Args:
        command (str, list): The command to run
        and it's arguments.
        shell (bool), optional: True if executing on
        shell, else False. Default is False.
        timeout (int, None), optional: Set a max
        execution time in seconds for the command.

    Returns:
        str: Command output if the command ran with
        a zero exit code. Returns a string containing
        the error reason in case the command failed.
    """
    try:
        return subprocess.run(command, shell=shell, check=True, universal_newlines=True,
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              timeout=timeout).stdout
    except subprocess.CalledProcessError:
        return "invalid"
    except subprocess.TimeoutExpired:
        return "timeout"
    except FileNotFoundError:
        return "unavailable"


def verify_interface(target_interface):
    """Verify if a network interface exists and is
    operational using psutil.

    Args:
        target_interface (str): The network interface to
        verify.

    Returns:
        None
    """
    stats = psutil.net_if_stats()
    if target_interface in stats:
        if not stats[target_interface].isup:
            logging.error("Interface {0} is not ready.".format(target_interface))
        return

    # Fallback check ignoring case and special characters
    target_clean = re.sub(r'[^a-zA-Z0-9]', '', target_interface).lower()
    for intf in stats:
        intf_clean = re.sub(r'[^a-zA-Z0-9]', '', intf).lower()
        if target_clean in intf_clean or intf_clean in target_clean:
            if not stats[intf].isup:
                logging.error("Interface {0} ({1}) is not ready.".format(intf, target_interface))
            return
            
    # If we reached here and it's Windows, common interfaces are often named "Wi-Fi"
    if os.name == 'nt' and "Wi-Fi" in stats:
        return

    if target_interface != "wlan0":
        logging.warning("Interface {0} could not be verified by psutil, but continuing anyway.".format(target_interface))


def process_iw(target_interface):
    """Get metrics from a wireless interface on Windows.

    Args:
        target_interface (str): The network interface to
        capture metrics from.

    Returns:
        dict: A dictionary containing the metrics and
        their values as corresponding (key, value) pairs.
    """
    verify_interface(target_interface)

    metrics = get_wifi_metrics_windows(target_interface)
    
    if metrics is not None:
        return metrics

    # Fallback to netsh if wlanapi fails
    try:
        netsh_info = get_application_output(
            ["netsh", "wlan", "show", "interfaces"],
            shell=True, timeout=10).replace("\r", "")

        if "invalid" in netsh_info or "unavailable" in netsh_info:
            logging.error("The interface {0} is not a wireless interface or netsh failed".format(target_interface))
            return None

        results = {}
        results["interface"] = target_interface
        
        # Support both English and Portuguese (PT-BR) netsh output labels
        ssid_match = re.search(r"^\s*SSID\s*:\s*(.*)$", netsh_info, re.MULTILINE)
        if ssid_match:
            results["ssid"] = ssid_match.group(1).strip()
        else:
            logging.error("netsh could not find required SSID.")
            return None
            
        bssid_match = re.search(r"^\s*BSSID\s*:\s*(.*)$", netsh_info, re.MULTILINE)
        if bssid_match:
            results["ssid_mac"] = bssid_match.group(1).strip()
            if not verify_mac(results["ssid_mac"]):
                logging.error("The station {0} has an invalid MAC address".format(results["ssid"]))
                return None
        else:
            results["ssid_mac"] = "00:00:00:00:00:00"
            
        # "Channel" (EN) or "Canal" (PT-BR)
        channel_match = re.search(r"^\s*(?:Channel|Canal)\s*:\s*(\d+)", netsh_info, re.MULTILINE)
        if channel_match:
            results["channel"] = int(channel_match.group(1))
        else:
            results["channel"] = 0
            
        # Approximation for frequency if we only have channel
        if results["channel"] > 14:
            results["channel_frequency"] = 5000 + (results["channel"] * 5)
        else:
            results["channel_frequency"] = 2407 + (results["channel"] * 5)
            if results["channel"] == 14:
                results["channel_frequency"] = 2484

        # "Signal" (EN) or "Sinal" (PT-BR)
        signal_match = re.search(r"^\s*(?:Signal|Sinal)\s*:\s*(\d+)%", netsh_info, re.MULTILINE)
        if signal_match:
            signal_percent = int(signal_match.group(1))
            results["signal_strength"] = int((signal_percent / 2) - 100)
        else:
            results["signal_strength"] = -100

        results["interface_mac"] = "00:00:00:00:00:00"
        return results

    except Exception as e:
        raise ParseError("Unable to parse netsh output: " + str(e)) from None


def verify_mac(mac):
    """Verify if a MAC address is valid.

    Args:
        mac (str): The MAC address to verify.

    Returns:
        bool: True if the MAC address is valid,
        False if not.
    """
    if re.match(r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$", mac):
        return True
    else:
        return False





def save_json(file_path, data):
    """Save a json dictionary to disk.

    Args:
        file_path (str): Path to the json
        file.
        data (dict): json dictionary to be saved.

    Returns:
        bool: True if json dictionary was saved,
        False otherwise.
    """
    try:
        with open(file_path, "w") as f:
            json.dump(data, f, indent=4)
            return True
    except Exception:
        return False


def load_json(file_path):
    """Read a json dictionary from disk.

    Args:
        file_path (str): Path to the json
        file.

    Returns:
        dict or bool: json dictionary
        if file was read successfully.
        False if it failed to read.
    """
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except Exception:
        return False


def get_property_from(dict, key):
    """Get a key value from a dictionary.

    Args:
        dict (dict): Dictionary to read
        from.
        key (str): key in the dictionary
        to get the value for.

    Returns:
        object: Containing the value.

    Raises:
        ValueError: When key does not
        exist in the dictionary.
    """
    try:
        return dict[key]
    except KeyError:
        raise ValueError("Could not retrieve property {0}".format(key)) from None


def bytes_to_human_readable(bytes, ndigits=2, limit=None):
    """Convert bytes to human readable format.

    Args:
        bytes (int): Size in bytes.
        ndigits (int), optional: Number of decimal
        places to round the human readable size to.
        Defaults to 2.
        limit (int), optional: Limit to a predefined
        unit size.

    Returns:
        tuple: Tuple containing the readable bytes
        in float, unit size in float, unit suffix
        in str.
    """
    if limit is None:
        for limit, suffix in HUMAN_BYTE_SIZE:
            if bytes >= limit:
                break

        if limit == 1 and bytes > 1:
            suffix += "s"

    readable_bytes = round((bytes / limit), ndigits)
    return (readable_bytes, limit, suffix)


def get_ip_address_from_interface(interface):
    """Get the IPv4 address of an interface.

    Args:
        target_interface (str): The network interface to
        get the ip address for.

    Returns:
        str or None: Returns the IPv4 address of the
        interface, returns None if no IPv4 address
        exists for that interface.
    """
    addrs = psutil.net_if_addrs()
    
    # Try exact match first
    if interface in addrs:
        target_interface = interface
    else:
        # Fallback to loose match (like Wi-Fi)
        target_interface = None
        for intf in addrs:
            if interface.lower() in intf.lower():
                target_interface = intf
                break

    if target_interface and target_interface in addrs:
        for addr in addrs[target_interface]:
            # Address family 2 is AF_INET (IPv4)
            if addr.family == socket.AF_INET:
                ip_addr = addr.address
                if validate_ipv4(ip_addr) and ip_addr != "127.0.0.1":
                    return ip_addr
    return None


def validate_ipv4(ip_address):
    """Validate an IPv4 address.

    Args:
        ip_address (str): The IPv4 address to check.

    Returns:
        bool: True if a valid IPv4 address, False
        otherwise.
    """
    if re.match(r"\b((?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)(?:(?<!\.)\b|\.)){4}", ip_address):
        return True
    else:
        return False
