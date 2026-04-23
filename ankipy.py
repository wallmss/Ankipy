#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ankipy - Importador automático de frases com áudio para Anki
Versão 2.4.0 - Editor com toolbars fixas, atalhos corrigidos e localização visível
"""

import os
import re
import json
import shutil
import urllib.request
import urllib.error
import msvcrt
import time
import tkinter as tk
from tkinter import ttk, scrolledtext, colorchooser, filedialog, messagebox
import tkinter.font as tkfont
from pathlib import Path
from datetime import datetime

ANKI_CONNECT_URL = "http://localhost:8765"
CONFIG_FILE = Path(__file__).parent / "config.txt"
ULTIMA_CONFIG = Path(__file__).parent / "ultima_config.txt"
MODELO_NOME = "Ankipy_Model"

# ------------------------------------------------------------------------------
# Configuração da pasta de mídia do Anki
# ------------------------------------------------------------------------------
def ler_pasta_media():
    if not CONFIG_FILE.exists():
        exemplo = r"C:\Users\SeuUsuario\AppData\Roaming\Anki2\SeuPerfil\collection.media"
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            f.write("# Cole abaixo o caminho completo da pasta collection.media do Anki\n")
            f.write("# Como encontrar: Abra o Anki > Ferramentas > Gerenciar Arquivos de Mídia > Abrir Pasta de Mídia\n")
            f.write(f"{exemplo}\n")
        print(f"❌ config.txt não encontrado. Um modelo foi criado em {CONFIG_FILE}")
        print("Edite o arquivo com o caminho correto e execute novamente.")
        exit(1)
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        for linha in f:
            linha = linha.strip()
            if linha and not linha.startswith('#'):
                caminho = Path(linha)
                if caminho.exists():
                    return caminho
                else:
                    print(f"❌ Caminho informado em config.txt não existe: {caminho}")
                    exit(1)
    print("❌ Nenhum caminho válido encontrado em config.txt")
    exit(1)

PASTA_MIDIA_ANKI = ler_pasta_media()

# ------------------------------------------------------------------------------
# Comunicação com AnkiConnect
# ------------------------------------------------------------------------------
def anki_call(action, **params):
    payload = json.dumps({"action": action, "version": 6, "params": params}).encode('utf-8')
    req = urllib.request.Request(ANKI_CONNECT_URL, data=payload, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=10) as resp:
        result = json.loads(resp.read().decode('utf-8'))
        if result.get("error"):
            raise Exception(f"Erro AnkiConnect: {result['error']}")
        return result.get("result")

# ------------------------------------------------------------------------------
# Utilitários de texto e áudio
# ------------------------------------------------------------------------------
def sanitizar_nome(nome_arquivo):
    nome, _ = os.path.splitext(nome_arquivo)
    nome = re.sub(r'^\d+\s*', '', nome).strip()
    nome = re.sub(r'[^\w\s]', '', nome).lower()
    return nome

def ler_pares_do_texto(caminho_txt):
    with open(caminho_txt, 'r', encoding='utf-8') as f:
        linhas = [linha.rstrip() for linha in f if linha.strip()]
    pares = []
    for i in range(0, len(linhas), 2):
        if i+1 < len(linhas):
            pares.append((linhas[i].strip(), linhas[i+1].strip()))
    return pares

def copiar_mp3s_para_media(pasta_origem):
    mp3s = [f for f in os.listdir(pasta_origem) if f.endswith('.mp3')]
    copiados = 0
    for mp3 in mp3s:
        origem = Path(pasta_origem) / mp3
        destino = PASTA_MIDIA_ANKI / mp3
        if not destino.exists():
            shutil.copy2(origem, destino)
            print(f"📀 Áudio copiado: {mp3}")
            copiados += 1
        else:
            print(f"✓ Áudio já existe: {mp3}")
    return copiados

def selecionar_audio_manual(frase_ingles):
    root = tk.Tk()
    root.withdraw()
    titulo = f"Selecione o áudio para: {frase_ingles[:60]}..."
    arquivo = filedialog.askopenfilename(
        title=titulo,
        filetypes=[("Arquivos MP3", "*.mp3"), ("Todos os arquivos", "*.*")]
    )
    root.destroy()
    return arquivo if arquivo else None

# ------------------------------------------------------------------------------
# Verificação de duplicatas e interação com usuário
# ------------------------------------------------------------------------------
def nota_existe(deck_nome, texto_frente):
    texto_puro = re.sub(r'\[sound:.*?\]', '', texto_frente).strip()
    texto_escapado = texto_puro.replace('"', '\\"')
    query = f'deck:"{deck_nome}" "{texto_escapado}"'
    try:
        ids = anki_call("findNotes", query=query)
        return len(ids) > 0
    except Exception:
        return False

def perguntar_duplicata(frase_ingles):
    print(f"\n⚠️ FRASE DUPLICADA: {frase_ingles[:70]}...")
    print("Deseja adicionar mesmo assim? (S = sim, N = não, Enter = sim após 10s)")
    inicio = time.time()
    while time.time() - inicio < 10:
        if msvcrt.kbhit():
            tecla = msvcrt.getch().decode('utf-8').lower()
            if tecla == 's' or tecla == '\r':
                print(" ✅ Adicionando...")
                return True
            elif tecla == 'n':
                print(" ❌ Ignorando duplicata.")
                return False
        time.sleep(0.1)
    print(" ⏱️ Timeout: ignorando duplicata.")
    return False

def perguntar_sim_nao(mensagem, timeout=0):
    print(mensagem)
    if timeout > 0:
        inicio = time.time()
        while time.time() - inicio < timeout:
            if msvcrt.kbhit():
                tecla = msvcrt.getch().decode('utf-8').lower()
                if tecla == 's' or tecla == '\r':
                    return True
                elif tecla == 'n':
                    return False
            time.sleep(0.05)
        print(" ⏱️ Timeout: assumindo 'N'.")
        return False
    else:
        while True:
            tecla = msvcrt.getch().decode('utf-8').lower()
            if tecla == 's' or tecla == '\r':
                return True
            elif tecla == 'n':
                return False

# ------------------------------------------------------------------------------
# Gerência do modelo Anki
# ------------------------------------------------------------------------------
def criar_ou_atualizar_modelo():
    modelos = anki_call("modelNames")
    if MODELO_NOME not in modelos:
        modelo = {
            "modelName": MODELO_NOME,
            "inOrderFields": ["Frente", "Verso"],
            "css": ".card { font-family: arial; font-size: 20px; text-align: center; }",
            "cardTemplates": [{
                "Name": "Card 1",
                "Front": "{{Frente}}",
                "Back": "{{FrontSide}}\n<hr id=answer>\n{{Verso}}"
            }]
        }
        anki_call("createModel", **modelo)
        print(f"✅ Modelo '{MODELO_NOME}' criado.")
    else:
        templates = anki_call("modelTemplates", modelName=MODELO_NOME)
        card1 = templates.get("Card 1", {})
        template_correto = "{{FrontSide}}\n<hr id=answer>\n{{Verso}}"
        if card1.get("Back") != template_correto:
            anki_call("updateModelTemplates", model={
                "name": MODELO_NOME,
                "templates": {"Card 1": {"Front": "{{Frente}}", "Back": template_correto}}
            })
            print(f"🔄 Modelo '{MODELO_NOME}' atualizado (template corrigido).")
        else:
            print(f"✅ Modelo '{MODELO_NOME}' já existe e está atualizado.")

# ------------------------------------------------------------------------------
# Criação dos cartões no Anki
# ------------------------------------------------------------------------------
def criar_cartoes_anki(deck_nome, pares, pasta_mp3):
    anki_call("createDeck", deck=deck_nome)
    print(f"✅ Deck '{deck_nome}' pronto.")
    
    mp3s_info = {sanitizar_nome(f): f for f in os.listdir(pasta_mp3) if f.endswith('.mp3')}
    total_adicionados = 0
    total_duplicados = 0
    
    for ingles, portugues in pares:
        try:
            # --- 1) Monta o texto puro (sem áudio) para verificação de duplicata ---
            frente_pura = ingles  # texto sem tag de som ainda
            
            # --- 2) Verifica se a frase já existe no deck ---
            if nota_existe(deck_nome, frente_pura):
                print(f"⏭️ Frase duplicada, ignorando: {ingles[:50]}...")
                total_duplicados += 1
                continue
            
            # --- 3) Não é duplicata: buscar áudio ---
            frase_chave = sanitizar_nome(ingles[:50])
            mp3_encontrado = None
            # tenta encontrar automaticamente
            for chave, nome_mp3 in mp3s_info.items():
                if frase_chave.startswith(chave) or chave.startswith(frase_chave):
                    mp3_encontrado = nome_mp3
                    break
            
            # se não encontrou, pergunta manualmente
            if not mp3_encontrado:
                print(f"\n⚠️ Áudio não encontrado para: {ingles[:60]}...")
                caminho_audio = selecionar_audio_manual(ingles)
                if caminho_audio:
                    nome_arquivo = os.path.basename(caminho_audio)
                    # copia para pasta de origem (para futuras execuções)
                    destino_origem = Path(pasta_mp3) / nome_arquivo
                    if not destino_origem.exists():
                        shutil.copy2(caminho_audio, destino_origem)
                        print(f"📀 Áudio copiado para pasta de origem: {nome_arquivo}")
                    # copia para a pasta de mídia do Anki
                    destino_media = PASTA_MIDIA_ANKI / nome_arquivo
                    if not destino_media.exists():
                        shutil.copy2(caminho_audio, destino_media)
                        print(f"📀 Áudio copiado para mídia: {nome_arquivo}")
                    mp3_encontrado = nome_arquivo
                    # adiciona ao dicionário para uso futuro no mesmo lote
                    mp3s_info[sanitizar_nome(nome_arquivo)] = nome_arquivo
                else:
                    print(f"⏭️ Áudio ignorado para: {ingles[:40]}...")
            
            # --- 4) Monta a frente com áudio (se houver) ---
            if mp3_encontrado:
                frente = f"{ingles} [sound:{mp3_encontrado}]"
                print(f"🔊 Áudio vinculado: {mp3_encontrado}")
            else:
                frente = ingles
                print(f"⚠️ Sem áudio, cartão será criado sem som.")
            
            # --- 5) Cria o cartão ---
            nota = {
                "deckName": deck_nome,
                "modelName": MODELO_NOME,
                "fields": {"Frente": frente, "Verso": portugues},
                "tags": ["importado_auto"],
                "options": {"allowDuplicate": False}
            }
            anki_call("addNote", note=nota)
            total_adicionados += 1
            print(f"✅ Cartão adicionado: {ingles[:50]}...")
            
        except Exception as e:
            # Caso o AnkiConnect ainda acuse duplicata (por diferença de formatação)
            if "duplicate" in str(e).lower():
                print(f"⏭️ Duplicata detectada pelo Anki (pós-formatação), ignorando: {ingles[:50]}...")
                total_duplicados += 1
            else:
                print(f"❌ Erro inesperado: {e}")
    
    print(f"\n📊 Resumo: {total_adicionados} cartões adicionados, {total_duplicados} duplicados evitados.")
    return total_adicionados

# ------------------------------------------------------------------------------
# Editor de texto com layout em grid e localização visível
# ------------------------------------------------------------------------------
class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        widget.bind('<Enter>', self.show_tip)
        widget.bind('<Leave>', self.hide_tip)
    def show_tip(self, event):
        if self.tipwindow:
            return
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                         background="#ffffe0", relief=tk.SOLID, borderwidth=1)
        label.pack()
    def hide_tip(self, event):
        if self.tipwindow:
            self.tipwindow.destroy()
            self.tipwindow = None

def abrir_editor_texto():
    resultado = {"texto": None, "cancelado": False}
    
    root = tk.Tk()
    root.title("Ankipy - Editor de Texto")
    root.geometry("1000x700")
    # Centralizar
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = (screen_width - 1000) // 2
    y = (screen_height - 700) // 2
    root.geometry(f"+{x}+{y}")
    root.configure(bg='#2e3b3e')
    
    root.lift()
    root.focus_force()
    root.attributes('-topmost', True)
    root.after(200, lambda: root.attributes('-topmost', False))
    
    # Área de texto com scroll
    text_area = scrolledtext.ScrolledText(root, wrap=tk.WORD, font=("Arial", 12),
                                          bg='#1e2a2c', fg='#e0e0e0',
                                          insertbackground='white', selectbackground='#4c8b9c',
                                          undo=True)
    
    # Toolbars
    toolbar1 = tk.Frame(root, bg='#2e3b3e', height=35)
    toolbar1.pack_propagate(False)
    toolbar2 = tk.Frame(root, bg='#2e3b3e', height=35)
    toolbar2.pack_propagate(False)
    
    btn_style = {"bg": "#3c4f55", "fg": "white", "font": ("Segoe UI", 9, "bold"),
                 "relief": tk.RAISED, "bd": 1, "padx": 5, "pady": 2}
    
    # Variáveis de fonte
    fonte_familia = tk.StringVar(value="Arial")
    fonte_tamanho = tk.IntVar(value=12)
    
    def atualizar_tags():
        text_area.tag_configure("bold", font=(fonte_familia.get(), fonte_tamanho.get(), "bold"))
        text_area.tag_configure("italic", font=(fonte_familia.get(), fonte_tamanho.get(), "italic"))
        text_area.tag_configure("underline", font=(fonte_familia.get(), fonte_tamanho.get(), "underline"))
    
    def aplicar_formatacao(tag):
        def aplicar():
            try:
                if text_area.tag_ranges(tk.SEL):
                    start, end = text_area.index(tk.SEL_FIRST), text_area.index(tk.SEL_LAST)
                    if tag in text_area.tag_names(start):
                        text_area.tag_remove(tag, start, end)
                    else:
                        text_area.tag_add(tag, start, end)
            except:
                pass
        return aplicar
    
    aplicar_negrito = aplicar_formatacao("bold")
    aplicar_italico = aplicar_formatacao("italic")
    aplicar_sublinhado = aplicar_formatacao("underline")
    
    def limpar_formatacao():
        try:
            if text_area.tag_ranges(tk.SEL):
                start, end = text_area.index(tk.SEL_FIRST), text_area.index(tk.SEL_LAST)
                for tag in ("bold", "italic", "underline"):
                    text_area.tag_remove(tag, start, end)
                for tag in text_area.tag_names():
                    if tag.startswith("color_"):
                        text_area.tag_remove(tag, start, end)
        except:
            pass
    
    def aumentar_fonte():
        tamanho = fonte_tamanho.get() + 1
        fonte_tamanho.set(tamanho)
        text_area.configure(font=(fonte_familia.get(), tamanho))
        atualizar_tags()
        root.update()
    
    def diminuir_fonte():
        tamanho = fonte_tamanho.get() - 1
        if tamanho >= 6:
            fonte_tamanho.set(tamanho)
            text_area.configure(font=(fonte_familia.get(), tamanho))
            atualizar_tags()
            root.update()
    
    def zoom_mouse(event):
        if event.delta > 0:
            aumentar_fonte()
        else:
            diminuir_fonte()
        return "break"
    
    def aplicar_cor():
        try:
            if text_area.tag_ranges(tk.SEL):
                start, end = text_area.index(tk.SEL_FIRST), text_area.index(tk.SEL_LAST)
                cor = colorchooser.askcolor(title="Cor do texto")[1]
                if cor:
                    tag = f"color_{cor.replace('#', '')}"
                    text_area.tag_configure(tag, foreground=cor, font=(fonte_familia.get(), fonte_tamanho.get()))
                    text_area.tag_add(tag, start, end)
        except:
            pass
    
    # ---------- Importar arquivo .txt ----------
    def importar_arquivo():
        file_path = filedialog.askopenfilename(
            title="Selecionar arquivo .txt",
            filetypes=[("Arquivos de texto", "*.txt"), ("Todos os arquivos", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    conteudo = f.read()
                # Substitui todo o conteúdo atual
                text_area.delete("1.0", tk.END)
                text_area.insert("1.0", conteudo)
                messagebox.showinfo("Importado", f"Arquivo '{os.path.basename(file_path)}' carregado com sucesso.")
                atualizar_contagem()
            except Exception as e:
                messagebox.showerror("Erro", f"Não foi possível ler o arquivo:\n{e}")
    
    # ---------- Localizar (com navegação e foco) ----------
    find_window = None
    find_entry = None
    find_label = None
    current_match = 0
    total_matches = 0
    last_search = ""
    
    def update_match_counter():
        if find_label:
            if total_matches == 0:
                find_label.config(text="0 ocorrências")
            else:
                find_label.config(text=f"{current_match} de {total_matches}")
    
    def find_all_occurrences(term):
        nonlocal total_matches, current_match, last_search
        if not term:
            return []
        text = text_area.get("1.0", tk.END)
        positions = []
        start = "1.0"
        while True:
            pos = text_area.search(term, start, tk.END, nocase=True)
            if not pos:
                break
            end = f"{pos}+{len(term)}c"
            positions.append((pos, end))
            start = end
        total_matches = len(positions)
        last_search = term
        return positions
    
    def go_to_match(index):
        nonlocal current_match
        if index < 0 or index >= total_matches:
            return
        current_match = index + 1
        positions = find_all_occurrences(last_search)
        if positions:
            pos, end = positions[index]
            text_area.tag_remove(tk.SEL, "1.0", tk.END)
            text_area.tag_add(tk.SEL, pos, end)
            text_area.mark_set(tk.INSERT, end)
            text_area.see(pos)
            text_area.focus_set()
            update_match_counter()
    
    def find_next():
        if not last_search or total_matches == 0:
            return
        next_idx = current_match % total_matches
        go_to_match(next_idx)
    
    def find_prev():
        if not last_search or total_matches == 0:
            return
        prev_idx = (current_match - 2) % total_matches
        go_to_match(prev_idx)
    
    def on_find():
        nonlocal find_entry
        if find_entry is None:
            return
        term = find_entry.get()
        if not term:
            return
        all_pos = find_all_occurrences(term)
        if all_pos:
            current_match = 1
            pos, end = all_pos[0]
            text_area.tag_remove(tk.SEL, "1.0", tk.END)
            text_area.tag_add(tk.SEL, pos, end)
            text_area.mark_set(tk.INSERT, end)
            text_area.see(pos)
            text_area.focus_set()
            update_match_counter()
        else:
            current_match = 0
            total_matches = 0
            update_match_counter()
            messagebox.showinfo("Localizar", f"Nenhuma ocorrência de '{term}' encontrada.")
    
    def open_find_dialog():
        nonlocal find_window, find_entry, find_label
        if find_window and find_window.winfo_exists():
            find_window.lift()
            find_window.focus()
            return
        find_window = tk.Toplevel(root)
        find_window.title("Localizar")
        find_window.geometry("350x120")
        find_window.configure(bg='#2e3b3e')
        find_window.resizable(False, False)
        root_x = root.winfo_rootx()
        root_y = root.winfo_rooty()
        find_window.geometry(f"+{root_x+10}+{root_y+50}")
        # Configurar para ficar sempre na frente do editor (mas não de outros apps)
        find_window.attributes('-topmost', True)
        find_window.attributes('-topmost', False)
        
        def raise_find_window():
            if find_window and find_window.winfo_exists():
                find_window.lift()
                find_window.attributes('-topmost', True)
                find_window.attributes('-topmost', False)
        root.bind("<FocusIn>", lambda e: raise_find_window())
        find_window.bind("<FocusIn>", lambda e: raise_find_window())
        
        frame1 = tk.Frame(find_window, bg='#2e3b3e')
        frame1.pack(fill=tk.X, padx=5, pady=5)
        tk.Label(frame1, text="Buscar:", bg='#2e3b3e', fg='white').pack(side=tk.LEFT, padx=5)
        find_entry = tk.Entry(frame1, width=30)
        find_entry.pack(side=tk.LEFT, padx=5)
        find_entry.bind("<Return>", lambda e: on_find())
        
        frame2 = tk.Frame(find_window, bg='#2e3b3e')
        frame2.pack(fill=tk.X, padx=5, pady=5)
        btn_find = tk.Button(frame2, text="🔍 Localizar", command=on_find, **btn_style)
        btn_find.pack(side=tk.LEFT, padx=2)
        btn_prev = tk.Button(frame2, text="◀ Anterior", command=find_prev, **btn_style)
        btn_prev.pack(side=tk.LEFT, padx=2)
        btn_next = tk.Button(frame2, text="Próximo ▶", command=find_next, **btn_style)
        btn_next.pack(side=tk.LEFT, padx=2)
        
        find_label = tk.Label(find_window, text="0 ocorrências", bg='#2e3b3e', fg='#e0e0e0')
        find_label.pack(pady=2)
        
        find_window.protocol("WM_DELETE_WINDOW", lambda w=find_window: w.destroy())
        find_window.lift()
        find_window.focus_force()
        find_entry.focus()
    
    def atualizar_contagem(event=None):
        texto = text_area.get("1.0", tk.END)
        palavras = len(texto.split())
        caracteres = len(texto) - 1
        label_contagem.config(text=f"Palavras: {palavras} | Caracteres: {caracteres}")
    
    def mudar_familia(event=None):
        nova_familia = combo_fonte.get()
        fonte_familia.set(nova_familia)
        text_area.configure(font=(nova_familia, fonte_tamanho.get()))
        atualizar_tags()
    
    # ---------- Construção da interface (grid) ----------
    root.grid_rowconfigure(0, weight=0)
    root.grid_rowconfigure(1, weight=0)
    root.grid_rowconfigure(2, weight=1)
    root.grid_rowconfigure(3, weight=0)
    root.grid_rowconfigure(4, weight=0)
    root.grid_columnconfigure(0, weight=1)
    
    toolbar1.grid(row=0, column=0, sticky="ew", padx=5, pady=(2,0))
    toolbar2.grid(row=1, column=0, sticky="ew", padx=5, pady=(0,2))
    text_area.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)
    
    # toolbar1 (formatação e importar)
    btn_bold = tk.Button(toolbar1, text="B", width=3, command=aplicar_negrito, **btn_style)
    btn_bold.pack(side=tk.LEFT, padx=2, pady=2)
    ToolTip(btn_bold, "Negrito (Ctrl+B)")
    
    btn_italic = tk.Button(toolbar1, text="I", width=3, command=aplicar_italico, **btn_style)
    btn_italic.pack(side=tk.LEFT, padx=2, pady=2)
    ToolTip(btn_italic, "Itálico (Ctrl+I)")
    
    btn_underline = tk.Button(toolbar1, text="U", width=3, command=aplicar_sublinhado, **btn_style)
    btn_underline.pack(side=tk.LEFT, padx=2, pady=2)
    ToolTip(btn_underline, "Sublinhado (Ctrl+U)")
    
    btn_clear = tk.Button(toolbar1, text="Limpar", width=7, command=limpar_formatacao, **btn_style)
    btn_clear.pack(side=tk.LEFT, padx=5, pady=2)
    ToolTip(btn_clear, "Limpar formatação da seleção")
    
    btn_color = tk.Button(toolbar1, text="🎨", width=3, command=aplicar_cor, **btn_style)
    btn_color.pack(side=tk.LEFT, padx=2, pady=2)
    ToolTip(btn_color, "Cor do texto")
    
    btn_find = tk.Button(toolbar1, text="🔍", width=3, command=open_find_dialog, **btn_style)
    btn_find.pack(side=tk.LEFT, padx=2, pady=2)
    ToolTip(btn_find, "Localizar (Ctrl+F)")
    
    # NOVO BOTÃO: Importar arquivo .txt
    btn_import = tk.Button(toolbar1, text="📎", width=3, command=importar_arquivo, **btn_style)
    btn_import.pack(side=tk.LEFT, padx=2, pady=2)
    ToolTip(btn_import, "Importar arquivo .txt")
    
    # toolbar2 (fonte e zoom) - inalterada
    tk.Label(toolbar2, text="Fonte:", bg='#2e3b3e', fg='white', font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=2)
    fontes_disponiveis = sorted(list(tkfont.families()))
    combo_fonte = ttk.Combobox(toolbar2, values=fontes_disponiveis, textvariable=fonte_familia, width=15)
    combo_fonte.pack(side=tk.LEFT, padx=2)
    combo_fonte.bind("<<ComboboxSelected>>", mudar_familia)
    ToolTip(combo_fonte, "Selecionar família da fonte")
    
    tk.Label(toolbar2, text="Tamanho:", bg='#2e3b3e', fg='white', font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=5)
    spin_tamanho = tk.Spinbox(toolbar2, from_=6, to=72, width=4, textvariable=fonte_tamanho,
                              command=lambda: [text_area.configure(font=(fonte_familia.get(), fonte_tamanho.get())), atualizar_tags()])
    spin_tamanho.pack(side=tk.LEFT, padx=2)
    ToolTip(spin_tamanho, "Tamanho da fonte")
    
    btn_font_up = tk.Button(toolbar2, text="➕", width=3, command=aumentar_fonte, **btn_style)
    btn_font_up.pack(side=tk.LEFT, padx=2)
    ToolTip(btn_font_up, "Aumentar fonte (Ctrl++)")
    
    btn_font_down = tk.Button(toolbar2, text="➖", width=3, command=diminuir_fonte, **btn_style)
    btn_font_down.pack(side=tk.LEFT, padx=2)
    ToolTip(btn_font_down, "Diminuir fonte (Ctrl+-)")
    
    # Rodapé e botões
    frame_rodape = tk.Frame(root, bg='#2e3b3e', height=25)
    frame_rodape.grid(row=3, column=0, sticky="ew", pady=2)
    label_contagem = tk.Label(frame_rodape, text="Palavras: 0 | Caracteres: 0",
                              bg='#2e3b3e', fg='#e0e0e0', font=("Segoe UI", 9))
    label_contagem.pack(side=tk.RIGHT, padx=5)
    
    frame_botoes = tk.Frame(root, bg='#2e3b3e')
    frame_botoes.grid(row=4, column=0, sticky="ew", pady=5)
    
    btn_salvar = tk.Button(frame_botoes, text="Salvar e Importar", 
                           bg='#4cae4c', fg='white', padx=10, font=("Segoe UI", 10, "bold"))
    btn_salvar.pack(side=tk.RIGHT, padx=10)
    ToolTip(btn_salvar, "Salvar o texto e importar como cartões")
    btn_cancelar = tk.Button(frame_botoes, text="Cancelar",
                             bg='#d9534f', fg='white', padx=10, font=("Segoe UI", 10, "bold"))
    btn_cancelar.pack(side=tk.RIGHT, padx=5)
    ToolTip(btn_cancelar, "Cancelar e voltar")
    
    # Atalhos
    def cancelar_evento(e):
        return "break"
    
    text_area.bind("<Control-i>", lambda e: (aplicar_italico(), cancelar_evento(e)))
    text_area.bind("<Control-b>", lambda e: (aplicar_negrito(), cancelar_evento(e)))
    text_area.bind("<Control-u>", lambda e: (aplicar_sublinhado(), cancelar_evento(e)))
    text_area.bind("<Control-f>", lambda e: (open_find_dialog(), cancelar_evento(e)))
    text_area.bind("<Control-plus>", lambda e: (aumentar_fonte(), cancelar_evento(e)))
    text_area.bind("<Control-minus>", lambda e: (diminuir_fonte(), cancelar_evento(e)))
    text_area.bind("<Control-MouseWheel>", zoom_mouse)
    text_area.bind("<<Modified>>", lambda e: [atualizar_contagem(), text_area.edit_modified(False)])
    
    atualizar_contagem()
    text_area.focus_set()
    
    def salvar():
        conteudo = text_area.get("1.0", tk.END).rstrip("\n")
        if not conteudo:
            messagebox.showwarning("Aviso", "Nenhum texto foi inserido.")
            return
        resultado["texto"] = conteudo
        if find_window and find_window.winfo_exists():
            find_window.destroy()
        root.destroy()
    
    def cancelar():
        resultado["cancelado"] = True
        if find_window and find_window.winfo_exists():
            find_window.destroy()
        root.destroy()
    
    btn_salvar.config(command=salvar)
    btn_cancelar.config(command=cancelar)
    root.protocol("WM_DELETE_WINDOW", cancelar)
    root.mainloop()
    
    if resultado["cancelado"]:
        return None
    return resultado["texto"]

# ------------------------------------------------------------------------------
# Persistência de configurações
# ------------------------------------------------------------------------------
def carregar_ultima_config():
    config = {}
    if ULTIMA_CONFIG.exists():
        with open(ULTIMA_CONFIG, 'r', encoding='utf-8') as f:
            for linha in f:
                if '=' in linha:
                    chave, valor = linha.strip().split('=', 1)
                    config[chave] = valor
    return config.get("pasta"), config.get("deck")

def salvar_ultima_config(pasta, deck):
    with open(ULTIMA_CONFIG, 'w', encoding='utf-8') as f:
        f.write(f"pasta={pasta}\n")
        f.write(f"deck={deck}\n")

# ------------------------------------------------------------------------------
# Função principal
# ------------------------------------------------------------------------------
def main():
    print("=== Ankipy - Importador Automático para Anki ===\n")
    
    ultima_pasta, ultimo_deck = carregar_ultima_config()
    
    prompt_pasta = "📂 Pasta com .txt e MP3s"
    if ultima_pasta:
        prompt_pasta += f" (Enter para reutilizar '{ultima_pasta}')"
    prompt_pasta += ": "
    pasta_input = input(prompt_pasta).strip()
    if pasta_input == "" and ultima_pasta:
        pasta = ultima_pasta
    else:
        pasta = pasta_input
    if not Path(pasta).exists():
        print("❌ Pasta não encontrada.")
        return
    
    prompt_deck = "📚 Nome do deck"
    if ultimo_deck:
        prompt_deck += f" (Enter para reutilizar '{ultimo_deck}')"
    prompt_deck += ": "
    deck_input = input(prompt_deck).strip()
    if deck_input == "" and ultimo_deck:
        deck = ultimo_deck
    else:
        deck = deck_input
    if not deck:
        print("❌ Nome do deck inválido.")
        return
    
    salvar_ultima_config(pasta, deck)
    
    txts = list(Path(pasta).glob("*.txt"))
    if not txts:
        print("❌ Nenhum arquivo .txt encontrado. Abrindo editor de texto...")
        texto_editado = abrir_editor_texto()
        if texto_editado:
            temp_txt = Path(pasta) / "temp_import.txt"
            with open(temp_txt, 'w', encoding='utf-8') as f:
                f.write(texto_editado)
            caminho_txt = temp_txt
            print(f"📄 Arquivo temporário criado: {temp_txt.name}")
        else:
            print("❌ Nenhum texto fornecido. Abortando.")
            return
    else:
        caminho_txt = txts[0]
        print(f"📄 Arquivo: {caminho_txt.name}")
    
    pares = ler_pares_do_texto(caminho_txt)
    print(f"🔍 {len(pares)} pares de frases.")
    
    copiar_mp3s_para_media(pasta)
    
    try:
        anki_call("version")
        print("✅ Conectado ao AnkiConnect.")
    except Exception as e:
        print(f"❌ Erro de conexão: {e}")
        print("Abra o Anki e instale AnkiConnect (código 2055492159).")
        return
    
    criar_ou_atualizar_modelo()
    total = criar_cartoes_anki(deck, pares, pasta)
    print(f"\n✨ Importação concluída! {total} cartões adicionados ao deck '{deck}'.")

if __name__ == "__main__":
    main()