<img src="https://raw.githubusercontent.com/wallmss/Ankipy/main/ankipy.png" width="80" align="left">

# 🃏 AnkiPy

### Importador automático de frases com áudio para o [Anki](https://apps.ankiweb.net/)

[![Licença MIT](https://img.shields.io/badge/Licença-MIT-blue.svg)](LICENSE)
[![Versão](https://img.shields.io/github/v/release/wallmss/Ankipy)](https://github.com/wallmss/Ankipy/releases)
[![Windows](https://img.shields.io/badge/Windows-10%2B-0078D6)](https://microsoft.com)

**AnkiPy** transforma automaticamente um arquivo de texto (.txt) com frases em inglês e suas traduções em **flashcards** no Anki, com áudio incluso.  
Ideal para quem está fazendo o **[Curso de Inglês do Mairo Vergara](https://mairovergara.com)** ou qualquer outro estudo de idiomas.

> ✅ **Versão 3.0 – Apenas um executável!**  
> Nenhum arquivo extra, nenhuma instalação de Python. Baixe, configure uma única vez e importe dezenas de cartões em segundos.

---

## 🚀 Como usar (para quem não programa)

### 1️⃣ Baixe o executável
- Acesse a [página de Releases](https://github.com/wallmss/Ankipy/releases)
- Baixe o arquivo `AnkiPy.exe` da versão mais recente
- Coloque‑o em qualquer pasta do seu computador (por exemplo, `C:\AnkiPy`)

### 2️⃣ Instale o complemento AnkiConnect no Anki
O AnkiPy se comunica com o Anki através do complemento **AnkiConnect**. Você precisa instalá‑lo.

1. Abra o Anki
2. Vá em **Ferramentas → Complementos → Obter Complementos…**
3. Digite o código **`2055492159`** e clique em OK
4. Reinicie o Anki (feche e abra novamente)

> ⚠️ O Anki **precisa estar aberto** enquanto o AnkiPy estiver rodando.

### 3️⃣ Configure a pasta `collection.media` do Anki
O AnkiPy precisa saber onde o Anki guarda os arquivos de mídia (MP3, imagens).  
Siga os passos:

1. No Anki, vá em **Ferramentas → Gerenciar Arquivos de Mídia**
2. Clique no botão **Abrir Pasta de Mídia**
3. Uma janela do Explorador será aberta. **Copie o caminho completo** que aparece na barra de endereços  
   (exemplo: `C:\Users\SeuNome\AppData\Roaming\Anki2\Usuário 1\collection.media`)
4. Execute o `AnkiPy.exe`
5. Clique no botão **⚙️ Configurações**
6. Cole o caminho no campo “Pasta collection.media do Anki” e clique em **Salvar**

### 4️⃣ Importe suas frases
- Na janela principal, clique em **Procurar** e selecione a pasta onde estão seus arquivos `.txt` e `.mp3`
- Digite o nome do **deck** (pode ser um existente ou um novo, ex.: `Inglês::Frases`)
- Clique em **▶ Iniciar Importação**
- Se não houver nenhum arquivo `.txt`, o editor de texto integrado será aberto – cole ou digite as frases no formato:

```text
Frase em inglês linha 1
Tradução em português linha 1
Frase em inglês linha 2
Tradução em português linha 2
...
```


- O editor tem **formatação básica** (negrito, itálico, cor), **localizador (Ctrl+F)** com contador de ocorrências, **zoom** e botão **📎 Importar arquivo .txt**
- Ao salvar, a importação será feita automaticamente

### 5️⃣ Resultado
Os cartões serão criados no Anki com a **frente** mostrando a frase em inglês (com o botão de play para o áudio) e o **verso** mostrando a tradução, além da frente novamente (para relembrar).

## ⚠️ Limitação conhecida

O editor de texto do AnkiPy **não suporta desfazer (Ctrl+Z) para ações de formatação** (negrito, itálico, cor, etc.).  
Isso ocorre porque o widget `Text` do Tkinter (biblioteca usada para a interface) só registra alterações de texto (digitação, colagem, exclusão), mas não formatações.  
Portanto, ao aplicar negrito, não será possível desfazer apenas aquela formatação (o Ctrl+Z desfará a última ação de digitação/cola).  

**Recomendação:** use o botão "Limpar formatação" para remover estilos indesejados.  
É uma limitação técnica, pois o AnkiPy foi pensado como um aplicativo simples e leve, sem a complexidade de um editor full-featured.

---

## 🧰 Para quem programa (usar o código fonte)

Se você quiser modificar ou executar o código diretamente (sem o executável):

1. Clone o repositório:
   ```bash
   git clone https://github.com/wallmss/Ankipy.git
   cd Ankipy
   ```
2. Crie um ambiente virtual (recomendado):
   ```bash
   python -m venv venv
   .\venv\Scripts\activate   # Windows
   source venv/bin/activate   # Linux/Mac


3. Instale as dependências:
   ```bash
   pip install -r requirements.txt

4. Execute:
   ```bash
   python ankipy_gui.py
   
5. Instalar Pyinstaller para poder gerar o executável (com PyInstaller):
   ```bash
   pip install pyinstaller Pillow

6. Gerar executável:
   ```bash
   pyinstaller --onefile --windowed --add-data "ankipy.ico;." --add-data "ankipy.png;." --add-data "GitHub_Invertocat_Black.png;." --icon=ankipy.ico --name AnkiPy ankipy_gui.py
   
O arquivo será criado em dist/AnkiPy.exe.

🤔 Perguntas frequentes
1. O executável é seguro?
Sim, o código é 100% aberto. Alguns antivírus podem acusar falso‑positivo porque o PyInstaller empacota um interpretador Python – é normal.

2. Posso usar AnkiPy no Linux/Mac?
O código Python é multiplataforma, mas o executável é apenas para Windows. No Linux/Mac, use o código fonte diretamente.

3. Preciso instalar o Python para rodar o .exe?
Não. O executável já contém tudo o que é necessário.

4. Onde ficam as configurações salvas?
No Registro do Windows, em HKEY_CURRENT_USER\Software\Ankipy. Você pode apagar essa chave para resetar.

5. Como faço para atualizar o programa?
Baixe o novo .exe da última release e substitua o antigo. Suas configurações continuam salvas.

📜 Licença
MIT – use, modifique e distribua livremente, mantendo os créditos.

👤 Créditos
Desenvolvido por @wallmss
Projetado para facilitar o estudo de idiomas com o Curso do Mairo Vergara.

🔗 Site oficial do curso

🤝 Contribuindo
Sugestões, relatórios de bug e pull requests são muito bem‑vindos!
Abra uma issue ou um pull request.

📹 Vídeos tutoriais (em breve)
Em breve serão adicionados GIFs e vídeos curtos mostrando cada passo. Por enquanto, siga as instruções escritas acima – é bem simples!
