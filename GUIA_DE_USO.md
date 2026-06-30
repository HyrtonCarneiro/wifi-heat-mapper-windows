# 📖 Guia Definitivo — Wi-Fi Heat Mapper (Professional Academic Edition)

## 🎯 Visão Geral
O **Wi-Fi Heat Mapper** é uma ferramenta de auditoria de rede desenvolvida para Windows, projetada para coletar métricas avançadas de Wi-Fi e gerar mapas de calor precisos. Diferente de ferramentas comuns, este software captura dados de **todas as redes visíveis simultaneamente** de forma **passiva**, sem necessidade de conexão ativa ou internet para a realização das medições.

---

## 🛠️ Fluxo de Trabalho (Passo a Passo)

### 1️⃣ Preparação e Novo Projeto
Execute o `WiFi-Heat-Mapper.exe`. No menu principal, selecione **"Novo Projeto"**.

1.  **Configuração de Rede**: O software detecta automaticamente o nome da sua placa Wi-Fi e a rede conectada.
    *   *Nota*: Agora o software coleta dados de **todas as redes próximas** simultaneamente a cada clique.
2.  **Métricas Selecionadas**: Escolha quais métricas deseja gerar. A lista agora possui uma **barra de rolagem** para facilitar a seleção de todas as métricas acadêmicas.
3.  **Planta Baixa**: Selecione a imagem do local (`.jpg`, `.png`).
4.  **Salvar**: Salve o arquivo `.json`. Recomendamos criar uma pasta por local (ex: `Bloco_725/`) para manter a planta e os dados juntos.

### 2️⃣ Coleta de Dados (Benchmark)
Com o notebook em mãos:
1.  **Opcional - Calibrar Planta**: Se desejar converter pixels para metros, clique em **"Calibrar Planta"**. Clique no início e no fim de uma parede no mapa, em seguida informe a distância real em metros.
2.  Caminhe até um ponto do mapa. No painel lateral, você poderá acompanhar em tempo real o sinal do alvo e o scan de todas as outras redes sendo atualizados continuamente.
3.  **Clique com o botão esquerdo** na planta para marcar sua posição.
4.  **Clique com o botão direito** no ponto e selecione **"Benchmark"**.
5.  O software realizará a captura instantânea de:
    *   Scan completo de todas as redes Wi-Fi (separadas por SSIDs e bandas 2.4/5GHz).
    *   Cálculo automático de interferências (Co-channel e Adjacent).
    *   Métricas de qualidade de sinal baseadas no ambiente local.
6.  Repita o processo em pelo menos **3 a 5 pontos** espalhados pelo ambiente.
7.  Clique em **"Save Results"** ao terminar.

### 3️⃣ Visualização Interativa (Heatmaps)
No menu principal, clique em **"Gerar Mapas de Calor"**. Esta é a ferramenta mais poderosa para sua análise:

*   **Dropdown de Métricas**: Alterne entre Sinal (RSSI), SNR, Canal, **Interferência Co-channel**, **Densidade de APs**, etc. O ícone de 'ⓘ' mostra a descrição da métrica ao passar o mouse.
*   **Seleção de Redes**: Na lateral, as redes detectadas são divididas entre **Redes Abertas** (sem senha) e **Redes Fechadas** (seguras). Marque ou desmarque os SSIDs (ou bandas específicas de um SSID) para ajustar dinamicamente o mapa.
*   **Triangulação de APs**: Ao selecionar uma rede (com a opção habilitada), um ícone de **"X" vermelho** aparecerá no mapa indicando a localização física estimada do roteador.
*   **Escala Calibrada**: Clique em **"Ver Escala Calibrada"** para exibir visualmente a proporção real do ambiente com base na calibração feita na etapa anterior.
*   **Exportar**: Escolha o formato (png, pdf, svg) e clique em **"Salvar Imagem"** para exportar a vista atual com precisão.

### 4️⃣ Geração de Relatórios Acadêmicos
No menu principal, utilize o botão **"Gerar Relatório Acadêmico"**.
*   Selecione o arquivo `.json` do seu projeto.
*   O software gerará um arquivo `_RELATORIO.md` contendo:
    *   Médias de performance de toda a área.
    *   **Inventário Completo de Access Points**: Uma tabela com todos os MACs (BSSIDs), Canais e Tecnologias (Wi-Fi 4, 5, 6 ou 7) detectados.

---

## 🔬 Funcionalidades Avançadas e Termos Acadêmicos

| Funcionalidade | Descrição Acadêmica | Importância para o TCC |
|---|---|---|
| **Co-Channel Interference** | Quantidade de APs operando na mesma frequência. | Identifica saturação do espectro. |
| **PHY Mode Analysis** | Identificação da tecnologia (802.11n/ac/ax). | Analisa a obsolescência da infraestrutura. |
| **AP Density** | Quantidade de SSIDs detectados por ponto. | Avalia redundância e poluição de sinais. |
| **SNR Estimado** | Relação entre o sinal desejado e o ruído de fundo. | Mede a qualidade real do link de rádio. |

---

## 📂 Organização de Arquivos Sugerida
Para um TCC organizado, mantenha uma estrutura de diretórios:
```
Software/
└── wifi-heat-mapper/
    ├── WiFi-Heat-Mapper.exe
    ├── Bloco_725/
    │   ├── planta_725.png
    │   ├── dados_coletados.json
    │   ├── dados_coletados_RELATORIO.md
    │   └── heatmap_sinal_UFC_WIFI.png
    └── Bloco_710/
        ├── ...
```

---

## 🪵 Diagnóstico e Logs
Caso ocorra qualquer erro inesperado, verifique o arquivo `whm_debug.log` na raiz do programa. Ele registra cada scan e erro de interface Wi-Fi detalhadamente.
