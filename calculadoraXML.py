import os 
import sys
import zipfile
import xml.etree.ElementTree as ET

import tkinter as tk
from tkinter import filedialog, messagebox

# CustomTkinter para o visual moderno em Dark Mode
import customtkinter as ctk
# Biblioteca auxiliar para permitir o "arrastar e soltar" de arquivos na tela
from tkinterdnd2 import TkinterDnD, DND_FILES

# Configuração inicial do tema da janela
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

def pasta_base():
    # Função para identificar o diretório atual do projeto.
    # sys.frozen garante o caminho correto ao compilar para .exe
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = pasta_base()

def formatar_moeda_br(valor):
    # Formatação dos valores float no padrão da moeda brasileira (R$)
    texto = f"{valor:,.2f}"
    texto = texto.replace(",", "X")
    texto = texto.replace(".", ",")
    texto = texto.replace("X", ".")
    return f"R$ {texto}"

def selecionar_pasta():
    caminho_inicial = entrada_pasta.get().strip()

    if os.path.isdir(caminho_inicial):
        dir_inicial = caminho_inicial
    else:
        dir_inicial = BASE_DIR

    caminho = filedialog.askdirectory(initialdir=dir_inicial)

    if caminho:
        entrada_pasta.delete(0, "end")
        entrada_pasta.insert(0, caminho)

def soltar_arquivo(evento):
    caminho = evento.data
    if caminho.startswith('{') and caminho.endswith('}'):
        caminho = caminho[1:-1]
    
    entrada_pasta.delete(0, "end")
    entrada_pasta.insert(0, caminho)

def limpar_tela():
    entrada_pasta.delete(0, "end")
    label_validas_valor.configure(text="0")
    label_outros_valor.configure(text="0")
    label_erros_valor.configure(text="0")
    label_nfe_valor.configure(text="R$ 0,00")
    label_nfce_valor.configure(text="R$ 0,00")
    label_geral_valor.configure(text="R$ 0,00")
    label_status.configure(text="Aguardando arquivos...", text_color="#94a3b8")
    limpar_caixa_resultados()

def limpar_caixa_resultados():
    caixa_resultados.configure(state="normal")
    caixa_resultados.delete("1.0", "end")
    caixa_resultados.configure(state="disabled")

def extrair_dados_xml(raiz):
    numero = None
    modelo = None
    cstat = None
    motivo = None
    valor = 0.0

    for elem in raiz.iter():
        tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag

        if tag == "nNF" and numero is None:
            numero = elem.text
        elif tag == "mod" and modelo is None:
            modelo = elem.text
        elif tag == "cStat" and cstat is None:
            cstat = elem.text
        elif tag == "xMotivo" and motivo is None:
            motivo = elem.text
        elif tag == "ICMSTot":
            for filho in elem:
                ftag = (filho.tag.split('}')[-1] if '}' in filho.tag else filho.tag)
                if ftag == "vNF":
                    valor = float(filho.text)
                    break

    if cstat is None:
        raise ValueError("Tag cStat não encontrada no documento.")
    
    return {
        "numero": numero or "S/N",
        "modelo": modelo or "N/D",
        "cstat": cstat,
        "motivo": motivo or "Status desconhecido",
        "valor": valor
    }

def processar_arquivo(conteudo_ou_caminho, eh_zip=False):
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

    if not caminho_input:
        messagebox.showwarning("Aviso", "Selecione ou arraste uma pasta/arquivo ZIP primeiro.")
        return

    if not os.path.exists(caminho_input):
        messagebox.showerror("Erro", "O caminho informado não existe.")
        return

    botao_calcular.configure(state="disabled")
    botao_limpar.configure(state="disabled")
    janela.update()

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

    lixos_sistema = ["__macosx", ".ds_store", "desktop.ini"]

    if os.path.isfile(caminho_input) and caminho_input.lower().endswith(".zip"):
        try:
            with zipfile.ZipFile(caminho_input, 'r') as zf:
                for nome in zf.namelist():
                    nome_min = nome.lower()
                    if not nome.endswith('/') and "nfedfe" not in nome_min and not any(lixo in nome_min for lixo in lixos_sistema):
                        if nome_min.endswith('.xml'):
                            nome_exibicao = os.path.basename(nome)
                            arquivos_alvo.append((nome_exibicao, zf.read(nome), True))
        except zipfile.BadZipFile:
            messagebox.showerror("Erro", "O arquivo ZIP está corrompido ou é inválido.")
            restaurar_botoes()
            return
            
    elif os.path.isdir(caminho_input):
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

    for i, (nome_arquivo, conteudo_caminho, eh_zip) in enumerate(arquivos_alvo, 1):
        if i % 20 == 0 or i == total_arquivos:
            label_status.configure(text=f"Processando: {i} de {total_arquivos} arquivos...", text_color="#3b82f6")
            janela.update_idletasks()

        dados, erro = processar_arquivo(conteudo_caminho, eh_zip)

        if erro:
            qtd_erros += 1
            docs_com_erro.append(f"{nome_arquivo} - ERRO: {erro}")
            continue

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
            if motivo not in docs_outros_status:
                docs_outros_status[motivo] = []
            docs_outros_status[motivo].append(f"NF {dados['numero']:<7} | Mod {dados['modelo']:<2} | {nome_arquivo}")

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

def escrever_resumos_finais(docs_outros_status, docs_com_erro):
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
    caixa_resultados.configure(state="normal")
    caixa_resultados.insert("end", texto)
    caixa_resultados.see("end")
    caixa_resultados.configure(state="disabled")

# =========================================================
# JANELA DE ANÁLISE DE XML DETALHADA
# =========================================================

def analisar_xml():
    janela_analise = ctk.CTkToplevel(janela)
    janela_analise.title("Analisar XML Fiscal Detalhado")
    janela_analise.geometry("980x780")
    janela_analise.configure(fg_color="#0b0f19")
    janela_analise.transient(janela)

    # 1. Habilitando o Drag and Drop nesta janela
    janela_analise.drop_target_register(DND_FILES)

    def soltar_arquivo_analise(evento):
        caminho = evento.data
        if caminho.startswith('{') and caminho.endswith('}'):
            caminho = caminho[1:-1]
        
        if caminho.lower().endswith('.xml'):
            entrada_xml.delete(0, "end")
            entrada_xml.insert(0, caminho)
            try:
                arvore = ET.parse(caminho)
                carregar_dados_raiz(arvore.getroot())
            except Exception as e:
                messagebox.showerror("Erro", f"Falha ao ler XML:\n\n{e}", parent=janela_analise)
        else:
            messagebox.showwarning("Aviso", "Por favor, solte apenas arquivos .XML", parent=janela_analise)

    janela_analise.dnd_bind('<<Drop>>', soltar_arquivo_analise)

    # 2. Busca manual de arquivos
    def selecionar_xml():
        caminho = filedialog.askopenfilename(
            title="Selecione um XML",
            filetypes=[("Arquivos XML", "*.xml"), ("Todos os arquivos", "*.*")]
        )
        if caminho:
            entrada_xml.delete(0, "end")
            entrada_xml.insert(0, caminho)
            try:
                arvore = ET.parse(caminho)
                carregar_dados_raiz(arvore.getroot())
            except Exception as e:
                messagebox.showerror("Erro", f"Falha ao ler XML:\n\n{e}", parent=janela_analise)

    # 3. Modal para digitar/colar o XML em texto
    def abrir_tela_texto():
        janela_texto = ctk.CTkToplevel(janela_analise)
        janela_texto.title("Colar Conteúdo XML")
        janela_texto.geometry("650x500")
        janela_texto.configure(fg_color="#0b0f19")
        janela_texto.transient(janela_analise)

        ctk.CTkLabel(janela_texto, text="Cole o conteúdo do XML abaixo:", font=f_card_title, text_color="#f8fafc").pack(pady=(20, 5), padx=20, anchor="w")
        caixa_texto = ctk.CTkTextbox(janela_texto, font=f_log, fg_color="#0f172a", border_color="#334155", border_width=1, corner_radius=8)
        caixa_texto.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        def processar_texto():
            texto = caixa_texto.get("1.0", "end-1c").strip()
            if not texto: return
            try:
                raiz = ET.fromstring(texto.encode('utf-8'))
                entrada_xml.delete(0, "end")
                entrada_xml.insert(0, "< XML Inserido Manualmente >")
                carregar_dados_raiz(raiz)
                janela_texto.destroy()
            except Exception as e:
                messagebox.showerror("Erro", f"XML Inválido ou Mal Formatado:\n\n{e}", parent=janela_texto)

        ctk.CTkButton(janela_texto, text="Processar Texto", font=f_btn, fg_color="#2563eb", hover_color="#1d4ed8", corner_radius=8, height=45, command=processar_texto).pack(pady=(0, 20), padx=20, fill="x")

    # 4. Extração completa dos campos da Sefaz
    def carregar_dados_raiz(raiz):
        dados = {
            "chave": "Não encontrada", "numero": "Não encontrado", "serie": "Não encontrada",
            "modelo": "Não encontrado", "data": "Não encontrada", "protocolo": "Não encontrado",
            "cstat": "Não encontrado", "motivo": "Não encontrado", "emitente": "Não encontrado",
            "cnpj": "Não encontrado", "valor_produtos": 0.0, "valor_nf": 0.0,
            "base_icms": 0.0, "valor_icms": 0.0, "base_icms_st": 0.0, "valor_icms_st": 0.0,
            "valor_ipi": 0.0, "valor_pis": 0.0, "valor_cofins": 0.0,
            "valor_ibs": 0.0, "valor_cbs": 0.0,
            "produtos": []
        }

        for elem in raiz.iter():
            tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
            texto = elem.text.strip() if elem.text else ""

            if tag == "nNF": dados["numero"] = texto
            elif tag == "serie": dados["serie"] = texto
            elif tag == "mod": dados["modelo"] = texto
            elif tag == "dhEmi": dados["data"] = texto
            elif tag == "chNFe": dados["chave"] = texto
            elif tag == "nProt": dados["protocolo"] = texto
            elif tag == "cStat": dados["cstat"] = texto
            elif tag == "xMotivo": dados["motivo"] = texto
            elif tag == "xNome" and dados["emitente"] == "Não encontrado": dados["emitente"] = texto
            elif tag == "CNPJ" and dados["cnpj"] == "Não encontrado": dados["cnpj"] = texto
            elif tag == "vProd": dados["valor_produtos"] = float(texto or 0)
            elif tag == "vNF": dados["valor_nf"] = float(texto or 0)
            elif tag == "vBC": dados["base_icms"] = float(texto or 0)
            elif tag == "vICMS": dados["valor_icms"] = float(texto or 0)
            elif tag == "vBCST": dados["base_icms_st"] = float(texto or 0)
            elif tag == "vST": dados["valor_icms_st"] = float(texto or 0)
            elif tag == "vIPI": dados["valor_ipi"] = float(texto or 0)
            elif tag == "vPIS": dados["valor_pis"] = float(texto or 0)
            elif tag == "vCOFINS": dados["valor_cofins"] = float(texto or 0)
            elif tag == "vIBS": dados["valor_ibs"] = float(texto or 0)
            elif tag == "vCBS": dados["valor_cbs"] = float(texto or 0)
            
            # Navega na tag <det> para buscar cada item e sua tributação
            elif tag == "det":
                nome_produto = "Desconhecido"
                classtrib = "N/D"
                for sub_elem in elem.iter():
                    sub_tag = sub_elem.tag.split('}')[-1] if '}' in sub_elem.tag else sub_elem.tag
                    
                    if sub_tag.lower() == "xprod":
                        nome_produto = sub_elem.text.strip() if sub_elem.text else "Desconhecido"
                    elif sub_tag.lower() == "cclasstrib":
                        classtrib = sub_elem.text.strip() if sub_elem.text else "N/D"
                
                dados["produtos"].append({"nome": nome_produto, "classtrib": classtrib})

        atualizar_ui_analise(dados)

    def atualizar_ui_analise(dados):
        lbl_status_badge.configure(
            text=f" {dados['cstat']} - {dados['motivo']} ",
            fg_color="#064e3b" if dados["cstat"] in ["100", "150"] else "#78350f",
            text_color="#34d399" if dados["cstat"] in ["100", "150"] else "#fbbf24"
        )
        
        lbl_numero.configure(text=dados["numero"])
        lbl_serie.configure(text=dados["serie"])
        lbl_modelo.configure(text=dados["modelo"])
        lbl_chave.configure(text=dados["chave"])
        lbl_emissao.configure(text=dados["data"])
        
        lbl_emitente.configure(text=dados["emitente"])
        lbl_cnpj.configure(text=dados["cnpj"])

        lbl_val_prod.configure(text=formatar_moeda_br(dados["valor_produtos"]))
        lbl_val_bc.configure(text=formatar_moeda_br(dados["base_icms"]))
        lbl_val_icms.configure(text=formatar_moeda_br(dados["valor_icms"]))
        lbl_val_bcst.configure(text=formatar_moeda_br(dados["base_icms_st"]))
        lbl_val_st.configure(text=formatar_moeda_br(dados["valor_icms_st"]))
        lbl_val_ipi.configure(text=formatar_moeda_br(dados["valor_ipi"]))
        lbl_val_pis.configure(text=formatar_moeda_br(dados["valor_pis"]))
        lbl_val_cofins.configure(text=formatar_moeda_br(dados["valor_cofins"]))
        lbl_val_ibs.configure(text=formatar_moeda_br(dados["valor_ibs"]))
        lbl_val_cbs.configure(text=formatar_moeda_br(dados["valor_cbs"]))

        lbl_val_total.configure(text=formatar_moeda_br(dados["valor_nf"]))
        
        # Preenchimento da tabela de produtos
        caixa_produtos.configure(state="normal")
        caixa_produtos.delete("1.0", "end")
        if dados["produtos"]:
            caixa_produtos.insert("end", f"{'PRODUTO':<65} | {'cClassTrib'}\n")
            caixa_produtos.insert("end", "-" * 85 + "\n")
            
            for p in dados["produtos"]:
                nome = p['nome']
                nome_curto = nome[:60] + "..." if len(nome) > 60 else nome
                caixa_produtos.insert("end", f"{nome_curto:<65} | {p['classtrib']}\n")
        else:
            caixa_produtos.insert("end", "Nenhum produto encontrado neste XML.")
        
        caixa_produtos.configure(state="disabled")

    # 5. Interface Visual do Dashboard
    header_frame = ctk.CTkFrame(janela_analise, fg_color="transparent")
    header_frame.pack(fill="x", padx=30, pady=(25, 5))
    
    ctk.CTkLabel(header_frame, text="Analise de XML Fiscal", font=f_titulo, text_color="#f8fafc").pack(anchor="w")
    ctk.CTkLabel(header_frame, text="Arraste um XML, busque um arquivo ou cole o texto diretamente.", font=f_sub, text_color="#94a3b8").pack(anchor="w")

    frame_controles = ctk.CTkFrame(janela_analise, fg_color="#1e293b", corner_radius=12)
    frame_controles.pack(fill="x", padx=30, pady=(10, 15))

    entrada_xml = ctk.CTkEntry(frame_controles, font=f_sub, fg_color="#0f172a", border_color="#334155", border_width=1, corner_radius=8, height=40, placeholder_text="Arraste ou selecione um XML...")
    entrada_xml.pack(side="left", fill="x", expand=True, padx=(15, 10), pady=15)

    ctk.CTkButton(frame_controles, text="Buscar Arquivo", font=f_btn, fg_color="#334155", hover_color="#475569", corner_radius=8, height=40, width=130, command=selecionar_xml).pack(side="left", padx=(0, 10))
    ctk.CTkButton(frame_controles, text="Digitar/Colar XML", font=f_btn, fg_color="#4f46e5", hover_color="#4338ca", corner_radius=8, height=40, width=140, command=abrir_tela_texto).pack(side="left", padx=(0, 15))

    lbl_status_badge = ctk.CTkLabel(janela_analise, text=" AGUARDANDO DOCUMENTO ", font=f_card_title, fg_color="#334155", text_color="#94a3b8", corner_radius=6)
    lbl_status_badge.pack(anchor="w", padx=30, pady=(0, 15))

    scroll_info = ctk.CTkScrollableFrame(janela_analise, fg_color="transparent")
    scroll_info.pack(fill="both", expand=True, padx=30, pady=(0, 20))

    # --- Seção Identificação ---
    sec_id = ctk.CTkFrame(scroll_info, fg_color="#1e293b", corner_radius=12)
    sec_id.pack(fill="x", pady=(0, 15))
    ctk.CTkLabel(sec_id, text="IDENTIFICAÇÃO", font=f_card_title, text_color="#94a3b8").pack(anchor="w", padx=20, pady=(15, 10))
    
    grid_id = ctk.CTkFrame(sec_id, fg_color="transparent")
    grid_id.pack(fill="x", padx=15, pady=(0, 15))
    
    def criar_item_info(pai, row, col, titulo):
        f = ctk.CTkFrame(pai, fg_color="transparent")
        f.grid(row=row, column=col, sticky="w", padx=5, pady=5)
        ctk.CTkLabel(f, text=titulo, font=f_sub, text_color="#94a3b8").pack(anchor="w")
        lbl = ctk.CTkLabel(f, text="-", font=f_card_title, text_color="#f8fafc")
        lbl.pack(anchor="w")
        pai.grid_columnconfigure(col, weight=1)
        return lbl

    lbl_chave = criar_item_info(grid_id, 0, 0, "Chave de Acesso")
    lbl_numero = criar_item_info(grid_id, 0, 1, "Número")
    lbl_serie = criar_item_info(grid_id, 0, 2, "Série")
    lbl_modelo = criar_item_info(grid_id, 1, 0, "Modelo")
    lbl_emissao = criar_item_info(grid_id, 1, 1, "Data de Emissão")

    # --- Seção Emitente ---
    sec_emit = ctk.CTkFrame(scroll_info, fg_color="#1e293b", corner_radius=12)
    sec_emit.pack(fill="x", pady=(0, 15))
    ctk.CTkLabel(sec_emit, text="EMITENTE", font=f_card_title, text_color="#94a3b8").pack(anchor="w", padx=20, pady=(15, 5))
    
    grid_emit = ctk.CTkFrame(sec_emit, fg_color="transparent")
    grid_emit.pack(fill="x", padx=15, pady=(0, 15))
    lbl_emitente = criar_item_info(grid_emit, 0, 0, "Razão Social")
    lbl_cnpj = criar_item_info(grid_emit, 0, 1, "CNPJ")

    # --- Seção Valores e Tributação ---
    sec_val = ctk.CTkFrame(scroll_info, fg_color="#1e293b", corner_radius=12)
    sec_val.pack(fill="x", pady=(0, 15))
    ctk.CTkLabel(sec_val, text="VALORES E TRIBUTAÇÃO", font=f_card_title, text_color="#94a3b8").pack(anchor="w", padx=20, pady=(15, 5))

    grid_val = ctk.CTkFrame(sec_val, fg_color="transparent")
    grid_val.pack(fill="x", padx=15, pady=(0, 15))

    def criar_card_valor(pai, row, col, titulo):
        card = ctk.CTkFrame(pai, fg_color="#0f172a", corner_radius=8)
        card.grid(row=row, column=col, sticky="nsew", padx=5, pady=5)
        ctk.CTkLabel(card, text=titulo, font=f_card_title, text_color="#94a3b8").pack(anchor="w", padx=15, pady=(12, 0))
        lbl = ctk.CTkLabel(card, text="R$ 0,00", font=f_btn, text_color="#e2e8f0")
        lbl.pack(anchor="w", padx=15, pady=(0, 12))
        pai.grid_columnconfigure(col, weight=1)
        return lbl

    # Linha 1
    lbl_val_prod = criar_card_valor(grid_val, 0, 0, "Total Produtos")
    lbl_val_bc = criar_card_valor(grid_val, 0, 1, "Base ICMS")
    lbl_val_icms = criar_card_valor(grid_val, 0, 2, "Valor ICMS")
    
    # Linha 2
    lbl_val_bcst = criar_card_valor(grid_val, 1, 0, "Base ICMS ST")
    lbl_val_st = criar_card_valor(grid_val, 1, 1, "Valor ICMS ST")
    lbl_val_ipi = criar_card_valor(grid_val, 1, 2, "IPI")
    
    # Linha 3
    lbl_val_pis = criar_card_valor(grid_val, 2, 0, "PIS")
    lbl_val_cofins = criar_card_valor(grid_val, 2, 1, "COFINS")

    # Linha 4 (IBS e CBS)
    lbl_val_ibs = criar_card_valor(grid_val, 3, 0, "IBS")
    lbl_val_cbs = criar_card_valor(grid_val, 3, 1, "CBS")

    # Card Total da NF
    card_total = ctk.CTkFrame(sec_val, fg_color="#064e3b", corner_radius=8)
    card_total.pack(fill="x", padx=20, pady=(10, 20))
    ctk.CTkLabel(card_total, text="TOTAL DA NOTA", font=f_card_title, text_color="#6ee7b7").pack(side="left", padx=20, pady=20)
    lbl_val_total = ctk.CTkLabel(card_total, text="R$ 0,00", font=ctk.CTkFont(family="Segoe UI", size=28, weight="bold"), text_color="#f8fafc")
    lbl_val_total.pack(side="right", padx=20, pady=20)

    # --- Seção de Produtos ---
    sec_prod = ctk.CTkFrame(scroll_info, fg_color="#1e293b", corner_radius=12)
    sec_prod.pack(fill="x", pady=(0, 20))
    ctk.CTkLabel(sec_prod, text="DETALHAMENTO DE PRODUTOS", font=f_card_title, text_color="#94a3b8").pack(anchor="w", padx=20, pady=(15, 5))
    
    caixa_produtos = ctk.CTkTextbox(sec_prod, font=f_log, fg_color="#0f172a", text_color="#cbd5e1", height=180, corner_radius=8, border_width=1, border_color="#334155")
    caixa_produtos.pack(fill="x", padx=20, pady=(0, 20))
    caixa_produtos.configure(state="disabled")

# =========================================================
# CONSTRUÇÃO DA INTERFACE GRÁFICA (GUI) PRINCIPAL
# =========================================================

janela = TkinterDnD.Tk()
janela.title("Calculadora de XML Fiscal")
janela.geometry("900x700")
janela.configure(bg="#0b0f19")

janela.drop_target_register(DND_FILES)
janela.dnd_bind('<<Drop>>', soltar_arquivo)

# Tipografia
f_titulo = ctk.CTkFont(family="Segoe UI", size=26, weight="bold")
f_sub = ctk.CTkFont(family="Segoe UI", size=13)
f_card_title = ctk.CTkFont(family="Segoe UI", size=12, weight="bold")
f_card_val = ctk.CTkFont(family="Segoe UI", size=24, weight="bold")
f_btn = ctk.CTkFont(family="Segoe UI", size=14, weight="bold")
f_log = ctk.CTkFont(family="Consolas", size=13) 

main_frame = ctk.CTkFrame(janela, fg_color="#0b0f19", corner_radius=0)
main_frame.pack(fill="both", expand=True, padx=30, pady=30)

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

def criar_card(pai, titulo, cor_destaque):
    card = ctk.CTkFrame(pai, fg_color="#1e293b", corner_radius=12)
    ctk.CTkLabel(card, text=titulo.upper(), font=f_card_title, text_color="#94a3b8").pack(anchor="w", padx=20, pady=(16, 2))
    lbl_valor = ctk.CTkLabel(card, text="0", font=f_card_val, text_color=cor_destaque)
    lbl_valor.pack(anchor="w", padx=20, pady=(0, 16))
    return card, lbl_valor

# Cards de Resumo da Leitura
linha1 = ctk.CTkFrame(main_frame, fg_color="transparent")
linha1.pack(fill="x", pady=(0, 12))

card1, label_validas_valor = criar_card(linha1, "Validadas (Sefaz)", "#3b82f6")
card1.pack(side="left", fill="both", expand=True, padx=(0, 6))
card2, label_outros_valor = criar_card(linha1, "Outros Status", "#f59e0b")
card2.pack(side="left", fill="both", expand=True, padx=6)
card3, label_erros_valor = criar_card(linha1, "Falha de Leitura", "#ef4444")
card3.pack(side="left", fill="both", expand=True, padx=(6, 0))

# Cards de Resultados Financeiros
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

# Botões da esquerda agrupados
frame_acoes_esq = ctk.CTkFrame(frame_acoes, fg_color="transparent")
frame_acoes_esq.pack(side="left")

botao_calcular = ctk.CTkButton(frame_acoes_esq, text="Processar Dados", font=f_btn, fg_color="#2563eb", hover_color="#1d4ed8", corner_radius=8, height=45, width=160, command=somar_xmls)
botao_calcular.pack(side="left", padx=(0, 12))

botao_limpar = ctk.CTkButton(frame_acoes_esq, text="Limpar", font=f_btn, fg_color="#334155", hover_color="#475569", corner_radius=8, height=45, width=140, command=limpar_tela)
botao_limpar.pack(side="left")

# Botão isolado à direita
botao_analisar = ctk.CTkButton(
    frame_acoes,
    text="🔍 Analisar XML",
    font=f_btn,
    fg_color="#7c3aed",
    hover_color="#6d28d9",
    corner_radius=8,
    height=45,
    width=190,
    command=analisar_xml
)
botao_analisar.pack(side="right")

# Console de Saída
header_log = ctk.CTkFrame(main_frame, fg_color="transparent")
header_log.pack(fill="x", pady=(0, 8))

ctk.CTkLabel(header_log, text="Log de Execução", font=f_card_title, text_color="#e2e8f0").pack(side="left")
label_status = ctk.CTkLabel(header_log, text="Aguardando diretório...", font=f_sub, text_color="#94a3b8")
label_status.pack(side="right")

caixa_resultados = ctk.CTkTextbox(main_frame, font=f_log, fg_color="#0f172a", text_color="#cbd5e1", corner_radius=12, border_width=1, border_color="#1e293b")
caixa_resultados.pack(fill="both", expand=True)
caixa_resultados.configure(state="disabled")

# Inicialização da Janela
try:
    janela.mainloop()
except Exception as erro:
    messagebox.showerror("Erro Crítico", f"Falha na aplicação:\n\n{erro}")
