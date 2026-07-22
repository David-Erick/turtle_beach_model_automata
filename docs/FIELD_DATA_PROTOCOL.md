# Protocolo de dados para calibração integral de uma praia

## 1. Unidade espacial e sistema de coordenadas

Defina um sistema local em metros:

- `x = 0`: referência terrestre ou pé da duna;
- `x > 0`: direção do oceano;
- `y`: posição ao longo da costa.

Registre a transformação entre coordenadas geográficas e o sistema local. Use o mesmo datum, origem e orientação para luz, ninhos, perfil e trajetórias.

## 2. Perfil de praia

Para cada transecto ao longo de `y`, registre:

```text
y_m,waterline_x_m,dune_height_m,slope_deg,source_status,notes
```

Recomendações:

- medir em mais de uma maré e registrar horário e nível da água;
- registrar o pé e a crista da duna;
- usar RTK-GNSS, estação total, LiDAR ou fotogrametria validada;
- documentar a incerteza de cada medida;
- evitar combinar perfil de uma data com comportamento de outra sem justificar.

## 3. Campo luminoso

O modelo aceita medições direcionais em formato longo:

```text
site_id,latitude,longitude,y_m,direction,mag_arcsec2
```

Direções reconhecidas:

- `dune`;
- `ocean`;
- `north`;
- `south`;
- `zenith`.

Registre também, em arquivo auxiliar ou novas colunas:

- data, hora e fuso;
- altura e orientação do sensor;
- cobertura de nuvens;
- fase, fração iluminada, altitude e azimute lunar;
- maré;
- tipo de instrumento;
- número de repetições;
- espectro/cor correlata das fontes;
- presença de vegetação, edificações e blindagem.

O SQM fornece brilho em `mag/arcsec²`, não lux e nem uma função de sensibilidade específica da tartaruga. Para calibração espectral, prefira radiometria calibrada por comprimento de onda ou câmera calibrada, mantendo o SQM como medida complementar.

## 4. Ninhos

Formato:

```text
nest_id,x_m,y_m,weight,source_status,notes
```

- use a posição real de emergência;
- `weight` pode representar a frequência relativa de emergência no experimento;
- registre espécie, data, tamanho da emergência e tratamento do ninho.

## 5. Trajetórias

Filme com infravermelho não visível para os filhotes e digitalize:

```text
turtle_id,nest_id,time_s,x_m,y_m,outcome
```

A frequência de amostragem deve ser suficiente para não omitir mudanças de direção. Registre o ponto inicial, a linha d'água e os limites do campo visual.

Desfechos padronizados:

- `sea`;
- `predated`;
- `exhausted`;
- `landward_exit`;
- `lateral_exit`;
- `censored`.

Não descarte indivíduos sem desfecho: classifique-os como censurados.

## 6. Desenho amostral

Inclua variação em:

- noites escuras e claras;
- diferentes setores de iluminação;
- fontes blindadas e não blindadas;
- distâncias da fonte;
- perfis de duna;
- diferentes larguras de praia.

Separe dados por noite ou ninho entre calibração e validação. Uma divisão aleatória de pontos da mesma trajetória cria dependência e superestima o desempenho.

## 7. Predação e exaustão

Se não houver dados próprios, mantenha os módulos desativados ou trate-os em análise de sensibilidade. Para calibrar:

- registre tempo e posição de eventos de predação;
- estime risco por unidade de tempo/exposição;
- meça velocidade e duração de travessia;
- evite converter automaticamente toda demora em mortalidade.

## 8. Controle de qualidade

Antes da calibração:

1. desenhe todas as trajetórias sobre o mapa;
2. confirme que o oceano está no sentido positivo de `x`;
3. verifique unidades e fusos;
4. procure saltos incompatíveis com a velocidade física;
5. confira se cada ninho está dentro do perfil correspondente;
6. preserve os dados brutos e produza uma tabela derivada separada.
