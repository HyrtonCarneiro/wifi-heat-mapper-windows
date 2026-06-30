# APÊNDICE: Arquitetura e Implementação do Sistema

## 1. Visão Geral e Requisitos do Sistema

- **Descrição Sucinta:** O software tem como propósito a coleta passiva de métricas de rádio para o diagnóstico e análise de redes Wi-Fi, permitindo a geração de mapas de cobertura e a visualização da saúde da rede local.
- **Ambiente de Execução:** O sistema foi projetado levando em consideração a portabilidade, possuindo uma transição bem-sucedida de um ambiente primário em Linux para uma execução robusta no Windows.
- **Requisitos de Hardware/Software:** O sistema opera em ambiente Windows e interage com a placa de rede por meio de drivers NDIS padrão. Não é necessária a utilização de hardware especial ou de firmwares/drivers modificados, aproveitando as interfaces nativas do sistema operacional para as coletas.

## 2. Arquitetura Lógica e Fluxo de Dados

O funcionamento do sistema é segmentado em três grandes processos descritos a seguir de maneira procedimental:

### Fase de Captura (Ingestão)
O software precisa coletar as informações do meio sem fio sem necessitar de uma associação ativa a cada rede (Access Point).
Para realizar isso em ambiente Windows:
1. O sistema faz uso da API nativa de redes sem fio (`wlanapi.dll`).
2. Ele dispara chamadas de sistema para solicitar varreduras e acessar os resultados em cache.
3. Isso permite que o software capture os quadros de gerenciamento (especialmente *Beacons*) enviados pelos APs de forma completamente transparente.

### Fase de Processamento Matemático
Após a coleta dos dados brutos da interface, o sistema aplica cálculos matemáticos para extrair métricas de qualidade:

- **Decodificação do BSS Load (QBSS):**
  Realiza-se a conversão binária da tag *BSS Load Element* (Element ID 11) contida nos *Beacons*. O byte correspondente ao *Channel Utilization* (valor de 0 a 255) é extraído e convertido para refletir a utilização de canal em porcentagem.

- **Coleta e Representação do RSSI:**
  O *Received Signal Strength Indicator* (RSSI) é extraído diretamente da estrutura de rede retornada pelas varreduras do sistema operacional (da API WLAN nativa). Ele é reportado em decibéis-miliwatt (dBm), representando a potência do sinal recebido pela placa de rede no momento exato da captura, oscilando em valores tipicamente negativos (ex: de $-30\text{ dBm}$ a $-90\text{ dBm}$).

- **Cálculo do SNR Estimado:**
  Devido às limitações da camada de abstração de hardware (HAL), que muitas vezes não reporta o nível de ruído base dinamicamente, adota-se uma abordagem conservadora. Utiliza-se um piso de ruído estático fixado em $-92\text{ dBm}$. Assim, a Relação Sinal-Ruído (SNR) é calculada como:
  $$SNR = RSSI + 92$$

- **Conversão de Frequência para Canal:**
  Os canais operacionais correspondentes são derivados convertendo a frequência portadora central bruta através das seguintes fórmulas (considerando a frequência em MHz):
  $$\text{Canal (2.4 GHz)} = \frac{\text{Frequência} - 2407}{5}$$
  $$\text{Canal (5 GHz)} = \frac{\text{Frequência} - 5000}{5}$$

- **Contadores de Interferência (CCI e ACI):**
  - **Interferência Co-canal (CCI):** O algoritmo contabiliza o número de redes operando no exato mesmo canal da rede alvo.
  - **Interferência de Canal Adjacente (ACI):** O sistema aplica uma regra de verificação nos canais vizinhos. Na banda legada (2.4 GHz), contabilizam-se as redes operando no intervalo de $\pm1$ a $\pm4$ canais em relação ao canal analisado, evidenciando o impacto de sobreposição de frequências.

### Fase de Interpolação Gráfica
Para a visualização dos dados em formato de mapa de calor:
1. **Algoritmo RBF:** O sistema utiliza o algoritmo de Função de Base Radial (RBF) para interpolar espacialmente as amostras capturadas, gerando uma malha densa de $100\times100$ células.
2. **Contenção de Bordas:** Para evitar extrapolações errôneas do mapa de calor em áreas não caminhadas (onde a matemática do RBF poderia gerar valores altos artificiais), o sistema insere pontos de borda fictícios ao redor da área de coleta forçando o valor para o mínimo aceitável ($vmin = -90\text{ dBm}$).

## 3. Snippets de Código Críticos (Trechos Essenciais)

### Cálculo de Interferência (CCI e ACI)
Este algoritmo é executado durante o processo de *Site Survey*. Ele calcula matematicamente a poluição do espectro, diferenciando o comportamento de sobreposição da banda de 2.4 GHz (onde canais próximos se sobrepõem) da banda de 5 GHz.

```python
# 'connected_channel' é o canal da rede alvo sendo analisada
# 'net' é a rede vizinha capturada no scan passivo
if connected_channel > 0 and net['channel'] > 0:
    ch_diff = abs(net['channel'] - connected_channel)
    
    # Verifica se ambas as redes estão operando na banda de 2.4 GHz (Canais 1-14)
    is_2g = connected_channel <= 14 and net['channel'] <= 14
    
    # Interferência Co-Canal (CCI)
    if net['channel'] == connected_channel:
        co_interf += net.get('ap_count', 1)
        
    # Interferência de Canal Adjacente (ACI)
    elif is_2g and 1 <= ch_diff <= 4:
        # Na banda de 2.4GHz canais vizinhos até 4 números de distância se sobrepõem fisicamente
        adj_interf += net.get('ap_count', 1)
        
    elif not is_2g and ch_diff == 1:
        # Na banda de 5GHz, consideramos apenas canais imediatamente vizinhos
        adj_interf += net.get('ap_count', 1)

# O próprio AP alvo é subtraído do contador de CCI
results["co_channel_interference"] = max(0, co_interf - 1)
results["adjacent_channel_interference"] = adj_interf
```

### Algoritmo de Interpolação do Heatmap (RBF)
No processo de geração dos mapas de calor, o sistema coleta os pontos de amostra física e utiliza a Função de Base Radial para prever matematicamente a força do sinal em todos os pixels (matriz 100x100) da planta baixa.

```python
import numpy as np
from scipy.interpolate import Rbf

# Cria a malha de pixels (grid) de 100x100 baseada no tamanho da planta (fdimx, fdimy)
xi = np.linspace(0, fdimx, 100)
yi = np.linspace(0, fdimy, 100)
xi, yi = np.meshgrid(xi, yi)

# (xs, ys, zs) são as listas de coordenadas (x, y) e métricas (ex: RSSI ou SNR) coletadas
# Interpolação espacial matemática (RBF Linear)
di = Rbf(xs, ys, zs, function="linear")
zi = di(xi, yi)

# Fixação das bordas para impedir que o modelo matemático extrapole e crie
# cores falsas em regiões muito distantes do sinal (fora do domínio conhecido)
zi[zi < vmin] = vmin
zi[zi > vmax] = vmax
```

### Decodificação Binária do BSS Load (QBSS)
Este trecho demonstra o percurso pelos bytes dos *Information Elements* buscando extrair a tag de Element ID 11 correspondente ao BSS Load.

```python
def parse_bss_load_utilization(ie_bytes):
    """
    Extrai a métrica de utilização do canal (QBSS) em porcentagem.
    """
    idx = 0
    length = len(ie_bytes)
    
    while idx < length:
        element_id = ie_bytes[idx]
        element_length = ie_bytes[idx + 1]
        
        # BSS Load Element ID é 11
        if element_id == 11 and element_length >= 3:
            # station_count = int.from_bytes(ie_bytes[idx+2:idx+4], 'little')
            channel_util = ie_bytes[idx + 4]
            
            # Converte o byte (0-255) para porcentagem (0-100%)
            return (channel_util / 255.0) * 100.0
            
        idx += 2 + element_length
        
    return None  # Não encontrado no Beacon
```

## 4. Interface Gráfica e Modo de Uso

A operação do sistema através de sua interface gráfica baseia-se em um fluxo de trabalho intuitivo, desde a captura até a análise:

1. **Escaneamento em Tempo Real:** 
   Na tela principal, ao iniciar a varredura, uma tabela central é atualizada dinamicamente exibindo todas as redes detectadas, mostrando o SSID, canal, RSSI, SNR, interferência (CCI/ACI) e a utilização do canal (QBSS) em tempo real.
2. **Registro de Pontos de Medição (Site Survey):** 
   O usuário carrega a imagem da planta baixa do local no painel de visualização. Conforme caminha fisicamente pelo ambiente, o usuário dá um clique no mapa na posição correspondente à sua localização física atual. O software captura as métricas de rádio de forma passiva para todas as redes ao alcance naquele instante e associa esse conjunto de medições à coordenada $(x, y)$ da planta baixa.
3. **Geração dos Mapas de Calor:** 
   Após mapear a área coletando pontos representativos, o usuário solicita a geração do mapa de calor (botão "Gerar Mapa"). O software executa a interpolação RBF sobre a malha de dados capturados e projeta uma camada translúcida colorida (gradiente térmico) sobre a planta baixa. O usuário pode alternar a visualização para analisar o mapa de calor de diferentes SSIDs detectados ou focar em métricas específicas como RSSI ou SNR.
4. **Relatórios e Análises:** 
   Os resultados processados (o mapa de calor georreferenciado e as estatísticas dos pontos) podem ser salvos ou exportados através das opções de salvar mapa ou gerar relatórios de forma simples pelo menu superior.
