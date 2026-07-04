import os 
import sys
import zipfile
import xml.etree.ElementTree as ET

import tkinter as tk
from tkinter import filedialog, messagebox

# Resolvi usar o customtkinter para dar um visual mais moderno (Dark Mode) pra aplicação
import customtkinter as ctk
# Biblioteca auxiliar para permitir o "arrastar e soltar" de arquivos na tela
from tkinterdnd2 import TkinterDnD, DND_FILES

# Configuração inicial do tema da janela
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

def pasta_base():
    # Função para identificar o diretório atual do projeto.
    # Adicionei o sys.frozen para garantir que o caminho não quebre quando eu compilar o projeto para .exe
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = pasta_base()

def formatar_moeda_br(valor):
    # Função auxiliar para formatar os valores float no padrão da moeda brasileira (R$)
    # Tive que fazer esse replace em cadeia para inverter os pontos e vírgulas corretamente
    texto = f"{valor:,.2f}"
    texto = texto.replace(",", "X")
    texto = texto.replace(".", ",")
    texto = texto.replace("X", ".")

    return f"R$ {texto}"

def selecionar_pasta():
    # Abre o explorador de arquivos do Windows para o usuário selecionar a pasta com os XMLs
    caminho_inicial = entrada_pasta.get().strip()

    if os.path.isdir(caminho_inicial):
        dir_inicial = caminho_inicial
    else:
        dir_inicial = BASE_DIR

    caminho = filedialog.askdirectory(
        initialdir=dir_inicial
    )

    if caminho:
        entrada_pasta.delete(0, "end")
        entrada_pasta.insert(0, caminho)

def soltar_arquivo(evento):
    # Lida com o evento de Drag and Drop (arrastar e soltar um ZIP ou pasta na tela)
    caminho = evento.data

    if caminho.startswith('{') and caminho.endswith('}'):
        caminho = caminho[1:-1]
    
    entrada_pasta.delete(0, "end")
    entrada_pasta.insert(0, caminho)

def limpar_tela():
    # Zera todos os contadores, os labels visuais da interface e limpa o log
    entrada_pasta.delete(0, "end")

    label_validas_valor.configure(text="0")
    label_outros_valor.configure(text="0")
    label_erros_valor.configure(text="0")

    label_nfe_valor.configure(text="R$ 0,00")
    label_nfce_valor.configure(text="R$ 0,00")
    label_geral_valor.configure(text="R$ 0,00")

    label_status.configure(
        text="Aguardando arquivos...",
        text_color="#94a3b8"
    )

    limpar_caixa_resultados()

def limpar_caixa_resultados():
    # O Textbox fica desabilitado pro usuário não digitar nada, então preciso habilitar antes de limpar
    caixa_resultados.configure(state="normal")
    caixa_resultados.delete("1.0", "end")
    caixa_resultados.configure(state="disabled")

def extrair_dados_xml(raiz):
    # Aqui é o coração da extração. Navega pela árvore do XML (ElementTree) procurando as tags da Sefaz
    numero = None
    modelo = None
    cstat = None
    motivo = None
    valor = 0.0

    for elem in raiz.iter():
        # Limpa o namespace da tag (aquele link do xmlns) para facilitar a busca
        tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag

        # Capturando os dados básicos da Nota Fiscal
        if tag == "nNF" and numero is None:
            numero = elem.text
        elif tag == "mod" and modelo is None:
            modelo = elem.text
        elif tag == "cStat" and cstat is None:
            cstat = elem.text
        elif tag == "xMotivo" and motivo is None:
            motivo = elem.text
        elif tag == "ICMSTot":
            # Quando acha o totalizador, entra nos filhos para buscar o valor total da nota (vNF)
            for filho in elem:
                ftag = (
                    filho.tag.split('}')[-1]
                    if '}' in filho.tag
                    else filho.tag 
                )

                if ftag == "vNF":
                    valor = float(filho.text)
                    break

    # Se a nota não tem cStat, ela provavelmente não é um XML de Sefaz válido
    if cstat is None:
        raise ValueError(
            "Tag cStat não encontrada no documento."
        )
    
    return {
        "numero": numero or "S/N",
        "modelo": modelo or "N/D",
        "cstat": cstat,
        "motivo": motivo or "Status desconhecido",
        "valor": valor
    }

def processar_arquivo(conteudo_ou_caminho, eh_zip=False):
    # Lida tanto com o XML direto do diretório quanto com a leitura em memória (se vier do ZIP)
    try:
        if eh_zip:
            raiz = ET.fromstring(conteudo_ou_caminho)
        else:
            arvore = ET.parse(conteudo_ou_caminho)
            raiz = arvore.getroot()

        return extrair_dados_xml(raiz), None
    
    except Exception as e:
        return None, str(e)
    
def somar_xmls():
    caminho_input = entrada_pasta.get().strip()

    # Validação inicial de entrada do usuário
    if not caminho_input:
        messagebox.showwarning("Aviso", "Selecione ou arraste uma pasta/arquivo ZIP primeiro.")
        return

    if not os.path.exists(caminho_input):
        messagebox.showerror("Erro", "O caminho informado não existe.")
        return

    # Trava os botões durante o processamento para evitar quebra de fluxo
    botao_calcular.configure(state="disabled")
    botao_limpar.configure(state="disabled")
    janela.update()

    # Inicializando as variáveis acumuladoras
    soma_nfe = soma_nfce = 0.0
    qtd_validas = qtd_outros = qtd_erros = 0
    docs_outros_status = {}
    docs_com_erro = []
    arquivos_alvo = []

    limpar_caixa_resultados()
    escrever_resultado("Iniciando varredura...\n")
    escrever_resultado("-" * 75 + "\n")
    escrever_resultado(f"{'NOTA':<10} | {'MOD':<4} | {'VALOR':>15} | {'ARQUIVO'}\n")
    escrever_resultado("-" * 75 + "\n")

    label_status.configure(text="Mapeando arquivos...", text_color="#94a3b8")
    janela.update_idletasks()

    # Lista de arquivos inúteis gerados por SO que devem ser ignorados no loop
    lixos_sistema = ["__macosx", ".ds_store", "desktop.ini"]

    # Verifica se o input é um arquivo compactado ZIP ou um diretório normal
    if os.path.isfile(caminho_input) and caminho_input.lower().endswith(".zip"):
        try:
            with zipfile.ZipFile(caminho_input, 'r') as zf:
                for nome in zf.namelist():
                    nome_min = nome.lower()
                    if not nome.endswith('/') and "nfedfe" not in nome_min and not any(lixo in nome_min for lixo in lixos_sistema):
                        if nome_min.endswith('.xml'):
                            nome_exibicao = os.path.basename(nome)
                            # Adiciona na lista passando o conteúdo binário e a flag eh_zip=True
                            arquivos_alvo.append((nome_exibicao, zf.read(nome), True))
        except zipfile.BadZipFile:
            messagebox.showerror("Erro", "O arquivo ZIP está corrompido ou é inválido.")
            restaurar_botoes()
            return
            
    elif os.path.isdir(caminho_input):
        # Varre recursivamente todas as subpastas usando os.walk
        for raiz_dir, _, arquivos in os.walk(caminho_input):
            for nome in arquivos:
                nome_min = nome.lower()
                if nome_min.endswith(".xml") and "nfedfe" not in nome_min and not any(lixo in nome_min for lixo in lixos_sistema):
                    caminho_completo = os.path.join(raiz_dir, nome)
                    arquivos_alvo.append((nome, caminho_completo, False))

    total_arquivos = len(arquivos_alvo)
    
    if total_arquivos == 0:
        escrever_resultado("Nenhum arquivo XML válido encontrado na base selecionada.")
        label_status.configure(text="Pronto. Nenhum XML encontrado.", text_color="#94a3b8")
        restaurar_botoes()
        return

    # Inicia o processamento da fila de arquivos mapeados
    for i, (nome_arquivo, conteudo_caminho, eh_zip) in enumerate(arquivos_alvo, 1):
        # Atualização do feedback visual em lotes para não sobrecarregar a UI thread do Tkinter
        if i % 20 == 0 or i == total_arquivos:
            label_status.configure(text=f"Processando: {i} de {total_arquivos} arquivos...", text_color="#3b82f6")
            janela.update_idletasks()

        dados, erro = processar_arquivo(conteudo_caminho, eh_zip)

        if erro:
            qtd_erros += 1
            docs_com_erro.append(f"{nome_arquivo} - ERRO: {erro}")
            continue

        # Regra de negócio: cStat 100 e 150 representam notas autorizadas pela Sefaz.
        # Notas denegadas/canceladas (outros status) não devem entrar na soma financeira.
        if dados['cstat'] in ["100", "150"]:
            qtd_validas += 1
            if dados['modelo'] == "55": 
                soma_nfe += dados['valor']
            elif dados['modelo'] == "65": 
                soma_nfce += dados['valor']
            else: 
                soma_nfe += dados['valor'] 
                
            escrever_resultado(f"NF {dados['numero']:<7} | {dados['modelo']:<4} | {formatar_moeda_br(dados['valor']):>15} | {nome_arquivo}\n")
        else:
            qtd_outros += 1
            motivo = dados['motivo']
            # Agrupa os status diferentes usando um dicionário para o relatório final
            if motivo not in docs_outros_status:
                docs_outros_status[motivo] = []
            docs_outros_status[motivo].append(f"NF {dados['numero']:<7} | Mod {dados['modelo']:<2} | {nome_arquivo}")

    # Escreve o relatório final no console e popula as labels da GUI
    escrever_resumos_finais(docs_outros_status, docs_com_erro)

    soma_geral = soma_nfe + soma_nfce
    label_validas_valor.configure(text=str(qtd_validas))
    label_outros_valor.configure(text=str(qtd_outros))
    label_erros_valor.configure(text=str(qtd_erros))
    label_nfe_valor.configure(text=formatar_moeda_br(soma_nfe))
    label_nfce_valor.configure(text=formatar_moeda_br(soma_nfce))
    label_geral_valor.configure(text=formatar_moeda_br(soma_geral))

    label_status.configure(text=f"Concluído. {total_arquivos} arquivos processados.", text_color="#10b981")
    restaurar_botoes()


# --- Funções de manipulação do log na tela ---

def escrever_resumos_finais(docs_outros_status, docs_com_erro):
    # Printa os agrupamentos de notas não validadas no console inferior
    if docs_outros_status:
        escrever_resultado("\n" + "=" * 75 + "\n")
        escrever_resultado("DOCUMENTOS COM OUTROS STATUS (Ignorados na soma)\n")
        escrever_resultado("=" * 75 + "\n")
        for motivo, lista_arquivos in docs_outros_status.items():
            escrever_resultado(f"\n[ {motivo.upper()} ] - {len(lista_arquivos)} arquivo(s)\n")
            escrever_resultado("-" * 75 + "\n")
            for arquivo in lista_arquivos:
                escrever_resultado(f"  {arquivo}\n")

    if docs_com_erro:
        escrever_resultado("\n" + "=" * 75 + "\n")
        escrever_resultado("ARQUIVOS COM ERRO (Corrompidos ou fora do padrão XML Sefaz)\n")
        escrever_resultado("=" * 75 + "\n")
        for arquivo in docs_com_erro:
            escrever_resultado(f"  {arquivo}\n")
            
    escrever_resultado("\nProcessamento finalizado.\n")

def restaurar_botoes():
    botao_calcular.configure(state="normal")
    botao_limpar.configure(state="normal")

def escrever_resultado(texto):
    # Destrava o componente, insere a string, desce o scroll pro final e trava novamente
    caixa_resultados.configure(state="normal")
    caixa_resultados.insert("end", texto)
    caixa_resultados.see("end")
    caixa_resultados.configure(state="disabled")


# =========================================================
# CONSTRUÇÃO DA INTERFACE GRÁFICA (GUI)
# =========================================================

# Instanciando a janela principal usando a classe do TkinterDnD para ter suporte ao Drag/Drop
janela = TkinterDnD.Tk()
janela.title("Calculadora e Extrator de XML Fiscal")
janela.geometry("900x700")
janela.configure(bg="#0b0f19")

# Binding do evento de soltar arquivo
janela.drop_target_register(DND_FILES)
janela.dnd_bind('<<Drop>>', soltar_arquivo)

# Definindo a tipografia do projeto
f_titulo = ctk.CTkFont(family="Segoe UI", size=26, weight="bold")
f_sub = ctk.CTkFont(family="Segoe UI", size=13)
f_card_title = ctk.CTkFont(family="Segoe UI", size=12, weight="bold")
f_card_val = ctk.CTkFont(family="Segoe UI", size=24, weight="bold")
f_btn = ctk.CTkFont(family="Segoe UI", size=14, weight="bold")
f_log = ctk.CTkFont(family="Consolas", size=13) 

# Container Base
main_frame = ctk.CTkFrame(janela, fg_color="#0b0f19", corner_radius=0)
main_frame.pack(fill="both", expand=True, padx=30, pady=30)

# Header
topo = ctk.CTkFrame(main_frame, fg_color="transparent")
topo.pack(fill="x", pady=(0, 20))
ctk.CTkLabel(topo, text="Calculadora de XML", font=f_titulo, text_color="#f8fafc").pack(anchor="w")
ctk.CTkLabel(topo, text="Arraste diretórios ou arquivos .ZIP para varredura e consolidação de notas fiscais.", font=f_sub, text_color="#94a3b8").pack(anchor="w")

# Seção de input (Diretório)
card_pasta = ctk.CTkFrame(main_frame, fg_color="#1e293b", corner_radius=12)
card_pasta.pack(fill="x", pady=(0, 20))

ctk.CTkLabel(card_pasta, text="Caminho Base", font=f_card_title, text_color="#e2e8f0").pack(anchor="w", padx=20, pady=(16, 8))

frame_input = ctk.CTkFrame(card_pasta, fg_color="transparent")
frame_input.pack(fill="x", padx=20, pady=(0, 20))

entrada_pasta = ctk.CTkEntry(frame_input, font=f_sub, fg_color="#0f172a", border_color="#334155", border_width=1, corner_radius=8, height=40, placeholder_text="Solte a pasta/arquivo aqui ou busque manualmente...")
entrada_pasta.pack(side="left", fill="x", expand=True, padx=(0, 12))

botao_pasta = ctk.CTkButton(frame_input, text="Buscar", font=f_btn, fg_color="#334155", hover_color="#475569", corner_radius=8, height=40, width=120, command=selecionar_pasta)
botao_pasta.pack(side="left")

# Criei essa função para não precisar instanciar os mesmos labels 6 vezes seguidas na mão
def criar_card(pai, titulo, cor_destaque):
    card = ctk.CTkFrame(pai, fg_color="#1e293b", corner_radius=12)
    ctk.CTkLabel(card, text=titulo.upper(), font=f_card_title, text_color="#94a3b8").pack(anchor="w", padx=20, pady=(16, 2))
    lbl_valor = ctk.CTkLabel(card, text="0", font=f_card_val, text_color=cor_destaque)
    lbl_valor.pack(anchor="w", padx=20, pady=(0, 16))
    return card, lbl_valor

# Linha de Cards 1 (Estatísticas de Leitura)
linha1 = ctk.CTkFrame(main_frame, fg_color="transparent")
linha1.pack(fill="x", pady=(0, 12))

card1, label_validas_valor = criar_card(linha1, "Validadas (Sefaz)", "#3b82f6")
card1.pack(side="left", fill="both", expand=True, padx=(0, 6))

card2, label_outros_valor = criar_card(linha1, "Outros Status", "#f59e0b")
card2.pack(side="left", fill="both", expand=True, padx=6)

card3, label_erros_valor = criar_card(linha1, "Falha de Leitura", "#ef4444")
card3.pack(side="left", fill="both", expand=True, padx=(6, 0))

# Linha de Cards 2 (Resultados Financeiros)
linha2 = ctk.CTkFrame(main_frame, fg_color="transparent")
linha2.pack(fill="x", pady=(0, 24))

card4, label_nfe_valor = criar_card(linha2, "Subtotal NF-e (55)", "#a855f7")
label_nfe_valor.configure(text="R$ 0,00")
card4.pack(side="left", fill="both", expand=True, padx=(0, 6))

card5, label_nfce_valor = criar_card(linha2, "Subtotal NFC-e (65)", "#a855f7")
label_nfce_valor.configure(text="R$ 0,00")
card5.pack(side="left", fill="both", expand=True, padx=6)

card6, label_geral_valor = criar_card(linha2, "Faturamento Total", "#10b981")
label_geral_valor.configure(text="R$ 0,00")
card6.pack(side="left", fill="both", expand=True, padx=(6, 0))

# Seção de Ações
frame_acoes = ctk.CTkFrame(main_frame, fg_color="transparent")
frame_acoes.pack(fill="x", pady=(0, 20))

botao_calcular = ctk.CTkButton(frame_acoes, text="Processar Dados", font=f_btn, fg_color="#2563eb", hover_color="#1d4ed8", corner_radius=8, height=45, width=160, command=somar_xmls)
botao_calcular.pack(side="left", padx=(0, 12))

botao_limpar = ctk.CTkButton(frame_acoes, text="Limpar", font=f_btn, fg_color="#334155", hover_color="#475569", corner_radius=8, height=45, width=140, command=limpar_tela)
botao_limpar.pack(side="left")

# Console de Saída
header_log = ctk.CTkFrame(main_frame, fg_color="transparent")
header_log.pack(fill="x", pady=(0, 8))

ctk.CTkLabel(header_log, text="Log de Execução", font=f_card_title, text_color="#e2e8f0").pack(side="left")
label_status = ctk.CTkLabel(header_log, text="Aguardando diretório...", font=f_sub, text_color="#94a3b8")
label_status.pack(side="right")

caixa_resultados = ctk.CTkTextbox(main_frame, font=f_log, fg_color="#0f172a", text_color="#cbd5e1", corner_radius=12, border_width=1, border_color="#1e293b")
caixa_resultados.pack(fill="both", expand=True)
caixa_resultados.configure(state="disabled")

# Mainloop do Tkinter
try:
    janela.mainloop()
except Exception as erro:
    messagebox.showerror("Erro Crítico", f"Falha na aplicação:\n\n{erro}")