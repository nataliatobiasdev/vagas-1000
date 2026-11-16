# Limitações e roadmap

## Limitações da V1.0

| Limitação | Detalhe |
| --- | --- |
| Só Windows | Janela Tk, instalador NSIS e atalhos são para Windows 10 e 11 |
| Chrome para a Stone | Única fonte por navegador; as demais não precisam |
| Workday com 429 | Descrições da Salesforce às vezes falham ([relatório](/qualidade/relatorio)) |
| Sem assinatura | O SmartScreen avisa na primeira execução |
| LinkedIn fora do instalador | Só na instalação pelo código-fonte, em modo seguro |
| Perfil de exemplo pessoal | Edite `profile.json` antes de confiar na nota |
| Sem atualização automática | Baixe o novo instalador em [Releases](https://github.com/nataliatobiasdev/vagas-1000/releases); seus dados são mantidos |

## Próximos passos

<span class="tag plan">Planejado</span> Assistente de primeira execução para montar o `profile.json` pelas suas tecnologias.

<span class="tag plan">Planejado</span> Recuo exponencial no Workday e segunda passada só nas descrições que falharam.

<span class="tag plan">Planejado</span> Aviso na janela quando uma nova versão estiver publicada.

<span class="tag open">Aberto</span> Mais fontes sem feed público (Mercado Livre, OLX, Magalu) exigem scraper próprio, como o da Stone.

<span class="tag open">Aberto</span> Testes de widget da janela com display virtual no CI.

<span class="tag open">Aberto</span> Assinatura de código do instalador.
