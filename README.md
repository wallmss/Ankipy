# 🃏 Ankipy – Importador de Frases com Áudio

Automatize a criação de flashcards no Anki a partir de um arquivo de texto e arquivos MP3.
Para o curso do Mairo Vergara de inglês. Mas sinsta-se livre para usar o código de exemplo.

## ✨ Funcionalidades

- Lê um arquivo `.txt` com frases alternadas (inglês/português)
- Associa automaticamente cada frase em inglês a um MP3 (baseado no início da frase)
- Copia os áudios para a pasta `collection.media` do Anki
- Cria um **deck** e um **modelo de nota novo** (não altera seus modelos existentes)
- Utiliza o **AnkiConnect** para importar diretamente – sem arquivos CSV intermediários
- Template personalizado: frente mostra inglês + áudio, verso mostra a frente + tradução

## 📋 Pré‑requisitos

- [Anki](https://apps.ankiweb.net/) instalado
- Complemento [AnkiConnect](https://ankiweb.net/shared/info/2055492159) (código `2055492159`)
- Python 3.8 ou superior

## 🚀 Como usar

### 1. Instalar dependências

```bash
pip install -r requirements.txt
```

### 2. Configurar o caminho da pasta de mídia do Anki
Edite o arquivo config.txt (criado automaticamente na primeira execução) e cole o caminho completo da sua pasta collection.media.

Como encontrar essa pasta?

Abra o Anki

Clique em Ferramentas → Gerenciar Arquivos de Mídia

Clique em Abrir Pasta de Mídia

Copie o endereço que aparece na barra de endereços

Exemplo (Windows):

```text
C:\Users\SeuNome\AppData\Roaming\Anki2\Usuário 1\collection.media
```

### 3. Preparar os arquivos
Organize seus arquivos em uma pasta:

Um arquivo .txt com frases no formato:

```text
Frase em inglês linha 1
Tradução em português linha 1
Frase em inglês linha 2
Tradução em português linha 2
...
```

(linhas em branco são ignoradas)

Arquivos MP3 com nomes como 33 he works hard.mp3, 34 but even so.mp3 etc.
O script ignora o número inicial e compara o restante com o início da frase em inglês.

### 4. Executar
primeiro abra o seu Anki no computador, depois no cmd na pasta do codigo execute:

```bash
python importar_anki.py
```

Responda:

- Caminho da pasta com .txt e MP3s
- Nome do deck

Pronto! Os cartões aparecerão automaticamente no Anki.

⚙️ Exemplo de arquivo de entrada (exemplo.txt)

```text
Jack looked up at the pale blue sky,
Jack olhou para o céu azul claro,

and he said, “I came from Heaven.”
e ele disse, “eu vim do céu”.
```

🛠️ Personalização
O modelo de nota criado tem o nome AnkiImporter_YYYYMMDD_HHMMSS para não conflitar.

O template do verso é: {{FrontSide}}<hr id=answer>{{Verso}} (mostra a frente novamente).

Se quiser outro template, edite a função criar_modelo_unico().

❓ Perguntas frequentes
E se o áudio não tocar?
Verifique se o arquivo MP3 foi copiado para a pasta collection.media (o script já faz isso) e se o nome do arquivo (sem número) é o início da frase em inglês.

Posso importar para um deck existente?
Sim, o deck pode já existir. As cartas serão adicionadas a ele.

O que acontece se eu rodar o script duas vezes com o mesmo deck?
Será criado um novo modelo (com timestamp diferente) e as cartas serão adicionadas ao mesmo deck, sem duplicatas (a menos que a frase seja exatamente igual).

Preciso instalar o AnkiConnect?
Sim. Instale no Anki: Ferramentas → Complementos → Obter Complementos… → código 2055492159.

📄 Licença
MIT – use à vontade.

🙏 Agradecimentos
Ao Anki e ao AnkiConnect.