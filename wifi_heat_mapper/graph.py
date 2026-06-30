from wifi_heat_mapper.config import ConfigurationOptions
from wifi_heat_mapper.misc import load_json, get_property_from, bytes_to_human_readable
from wifi_heat_mapper.debugger import log_arguments
from PIL import Image
import matplotlib.pyplot as plt
import numpy as np
import math
from matplotlib.pyplot import imread
from scipy.interpolate import Rbf
from tqdm import tqdm
import os
import heapq
import logging
import sys

# Auxiliar para evitar crash em modo Windowed (sem console)
class NullWriter:
    def write(self, x): pass
    def flush(self): pass
    def isatty(self): return False


class MissingMetricError(Exception):
    pass


class GraphPlot:
    def __init__(self, results, key, floor_map, vmin=None, vmax=None, conversion=False, reverse=False, default_ssid="Default"):
        self.results = results
        self.floor_map = floor_map
        self.vmin = vmin
        self.vmax = vmax
        self.key = key
        self.processed_results = None
        self.floor_map_dimensions = None
        self.conversion = conversion
        self.suffix = None
        self.reverse = reverse
        self.default_ssid = default_ssid

    def process_result(self):
        """Process the results captured for a metric. """
        processed_results = {"x": [], "y": [], "z": [], "sx": [], "sy": [], "active_ssids": []}
        for result in self.results.keys():
            if self.results[result]["results"] is not None:
                processed_results["x"].append(self.results[result]["position"]["x"])
                processed_results["y"].append(self.results[result]["position"]["y"])
                
                # Rastreamento de SSID ativo para diferenciação no gráfico
                active_ssid = self.results[result]["results"].get("active_benchmark_ssid", self.default_ssid)
                processed_results["active_ssids"].append(active_ssid)

                try:
                    processed_results["z"].append(self.results[result]["results"][self.key])
                except KeyError:
                    raise MissingMetricError("Missing Metric {0}".format(self.key)) from None
                if self.results[result]["station"]:
                    processed_results["sx"].append(self.results[result]["position"]["x"])
                    processed_results["sy"].append(self.results[result]["position"]["y"])
        self.processed_results = processed_results

    def add_zero_boundary(self):
        """Add 4 zero (vmin or vmax) benchmark points. """
        self.processed_results["x"] += [0, 0, self.floor_map_dimensions[0],
                                        self.floor_map_dimensions[0]]
        self.processed_results["y"] += [0, self.floor_map_dimensions[1],
                                        self.floor_map_dimensions[1], 0]
        self.set_min_max()
        if self.reverse:
            self.processed_results["z"] += [self.vmax] * 4
        else:
            self.processed_results["z"] += [self.vmin] * 4

    def set_floor_map_dimensions(self):
        """Set the floor map dimensions (x, y) from image. """
        im = Image.open(self.floor_map)
        xmax, ymax = im.size
        self.floor_map_dimensions = (xmax, ymax)

    def set_min_max(self):
        if self.vmin is None:
            self.vmin = min(self.processed_results["z"])
        if self.vmax is None:
            self.vmax = max(self.processed_results["z"])

    def apply_conversion(self):
        """If metric is of type bandwidth apply byte to human
        readable size formula. """
        smallest_values = heapq.nsmallest(2, set(self.processed_results["z"]))
        smallest_value = smallest_values[0]
        if self.vmin == smallest_values[0] == 0:
            smallest_value = smallest_values[1]

        limit = bytes_to_human_readable(smallest_value, 2, None)
        if "bits" in self.key:
            if "Byte" in limit[2]:
                self.suffix = limit[2].replace("Byte", "Bit")
            else:
                self.suffix = limit[2].replace("B", "b")
        else:
            self.suffix = limit[2]
        factor = limit[1]
        self.processed_results["z"] = [z_val / factor for z_val in self.processed_results["z"]]
        self.vmin /= factor
        self.vmax /= factor

    def generate_plot(self, levels, dpi, file_type):
        """Generate heatmap plot from resultant metrics.
        Args:
            levels (int): number of countour levels.
            dpi (int): Dots Per Inch resolution for
            certain image types such as png.
            file_type (str): Plot save file type.

        Returns:
            None
        """
        self.process_result()
        self.set_floor_map_dimensions()
        self.add_zero_boundary()
        if self.conversion:
            self.apply_conversion()

        fdimx, fdimy = self.floor_map_dimensions
        xi = np.linspace(0, fdimx, 100)
        yi = np.linspace(0, fdimy, 100)

        xi, yi = np.meshgrid(xi, yi)
        di = Rbf(self.processed_results["x"], self.processed_results["y"],
                 self.processed_results["z"], function="linear")
        zi = di(xi, yi)
        zi[zi < self.vmin] = self.vmin
        zi[zi > self.vmax] = self.vmax

        is_discrete = self.key in ("co_channel_interference", "adjacent_channel_interference", "ap_density")
        if is_discrete and (math.ceil(self.vmax) - math.floor(self.vmin)) >= 1:
            levels_contour = np.arange(math.floor(self.vmin), math.ceil(self.vmax) + 1)
            levels_contourf = levels_contour
            fmt = '%d'
        else:
            levels_contourf = np.linspace(self.vmin, self.vmax, levels + 1)
            levels_contour = np.linspace(self.vmin, self.vmax, 16)
            fmt = '%.1f'

        fig, ax = plt.subplots(1, 1, figsize=(fdimx / 100, fdimy / 100))

        fdim_coef = math.sqrt(fdimx * fdimy)
        
        # Heatmap preenchido com escala intuitiva Semáforo (Cores fortes e vibrantes)
        cmap_name = "RdYlGn_r" if self.reverse else "RdYlGn"
        bench_plot = ax.contourf(xi, yi, zi, cmap=cmap_name, vmin=self.vmin, vmax=self.vmax,
                                 alpha=0.60, zorder=150, antialiased=True, levels=levels_contourf, extend='both')
        
        # Adiciona Isolinhas (Contour Lines) para facilitar a leitura técnica
        contours = ax.contour(xi, yi, zi, levels=levels_contour, colors='black', 
                              linewidths=0.5, alpha=0.3, zorder=155)
        ax.clabel(contours, inline=True, fontsize=max(6, fdim_coef // 140), fmt=fmt, colors='black')
        marker_size = max(4, fdim_coef // 210)
        
        # Diferenciação visual se houver mais de uma rede no benchmarking ativo
        unique_ssids = sorted(list(set(self.processed_results.get("active_ssids", []))))
        if len(unique_ssids) > 1:
            for ssid in unique_ssids:
                indices = [i for i, val in enumerate(self.processed_results["active_ssids"]) if val == ssid]
                ax.plot([self.processed_results["x"][i] for i in indices],
                        [self.processed_results["y"][i] for i in indices],
                        zorder=200, marker='o', markeredgecolor='black', markeredgewidth=0.5,
                        linestyle='None', markersize=marker_size, label=f"Ponto (Rede: {ssid})")
        else:
            ax.plot(self.processed_results["x"], self.processed_results["y"], zorder=200, marker='o',
                    markeredgecolor='black', markeredgewidth=0.5, linestyle='None', markersize=marker_size,
                    label="Benchmark Point")

        ax.plot(self.processed_results["sx"], self.processed_results["sy"], zorder=250, marker='o',
                markeredgecolor='black', markerfacecolor="orange", markeredgewidth=0.5,
                linestyle='None', markersize=marker_size, label="Base Station")

        ax.imshow(imread(self.floor_map)[::-1], interpolation='bicubic', zorder=1, alpha=1,
                  origin="lower")

        title_size = max(10, fdim_coef // 70)
        label_size = max(7, title_size - 5)

        cb = fig.colorbar(bench_plot)
        cb.ax.tick_params(labelsize=label_size)
        desc = ConfigurationOptions.configuration[self.key]["description"]
        if self.suffix is not None:
            desc = desc.format(self.suffix)

        plt.title("{0}".format(desc), fontsize=title_size)
        plt.axis('off')
        plt.legend(
            loc='upper center',
            bbox_to_anchor=(0.5, -0.05),
            ncol=2,
            prop={"size": label_size}
        )
        file_name = "{0}.{1}".format(self.key, file_type)
        plt.savefig(file_name, format=file_type, dpi=dpi)

    def generate_plot_named(self, levels, dpi, file_type, file_label, title_suffix=""):
        """Generate heatmap plot with custom file name and title suffix.
        Used for per-SSID heatmaps.
        """
        self.process_result()
        self.set_floor_map_dimensions()
        self.add_zero_boundary()
        if self.conversion:
            self.apply_conversion()

        fdimx, fdimy = self.floor_map_dimensions
        xi = np.linspace(0, fdimx, 100)
        yi = np.linspace(0, fdimy, 100)

        xi, yi = np.meshgrid(xi, yi)
        di = Rbf(self.processed_results["x"], self.processed_results["y"],
                 self.processed_results["z"], function="linear")
        zi = di(xi, yi)
        zi[zi < self.vmin] = self.vmin
        zi[zi > self.vmax] = self.vmax

        is_discrete = self.key in ("co_channel_interference", "adjacent_channel_interference", "ap_density")
        if is_discrete and (math.ceil(self.vmax) - math.floor(self.vmin)) >= 1:
            levels_contour = np.arange(math.floor(self.vmin), math.ceil(self.vmax) + 1)
            levels_contourf = levels_contour
            fmt = '%d'
        else:
            levels_contourf = np.linspace(self.vmin, self.vmax, levels + 1)
            levels_contour = np.linspace(self.vmin, self.vmax, 16)
            fmt = '%.1f'

        fig, ax = plt.subplots(1, 1, figsize=(fdimx / 100, fdimy / 100))

        # Heatmap preenchido com escala intuitiva Semáforo (Cores fortes e vibrantes)
        cmap_name = "RdYlGn_r" if self.reverse else "RdYlGn"
        bench_plot = ax.contourf(xi, yi, zi, cmap=cmap_name, vmin=self.vmin, vmax=self.vmax,
                                 alpha=0.60, zorder=150, antialiased=True, levels=levels_contourf, extend='both')
        
        fdim_coef = math.sqrt(fdimx * fdimy)

        # Adiciona Isolinhas (Contour Lines) para facilitar a leitura técnica
        contours = ax.contour(xi, yi, zi, levels=levels_contour, colors='black', 
                              linewidths=0.5, alpha=0.3, zorder=155)
        ax.clabel(contours, inline=True, fontsize=max(6, fdim_coef // 140), fmt=fmt, colors='black')
        marker_size = max(4, fdim_coef // 210)
        
        unique_ssids = sorted(list(set(self.processed_results.get("active_ssids", []))))
        if len(unique_ssids) > 1:
            for ssid in unique_ssids:
                indices = [i for i, val in enumerate(self.processed_results["active_ssids"]) if val == ssid]
                ax.plot([self.processed_results["x"][i] for i in indices],
                        [self.processed_results["y"][i] for i in indices],
                        zorder=200, marker='o', markeredgecolor='black', markeredgewidth=0.5,
                        linestyle='None', markersize=marker_size, label=f"Ponto (Rede: {ssid})")
        else:
            ax.plot(self.processed_results["x"], self.processed_results["y"], zorder=200, marker='o',
                    markeredgecolor='black', markeredgewidth=0.5, linestyle='None', markersize=marker_size,
                    label="Benchmark Point")

        ax.plot(self.processed_results["sx"], self.processed_results["sy"], zorder=250, marker='o',
                markeredgecolor='black', markerfacecolor="orange", markeredgewidth=0.5,
                linestyle='None', markersize=marker_size, label="Base Station")

        ax.imshow(imread(self.floor_map)[::-1], interpolation='bicubic', zorder=1, alpha=1,
                  origin="lower")

        title_size = max(10, fdim_coef // 70)
        label_size = max(7, title_size - 5)

        cb = fig.colorbar(bench_plot)
        cb.ax.tick_params(labelsize=label_size)
        desc = ConfigurationOptions.configuration[self.key]["description"]
        if self.suffix is not None:
            desc = desc.format(self.suffix)

        plt.title("{0}{1}".format(desc, title_suffix), fontsize=title_size)
        plt.axis('off')
        plt.legend(
            loc='upper center',
            bbox_to_anchor=(0.5, -0.05),
            ncol=2,
            prop={"size": label_size}
        )
        file_name = "{0}.{1}".format(file_label, file_type)
        plt.savefig(file_name, format=file_type, dpi=dpi)
        plt.close(fig)


@log_arguments
def generate_graph(data, floor_map, levels=100, dpi=300, file_type="png"):
    """Starting point for the plot submodule for whm.

    Args:
        data (str): the path to the configuration file.
        floor_map (str): the path to the floor map.
        levels (int): number of countour levels.
        dpi (int): Dots Per Inch resolution for
        certain image types such as png.
        file_type (str): Plot save file type.

    Returns:
        None
    """
    file_type = file_type.lower().replace(".", "")
    supported_formats = ["png", "pdf", "ps", "eps", "svg"]
    if file_type not in supported_formats:
        logging.error("Unsupported file type: %s", file_type)
        return

    if not isinstance(data, dict):
        data = os.path.abspath(data)
        data = load_json(data)
        if not data:
            logging.error("Could not load configuration file: %s", data)
            return
    benchmark_results = get_property_from(data, "results")
    configuration = get_property_from(data, "configuration")
    graph_modes = ConfigurationOptions.configuration
    target_ssids = configuration.get("target_ssids", [])
    main_ssid = configuration.get("ssid", "Default")

    # Base metric keys that exist per-network
    per_network_metrics = {"signal_strength", "snr_estimated", "signal_quality",
                           "signal_quality_percent", "channel", "channel_frequency"}

    # 1. Generate standard graphs (connected network / iperf / speedtest)
    tqdm_out = sys.stderr if (sys.stderr and hasattr(sys.stderr, 'write')) else NullWriter()
    disable_pbar = not hasattr(tqdm_out, 'write') or isinstance(tqdm_out, NullWriter)

    for key_name in tqdm(configuration["graphs"], desc="Generating Plots", file=tqdm_out, disable=disable_pbar):
        if key_name not in graph_modes:
            logging.warning("Skipping unknown graph key: %s", key_name)
            continue
        vmin = graph_modes[key_name].get("vmin", None)
        vmax = graph_modes[key_name].get("vmax", None)
        logging.debug("Generating plot for {0} with (vmin, vmax) = ({1}, {2})".format(key_name, vmin, vmax))
        try:
            GraphPlot(benchmark_results, key_name, floor_map, vmin=vmin, vmax=vmax,
                      conversion=graph_modes[key_name]["conversion"],
                      reverse=graph_modes[key_name]["reverse"],
                      default_ssid=main_ssid)\
                .generate_plot(levels=levels, dpi=dpi, file_type=file_type)
        except MissingMetricError:
            logging.warning("Metric '%s' not found in results, skipping.", key_name)
        logging.debug("Finished generating plot")

    # 2. Generate per-SSID heatmaps if multi-network data exists
    if target_ssids:
        for ssid_name in tqdm(target_ssids, desc="Generating Per-Network Plots", file=tqdm_out, disable=disable_pbar):
            # Create a virtual copy of results with this SSID's data as the main metrics
            virtual_results = _build_virtual_results_for_ssid(benchmark_results, ssid_name)
            if not virtual_results:
                logging.warning("No data found for SSID '%s', skipping.", ssid_name)
                continue

            # Generate heatmaps for each per-network metric
            for key_name in per_network_metrics:
                if key_name not in graph_modes:
                    continue
                vmin = graph_modes[key_name].get("vmin", None)
                vmax = graph_modes[key_name].get("vmax", None)
                safe_ssid = ssid_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
                file_label = f"{key_name}__{safe_ssid}"
                logging.debug("Generating per-SSID plot: %s", file_label)
                try:
                    plotter = GraphPlot(virtual_results, key_name, floor_map, vmin=vmin, vmax=vmax,
                                        conversion=graph_modes[key_name]["conversion"],
                                        reverse=graph_modes[key_name]["reverse"],
                                        default_ssid=ssid_name)
                    # Override key for file naming and title
                    plotter.generate_plot_named(
                        levels=levels, dpi=dpi, file_type=file_type,
                        file_label=file_label,
                        title_suffix=f" [{ssid_name}]"
                    )
                except MissingMetricError:
                    logging.warning("Metric '%s' for SSID '%s' not found, skipping.", key_name, ssid_name)

    logging.info("Finished plotting.")
    logging.debug("Finished plotting")


def _build_virtual_results_for_ssid(benchmark_results, ssid_name):
    """Create a copy of benchmark results where per-network metrics are
    pulled from results['networks'][ssid_name] to the top level.

    This allows the existing GraphPlot to work unchanged for per-SSID data.
    """
    import copy
    virtual = {}
    has_data = False
    for point_key, point_data in benchmark_results.items():
        vp = copy.deepcopy(point_data)
        if vp.get("results") and vp["results"].get("networks"):
            net_data = vp["results"]["networks"].get(ssid_name)
            if net_data:
                # Override top-level metrics with this SSID's data
                for metric_key, metric_val in net_data.items():
                    vp["results"][metric_key] = metric_val
                has_data = True
            else:
                # SSID not visible at this point — set to worst values
                vp["results"]["signal_strength"] = -100
                vp["results"]["snr_estimated"] = 0
                vp["results"]["signal_quality"] = 0
                vp["results"]["signal_quality_percent"] = 0
                vp["results"]["channel"] = 0
                vp["results"]["channel_frequency"] = 0
        virtual[point_key] = vp
    return virtual if has_data else None

