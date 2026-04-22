#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ankipy - Importador de frases com áudio para o Anki
- Lê configuração de config.txt (pasta de mídia)
- Cria modelo de nota separado para cada importação
- Template: frente (inglês + áudio), verso (tradução + frente)
"""

import os
import re
import json
import shutil
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

ANKI_CONNECT_URL = "http://localhost:8765"
CONFIG_FILE = Path(__file__).parent / "config.txt"

def ler_pasta_media():
    """Lê o caminho da collection.media do arquivo config.txt."""
    if not CONFIG_FILE.exists():
        # Cria arquivo de exemplo
        exemplo = r"C:\Users\SeuUsuario\AppData\Roaming\Anki2\SeuPerfil\collection.media"
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            f.write("# Cole abaixo o caminho completo da pasta collection.media do Anki\n")
            f.write("# Como encontrar: Abra o Anki > Ferramentas > Gerenciar Arquivos de Mídia > Abrir Pasta de Mídia\n")
            f.write(f"{exemplo}\n")
        print(f"❌ Arquivo config.txt não encontrado. Um modelo foi criado em {CONFIG_FILE}")
        print("Edite o arquivo com o caminho correto e execute o script novamente.")
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
    if not PASTA_MIDIA_ANKI.exists():
        raise Exception(f"Pasta de mídia não encontrada: {PASTA_MIDIA_ANKI}")
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

def criar_modelo_unico(deck_nome, modelo_nome):
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

def criar_cartoes_anki(deck_nome, modelo_nome, pares, pasta_mp3):
    anki_call("createDeck", deck=deck_nome)
    print(f"✅ Deck '{deck_nome}' pronto.")
    
    mp3s_info = {sanitizar_nome(f): f for f in os.listdir(pasta_mp3) if f.endswith('.mp3')}
    total = 0
    for ingles, portugues in pares:
        frase_chave = sanitizar_nome(ingles[:50])
        mp3_encontrado = None
        for chave, nome_mp3 in mp3s_info.items():
            if frase_chave.startswith(chave) or chave.startswith(frase_chave):
                mp3_encontrado = nome_mp3
                break
        if mp3_encontrado:
            frente = f"{ingles} [sound:{mp3_encontrado}]"
            print(f"🔊 Áudio: {mp3_encontrado}")
        else:
            frente = ingles
            print(f"⚠️ Sem áudio: {ingles[:40]}...")
        nota = {
            "deckName": deck_nome,
            "modelName": modelo_nome,
            "fields": {"Frente": frente, "Verso": portugues},
            "tags": ["importado_auto"],
            "options": {"allowDuplicate": False}
        }
        anki_call("addNote", note=nota)
        total += 1
    return total

def main():
    print("=== Ankipy - Importador Automático para Anki ===\n")
    pasta = input("📂 Pasta com .txt e MP3s: ").strip()
    if not Path(pasta).exists():
        print("❌ Pasta não encontrada.")
        return
    deck = input("📚 Nome do deck (ex: 'Inglês::Frases'): ").strip()
    if not deck:
        print("❌ Deck inválido.")
        return

    txts = list(Path(pasta).glob("*.txt"))
    if not txts:
        print("❌ Nenhum arquivo .txt encontrado.")
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
        print(f"❌ Erro: {e}\nAbra o Anki e instale AnkiConnect (código 2055492159).")
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    modelo_nome = f"Ankipy_{timestamp}"
    print(f"🆕 Modelo: {modelo_nome}")

    criar_modelo_unico(deck, modelo_nome)
    total = criar_cartoes_anki(deck, modelo_nome, pares, pasta)
    print(f"\n🎉 {total} cartões adicionados ao deck '{deck}'.")

if __name__ == "__main__":
    main()