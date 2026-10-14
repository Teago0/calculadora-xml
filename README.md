# Calculadora de XML Fiscal 🧾

Esse projeto nasceu de uma necessidade real no meu dia a dia de suporte e TI. Trabalhar com sistemas de PDV e lidar frequentemente com arquivos XML de notas fiscais (NF-e e NFC-e) exige muita conferência manual e soma de valores. 

Para resolver isso, desenvolvi esta aplicação para automatizar minha rotina de trabalho e, ao mesmo tempo, colocar em prática meus estudos na área de Análise de Sistemas.

## 🎯 Objetivo
O foco principal da ferramenta é varrer diretórios ou arquivos compactados (.zip), ler a estrutura do XML usando as tags oficiais da Sefaz e consolidar os valores financeiros apenas das notas fiscais válidas.

## ⚙️ O que a ferramenta faz?
- **Leitura em Lote:** Varre pastas inteiras ou processa arquivos `.zip` diretamente em memória, sem precisar descompactar.
- **Filtro Inteligente de Status:** Lê a tag `cStat` do XML e separa as notas validadas (Autorizadas) das notas com outros status (Canceladas, Denegadas, etc.), garantindo que a soma bata com a realidade.
- **Separação por Modelo:** Identifica automaticamente se a nota é uma NF-e (Modelo 55) ou NFC-e (Modelo 65) usando a tag `mod`.
- **Interface Amigável:** Interface gráfica moderna (Dark Mode) com suporte a "Arrastar e Soltar" (Drag and Drop) para facilitar o uso na correria do dia a dia.
- **Análise Detalhada (Inspecionar XML):** Uma janela dedicada para inspecionar notas individuais. Extrai automaticamente os dados do emitente, chave de acesso, lista de produtos (com `cClassTrib`) e um quadro completo de tributação (ICMS, ST, IPI, PIS, COFINS, IBS e CBS). Permite carregar o arquivo arrastando, buscando no diretório ou colando o texto do XML diretamente.

## 🛠️ Tecnologias e Bibliotecas Utilizadas
- **Python 3**
- **xml.etree.ElementTree:** Para a leitura ágil e navegação nas árvores dos arquivos XML.
- **CustomTkinter:** Para a construção da interface gráfica com um visual mais limpo e moderno.
- **TkinterDnD2:** Para adicionar a funcionalidade de arrastar e soltar diretórios direto na tela do app.
- **ZipFile & OS:** Para manipulação de rotas do sistema e processamento de arquivos.

## 🚀 Como executar o projeto localmente

1. Clone este repositório:
```bash
git clone [https://github.com/Teago0/calculadora-xml.git](https://github.com/Teago0/calculadora-xml.git)
