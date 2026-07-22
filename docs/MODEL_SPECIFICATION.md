# Especificação matemática e ODD resumido

## Propósito

Estimar como pistas luminosas naturais e artificiais, geometria da praia e variabilidade individual alteram orientação, tempo de travessia e probabilidade de alcançar a água.

## Entidades

- célula de praia;
- filhote;
- campo luminoso direcional;
- perfil da duna e linha d'água;
- obstáculo.

## Escalas

- espaço: `cell_size_m`;
- tempo: `dt_s`;
- domínio: `0 <= x <= waterline_x(y)` e `0 <= y <= length_m`.

## Conversão do SQM

Para magnitude direcional `m_d`:

\[
R_d = 10^{-0.4(m_d-m_{ref})}.
\]

`R_d` é radiância relativa. Valores menores de magnitude representam maior brilho.

## Pista marítima

\[
B_{sea}(y)=\frac{R_{ocean}(y)}{\operatorname{mediana}(R_{ocean})}.
\]

O vetor marítimo aponta no sentido positivo de `x`.

## Componente artificial operacional

\[
A_x(y)=-\frac{[R_{dune}(y)-R_{ocean}(y)]_+}{\widetilde R_{ocean}},
\]

\[
A_y(y)=\frac{[R_{north}(y)-R_{ocean}(y)]_+-[R_{south}(y)-R_{ocean}(y)]_+}{\widetilde R_{ocean}}.
\]

Essa decomposição não separa fisicamente cada fóton natural e artificial. Ela transforma o contraste direcional observado em um vetor concorrente.

No ponto `(x,y)`:

\[
\mathbf A(x,y)=a_s w_s (1-h_s)
\exp(-x/\lambda_A)
\exp(-\gamma\theta_D)
\mathbf A(y).
\]

- `a_s`: escala do cenário;
- `w_s`: peso espectral proxy;
- `h_s`: blindagem;
- `lambda_A`: decaimento transversal;
- `theta_D`: ângulo aparente da duna.

## Silhueta da duna

\[
\theta_D=\operatorname{atan2}(H_D-H_{eye},\max(x,\epsilon)),
\]

\[
B_D=\tanh(2\theta_D).
\]

A pista aponta para longe da silhueta terrestre, isto é, para o mar.

## Utilidade de movimento

Para a direção candidata unitária `m_k`:

\[
U_{i,k}=\kappa_{sea,i}\,\mathbf m_k\cdot\mathbf S
+\kappa_{art,i}\,\mathbf m_k\cdot\mathbf A
+\kappa_{dune,i}\,\mathbf m_k\cdot\mathbf D
+\kappa_{slope,i}\,\mathbf m_k\cdot\mathbf G
+\rho_i\,\mathbf m_k\cdot\mathbf h_{i,t-1}
-c_{stay}I_k.
\]

## Probabilidade de transição

\[
P_{i,k}=\frac{\exp(U_{i,k}/\tau_i)}
{\sum_{j\in\mathcal N_i}\exp(U_{i,j}/\tau_i)}.
\]

- `tau` alto: maior aleatoriedade;
- `tau` baixo: maior consistência na escolha;
- `rho`: persistência de rumo;
- os `kappa` controlam respostas às pistas.

## Heterogeneidade

Parâmetros positivos são amostrados por distribuição lognormal com coeficiente de variação configurável. Persistência é amostrada por normal truncada.

## Energia

\[
Q_i(t+\Delta t)=Q_i(t)-c_b\Delta t-c_m d_i
[1+c_s|\sin(s(y))|].
\]

Quando `Q <= 0`, o desfecho é `exhausted`.

## Predação

\[
p_{pred}=1-\exp[-\lambda(x,y,t)\Delta t].
\]

A taxa pode aumentar com tempo de exposição, posição terrestre e intensidade artificial. Sem dados locais, esses efeitos devem ser assumidos ou desativados.

## Sequência

1. calcular pistas no local atual;
2. calcular utilidades dos nove movimentos;
3. sortear movimento pela Softmax;
4. atualizar posição, rumo, tempo, trajetória e energia;
5. verificar água, bordas, exaustão e predação;
6. repetir até todos terem desfecho ou até o tempo máximo.

## Calibração

A função objetivo é uma soma ponderada de erros quadráticos padronizados entre métricas observadas e simuladas. O código usa evolução diferencial e sementes comuns durante a otimização.

## Validação

- ambiental: exclusão de um local luminoso por vez;
- comportamental: comparação com trajetórias não usadas no ajuste;
- estrutural: testes determinísticos e conservação de indivíduos;
- robustez: Monte Carlo e análise global de sensibilidade.
