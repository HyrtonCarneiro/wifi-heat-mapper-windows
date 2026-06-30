from wifi_heat_mapper.misc import TColor, check_application, process_iw, save_json, get_application_output
from wifi_heat_mapper.misc import get_ip_address_from_interface, verify_interface
from wifi_heat_mapper.debugger import log_arguments
from wifi_heat_mapper import __version__
from collections import OrderedDict
import os
import pathlib
import logging


class ConfigurationOptions:
    configuration = OrderedDict()
    configuration["signal_quality"] = {
        "description": "Signal Quality (out of 80)",
        "help": "Qualidade do sinal (RSSI + 110). Escala linear de 0 (sem sinal) a 80 (excelente, RSSI = -30 dBm).",
        "requirements": ["base"],
        "vmin": 0,
        "vmax": 80,
        "mode": ["base"],
        "conversion": False,
        "reverse": False,
    }
    configuration["signal_quality_percent"] = {
        "description": "Signal Quality (in percentage)",
        "help": "Qualidade do sinal expressa em porcentagem (0-100%).",
        "requirements": ["base"],
        "vmin": 0,
        "vmax": 100,
        "mode": ["base"],
        "conversion": False,
        "reverse": False,
    }
    configuration["signal_strength"] = {
        "description": "RSSI (Signal Strength)",
        "help": "RSSI (Received Signal Strength Indicator) em dBm. Valores mais altos (próximos a -30) são melhores.",
        "requirements": ["base"],
        "vmin": -90,
        "vmax": -30,
        "mode": ["base"],
        "conversion": False,
        "reverse": False,
    }
    configuration["ap_density"] = {
        "description": "Cell Density (Count of visible networks)",
        "help": "Densidade de redes vizinhas. Indica quantos Access Points diferentes foram detectados neste ponto.",
        "requirements": ["base"],
        "vmin": 0,
        "vmax": 20,
        "mode": ["base"],
        "conversion": False,
        "reverse": False,
    }
    configuration["co_channel_interference"] = {
        "description": "Channel Overlap (Co-channel)",
        "help": "Interferência Co-canal: Número de redes operando na mesma frequência (canal) que a rede alvo.",
        "requirements": ["base"],
        "vmin": 0,
        "vmax": 10,
        "mode": ["base"],
        "conversion": False,
        "reverse": True,
    }
    configuration["adjacent_channel_interference"] = {
        "description": "Channel Overlap (Adjacent)",
        "help": "Interferência de Canal Adjacente: Redes em canais vizinhos que podem causar ruído e interferência lateral.",
        "requirements": ["base"],
        "vmin": 0,
        "vmax": 10,
        "mode": ["base"],
        "conversion": False,
        "reverse": True,
    }
    configuration["snr_estimated"] = {
        "description": "SNR (Signal to Noise Ratio)",
        "help": "SNR (Signal-to-Noise Ratio) estimado. Diferença entre a força do sinal e o Noise Floor de referência (-92 dBm para canais de 20 MHz).",
        "requirements": ["base"],
        "vmin": 0,
        "vmax": 50,
        "mode": ["base"],
        "conversion": False,
        "reverse": False,
    }
    configuration["channel"] = {
        "description": "Wi-Fi Channel",
        "help": "Canal de operação do Wi-Fi. Nota: canais são variáveis categóricas — o heatmap interpolado mostra tendências, não canais exatos.",
        "requirements": ["base"],
        "vmin": 1,
        "vmax": 165,
        "mode": ["base"],
        "conversion": False,
        "reverse": False,
    }




accept = ("y", "yes")
reject = ("n", "no")


@log_arguments
def start_config(config_file):
    """Starting point for the bootstrap submodule for whm.

    Args:
        config_file (str): the path to the configuration file.

    Returns:
        None
    """
    print("Detecting benchmarking capabilities.")
    supported_modes = ["base"]

    logging.debug("System supports: {0}".format(str(supported_modes)))


    ssid = None
    target_interface = None
    libre_speed_list = ""

    while True:
        target_interface = input("Please enter the target wireless interface to run benchmark on (example: Wi-Fi): ")
        target_interface = target_interface.strip()
        if not target_interface:
            print("Invalid interface")
            exit(1)
        verify_interface(target_interface)

        logging.debug("Target Interface: {0}".format(target_interface))

        bind_ip = get_ip_address_from_interface(target_interface)
        if bind_ip is None:
            print("Interface {0} does not have a valid IPv4 address assigned.".format(target_interface))

        logging.debug("Target Interface IP Address: {0}".format(bind_ip))

        break

    while True:
        ssid = process_iw(target_interface)["ssid"]
        question = "You are connected to {0}{1}{2}. Is this the interface you want to benchmark on? (y/N) ".format(
                   TColor.BLUE, ssid, TColor.RESET)
        if ask_y_n(question):
            logging.debug("SSID: {0}".format(ssid))
            break

    while True:
        try:
            repeat_count = int(input("How many times do you want to repeat benchmarking? "))
            if repeat_count <= 0:
                raise ValueError
        except ValueError:
            print("Invalid value please try again.")
        else:
            logging.debug("Benchmark Iterations: {0}".format(repeat_count))
            break

    logging.debug("SpeedTest Mode: None")

    print("Using official list.")

    logging.debug("Custom Librespeed List: {0}".format(libre_speed_list))

    print("Supported Graphs:")
    configuration_dict = ConfigurationOptions.configuration
    configuration_dict_supported = []
    i = 1
    for itm in configuration_dict.keys():
        mode = configuration_dict[itm]["mode"]
        supported = set(mode).intersection(set(supported_modes))
        if supported:
            configuration_dict_supported.append(itm)
            print_graph_to_console(i, itm, configuration_dict[itm]["description"])
            i += 1

    print("{0}{1}{2}".format(TColor.UNDERLINE, "=>> Select graphs to plot. eg: 1 2 3 5 6 or simply type 'all'",
                             TColor.RESET))
    response = input("> ")
    selection = []
    graph_key = []

    if response == "all":
        for itm in configuration_dict_supported:
            selection += configuration_dict[itm]["requirements"]
        graph_key = tuple(configuration_dict_supported)

    elif len(response) > 0:
        keys = []
        if response.isdecimal():
            keys.append(int(response))
        elif " " in response:
            try:
                response = tuple(map(int, response.split(" ")))
            except ValueError:
                print("Invalid character")
                exit(1)
            for res in response:
                if int(res) <= len(configuration_dict.keys()) and int(res) > 0:
                    keys.append(res)
                else:
                    print("Invalid selection")
                    exit(1)
        else:
            print("Invalid character")
            exit(1)
        keys = tuple(set(keys))
        for key in keys:
            configuration_dict_key = list(configuration_dict)[key - 1]
            selection += configuration_dict[configuration_dict_key]["requirements"]
            graph_key.append(configuration_dict_key)

    else:
        print("No option was selected.")
        exit(1)
    selection = tuple(set(selection))

    config_data = {
        "configuration":
            {
                "graphs": graph_key,
                "modes": selection,
                "backends": supported_modes,
                "version": __version__,
                "target_interface": target_interface,
                "target_ip": bind_ip,
                "ssid": ssid,
                "speedtest": -1,
                "libre-speed-list": "",
                "benchmark_iterations": repeat_count,
            },
        "results": {}
    }

    config_file = os.path.abspath(config_file)

    logging.debug("Configuration Data: {0}".format(config_data))
    logging.debug("Configuration Save Path: {0}".format(config_file))

    if pathlib.Path(config_file).suffix != ".json":
        config_file += ".json"

    if save_json(config_file, config_data):
        print("Successfully bootstrapped configuration.")
        print("Configuration file saved at: {0}".format(config_file))


def print_graph_to_console(index, title, description):
    """Pretty print the configuration items on the
    terminal for the user.

    Args:
        index (int): row index number.
        title (str): title of the graph item.
        description (str): description of the graph
        item.

    Returns:
        None
    """
    print("  {0}{1}{2} {3}{4}{5}".format(TColor.GREEN, index, TColor.RESET, TColor.MAGENTA, title,
                                         TColor.RESET))
    print("        {0}".format(description))


def ask_y_n(question):
    """Ask a Yes or No question to user and get the
    boolean response for it.

    Args:
        index (int): row index number.
        title (str): title of the graph item.
        description (str): description of the
        graph item.

    Returns:
        bool : True if user accepts, False if
        rejects and repeats the question if
        invalid option.
    """
    while True:
        response = input(question).lower()
        if response in accept:
            return True
        elif response in reject:
            return False
        else:
            print("Invalid option. Please try again.")
