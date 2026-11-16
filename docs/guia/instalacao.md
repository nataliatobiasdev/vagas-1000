# Instalação

Há dois caminhos. O primeiro é o que a maioria das pessoas quer.

## 1. Instalador (recomendado)

1. Abra [Releases](https://github.com/nataliatobiasdev/vagas-1000/releases) e baixe `vagas1000-Setup-X.Y.Z.exe`.
2. Execute. O assistente instala **por usuário, sem administrador**, e deixa você escolher a pasta.
3. Abra o **vagas1000** pelo atalho da Área de Trabalho ou do Menu Iniciar.

::: warning Sem assinatura de código
O instalador não é assinado. Na primeira execução o SmartScreen mostra “Editor desconhecido”: clique em **Mais informações → Executar assim mesmo**.
:::

| Item | Valor |
| --- | --- |
| Programa | `%LOCALAPPDATA%\Programs\vagas1000` |
| Seus dados | `%APPDATA%\vagas1000` (banco, painel, logs e configuração) |
| Desinstalar | Configurações do Windows → Aplicativos, ou `Desinstalar.exe` na pasta do programa |
| Ao desinstalar | A pasta `%APPDATA%\vagas1000` **nunca é apagada** |

Requisito: **Google Chrome**, e só para a Stone (única fonte que usa navegador). Sem Chrome as outras 53 empresas funcionam normalmente e a Stone aparece como erro no relatório.

### Onde fica o que

```
%APPDATA%\vagas1000\
  config\companies.json   empresas e fontes (edite para acrescentar uma empresa)
  config\profile.json     seu perfil: pesos, tecnologias, senioridade, elegibilidade
  data\vagas.db           banco SQLite
  out\dashboard.html      painel offline
  out\presenciais.md      vagas presenciais por estado
  out\vagas-latest.json   última captura completa (também .csv)
  logs\scraper.log        log detalhado
```

As configurações são copiadas do pacote na primeira execução. Se você editar, as suas edições valem; novas versões do app não as sobrescrevem.

## 2. A partir do código-fonte

Requisitos: **Python 3.9+** e Google Chrome.

```bash
git clone https://github.com/nataliatobiasdev/vagas-1000.git
cd vagas-1000
instalar.bat
```

O `instalar.bat` cria o `.venv`, instala as dependências, roda os testes offline e cria os atalhos **vagas1000 - abrir app** e **vagas1000 - abrir painel**. Não agenda nada: a atualização é pelo botão **Atualizar base**.

Esse modo também libera o botão **Buscar no LinkedIn** (veja [Como usar](/guia/uso#linkedin)).

## Gerar o instalador você mesma

O CI faz isso a cada push. Localmente, num Windows com Python 3.12 e [NSIS](https://nsis.sourceforge.io):

```bash
pip install -r requirements-dev.txt
python scripts/make_version_info.py
pyinstaller vagas1000.spec --noconfirm
makensis /DVERSION=1.0.0 installer\vagas1000.nsi
```

O resultado fica em `dist\vagas1000-Setup-1.0.0.exe`. Detalhes em [Instalador Windows](/qualidade/instalador).
