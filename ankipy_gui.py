#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ankipy - Interface Gráfica Completa (sem terminal)
Versão 3.0.2 - Correção do editor na thread principal
"""

import os
import re
import json
import shutil
import urllib.request
import urllib.error
import sys
import time
import threading
import webbrowser
import ctypes
import tkinter as tk
from tkinter import ttk, scrolledtext, colorchooser, filedialog, messagebox
import tkinter.font as tkfont
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageTk
import winreg

# ----------------------------------------------------------------------
# Configuração de ID do aplicativo para o ícone da barra de tarefas
# ----------------------------------------------------------------------
myappid = 'wallmss.ankipy.version1'
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

# ----------------------------------------------------------------------
# Função para obter caminho de recursos (embutidos pelo PyInstaller)
# ----------------------------------------------------------------------
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS # type: ignore
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# ----------------------------------------------------------------------
# Gerenciamento de configurações no Registro do Windows
# ----------------------------------------------------------------------
REG_KEY = r"Software\Ankipy"

def reg_write(key, value):
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_KEY) as reg_key:
            winreg.SetValueEx(reg_key, key, 0, winreg.REG_SZ, str(value))
    except Exception as e:
        print(f"Erro ao escrever no registro: {e}")

def reg_read(key, default=""):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY) as reg_key:
            value, _ = winreg.QueryValueEx(reg_key, key)
            return value
    except FileNotFoundError:
        return default
    except Exception as e:
        print(f"Erro ao ler do registro: {e}")
        return default

def get_media_folder():
    return reg_read("media_folder", "")

def set_media_folder(path):
    reg_write("media_folder", path)

def get_last_pasta():
    return reg_read("last_pasta", "")

def set_last_pasta(pasta):
    reg_write("last_pasta", pasta)

def get_last_deck():
    return reg_read("last_deck", "")

def set_last_deck(deck):
    reg_write("last_deck", deck)

# ----------------------------------------------------------------------
# Configurações globais
# ----------------------------------------------------------------------
ANKI_CONNECT_URL = "http://localhost:8765"
MODELO_NOME = "Ankipy_Model"
PASTA_MIDIA_ANKI = None

def atualizar_pasta_media():
    global PASTA_MIDIA_ANKI
    caminho = get_media_folder()
    if caminho and Path(caminho).exists():
        PASTA_MIDIA_ANKI = Path(caminho)
    else:
        PASTA_MIDIA_ANKI = None

atualizar_pasta_media()

# ----------------------------------------------------------------------
# Comunicação com AnkiConnect
# ----------------------------------------------------------------------
def anki_call(action, **params):
    payload = json.dumps({"action": action, "version": 6, "params": params}).encode('utf-8')
    req = urllib.request.Request(ANKI_CONNECT_URL, data=payload, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=10) as resp:
        result = json.loads(resp.read().decode('utf-8'))
        if result.get("error"):
            raise Exception(f"Erro AnkiConnect: {result['error']}")
        return result.get("result")

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

def copiar_mp3s_para_media(pasta_origem, log_func):
    global PASTA_MIDIA_ANKI
    if PASTA_MIDIA_ANKI is None:
        log_func("❌ Pasta de mídia não definida. Configure nas configurações (⚙️).")
        return 0
    mp3s = [f for f in os.listdir(pasta_origem) if f.endswith('.mp3')]
    copiados = 0
    for mp3 in mp3s:
        origem = Path(pasta_origem) / mp3
        destino = PASTA_MIDIA_ANKI / mp3
        if not destino.exists():
            shutil.copy2(origem, destino)
            log_func(f"📀 Áudio copiado: {mp3}")
            copiados += 1
        else:
            log_func(f"✓ Áudio já existe: {mp3}")
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

def nota_existe(deck_nome, texto_frente):
    texto_puro = re.sub(r'\[sound:.*?\]', '', texto_frente).strip()
    texto_escapado = texto_puro.replace('"', '\\"')
    query = f'deck:"{deck_nome}" "{texto_escapado}"'
    try:
        ids = anki_call("findNotes", query=query)
        return len(ids) > 0
    except Exception:
        return False

def criar_ou_atualizar_modelo(log_func):
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
        log_func("✅ Modelo criado.")
    else:
        templates = anki_call("modelTemplates", modelName=MODELO_NOME)
        card1 = templates.get("Card 1", {})
        template_correto = "{{FrontSide}}\n<hr id=answer>\n{{Verso}}"
        if card1.get("Back") != template_correto:
            anki_call("updateModelTemplates", model={
                "name": MODELO_NOME,
                "templates": {"Card 1": {"Front": "{{Frente}}", "Back": template_correto}}
            })
            log_func("🔄 Modelo atualizado (template corrigido).")
        else:
            log_func("✅ Modelo já existe e está atualizado.")

def criar_cartoes_anki(deck_nome, pares, pasta_mp3, log_func):
    global PASTA_MIDIA_ANKI
    anki_call("createDeck", deck=deck_nome)
    log_func(f"✅ Deck '{deck_nome}' pronto.")
    
    mp3s_info = {sanitizar_nome(f): f for f in os.listdir(pasta_mp3) if f.endswith('.mp3')}
    total_adicionados = 0
    total_duplicados = 0
    
    for ingles, portugues in pares:
        try:
            if nota_existe(deck_nome, ingles):
                log_func(f"⏭️ Frase duplicada, ignorando: {ingles[:50]}...")
                total_duplicados += 1
                continue
            
            frase_chave = sanitizar_nome(ingles[:50])
            mp3_encontrado = None
            for chave, nome_mp3 in mp3s_info.items():
                if frase_chave.startswith(chave) or chave.startswith(frase_chave):
                    mp3_encontrado = nome_mp3
                    break
            
            if not mp3_encontrado:
                log_func(f"\n⚠️ Áudio não encontrado para: {ingles[:60]}...")
                caminho_audio = selecionar_audio_manual(ingles)
                if caminho_audio:
                    nome_arquivo = os.path.basename(caminho_audio)
                    destino_origem = Path(pasta_mp3) / nome_arquivo
                    if not destino_origem.exists():
                        shutil.copy2(caminho_audio, destino_origem)
                        log_func(f"📀 Áudio copiado para pasta de origem: {nome_arquivo}")
                    if PASTA_MIDIA_ANKI is not None:
                        destino_media = PASTA_MIDIA_ANKI / nome_arquivo
                        if not destino_media.exists():
                            shutil.copy2(caminho_audio, destino_media)
                            log_func(f"📀 Áudio copiado para mídia: {nome_arquivo}")
                    mp3_encontrado = nome_arquivo
                    mp3s_info[sanitizar_nome(nome_arquivo)] = nome_arquivo
                else:
                    log_func(f"⏭️ Áudio ignorado para: {ingles[:40]}...")
            
            if mp3_encontrado:
                frente = f"{ingles} [sound:{mp3_encontrado}]"
                log_func(f"🔊 Áudio vinculado: {mp3_encontrado}")
            else:
                frente = ingles
                log_func(f"⚠️ Sem áudio, cartão será criado sem som.")
            
            nota = {
                "deckName": deck_nome,
                "modelName": MODELO_NOME,
                "fields": {"Frente": frente, "Verso": portugues},
                "tags": ["importado_auto"],
                "options": {"allowDuplicate": False}
            }
            anki_call("addNote", note=nota)
            total_adicionados += 1
            log_func(f"✅ Cartão adicionado: {ingles[:50]}...")
        except Exception as e:
            if "duplicate" in str(e).lower():
                log_func(f"⏭️ Duplicata detectada pelo Anki (pós-formatação), ignorando: {ingles[:50]}...")
                total_duplicados += 1
            else:
                log_func(f"❌ Erro inesperado: {e}")
    
    log_func(f"\n📊 Resumo: {total_adicionados} adicionados, {total_duplicados} duplicados evitados.")
    return total_adicionados

# ----------------------------------------------------------------------
# Editor de texto (completo, com formatação, localizar, etc.)
# ----------------------------------------------------------------------
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

def carregar_icone_janela(window):
    try:
        ico_path = resource_path("ankipy.ico")
        png_path = resource_path("ankipy.png")
        if os.path.exists(png_path):
            img = tk.PhotoImage(file=png_path)
            # Mantém referência
            window._icon_img = img
            window.iconphoto(True, img)
        if os.path.exists(ico_path):
            try:
                window.iconbitmap(ico_path)
            except:
                pass
    except Exception:
        pass  # Falha silenciosa - não crítico

def abrir_editor_texto():
    resultado = {"texto": None, "cancelado": False}
    
    root = tk.Tk()
    root.title("Ankipy - Editor de Texto")
    carregar_icone_janela(root)
    root.geometry("1000x700")
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    if screen_width is None or screen_height is None:
        screen_width = 1280
        screen_height = 720
    x = max(0, (screen_width - 1000) // 2)
    y = max(0, (screen_height - 700) // 2)
    root.geometry(f"+{x}+{y}")
    root.configure(bg='#2e3b3e')
    
    root.lift()
    root.focus_force()
    root.attributes('-topmost', True)
    root.after(200, lambda: root.attributes('-topmost', False))
    
    text_area = scrolledtext.ScrolledText(root, wrap=tk.WORD, font=("Arial", 12),
                                          bg='#1e2a2c', fg='#e0e0e0',
                                          insertbackground='white', selectbackground='#4c8b9c',
                                          undo=True)
    
    toolbar1 = tk.Frame(root, bg='#2e3b3e', height=35)
    toolbar1.pack_propagate(False)
    toolbar2 = tk.Frame(root, bg='#2e3b3e', height=35)
    toolbar2.pack_propagate(False)
    
    btn_style = {"bg": "#3c4f55", "fg": "white", "font": ("Segoe UI", 9, "bold"),
                 "relief": tk.RAISED, "bd": 1, "padx": 5, "pady": 2}
    
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
    
    def importar_arquivo():
        file_path = filedialog.askopenfilename(
            title="Selecionar arquivo .txt",
            filetypes=[("Arquivos de texto", "*.txt"), ("Todos os arquivos", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    conteudo = f.read()
                text_area.delete("1.0", tk.END)
                text_area.insert("1.0", conteudo)
                messagebox.showinfo("Importado", f"Arquivo '{os.path.basename(file_path)}' carregado.")
                atualizar_contagem()
            except Exception as e:
                messagebox.showerror("Erro", f"Não foi possível ler o arquivo:\n{e}")
    
    # Localizar (sem substituir)
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
    
    # Layout com grid
    root.grid_rowconfigure(0, weight=0)
    root.grid_rowconfigure(1, weight=0)
    root.grid_rowconfigure(2, weight=1)
    root.grid_rowconfigure(3, weight=0)
    root.grid_rowconfigure(4, weight=0)
    root.grid_columnconfigure(0, weight=1)
    
    toolbar1.grid(row=0, column=0, sticky="ew", padx=5, pady=(2,0))
    toolbar2.grid(row=1, column=0, sticky="ew", padx=5, pady=(0,2))
    text_area.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)
    
    # Toolbar1
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
    
    btn_import = tk.Button(toolbar1, text="📎", width=3, command=importar_arquivo, **btn_style)
    btn_import.pack(side=tk.LEFT, padx=2, pady=2)
    ToolTip(btn_import, "Importar arquivo .txt")
    
    # Toolbar2
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
    
    # Rodapé
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

# ----------------------------------------------------------------------
# Janela de configurações
# ----------------------------------------------------------------------
class ConfigWindow:
    def __init__(self, parent, on_save_callback):
        self.parent = parent
        self.on_save = on_save_callback
        self.window = tk.Toplevel(parent)
        self.window.title("Configurações do Ankipy")
        self.window.geometry("650x200")
        self.window.configure(bg='#2e3b3e')
        self.window.resizable(True, False)  # permite redimensionar horizontalmente
        self.window.transient(parent)
        self.window.grab_set()
        
        # Ícone da janela
        carregar_icone_janela(self.window)
        
        main_frame = ttk.Frame(self.window, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Campo da pasta collection.media
        ttk.Label(main_frame, text="📁 Pasta collection.media do Anki:").grid(row=0, column=0, sticky='w', padx=5, pady=10)
        self.media_var = tk.StringVar(value=get_media_folder())
        entry_media = ttk.Entry(main_frame, textvariable=self.media_var, width=50)
        entry_media.grid(row=0, column=1, padx=5, pady=10, sticky='ew')
        btn_browse = ttk.Button(main_frame, text="Procurar", command=self.browse_media)
        btn_browse.grid(row=0, column=2, padx=5)
        
        # Botão de ajuda (interrogação) dentro da janela de configurações
        btn_help = ttk.Button(main_frame, text="❓", width=3, command=self.show_help)
        btn_help.grid(row=0, column=3, padx=5)
        
        # Configurar expansão da coluna do entry
        main_frame.columnconfigure(1, weight=1)
        
        # Botões OK e Cancelar
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=1, column=0, columnspan=4, pady=15)
        ttk.Button(btn_frame, text="Salvar", command=self.save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancelar", command=self.window.destroy).pack(side=tk.LEFT, padx=5)
    
    def browse_media(self):
        pasta = filedialog.askdirectory(title="Selecione a pasta collection.media do Anki")
        if pasta:
            self.media_var.set(pasta)
    
    def show_help(self):
        messagebox.showinfo(
            "Como encontrar a pasta collection.media",
            "1. Abra o Anki.\n"
            "2. No menu principal, vá em 'Ferramentas' → 'Gerenciar Arquivos de Mídia'.\n"
            "3. Clique no botão 'Abrir Pasta de Mídia'.\n"
            "4. Uma janela do Explorador será aberta. Copie o caminho que aparece na barra de endereços.\n"
            "5. Cole esse caminho no campo acima."
        )
    
    def save(self):
        novo_caminho = self.media_var.get().strip()
        if novo_caminho and Path(novo_caminho).exists():
            set_media_folder(novo_caminho)
            global PASTA_MIDIA_ANKI
            PASTA_MIDIA_ANKI = Path(novo_caminho)
            self.on_save()
            self.window.destroy()
        else:
            messagebox.showerror("Erro", "Caminho inválido ou pasta não encontrada.")

# ----------------------------------------------------------------------
# Interface gráfica principal (janela)
# ----------------------------------------------------------------------
class AnkipyGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("AnkiPy - Importador Inteligente")
        self.root.geometry("650x520")
        self.root.configure(bg='#2e3b3e')
        self.root.resizable(True, True)
        self.root.minsize(600, 480)
        carregar_icone_janela(self.root)
        
        # Centralizar a janela na tela
        self.root.update_idletasks()
        largura = self.root.winfo_width()
        altura = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (largura // 2)
        y = (self.root.winfo_screenheight() // 2) - (altura // 2)
        self.root.geometry(f"{largura}x{altura}+{x}+{y}")
        
        # Dar foco (sem topmost fixo)
        self.root.lift()
        self.root.focus_force()
        
        # Carregar última configuração
        self.last_pasta = get_last_pasta()
        self.last_deck = get_last_deck()
        
        self.pasta_var = tk.StringVar(value=self.last_pasta if self.last_pasta else "")
        self.deck_var = tk.StringVar(value=self.last_deck if self.last_deck else "")
        
        # Layout principal
        main_frame = ttk.Frame(self.root, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # === CABEÇALHO ===
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        title = ttk.Label(header_frame, text="AnkiPy", font=("Arial", 20, "bold"))
        title.pack(side=tk.LEFT)
        
        right_header = ttk.Frame(header_frame)
        right_header.pack(side=tk.RIGHT)
        
        github_img_path = resource_path("GitHub_Invertocat_Black.png")
        if os.path.exists(github_img_path):
            try:
                pil_img = Image.open(github_img_path)
                pil_img = pil_img.resize((24, 24), Image.Resampling.LANCZOS)
                self.github_icon = ImageTk.PhotoImage(pil_img)
                label_github = ttk.Label(right_header, image=self.github_icon, cursor="hand2")
                label_github.pack(side=tk.LEFT, padx=5)
                label_github.bind("<Button-1>", lambda e: webbrowser.open("https://github.com/wallmss/Ankipy"))
            except:
                ttk.Label(right_header, text="GitHub", cursor="hand2", foreground="blue").pack(side=tk.LEFT, padx=5)
        else:
            ttk.Label(right_header, text="GitHub", cursor="hand2", foreground="blue").pack(side=tk.LEFT, padx=5)
        
        credit_label = ttk.Label(right_header, text="by @wallmss", cursor="hand2")
        credit_label.pack(side=tk.LEFT, padx=5)
        credit_label.bind("<Button-1>", lambda e: webbrowser.open("https://github.com/wallmss"))
        
        # --- Campos principais ---
        frame_pasta = ttk.Frame(main_frame)
        frame_pasta.pack(fill=tk.X, pady=5)
        ttk.Label(frame_pasta, text="📂 Pasta com .txt e MP3s:").pack(side=tk.LEFT)
        entry_pasta = ttk.Entry(frame_pasta, textvariable=self.pasta_var)
        entry_pasta.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        btn_browse = ttk.Button(frame_pasta, text="Procurar", command=self.browse_pasta)
        btn_browse.pack(side=tk.LEFT)
        
        frame_deck = ttk.Frame(main_frame)
        frame_deck.pack(fill=tk.X, pady=5)
        ttk.Label(frame_deck, text="📚 Nome do deck:").pack(side=tk.LEFT)
        entry_deck = ttk.Entry(frame_deck, textvariable=self.deck_var)
        entry_deck.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        btn_config = ttk.Button(main_frame, text="⚙️ Configurações", command=self.open_settings)
        btn_config.pack(pady=10)
        
        btn_start = ttk.Button(main_frame, text="▶ Iniciar Importação", command=self.start_import)
        btn_start.pack(pady=5)
        
        # Área de log
        log_frame = ttk.LabelFrame(main_frame, text="Log")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD,
                                                   bg='#1e2a2c', fg='#e0e0e0',
                                                   insertbackground='white')
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
    
    def browse_pasta(self):
        pasta = filedialog.askdirectory(title="Selecione a pasta com .txt e MP3s")
        if pasta:
            self.pasta_var.set(pasta)
    
    def log(self, msg):
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
    
    def open_settings(self):
        ConfigWindow(self.root, self.atualizar_config)
    
    def atualizar_config(self):
        global PASTA_MIDIA_ANKI
        caminho = get_media_folder()
        if caminho and Path(caminho).exists():
            PASTA_MIDIA_ANKI = Path(caminho)
            self.log("✅ Configuração atualizada: pasta de mídia definida.")
        else:
            PASTA_MIDIA_ANKI = None
            self.log("⚠️ Configuração inválida ou não definida.")
    
    def start_import(self):
        if PASTA_MIDIA_ANKI is None:
            messagebox.showerror("Erro", "Pasta collection.media não definida.\nClique em '⚙️ Configurações' e defina o caminho.")
            return
        
        pasta = self.pasta_var.get().strip()
        deck = self.deck_var.get().strip()
        if not pasta or not Path(pasta).exists():
            messagebox.showerror("Erro", "Pasta com .txt e MP3s inválida ou não encontrada.")
            return
        if not deck:
            messagebox.showerror("Erro", "Nome do deck não pode ficar vazio.")
            return
        
        set_last_pasta(pasta)
        set_last_deck(deck)
        
        # Verificar .txt ANTES da thread (para evitar tkinter na thread secundária)
        txts = list(Path(pasta).glob("*.txt"))
        if not txts:
            self.log("❌ Nenhum arquivo .txt encontrado. Abrindo editor...")
            texto_editado = abrir_editor_texto()
            if texto_editado:
                temp_txt = Path(pasta) / "temp_import.txt"
                with open(temp_txt, 'w', encoding='utf-8') as f:
                    f.write(texto_editado)
                caminho_txt = temp_txt
                self.log(f"📄 Arquivo temporário criado: {temp_txt.name}")
            else:
                self.log("❌ Nenhum texto fornecido. Abortando.")
                return
        else:
            caminho_txt = txts[0]
            self.log(f"📄 Arquivo: {caminho_txt.name}")
        
        threading.Thread(target=self.importar, args=(pasta, deck, caminho_txt), daemon=True).start()
    
    def importar(self, pasta, deck, caminho_txt):
        self.log("=== Iniciando importação ===\n")
        try:
            anki_call("version")
            self.log("✅ Conectado ao AnkiConnect.")
        except Exception as e:
            self.log(f"❌ Erro de conexão: {e}")
            self.log("Certifique-se que o Anki está aberto e o complemento AnkiConnect instalado.")
            return
        
        self.log("Copiando arquivos de áudio...")
        copiar_mp3s_para_media(pasta, self.log)
        
        pares = ler_pares_do_texto(caminho_txt)
        self.log(f"🔍 {len(pares)} pares de frases encontrados.")
        
        criar_ou_atualizar_modelo(self.log)
        criar_cartoes_anki(deck, pares, pasta, self.log)
        self.log(f"\n✨ Importação concluída!")
    
    def on_close(self):
        self.root.destroy()

# ----------------------------------------------------------------------
# Ponto de entrada
# ----------------------------------------------------------------------
if __name__ == "__main__":
    app = AnkipyGUI()
    app.root.mainloop()