import FreeSimpleGUI as sg
import os.path
from wifi_heat_mapper.misc import process_iw, load_json, save_json
from wifi_heat_mapper.misc import get_property_from
from wifi_heat_mapper.graph import generate_graph
from wifi_heat_mapper.debugger import log_arguments
from wifi_heat_mapper.windows_wlan import scan_all_networks
from PIL import Image, ImageTk
import io
from tqdm import tqdm
from collections import defaultdict
import logging
import sys
import threading
import time
import datetime

# Auxiliar para evitar crash em modo Windowed (sem console)
class NullWriter:
    def write(self, x): pass
    def flush(self): pass
    def isatty(self): return False


class ConfigurationError(Exception):
    pass



@log_arguments
def start_gui(floor_map, config_file, output_file=None):
    """Starting point for the benchmark submodule for whm.

    Args:
        floor_map (str): the path to the floor map image.
        config_file (str): the path to the configuration
        file.
        output_file (str): the path to the output file.

    Returns:
        None
    """
    if os.path.isfile(config_file):
        config_file = os.path.abspath(config_file)
        data = load_json(config_file)
        if data is not False:
            configuration = get_property_from(data, "configuration")
            logging.debug("Configuration Loaded: {0}".format(configuration))
            ssid = get_property_from(configuration, "ssid")
            target_ssids = configuration.get("target_ssids", [])  # Multi-network support
            target_interface = get_property_from(configuration, "target_interface")
            target_ip = get_property_from(configuration, "target_ip")
            target_ip = get_property_from(configuration, "target_ip")

            # If multi-network mode, just verify interface is up (no SSID check needed)
            try:
                connected_info = process_iw(target_interface)
                connected_ssid = connected_info["ssid"]
                logging.debug("SSID Connected: {0}".format(connected_ssid))
            except Exception as e:
                connected_ssid = ""
                logging.warning("Could not get connected SSID: %s", e)



            if output_file is None:
                output_file = config_file

    else:
        raise ConfigurationError("Missing configuration file")

    modes = get_property_from(configuration, "modes")

    print("Loaded configuration file from: {0}".format(config_file))
    print("Target Interface: {0} and SSID: {1}".format(target_interface, ssid))

    right_click_items = ["Items", ["&Benchmark", "&Delete", "&Mark/Un-Mark as Station"]]

    print("Loading floor map")
    logging.info("Loading floor map: {0}".format(floor_map))

    im = Image.open(floor_map)
    canvas_size = (im.size[0], im.size[1])

    logging.info("Loaded floor map with dims: {0}".format(canvas_size))

    # Calcula tamanho máximo da janela baseado na resolução da tela (80% da tela)
    screen_w, screen_h = sg.Window.get_screen_size()
    max_w, max_h = int(screen_w * 0.8), int(screen_h * 0.8)
    
    # Define se a janela precisa de scrollbars (se o mapa for maior que 80% da tela)
    use_scroll = canvas_size[0] > max_w or canvas_size[1] > max_h
    win_size = (min(canvas_size[0] + 50, max_w), min(canvas_size[1] + 100, max_h))

    output_path_index = sg.InputText(visible=False, enable_events=True, key='output_path')
    # Painel lateral para redes em tempo real
    sidebar = [
        [sg.Text("Redes em Tempo Real", font=("Helvetica", 12, "bold"))],
        [sg.Listbox(values=["Iniciando scan..."], size=(30, 25), key="-NET-LIST-", font=("Courier", 9))],
        [sg.Text("Sinal do Alvo:", font=("Helvetica", 10, "bold"))],
        [sg.Text("---", key="-TARGET-SIGNAL-", font=("Helvetica", 12), text_color="yellow")]
    ]

    layout = [
        [sg.Column([
            [sg.Graph(
                canvas_size=canvas_size,
                graph_bottom_left=(0, 0),
                graph_top_right=canvas_size,
                key="Floor Map",
                enable_events=True,
                background_color="DodgerBlue",
                right_click_menu=right_click_items)]
        ], scrollable=use_scroll, size=win_size if use_scroll else None, 
           expand_x=True, expand_y=True, key="-COL-"),
         sg.Column(sidebar, vertical_alignment="top")]
    ]

    if not output_file:
        layout.append(
            [sg.Button("Exit"), output_path_index, sg.FileSaveAs(button_text="Save Results",
             file_types=(('JSON file', '*.json'),), default_extension="json", key="FileName"),
             sg.Button("Plot"), sg.Button("Clear All")])
    else:
        layout.append(
            [sg.Button("Exit"), output_path_index, sg.Button("Save Results"),
             sg.Button("Plot"), sg.Button("Clear All"), sg.Button("Calibrar Planta")])

    window_args = {
        "layout": layout,
        "finalize": True,
        "resizable": True
    }
    if not use_scroll:
        window_args["size"] = win_size

    window = sg.Window("Wi-Fi heat mapper", **window_args)

    if output_file:
        output_path_index.update(output_file)

    graph = window.Element("Floor Map")

    logging.info("Drawing on canvas")
    graph.DrawImage(data=get_img_data(floor_map, first=True), location=(0, canvas_size[1]))
    logging.info("Updated canvas")

    print("Loaded floor map")

    benchmark_points = get_property_from(data, "results")

    current_selection = None
    benchmark_count = len(benchmark_points.keys())
    logging.debug("Benchmarking Points detected from previous run(s): {0}".format(benchmark_count))
    if benchmark_count != 0:
        print("Restoring previous benchmark points [{0}]".format(benchmark_count))
        benchmark_points, current_selection = replot(graph, benchmark_points)

    calib_state = "IDLE"
    calib_p1 = None
    pixels_per_meter = configuration.get("pixels_per_meter", None)

    def draw_scale_bar(graph, ppm, canvas_h):
        # Desenha uma barra de 5 metros no canto inferior esquerdo
        if not ppm: return
        bar_len_px = 5 * ppm
        graph.draw_line((20, 20), (20 + bar_len_px, 20), color="white", width=4)
        graph.draw_text("5m", (20 + bar_len_px/2, 35), color="white", font=("Helvetica", 10, "bold"))

    # Lógica de Scan em Tempo Real
    last_scan_data = {"networks": [], "target": None}
    stop_scan = threading.Event()

    def scan_thread():
        while not stop_scan.is_set():
            try:
                nets = scan_all_networks(target_interface)
                target_metrics = process_iw(target_interface)
                if not stop_scan.is_set():
                    window.write_event_value("-UPDATE-NETS-", (nets, target_metrics))
            except Exception as e:
                logging.debug("Scan thread error: %s", e)
            
            # Sleep in small increments to respond to stop_scan faster
            for _ in range(20):
                if stop_scan.is_set(): break
                time.sleep(0.1)

    threading.Thread(target=scan_thread, daemon=True).start()

    print("Ready for benchmarking.")

    post_process = False

    while True:
        event, values = window.read()

        if event == "-UPDATE-NETS-":
            nets, target = event_data = values["-UPDATE-NETS-"]
            last_scan_data["networks"] = nets
            last_scan_data["target"] = target
            
            # Atualiza lista visual
            display_list = []
            for n in sorted(nets, key=lambda x: x['signal_strength'], reverse=True)[:15]:
                display_list.append(f"{n['signal_strength']:3d}dBm | {n['ssid'][:15]}")
            window["-NET-LIST-"].update(values=display_list)
            
            if target:
                window["-TARGET-SIGNAL-"].update(value=f"{target['ssid']}: {target['signal_strength']} dBm")
            continue

        if event == "Calibrar Planta":
            calib_state = "START"
            sg.popup_quick_message("Clique no 1º ponto da calibração (ex: início de uma parede)...", background_color="orange")
            continue

        if event == "Exit" or event == sg.WIN_CLOSED:
            stop_scan.set()
            break

        mouse = values["Floor Map"]
        if event == "Floor Map":
            if mouse == (None, None):
                continue

            pt_exists = False
            for itm in benchmark_points.keys():
                pt_bench = get_point(benchmark_points, itm)
                if contains(mouse, pt_bench):
                    pt_exists = True
                    benchmark_points[itm]["selected"] = True
                    if current_selection is None:
                        current_selection = itm
                    else:
                        benchmark_points[current_selection]["selected"] = False
                        current_selection = itm
                    break

            if calib_state == "START":
                calib_p1 = mouse
                graph.draw_point(mouse, size=10, color="orange")
                calib_state = "END"
                sg.popup_quick_message("Agora clique no 2º ponto...", background_color="orange")
                continue
            elif calib_state == "END":
                p2 = mouse
                dist_px = ((calib_p1[0] - p2[0])**2 + (calib_p1[1] - p2[1])**2)**0.5
                m_input = sg.popup_get_text(f"Distância em pixels: {dist_px:.1f}\nDigite a distância REAL em metros:", title="Calibrar")
                try:
                    meters = float(m_input)
                    pixels_per_meter = dist_px / meters
                    configuration["pixels_per_meter"] = pixels_per_meter
                    configuration["scale_p1"] = calib_p1
                    configuration["scale_p2"] = p2
                    configuration["scale_meters"] = meters
                    save_results_to_disk(output_file, configuration, benchmark_points)
                    sg.popup(f"Calibração concluída!\nEscala: {pixels_per_meter:.2f} px/m")
                except:
                    sg.popup_error("Valor inválido.")
                calib_state = "IDLE"
                calib_p1 = None # Reseta pontos de calibração
                benchmark_points, current_selection = replot(graph, benchmark_points)
                draw_scale_bar(graph, pixels_per_meter, canvas_size[1])
                continue

            if not pt_exists:
                index = graph.draw_circle(mouse, 7, fill_color="gray", line_color="blue",
                                          line_width=3)
                benchmark_points[index] = {
                    "position": {
                        "x": mouse[0],
                        "y": mouse[1]
                    },
                    "fill_color": "gray",
                    "selected": True,
                    "station": False,
                    "results": None
                }
                if current_selection is not None:
                    benchmark_points[current_selection]["selected"] = False
                    current_selection = index
                else:
                    current_selection = index

        benchmark_points, current_selection = replot(graph, benchmark_points)

        if event == "Delete":
            if current_selection is not None:
                graph.delete_figure(current_selection)
                benchmark_points.pop(current_selection)
                current_selection = None

        if event == "Benchmark":
            if current_selection is not None:
                logging.info("Capturando dados em tempo real...")
                
                # Pega os dados que o scanner de fundo acabou de ler
                all_nets = last_scan_data["networks"]
                iw = last_scan_data["target"]
                
                results = {}
                results["timestamp"] = datetime.datetime.now().isoformat()

                # Preenche com os dados de Wi-Fi "carimbados" do tempo real
                if iw:
                    results["signal_strength"] = iw["signal_strength"]
                    results["snr_estimated"] = iw["signal_strength"] - (-92)
                    results["signal_quality"] = iw["signal_strength"] + 110
                    results["signal_quality_percent"] = min((iw["signal_strength"] + 110) * (10 / 7), 100)
                    results["channel"] = iw["channel"]
                    results["channel_frequency"] = iw["channel_frequency"]
                    results["active_benchmark_ssid"] = iw["ssid"]
                    results["active_benchmark_mac"] = iw["ssid_mac"]

                if all_nets:
                    networks_data = {}
                    results["ap_density"] = len(all_nets)
                    connected_channel = results.get("channel", 0)
                    co_interf = 0
                    adj_interf = 0
                    
                    for net in all_nets:
                        # Identifica a banda (2.4GHz ou 5GHz) para separar no mapa
                        freq = net['channel_frequency']
                        band = "5GHz" if freq > 3000 else "2.4GHz"
                        bssid = net['ssid_mac']
                        
                        # Chave única por SSID + Banda + BSSID (MAC)
                        ssid_full = f"{net['ssid']} [{band}] ({bssid})"
                        rssi = net['signal_strength']
                        
                        networks_data[ssid_full] = {
                            'signal_strength': rssi,
                            'snr_estimated': rssi - (-92),
                            'signal_quality': rssi + 110,
                            'signal_quality_percent': min((rssi + 110) * (10 / 7), 100),
                            'channel': net['channel'],
                            'channel_frequency': freq,
                            'ssid_mac': bssid,
                            'phy_type': net.get('phy_type', 'Unknown'),
                            'is_secure': net.get('is_secure', False),
                            'bss_type': net.get('bss_type', 'Unknown'),
                            'beacon_period': net.get('beacon_period', 100),
                            'bss_load_station_count': net.get('bss_load_station_count', 0),
                            'bss_load_channel_utilization': net.get('bss_load_channel_utilization', 0.0),
                            'vendor': net.get('vendor', 'Unknown'),
                            'is_bssid_specific': True
                        }
                        
                        # Também mantemos uma entrada "Geral" para o SSID (Melhor sinal)
                        ssid_gen = f"{net['ssid']} [{band}]"
                        if ssid_gen not in networks_data or rssi > networks_data[ssid_gen]['signal_strength']:
                             networks_data[ssid_gen] = {
                                'signal_strength': rssi,
                                'snr_estimated': rssi - (-92),
                                'signal_quality': rssi + 110,
                                'signal_quality_percent': min((rssi + 110) * (10 / 7), 100),
                                'channel': net['channel'],
                                'channel_frequency': freq,
                                'ssid_mac': bssid,
                                'phy_type': net.get('phy_type', 'Unknown'),
                                'is_secure': net.get('is_secure', False),
                                'bss_type': net.get('bss_type', 'Unknown'),
                                'beacon_period': net.get('beacon_period', 100),
                                'bss_load_station_count': net.get('bss_load_station_count', 0),
                                'bss_load_channel_utilization': net.get('bss_load_channel_utilization', 0.0),
                                'vendor': net.get('vendor', 'Unknown'),
                                'is_bssid_specific': False
                            }
                        if connected_channel > 0 and net['channel'] > 0:
                            ch_diff = abs(net['channel'] - connected_channel)
                            # Em 2.4 GHz (canais 1-14), sobreposição ocorre para |Δch| < 5
                            # Em 5 GHz (canais > 14), canais são não-sobrepostos (apenas co-channel)
                            is_2g = connected_channel <= 14 and net['channel'] <= 14
                            if net['channel'] == connected_channel:
                                co_interf += net.get('ap_count', 1)
                            elif is_2g and 1 <= ch_diff <= 4:
                                adj_interf += net.get('ap_count', 1)
                            elif not is_2g and ch_diff == 1:
                                adj_interf += net.get('ap_count', 1)
                    
                    results["co_channel_interference"] = max(0, co_interf - 1)
                    results["adjacent_channel_interference"] = adj_interf
                    results["networks"] = networks_data

                benchmark_points[current_selection]["results"] = results
                benchmark_points[current_selection]["fill_color"] = "lightblue"
                benchmark_points, current_selection = replot(graph, benchmark_points)
                
                save_results_to_disk(output_file, configuration, benchmark_points)
                continue
            else:
                print("Please select a benchmark point.")
                sg.popup_error("Selecione um ponto de medição primeiro.")

        if event == "Mark/Un-Mark as Station":
            if current_selection is not None:
                if benchmark_points[current_selection]["station"]:
                    benchmark_points[current_selection]["station"] = False
                else:
                    benchmark_points[current_selection]["station"] = True
                benchmark_points, current_selection = replot(graph, benchmark_points)

        if event == "output_path":
            if values["output_path"]:
                benchmark_points = de_select(benchmark_points)
                data = {
                    "configuration": configuration,
                    "results": benchmark_points
                }
                if save_json(values["output_path"], data):
                    print("Saved to disk")
                    sg.popup_ok("Saved to disk")
                    output_path_index.update(value="")
                else:
                    print("Unable to save to disk")
                    sg.popup_error("Unable to save to disk!")
                    logging.error("Unable to save to disk")

        if event == "Save Results":
            benchmark_points = de_select(benchmark_points)
            data = {
                "configuration": configuration,
                "results": benchmark_points
            }
            if save_json(output_file, data):
                print("Saved to disk")
                sg.popup_ok("Saved to disk")
            else:
                print("Unable to save to disk")
                sg.popup_error("Unable to save to disk!")
                logging.error("Unable to save to disk")

        if event == "Plot":
            valid_benchmark_points = processed_results(benchmark_points)
            if valid_benchmark_points >= 4:
                post_process = True
                print("Exporting Results")
                break
            else:
                sg.popup_error("Not enough benchmark points! Try benchmarking {0} more."
                               .format(4 - valid_benchmark_points))

        if event == "Clear All":
            benchmark_points, current_selection = replot(graph, benchmark_points, clear=True)
            logging.error("Wiped all benchmark points")

    window.close()

    if post_process:
        data = {
            "configuration": configuration,
            "results": benchmark_points
        }
        generate_graph(data, floor_map)


def contains(pt1, pt2):
    """Check if tuple (x, y) of first point lies in
    a circle contructed from the center point of
    second point.

    Args:
        pt1 (tuple): tuple of (x, y).
        pt2 (tuple): tuple of (x, y).

    Returns:
        bool: True or False
    """
    return ((pt1[0] - pt2[0]) ** 2 + (pt1[1] - pt2[1]) ** 2) <= 7 ** 2


def get_point(data, index):
    """From a given dictionary and index returns a
    tuple (x, y).

    Args:
        data (dict): Dictionary to retrieve point
        from.
        index (int): Index of the point.

    Returns:
        tuple: Containing the x and y co-ordinates
        in the form of (x, y)
    """
    return (data[index]["position"]["x"], data[index]["position"]["y"])


def replot(graph, benchmark_points, clear=False):
    """Redraws the circles on the canvas from a
    dictionary containing benchmark points.

    Args:
        graph (object): Graph object defining the UI.
        benchmark_points (dict): Dictionary containing
        the benchmark points.
        clear (boolean), optional: True if you want
        to redraw circles.
        False if you want to delete all circles.

    Returns:
        new_benchmark_points (dict): Contaning the
        updated indices of the benchmark points.
        new_selection (int): New index of the selected
        point.
    """
    new_benchmark_point = {}
    new_selection = None
    for itm in benchmark_points.keys():
        graph.delete_figure(itm)
        line_color = "black"
        if not clear:
            if benchmark_points[itm]["station"]:
                line_color = "red"
            if benchmark_points[itm]["selected"]:
                line_color = "blue"
            pt = graph.draw_circle(get_point(benchmark_points, itm), 7, fill_color=benchmark_points[itm]["fill_color"],
                                   line_color=line_color, line_width=3)
            if benchmark_points[itm]["selected"]:
                new_selection = pt
            new_benchmark_point[pt] = benchmark_points[itm]
    return (new_benchmark_point, new_selection)


def de_select(benchmark_points):
    """Sets the 'selected' property for a benchmark
    point to False.

    Args:
        benchmark_points (dict): Dictionary containing
        the benchmark points.

    Returns:
        benchmark_points (dict): Dictionary with
        any 'selected' attribute set to False.
    """
    for itm in benchmark_points.keys():
        benchmark_points[itm]["selected"] = False
    return benchmark_points


def processed_results(benchmark_points):
    """Gets the number of benchmark points for which
    metrics have been captured.

    Args:
        benchmark_points (dict): Dictionary containing
        the benchmark points.

    Returns:
        results (int): Integer containing the number
        of points for which metrics have been captured.
    """
    results = 0
    for itm in benchmark_points.keys():
        if benchmark_points[itm]["results"] is not None:
            results += 1
    return results


def get_img_data(f, first=False):
    """Generate image data using PIL"""
    img = Image.open(f)
    if first:
        bio = io.BytesIO()
        img.save(bio, format="PNG")
        del img
        return bio.getvalue()
    return ImageTk.PhotoImage(img)


def save_results_to_disk(file_path, configuration_data, benchmark_points):
    """Saves the results to disk.

    Args:
        file_path (str): Save path to the configuration file.
        configuration_data (dict): Dictionary containing the
        metrics and configuration details.
        benchmark_points (dict): Dictionary containing
        the benchmark points.

    Returns:
        bool: True if results have been saved to disk,
        False otherwise.
    """
    benchmark_points = de_select(benchmark_points)
    data = {
        "configuration": configuration_data,
        "results": benchmark_points
    }
    return save_json(file_path, data)



