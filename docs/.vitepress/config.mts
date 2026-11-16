import { defineConfig } from 'vitepress'
import { withMermaid } from 'vitepress-plugin-mermaid'

const repo = 'https://github.com/nataliatobiasdev/vagas-1000'

export default withMermaid(
  defineConfig({
    lang: 'pt-BR',
    title: 'vagas1000 Docs',
    description: 'Documentação técnica do vagas1000: captura, pontuação e painel de vagas de TI',
    base: '/vagas-1000/',
    cleanUrls: true,
    lastUpdated: true,
    head: [
      ['link', { rel: 'icon', type: 'image/png', sizes: '32x32', href: '/vagas-1000/favicon-32.png' }],
      ['link', { rel: 'icon', type: 'image/png', sizes: '64x64', href: '/vagas-1000/favicon-64.png' }],
      ['link', { rel: 'apple-touch-icon', href: '/vagas-1000/icon-256.png' }],
      ['meta', { name: 'theme-color', content: '#0B0E19' }]
    ],
    markdown: { lineNumbers: false },
    themeConfig: {
      logo: '/favicon-64.png',
      siteTitle: 'vagas1000 Docs',
      nav: [
        { text: 'Visão geral', link: '/guia/visao', activeMatch: '/guia/' },
        { text: 'Instalação', link: '/guia/instalacao' },
        { text: 'Arquitetura', link: '/arquitetura/', activeMatch: '/arquitetura/' },
        { text: 'Qualidade', link: '/qualidade/relatorio', activeMatch: '/qualidade/' },
        { text: 'Versões', link: '/versionamento' },
        { text: 'Roadmap', link: '/roadmap' },
        { text: 'v1.0', items: [{ text: 'Releases', link: `${repo}/releases` }, { text: 'Actions', link: `${repo}/actions` }] }
      ],
      sidebar: [
        {
          text: 'Visão geral',
          items: [
            { text: 'Produto e escopo', link: '/guia/visao' },
            { text: 'Instalação', link: '/guia/instalacao' },
            { text: 'Como usar', link: '/guia/uso' },
            { text: 'Identidade visual', link: '/guia/identidade-visual' },
            { text: 'Rodar e contribuir', link: '/guia/desenvolvimento' }
          ]
        },
        {
          text: 'Arquitetura',
          items: [
            { text: 'Visão da arquitetura', link: '/arquitetura/' },
            { text: 'Fontes de vagas', link: '/arquitetura/fontes' },
            { text: 'Pontuação e elegibilidade', link: '/arquitetura/pontuacao' },
            { text: 'Banco e arquivos', link: '/arquitetura/dados' }
          ]
        },
        {
          text: 'Qualidade e entrega',
          items: [
            { text: 'Relatório de testes', link: '/qualidade/relatorio' },
            { text: 'Testes', link: '/qualidade/testes' },
            { text: 'CI e GitHub Pages', link: '/qualidade/ci' },
            { text: 'Instalador Windows', link: '/qualidade/instalador' }
          ]
        },
        {
          text: 'Projeto',
          items: [
            { text: 'Versionamento', link: '/versionamento' },
            { text: 'Limitações e roadmap', link: '/roadmap' }
          ]
        }
      ],
      outline: { level: [2, 3], label: 'Nesta página' },
      search: {
        provider: 'local',
        options: {
          translations: {
            button: { buttonText: 'Buscar', buttonAriaLabel: 'Buscar' },
            modal: {
              noResultsText: 'Nenhum resultado para',
              resetButtonTitle: 'Limpar busca',
              displayDetails: 'Mostrar detalhes',
              backButtonTitle: 'Fechar',
              footer: { selectText: 'abrir', navigateText: 'navegar', closeText: 'fechar' }
            }
          }
        }
      },
      socialLinks: [{ icon: 'github', link: repo }],
      editLink: { pattern: `${repo}/edit/main/docs/:path`, text: 'Editar esta página no GitHub' },
      lastUpdated: { text: 'Atualizado em', formatOptions: { dateStyle: 'short' } },
      docFooter: { prev: 'Anterior', next: 'Próxima' },
      darkModeSwitchLabel: 'Tema',
      lightModeSwitchTitle: 'Mudar para o tema claro',
      darkModeSwitchTitle: 'Mudar para o tema escuro',
      sidebarMenuLabel: 'Menu',
      returnToTopLabel: 'Voltar ao topo',
      langMenuLabel: 'Idioma',
      notFound: { title: 'Página não encontrada', quote: 'Este endereço não existe na documentação.', linkText: 'Voltar ao início' },
      footer: {
        message: 'Documentação técnica do vagas1000 · V1.0 com o design system Nevora',
        copyright: 'Copyright © 2026 Natalia Tobias'
      }
    },
    mermaid: { securityLevel: 'strict' }
  })
)
