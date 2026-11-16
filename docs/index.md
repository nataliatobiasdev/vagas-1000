---
layout: home
title: Início
hero:
  name: vagas1000
  text: Documentação técnica
  tagline: App desktop Windows que captura vagas de TI de 54 empresas, pontua pelo seu perfil e entrega um painel offline com o que dá para aplicar.
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
  - title: 54 empresas, 6 fontes
    details: Gupy, Greenhouse, Lever, Ashby, Workday e o portal da Stone. Quase tudo por API pública, sem abrir navegador.
    link: /arquitetura/fontes
  - title: Pontuação do seu perfil
    details: Título, tecnologia, senioridade e elegibilidade viram uma nota de 0 a 100 e um veredito, editáveis em profile.json.
    link: /arquitetura/pontuacao
  - title: Painel offline
    details: Um HTML único com filtros, histórico de execuções e novas vagas desde a última coleta. Sem internet, sem servidor.
    link: /arquitetura/dados
  - title: Instalador por usuário
    details: Instalador NSIS sem administrador, gerado no CI e publicado a cada tag. Seus dados ficam em %APPDATA%\vagas1000.
    link: /guia/instalacao
  - title: Design system Nevora
    details: Violeta e teal sobre neutros escuros, Space Grotesk, Inter e JetBrains Mono empacotadas, na janela e no painel.
    link: /guia/identidade-visual
  - title: Testado de verdade
    details: 51 testes offline, coleta real das 53 empresas sem navegador e execução do .exe empacotado. O relatório lista o que não funciona.
    link: /qualidade/relatorio
---
