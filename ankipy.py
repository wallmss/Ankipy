#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ankipy - Importador automático de frases com áudio para Anki
"""

import os
import re
import json
import shutil
import urllib.request
import urllib.error
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
from datetime import datetime
import msvcrt
import time

ANKI_CONNECT_URL = "http://localhost:8765"
CONFIG_FILE = Path(__file__).parent / "config.txt"
ULTIMA_CONFIG = Path(__file__).parent / "ultima_config.txt"

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
    root = tk.Tk()
    root.withdraw()
    msg = f"Áudio não encontrado automaticamente.\n\nFrase: {frase_ingles[:80]}...\n\nSelecione o arquivo MP3 correspondente (ou clique em Cancelar para pular)."
    resposta = messagebox.askokcancel("Áudio faltando", msg)
    if not resposta:
        return None
    arquivo = filedialog.askopenfilename(
        title="Selecione o arquivo MP3",
        filetypes=[("Arquivos MP3", "*.mp3")]
    )
    return arquivo if arquivo else None

def nota_existe(deck_nome, modelo_nome, frente_texto):
    """Verifica se já existe uma nota com o mesmo texto na frente (ignorando áudio)."""
    # Remove a tag [sound:...] e caracteres problemáticos
    texto_puro = re.sub(r'\[sound:.*?\]', '', frente_texto).strip()
    # Escapa aspas duplas para a busca do Anki
    texto_escapado = texto_puro.replace('"', '\\"')
    # Monta a query com escape adequado
    query = f'deck:"{deck_nome}" model:{modelo_nome} "Frente:{texto_escapado}"'
    try:
        ids = anki_call("findNotes", query=query)
        return len(ids) > 0
    except Exception as e:
        # Se a busca falhar (ex: caractere muito especial), assume que não existe
        # e continua, mas avisa o usuário
        print(f"⚠️ Erro ao verificar duplicata (ignorando): {e}")
        return False
    
def perguntar_duplicata(frase_ingles):
    """Pergunta ao usuário se deseja adicionar mesmo uma frase duplicada.
    Retorna True se apertar 'S' ou 's', False se apertar 'N' ou 'n' ou Enter, ou timeout de 10s.
    """
    print(f"\n⚠️ FRASE DUPLICADA: {frase_ingles[:70]}...")
    print("Deseja adicionar mesmo assim? (S = sim, N = não, Enter = não após 10s)")
    
    inicio = time.time()
    while time.time() - inicio < 10:
        if msvcrt.kbhit():
            tecla = msvcrt.getch().decode('utf-8').lower()
            if tecla == 's':
                print(" ✅ Adicionando...")
                return True
            elif tecla == 'n' or tecla == '\r':  # Enter é '\r' no Windows
                print(" ❌ Ignorando duplicata.")
                return False
        time.sleep(0.1)
    print(" ⏱️ Timeout: ignorando duplicata.")
    return False

def criar_cartoes_anki(deck_nome, modelo_nome, pares, pasta_mp3):
    anki_call("createDeck", deck=deck_nome)
    print(f"✅ Deck '{deck_nome}' pronto.")
    
    mp3s_info = {sanitizar_nome(f): f for f in os.listdir(pasta_mp3) if f.endswith('.mp3')}
    total_adicionados = 0
    total_duplicados = 0
    
    for ingles, portugues in pares:
        frase_chave = sanitizar_nome(ingles[:50])
        mp3_encontrado = None
        
        # Procura áudio automaticamente
        for chave, nome_mp3 in mp3s_info.items():
            if frase_chave.startswith(chave) or chave.startswith(frase_chave):
                mp3_encontrado = nome_mp3
                break
        
        # Se não achou, manual
        if not mp3_encontrado:
            print(f"\n⚠️ Áudio não encontrado para: {ingles[:60]}...")
            caminho_audio = selecionar_audio_manual(ingles)
            if caminho_audio:
                nome_arquivo = os.path.basename(caminho_audio)
                destino_origem = Path(pasta_mp3) / nome_arquivo
                if not destino_origem.exists():
                    shutil.copy2(caminho_audio, destino_origem)
                    print(f"📀 Áudio copiado para pasta de origem: {nome_arquivo}")
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
        
        # Verifica duplicata
        if nota_existe(deck_nome, modelo_nome, frente):
            total_duplicados += 1
            if not perguntar_duplicata(ingles):
                continue
        
        nota = {
            "deckName": deck_nome,
            "modelName": modelo_nome,
            "fields": {"Frente": frente, "Verso": portugues},
            "tags": ["importado_auto"],
            "options": {"allowDuplicate": False}
        }
        anki_call("addNote", note=nota)
        total_adicionados += 1
        print(f"✅ Cartão adicionado: {ingles[:50]}...")
    
    print(f"\n📊 Resumo: {total_adicionados} cartões adicionados, {total_duplicados} duplicados encontrados (alguns podem ter sido adicionados manualmente).")
    return total_adicionados

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
    
    txts = list(Path(pasta).glob("*.txt"))
    if not txts:
        print("❌ Nenhum arquivo .txt encontrado na pasta.")
        return
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
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    modelo_nome = f"Ankipy_{timestamp}"
    print(f"🆕 Modelo: {modelo_nome}")
    
    modelo = {
        "modelName": modelo_nome,
        "inOrderFields": ["Frente", "Verso"],
        "css": ".card { font-family: arial; font-size: 20px; text-align: center; }",
        "cardTemplates": [{
            "Name": "Card 1",
            "Front": "{{Frente}}",
            "Back": "{{FrontSide}}\n<hr id=answer>\n{{Verso}}"
        }]
    }
    anki_call("createModel", **modelo)
    print(f"✅ Modelo '{modelo_nome}' criado.")
    
    criar_cartoes_anki(deck, modelo_nome, pares, pasta)
    print("\n✨ Importação concluída! Verifique seu deck no Anki.")

if __name__ == "__main__":
    main()