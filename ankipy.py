#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ankipy - Importador automático de frases com áudio para Anki
Versão 2.0.0
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
from tkinter import scrolledtext, colorchooser, filedialog, messagebox
from pathlib import Path
from datetime import datetime

ANKI_CONNECT_URL = "http://localhost:8765"
CONFIG_FILE = Path(__file__).parent / "config.txt"
ULTIMA_CONFIG = Path(__file__).parent / "ultima_config.txt"
MODELO_NOME = "Ankipy_Model"  # Nome fixo do modelo

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
    """Abre janela Explorer para selecionar MP3, com a frase no título."""
    root = tk.Tk()
    root.withdraw()  # esconde a janela principal
    root.title("Ankipy - Selecionar áudio")
    # Cria uma janela de mensagem personalizada? Melhor: usar askopenfilename com title dinâmico
    titulo = f"Selecione o áudio para: {frase_ingles[:60]}..."
    arquivo = filedialog.askopenfilename(
        title=titulo,
        filetypes=[("Arquivos MP3", "*.mp3"), ("Todos os arquivos", "*.*")]
    )
    root.destroy()
    return arquivo if arquivo else None

def nota_existe(deck_nome, texto_frente):
    """
    Verifica se já existe uma nota no deck com o mesmo texto na frente (ignorando áudio).
    Busca apenas dentro do deck especificado.
    """
    # Remove a tag [sound:...] para comparar o texto puro
    texto_puro = re.sub(r'\[sound:.*?\]', '', texto_frente).strip()
    # Escapa aspas para a busca do Anki
    texto_escapado = texto_puro.replace('"', '\\"')
    # Busca em todo o deck (qualquer modelo) – modo mais seguro
    query = f'deck:"{deck_nome}" "{texto_escapado}"'
    try:
        ids = anki_call("findNotes", query=query)
        return len(ids) > 0
    except Exception:
        # Se falhar, assume que não existe (evita travamento)
        return False

def perguntar_duplicata(frase_ingles):
    """Pergunta com timeout de 10s, tecla única (S/N/Enter). Retorna True se 'S'."""
    print(f"\n⚠️ FRASE DUPLICADA: {frase_ingles[:70]}...")
    print("Deseja adicionar mesmo assim? (S = sim, N = não, Enter = não após 10s)")
    inicio = time.time()
    while time.time() - inicio < 10:
        if msvcrt.kbhit():
            tecla = msvcrt.getch().decode('utf-8').lower()
            if tecla == 's':
                print(" ✅ Adicionando...")
                return True
            elif tecla == 'n' or tecla == '\r':
                print(" ❌ Ignorando duplicata.")
                return False
        time.sleep(0.1)
    print(" ⏱️ Timeout: ignorando duplicata.")
    return False

def criar_ou_atualizar_modelo():
    """Cria o modelo fixo se não existir, ou atualiza os templates se estiverem desatualizados."""
    modelos = anki_call("modelNames")
    if MODELO_NOME not in modelos:
        # Cria novo modelo
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
        # Verifica se o template do verso está correto (atualização)
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

def criar_cartoes_anki(deck_nome, pares, pasta_mp3):
    anki_call("createDeck", deck=deck_nome)
    print(f"✅ Deck '{deck_nome}' pronto.")
    
    # Mapeia áudios disponíveis
    mp3s_info = {sanitizar_nome(f): f for f in os.listdir(pasta_mp3) if f.endswith('.mp3')}
    total_adicionados = 0
    total_duplicados = 0
    
    for ingles, portugues in pares:
        try:
            frase_chave = sanitizar_nome(ingles[:50])
            mp3_encontrado = None
            
            # Busca automática
            for chave, nome_mp3 in mp3s_info.items():
                if frase_chave.startswith(chave) or chave.startswith(frase_chave):
                    mp3_encontrado = nome_mp3
                    break
            
            # Se não achou, pergunta manualmente (janela Explorer)
            if not mp3_encontrado:
                print(f"\n⚠️ Áudio não encontrado para: {ingles[:60]}...")
                caminho_audio = selecionar_audio_manual(ingles)
                if caminho_audio:
                    nome_arquivo = os.path.basename(caminho_audio)
                    # Copia para pasta de origem (para reutilização futura)
                    destino_origem = Path(pasta_mp3) / nome_arquivo
                    if not destino_origem.exists():
                        shutil.copy2(caminho_audio, destino_origem)
                        print(f"📀 Áudio copiado para pasta de origem: {nome_arquivo}")
                    # Copia para mídia do Anki
                    destino_media = PASTA_MIDIA_ANKI / nome_arquivo
                    if not destino_media.exists():
                        shutil.copy2(caminho_audio, destino_media)
                        print(f"📀 Áudio copiado para mídia: {nome_arquivo}")
                    mp3_encontrado = nome_arquivo
                    mp3s_info[sanitizar_nome(nome_arquivo)] = nome_arquivo
                else:
                    print(f"⏭️ Áudio ignorado para: {ingles[:40]}...")
            
            if mp3_encontrado:
                frente = f"{ingles} [sound:{mp3_encontrado}]"
                print(f"🔊 Áudio vinculado: {mp3_encontrado}")
            else:
                frente = ingles
                print(f"⚠️ Sem áudio, cartão será criado sem som.")
            
            # Verifica duplicata (busca apenas no deck)
            if nota_existe(deck_nome, frente):
                total_duplicados += 1
                if not perguntar_duplicata(ingles):
                    continue
            
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
        except KeyboardInterrupt:
            print("\n🛑 Interrompido pelo usuário. Finalizando...")
            return total_adicionados
    print(f"\n📊 Resumo: {total_adicionados} cartões adicionados, {total_duplicados} duplicados evitados.")
    return total_adicionados

def abrir_editor_texto():
    """Editor simples com negrito (Ctrl+B) e cores."""
    resultado = {"texto": None, "cancelado": False}
    janela = tk.Tk()
    janela.title("Ankipy - Editor de Texto")
    janela.geometry("800x600")
    janela.configure(bg='#2b2b2b')
    
    # Toolbar
    toolbar = tk.Frame(janela, bg='#3c3f41', height=35)
    toolbar.pack(fill=tk.X)
    
    def aplicar_negrito():
        try:
            selecionado = text_area.tag_ranges("sel")
            if selecionado:
                if "bold" in text_area.tag_names("sel.first"):
                    text_area.tag_remove("bold", "sel.first", "sel.last")
                else:
                    text_area.tag_add("bold", "sel.first", "sel.last")
        except: pass
    
    def aplicar_cor():
        try:
            selecionado = text_area.tag_ranges("sel")
            if selecionado:
                cor = colorchooser.askcolor(title="Selecione a cor do texto")[1]
                if cor:
                    tag_name = f"color_{cor.replace('#', '')}"
                    text_area.tag_configure(tag_name, foreground=cor)
                    text_area.tag_add(tag_name, "sel.first", "sel.last")
        except: pass
    
    btn_bold = tk.Button(toolbar, text="B", font=("Arial", 10, "bold"), width=4, command=aplicar_negrito)
    btn_bold.pack(side=tk.LEFT, padx=2, pady=2)
    btn_cor = tk.Button(toolbar, text="🎨 Cor", font=("Arial", 9), command=aplicar_cor)
    btn_cor.pack(side=tk.LEFT, padx=2, pady=2)
    
    # Área de texto com scroll
    text_area = scrolledtext.ScrolledText(janela, wrap=tk.WORD, font=("Arial", 12),
                                          bg='#1e1e1e', fg='#d4d4d4',
                                          insertbackground='white',
                                          selectbackground='#264f78')
    text_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    text_area.tag_configure("bold", font=("Arial", 12, "bold"))
    
    def atalho_bold(event=None):
        aplicar_negrito()
    text_area.bind("<Control-b>", atalho_bold)
    text_area.bind("<Control-B>", atalho_bold)
    text_area.focus_set()
    
    def salvar():
        texto = text_area.get("1.0", tk.END).rstrip("\n")
        if not texto:
            messagebox.showwarning("Aviso", "Nenhum texto foi inserido.")
            return
        resultado["texto"] = texto
        janela.destroy()
    
    def cancelar():
        resultado["cancelado"] = True
        janela.destroy()
    
    frame_botoes = tk.Frame(janela, bg='#2b2b2b')
    frame_botoes.pack(fill=tk.X, pady=5)
    btn_salvar = tk.Button(frame_botoes, text="Salvar e Importar", command=salvar,
                           bg='#4cae4c', fg='white', padx=10, font=("Arial", 10, "bold"))
    btn_salvar.pack(side=tk.RIGHT, padx=10)
    btn_cancelar = tk.Button(frame_botoes, text="Cancelar", command=cancelar,
                             bg='#d9534f', fg='white', padx=10)
    btn_cancelar.pack(side=tk.RIGHT, padx=5)
    janela.protocol("WM_DELETE_WINDOW", cancelar)
    janela.mainloop()
    
    if resultado["cancelado"]:
        return None
    return resultado["texto"]

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
    
    # Encontra ou cria o arquivo .txt
    txts = list(Path(pasta).glob("*.txt"))
    if not txts:
        print("❌ Nenhum arquivo .txt encontrado na pasta.")
        resposta = input("Deseja abrir o editor de texto para criar um? (S/N): ").strip().lower()
        if resposta == 's':
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
    
    # Garante o modelo fixo
    criar_ou_atualizar_modelo()
    
    # Cria cartões (já usando o modelo fixo)
    total = criar_cartoes_anki(deck, pares, pasta)
    print(f"\n✨ Importação concluída! {total} cartões adicionados ao deck '{deck}'.")

if __name__ == "__main__":
    main()