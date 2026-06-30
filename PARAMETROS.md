# Parâmetros e Métricas de Benchmark

Este documento descreve todos os parâmetros, métricas e dados obtidos durante o processo de benchmarking no **Wi-Fi Heat Mapper**. Ele detalha o significado de cada dado e como ele é coletado ou calculado.

## 1. Métricas de Wi-Fi (Camada Física e Link)

Esses dados são obtidos diretamente do sistema operacional (Windows) ou calculados com base neles.

| Parâmetro | Descrição | Origem | Onde Ver |
| :--- | :--- | :--- | :--- |
| `ssid` | Nome da rede Wi-Fi conectada ou detectada. | Windows (WLAN API) | Relatório e Heatmaps |
| `ssid_mac` | Endereço físico (BSSID) do Ponto de Acesso (AP). | Windows (WLAN API) | JSON (Apenas) |
| `signal_strength` | Força do sinal recebido (RSSI) em **dBm**. | Windows (WLAN API) | Ambos |
| `channel` | Canal de operação da rede. | Windows (WLAN API) | Relatório e Heatmaps |
| `channel_frequency` | Frequência central do canal em **MHz**. | Windows (WLAN API) | JSON (Apenas) |
| `phy_type` | Padrão 802.11 em uso (ex: 802.11n, 802.11ac, 802.11ax). | Windows (WLAN API) | JSON (Apenas) |
| `is_secure` | Flag indicando se a rede possui senha/criptografia (True) ou se é aberta (False). | Windows (WLAN API) | Relatório |
| `bss_type` | Tipo de rede (ex: Infrastructure, Ad-Hoc). Permite detectar hotspots de celular. | Windows (WLAN API) | Relatório |
| `beacon_period` | Intervalo em que o roteador anuncia sua presença (Padrão: 100 TUs). | Windows (WLAN API) | JSON (Apenas) |
| `bss_load_station_count` | Quantidade de dispositivos conectados simultaneamente naquele roteador. | Windows (WLAN API) | Heatmaps (Tooltip) |
| `bss_load_channel_utilization` | Porcentagem de ocupação real do canal de rádio. | Windows (WLAN API) | Heatmaps (Tooltip) |
| `vendor` | Fabricante do roteador, deduzido a partir dos primeiros 3 bytes do MAC Address (OUI). | Dicionário Interno | Ambos |
| `signal_quality` | Escala linear de qualidade (RSSI + 110). | Calculado (Python) | Heatmaps |
| `signal_quality_percent` | Qualidade do sinal em porcentagem (0-100%). | Calculado (Python) | Heatmaps |
| `snr_estimated` | Relação Sinal-Ruído estimada (Sinal - Ruído Base de -92dBm). | Calculado (Python) | Relatório e Heatmaps |
| `ap_density` | Quantidade total de redes (BSSIDs) visíveis no local. | Calculado (Python) | Relatório |
| `co_channel_interference` | Número de redes operando no mesmo canal que o alvo. | Calculado (Python) | JSON (Apenas) |
| `adjacent_channel_interference` | Número de redes operando em canais adjacentes (sobrepostos). | Calculado (Python) | Relatório (Média) |

---

## 2. Dados de Localização e Ambiente

| Parâmetro | Descrição | Origem | Onde Ver |
| :--- | :--- | :--- | :--- |
| `position (x, y)` | Coordenadas do ponto de medição no mapa de calor. | Interface (Manual) | Heatmaps |
| `timestamp` | Data e hora exata em que a medição foi realizada. | Sistema (Automático) | Heatmaps (Tooltip) |
| `adapter_description` | Nome da placa Wi-Fi utilizada (salvo nas configurações globais do projeto). | Windows (Automático) | Relatório |
| `station` | Flag indicando se o ponto foi marcado como uma Estação Fixa. | Interface (Manual) | Heatmaps |
| `pixels_per_meter` | Escala da planta (utilizada para cálculos de distância). | Calibração (Manual) | JSON (Apenas) |
| `scale_p1` | Coordenadas do primeiro ponto selecionado na calibração de escala. | Interface (Manual) | JSON (Apenas) |
| `scale_p2` | Coordenadas do segundo ponto selecionado na calibração de escala. | Interface (Manual) | JSON (Apenas) |
| `scale_meters` | Distância real, em metros, informada pelo usuário entre p1 e p2. | Interface (Manual) | JSON (Apenas) |
| `networks` | Dicionário contendo os dados de todas as redes detectadas (com sufixo de banda, ex: `[2.4GHz]`), permitindo isolar a análise para um único AP ou banda. | Calculado (Python) | Relatório e JSON |

---

## 3. Equações Matemáticas e Modelos de Propagação

Abaixo estão as fórmulas utilizadas pelo software para cálculos derivados a partir das medições reais de rede.

### 3.1. Qualidade de Sinal e SNR (Calculados a partir do RSSI)

- **Signal Quality (Escala Linear):**  
  Mapeia o sinal para uma escala positiva simplificada, assumindo `-110 dBm` como o limite inferior de recepção.
  $$ \text{Signal Quality} = RSSI + 110 $$

- **Signal Quality Percent (%):**  
  Converte a qualidade linear para um valor percentual de 0 a 100%, onde sinais acima de `-40 dBm` chegam perto de 100% e `-110 dBm` é 0%.
  $$ \text{Percentual (\%)} = \min\left( (RSSI + 110) \times \frac{10}{7}, 100 \right) $$

- **SNR Estimado (Signal-to-Noise Ratio):**  
  Estima a Relação Sinal-Ruído (margem do sinal útil acima do ruído de fundo) subtraindo um "Noise Floor" padrão de `-92 dBm` do RSSI captado.
  $$ \text{SNR (dB)} = RSSI - (-92) $$


---

## Observações Técnicas

1.  **Coleta Windows**: O software prioriza a `wlanapi.dll` nativa do Windows para obter dados precisos de BSSID e RSSI. Caso falhe, utiliza o comando `netsh wlan show interfaces` como fallback.
2.  **Cálculo de Interferência**:
    - **Co-channel**: Conta APs no mesmo canal.
    - **Adjacent**: Em 2.4 GHz, considera a sobreposição física real de canais de 20/22 MHz (interferência espectral significativa ocorre para canais vizinhos a uma distância de até $\pm 4$ canais). Em 5 GHz, por não haver sobreposição nativa de canais adjacentes padrão, considera apenas a distância imediata de canal.
3.  **Tratamento de Pontos sem Cobertura (Zonas de Sombra)**: Nos locais onde o SSID selecionado não foi detectado (RSSI abaixo do limite de recepção da placa), o software define valores mínimos padrão (ex: RSSI = $-100$ dBm, SNR = $0$ dB) em vez de omitir o ponto. Isso garante rigor científico na interpolação RBF, evitando a falsa extrapolação de sinal alto sobre áreas de sombra do mapa de calor.
4.  **Análise Passiva**: Esta versão do software realiza exclusivamente a coleta passiva de dados, o que significa que não há geração de tráfego artificial (benchmark ativo) nem necessidade de conexão ativa com a internet ou servidores locais (iperf) para a coleta de métricas.

