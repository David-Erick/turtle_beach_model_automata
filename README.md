# Modelo calibrável de orientação de filhotes de tartarugas marinhas

Este projeto estrutura o autômato celular como um **modelo espacial estocástico, fisicamente escalado e calibrável para uma praia**. O eixo transversal `x` vai da duna para o oceano; o eixo `y` acompanha a linha da costa. A escolha de movimento combina pista marítima, campo luminoso artificial direcional, silhueta da duna, declividade, persistência e variabilidade individual.

## Estado da calibração incluída

O pacote contém três tipos de informação, identificados explicitamente nos arquivos:

| Componente | Estado no exemplo de Delray Beach |
|---|---|
| Campo luminoso | **Medido**: nove locais, quatro direções horizontais e zênite, em 17/08/2020 |
| Distância da duna à água, altura da duna, ninhos e obstáculos | **Demonstração**: devem ser substituídos por levantamento local |
| Parâmetros comportamentais | **Demonstração sintética**: o fluxo de calibração funciona, mas não é uma estimativa biológica final |

Portanto, a configuração `delray_demo.yaml` é uma **calibração ambiental parcial e um estudo computacional reproduzível**. Ela só se torna uma calibração integral da praia depois da substituição do perfil, dos ninhos e das trajetórias sintéticas por dados observados no mesmo setor e período.

## Estrutura do projeto

```text
configs/
  delray_demo.yaml                parâmetros e cenários
data/
  delray_sqm_mean.csv             medições direcionais publicadas
  delray_beach_profile_demo.csv   perfil demonstrativo
  delray_nests_demo.csv           ninhos demonstrativos
  obstacles_demo.csv              obstáculos demonstrativos
  observed_coordinates_template.csv
  observed_tracks_template.csv
docs/
  MODEL_SPECIFICATION.md          descrição matemática e protocolo ODD
  FIELD_DATA_PROTOCOL.md          protocolo para transformar o exemplo em estudo real
turtle_beach_model/
  config.py                       leitura e validação do YAML
  environment.py                  praia, luz, duna, declive e obstáculos
  agents.py                       estado individual
  movement.py                     utilidade e Softmax
  processes.py                    energia e risco de predação
  simulation.py                   motor temporal
  observations.py                 resumo de trajetórias de vídeo
  calibration.py                  ajuste por evolução diferencial
  validation.py                   validação luminosa e comportamental
  sensitivity.py                  hipercubo latino e correlação de Spearman
  experiments.py                  Monte Carlo por cenário
  metrics.py                      métricas e intervalos
  plots.py                        figuras
  cli.py                          comandos
outputs_demo/                     resultados já gerados para conferência
tests/                            testes automatizados
```

# 1. Instalação

Requer Python 3.10 ou superior.

## Windows — PowerShell

```powershell
cd turtle_beach_model
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

## Linux ou macOS

```bash
cd turtle_beach_model
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

Verifique a instalação:

```bash
python -m unittest discover -s tests -v
```

# 2. Executar a demonstração completa

No Windows:

```bat
scripts\run_delray_demo.bat
```

No Linux/macOS:

```bash
sh scripts/run_delray_demo.sh
```

Comando equivalente:

```bash
python -m turtle_beach_model.cli demo \
  --config configs/delray_demo.yaml \
  --output-dir outputs_demo \
  --quick \
  --synthetic-replicates 4 \
  --synthetic-turtles 25 \
  --replicates 8 \
  --n-turtles 30 \
  --validation-data-replicates 2 \
  --validation-replicates 4 \
  --validation-turtles 20 \
  --sensitivity-samples 16 \
  --sensitivity-turtles 15
```

A demonstração realiza, nesta ordem:

1. geração de um conjunto sintético para calibração;
2. geração de um segundo conjunto sintético independente para validação;
3. calibração rápida dos parâmetros comportamentais;
4. validação cruzada do campo luminoso;
5. validação comportamental demonstrativa;
6. Monte Carlo para seis cenários;
7. criação das figuras;
8. análise global de sensibilidade.

O modo `--quick` foi feito para verificar o fluxo. O arquivo `calibration.json` pode informar que o máximo de iterações foi atingido; isso não equivale a uma calibração científica concluída. Para a análise final, execute a calibração sem `--quick` e examine convergência, estabilidade e identificabilidade.

# 3. Fluxo para uma praia real

## 3.1 Substitua os dados ambientais

Edite ou substitua:

- `data/delray_beach_profile_demo.csv`;
- `data/delray_nests_demo.csv`;
- `data/obstacles_demo.csv`;
- `data/delray_sqm_mean.csv`.

Depois, atualize os caminhos em um novo YAML, por exemplo `configs/minha_praia.yaml`.

Valide os arquivos:

```bash
python -m turtle_beach_model.cli validate-data \
  --config configs/minha_praia.yaml
```

Valide a interpolação do campo luminoso:

```bash
python -m turtle_beach_model.cli validate-light \
  --config configs/minha_praia.yaml \
  --output outputs/light_validation.json
```

A validação luminosa usa exclusão de um local por vez. O RMSE mede o erro de interpolação em `mag/arcsec²`; ele não prova que o SQM representa sozinho toda a percepção visual do filhote.

## 3.2 Digitalize trajetórias reais

Crie um CSV no formato de `data/observed_coordinates_template.csv`:

```text
turtle_id,nest_id,time_s,x_m,y_m,outcome
```

- `x_m`: distância transversal, positiva em direção ao oceano;
- `y_m`: posição ao longo da costa;
- `time_s`: tempo desde o início da observação;
- `outcome`: `sea`, `predated`, `exhausted`, `landward_exit`, `lateral_exit` ou `censored`.

Converta as coordenadas em resumos:

```bash
python -m turtle_beach_model.cli summarize-observed \
  --config configs/minha_praia.yaml \
  --coordinates data/trajetorias_coordenadas.csv \
  --output data/trajetorias_resumo.csv
```

## 3.3 Separe calibração e validação

Não use os mesmos indivíduos para ajustar e validar. Separe por noite, ninho ou setor de praia, não apenas por linhas aleatórias, para reduzir vazamento de informação.

Exemplo conceitual:

```text
data/tracks_calibration.csv
  noites 1–6

data/tracks_validation.csv
  noites 7–8
```

## 3.4 Calibre o comportamento

```bash
python -m turtle_beach_model.cli calibrate \
  --config configs/minha_praia.yaml \
  --observed data/tracks_calibration.csv \
  --output outputs/calibration.json
```

O otimizador ajusta, por padrão:

- `kappa_sea`: resposta à pista marítima;
- `kappa_artificial`: resposta ao campo artificial;
- `persistence`: tendência de manter o rumo anterior;
- `temperature`: aleatoriedade da Softmax.

Os limites ficam em `calibration.bounds` no YAML. A função objetivo compara chegada ao mar, desorientação operacional, tempo de travessia, eficiência de trajetória e erro angular inicial.

## 3.5 Valide em dados independentes

```bash
python -m turtle_beach_model.cli validate-calibration \
  --config configs/minha_praia.yaml \
  --observed data/tracks_validation.csv \
  --calibration outputs/calibration.json \
  --output outputs/behavior_validation.json \
  --replicates 30
```

Não aceite o modelo apenas porque ele reproduz os dados de calibração. Compare os erros do JSON de validação e verifique se as conclusões se mantêm em diferentes noites, fases lunares e setores.

## 3.6 Execute os cenários

```bash
python -m turtle_beach_model.cli experiment \
  --config configs/minha_praia.yaml \
  --calibration outputs/calibration.json \
  --output-dir outputs/experiments \
  --replicates 100 \
  --n-turtles 50
```

Gere as figuras:

```bash
python -m turtle_beach_model.cli plot \
  --config configs/minha_praia.yaml \
  --experiment-dir outputs/experiments \
  --calibration outputs/calibration.json
```

## 3.7 Analise a sensibilidade

```bash
python -m turtle_beach_model.cli sensitivity \
  --config configs/minha_praia.yaml \
  --output-dir outputs/sensitivity \
  --samples 128 \
  --n-turtles 50
```

A correlação de Spearman indica associação monotônica, não causalidade isolada. Parâmetros correlacionados ou não identificáveis exigem perfis de verossimilhança, calibração Bayesiana ou novos dados experimentais.

# 4. Arquivos de saída

## `calibration.json`

Campos principais:

- `parameters`: valores ajustados;
- `objective`: erro ponderado final;
- `success`: critério numérico de convergência do otimizador;
- `observed_metrics` e `simulated_metrics`: comparação do ajuste;
- `n_function_evaluations`: custo computacional.

Um `success=false` no modo rápido significa que o limite curto de iterações foi atingido. Não use esse ajuste para conclusões finais.

## `scenario_summary.csv`

Cada linha representa um cenário. As colunas terminadas em:

- `_mean`: média entre repetições;
- `_sd`: desvio-padrão entre repetições;
- `_ci95_low` e `_ci95_high`: intervalo aproximado de 95% da média.

## `turtle_results.csv`

Uma linha por indivíduo simulado. Use para modelos estatísticos, distribuições e inspeção dos desfechos.

## `sample_tracks.csv`

Trajetórias das primeiras repetições de cada cenário, usadas nas figuras. O número de repetições salvas é controlado por `track_replicates_to_save`.

## `behavior_validation.json`

Compara dados independentes e simulação. Priorize:

- diferença de chegada ao mar;
- diferença da taxa de desorientação;
- erro do tempo mediano;
- erro da eficiência;
- erro angular inicial.

## `sensitivity_spearman.csv`

- valor positivo: aumento do parâmetro associa-se ao aumento da saída;
- valor negativo: aumento do parâmetro associa-se à redução da saída;
- valor próximo de zero: pouca associação monotônica no intervalo analisado.

# 5. Como interpretar os resultados demonstrativos

Na execução fornecida, a calibração comportamental usa dados sintéticos e a geometria é demonstrativa. Assim, os números abaixo comprovam o funcionamento do experimento, não a mortalidade real de Delray Beach.

A execução de referência produziu aproximadamente:

| Cenário | Chegada ao mar | Desorientação operacional | Tempo mediano até o mar |
|---|---:|---:|---:|
| `baseline` | 0,66 | 0,90 | 700 s |
| `lights_off` | 0,95 | 0,17 | 426 s |
| `shielded_70pct` | 0,91 | 0,38 | 478 s |
| `amber_proxy` | 0,92 | 0,48 | 516 s |
| `bright_moon_proxy` | 0,83 | 0,62 | 531 s |
| `combined_mitigation` | 0,95 | 0,12 | 421 s |

Interpretação correta:

> Sob a geometria assumida, os parâmetros sintéticos e a decomposição operacional do campo luminoso, a redução da componente artificial aumentou a chegada ao mar e reduziu a tortuosidade/desorientação definida pelo modelo.

Interpretação incorreta:

> Desligar as luzes reais de Delray Beach elevará a sobrevivência para exatamente 95%.

A segunda frase não é sustentada, porque faltam perfil topográfico real, ninhos e trajetórias locais no mesmo período, além de calibração espectral e de predação.

# 6. Definições das métricas

- **Chegada ao mar:** o agente alcançou `x >= waterline_x(y)`.
- **Eficiência:** distância direta até a água dividida pelo comprimento percorrido.
- **Ângulo inicial:** direção do deslocamento acumulado nos primeiros metros, relativa ao eixo marítimo.
- **Desorientação operacional:** ângulo inicial acima do limite, eficiência abaixo do limite ou saída pela borda terrestre/lateral. Esta definição é computacional e deve ser comparada cuidadosamente com o protocolo de campo usado.
- **Censurado:** o desfecho não foi observado até `max_time_s`; o indivíduo permanece no denominador.
- **Predação:** risco probabilístico por tempo de exposição. Os coeficientes incluídos são demonstrativos até serem calibrados.

# 7. Reprodutibilidade e controle de qualidade

- Use sementes registradas no YAML.
- Preserve os arquivos de entrada e o `calibration.json` junto aos resultados.
- Execute os testes antes de cada análise.
- Faça estudo de convergência aumentando repetições e indivíduos.
- Não mude simultaneamente dados, código e parâmetros sem registrar a versão.
- Relate separadamente parâmetros medidos, calibrados, assumidos e explorados.

# 8. Referências centrais

- Hirama, S. et al. (2022). *Light brightness data near sea turtle nests as measured from the horizon and zenith using a Sky Quality Meter*. Data in Brief, 43, 108430. DOI: 10.1016/j.dib.2022.108430.
- Stanley, T. R. et al. (2020). *Brightness of the Night Sky Affects Loggerhead Sea Turtle Hatchling Misorientation but Not Nest Site Selection*. Frontiers in Marine Science, 7, 221. DOI: 10.3389/fmars.2020.00221.
- Celano, L. et al. (2018). *Seafinding revisited: how hatchling marine turtles respond to natural lighting at a nesting beach*. Journal of Comparative Physiology A, 204, 1007–1015. DOI: 10.1007/s00359-018-1299-4.
- Salmon, M. et al. (1992). *Seafinding by hatchling sea turtles: role of brightness, silhouette and beach slope as orientation cues*. Behaviour, 122, 56–77.
- Grimm, V. et al. (2020). *The ODD Protocol for Describing Agent-Based and Other Simulation Models: A Second Update*. JASSS, 23(2), 7. DOI: 10.18564/jasss.4259.
- Schiff, J. L. (2008). *Cellular Automata: A Discrete View of the World*. Wiley-Interscience.
