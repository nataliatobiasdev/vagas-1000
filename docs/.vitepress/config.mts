import { defineConfig } from 'vitepress'

export default defineConfig({
  lang: 'pt-BR', title: 'vagas1000 | Arquitetura', base: '/vagas-1000/', cleanUrls: true,
  description: 'Arquitetura e operações do vagas1000',
  themeConfig: {
    nav: [{ text: 'Arquitetura', link: '/architecture/' }, { text: 'ADRs', link: '/adr/' }, { text: 'Operação', link: '/operacao' }, { text: 'GitHub', link: 'https://github.com/nataliatobiasdev/vagas-1000' }],
    sidebar: [
      { text: 'Sistema', items: [{ text: 'Visão geral', link: '/' }, { text: 'Visões C4 e sequência', link: '/architecture/' }, { text: 'Contratos e dados', link: '/contratos' }, { text: 'Build e operação', link: '/operacao' }] },
      { text: 'Decisões arquiteturais', items: [{ text: 'Índice de ADRs', link: '/adr/' }, { text: 'ADR 001 — Processos separados', link: '/adr/001-processos' }, { text: 'ADR 002 — Persistência e falhas', link: '/adr/002-dados' }, { text: 'ADR 003 — Integração local', link: '/adr/003-integracao' }] }
    ],
    search: { provider: 'local' }, socialLinks: [{ icon: 'github', link: 'https://github.com/nataliatobiasdev/vagas-1000' }]
  }
})
