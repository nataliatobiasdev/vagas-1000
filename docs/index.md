---
layout: home
title: Início
hero:
  name: vagas1000
  text: Documentação técnica
  tagline: App desktop Windows que consulta fontes de vagas de TI, pontua pelo seu perfil e apresenta os resultados em um painel offline.
  image:
    src: /logo.png
    alt: Ícone do vagas1000, uma lupa em gradiente violeta e teal
  actions:
    - theme: brand
      text: Instalar
      link: /guia/instalacao
    - theme: alt
      text: Visão geral
      link: /guia/visao
    - theme: alt
      text: Ver no GitHub
      link: https://github.com/nataliatobiasdev/vagas-1000
features:
  - title: 76 fontes configuradas
    details: Gupy, Greenhouse, Lever, Ashby, Workday, GFT e Stone. A lista completa fica na configuração; a GFT tem também um feed parcial.
    link: /arquitetura/fontes
  - title: Pontuação do seu perfil
    details: Título, tecnologia, senioridade e elegibilidade viram uma nota de 0 a 100 e um veredito, editáveis em profile.json.
    link: /arquitetura/pontuacao
  - title: Painel offline
    details: Um HTML único com filtros, histórico de execuções e novas vagas desde a última coleta. Sem internet, sem servidor.
    link: /arquitetura/dados
  - title: Acompanhe no CAM
    details: Envie uma vaga ao CAM e acompanhe no painel quais vagas foram salvas ou já tiveram candidatura registrada.
    link: /guia/uso#acompanhar-no-cam
  - title: Instalador por usuário
    details: Instalador NSIS sem administrador, gerado no CI e publicado a cada tag. Seus dados ficam em %APPDATA%\vagas1000.
    link: /guia/instalacao
  - title: Design system Nevora
    details: Violeta e teal sobre neutros escuros, Space Grotesk, Inter e JetBrains Mono empacotadas, na janela e no painel.
    link: /guia/identidade-visual
  - title: Testado de verdade
    details: Testes offline, verificações de coleta e execução do .exe empacotado. O relatório apresenta os resultados e limites.
    link: /qualidade/relatorio
---
