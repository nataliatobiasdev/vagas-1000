# Identidade visual

::: tip Entregue
O design system **Nevora** (mesmo do [CAM](https://github.com/nataliatobiasdev/agregador-carreiras)) está na janela do app, no painel `dashboard.html`, neste site e no ícone.
:::

O Nevora veio do arquivo Figma Make “Nevora Design System Showcase”, na direção *Linear × Raycast × Vercel Geist*: superfícies sólidas acetinadas, bordas de 1 px, glass só em elementos flutuantes e a proporção aproximada de **85% neutros escuros, 10% violeta e 5% teal**.

## Onde os tokens vivem

| Lugar | Arquivo |
| --- | --- |
| Janela (Tk) | `scraper/theme.py` |
| Painel offline | variáveis CSS no topo de `scraper/templates/dashboard.html` |
| Este site | `docs/.vitepress/theme/custom.css` |

Os três usam os mesmos valores; mudou uma cor, mude nos três.

## Paleta

O tema escuro é a referência. O claro (painel e site) usa os mesmos tons escurecidos para manter contraste AA sobre branco.

| Token | Papel | Escuro | Claro |
| --- | --- | --- | --- |
| `bg` | Fundo da janela | <span class="sw" style="background:#0B0E19"></span> `#0B0E19` | <span class="sw" style="background:#F6F7FC"></span> `#F6F7FC` |
| `panel` | Cards e painéis | <span class="sw" style="background:#151A2B"></span> `#151A2B` | <span class="sw" style="background:#FFFFFF"></span> `#FFFFFF` |
| `subtle` | Hover, fundo secundário | <span class="sw" style="background:#1C2238"></span> `#1C2238` | <span class="sw" style="background:#EEF0F8"></span> `#EEF0F8` |
| `field` | Inputs e área de log | <span class="sw" style="background:#0E121E"></span> `#0E121E` | <span class="sw" style="background:#FAFBFF"></span> `#FAFBFF` |
| `accent` | Violeta, ação principal | <span class="sw" style="background:#9D8CFF"></span> `#9D8CFF` | <span class="sw" style="background:#6C5CE7"></span> `#6C5CE7` |
| `teal` | Detalhes e destaque secundário | <span class="sw" style="background:#42D6CD"></span> `#42D6CD` | <span class="sw" style="background:#0A7A74"></span> `#0A7A74` |
| `success` | Sucesso | <span class="sw" style="background:#45D6A0"></span> `#45D6A0` | <span class="sw" style="background:#128058"></span> `#128058` |
| `warning` | Atenção | <span class="sw" style="background:#F5C66B"></span> `#F5C66B` | <span class="sw" style="background:#9C6008"></span> `#9C6008` |
| `danger` | Erro | <span class="sw" style="background:#FF718D"></span> `#FF718D` | <span class="sw" style="background:#CD2D50"></span> `#CD2D50` |
| `fg` / `muted` | Texto principal / secundário | `#F4F6FF` / `#A6B1CB` | `#0B0E19` / `#525C78` |

## Tipografia

| Uso | Fonte |
| --- | --- |
| Corpo | Inter |
| Títulos e números grandes | Space Grotesk |
| Dados, rótulos, log, cabeçalhos de tabela | JetBrains Mono |

As três estão **empacotadas** em `assets/fonts` (licença SIL OFL 1.1): a janela as registra só para o processo, via GDI; o painel embute um subconjunto latino em WOFF2 (~150 KB) para continuar offline. Sem elas, o Tk cai para Segoe UI e Consolas.

## Raios e componentes

| Raio | Uso |
| --- | --- |
| 8 px | Botões, inputs |
| 12 px | Cards, ícone |
| 16 px | Painéis |
| 24 px | Destaques |

| Componente | Como ficou |
| --- | --- |
| Botão primário | Violeta sólido, texto escuro, borda de 1 px |
| Botão secundário | Superfície `panel` com borda e hover `subtle` |
| Pílula de estado | Tom semântico (sucesso, erro, neutro) sobre `panel` |
| Barra de progresso | O **único** gradiente da janela: violeta → teal no preenchimento |
| Cartões de números | Rótulo em mono maiúsculo, número em Space Grotesk; “elegíveis” em violeta |
| Painel | Cards acetinados, cabeçalhos de tabela em mono, vereditos com tom próprio |

## Ícone

<img src="/icon-256.png" alt="Ícone do vagas1000: lupa com aro em gradiente violeta e teal" width="160" style="border:0">

Lupa com aro violeta → teal e cabo teal sobre o quadrado arredondado `panel`. É desenhado por `scripts/make_icon.py` (Pillow, ferramenta de desenvolvimento) e sai como `assets/icon.ico` (16 a 256 px), `assets/icon.png` e os favicons deste site. O script falha se algum canto sair opaco.

## Limites do Tk

O Tk não tem blur, sombras difusas nem transparência. Por isso a janela expressa o Nevora por **cor, borda de 1 px, tipografia e proporção de cor**, e deixa glass e atmosfera (gradientes radiais) para o painel e este site, onde o navegador renderiza.
