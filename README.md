# ⚽ CopaBot — Chatbot de Copas do Mundo, Futebol e Esportes

Aplicação full-stack com:

- Frontend: HTML + CSS + JavaScript vanilla.
- Backend: Python + Flask.
- IA: Groq.
- Gerenciamento Python: uv.
- Frontend preparado para Netlify.
- Backend preparado para Render.
- Chave Groq somente no backend.
- Filtro local de escopo executado antes da chamada à IA.
- Histórico local no navegador.
- Respostas via streaming SSE.

## 1. Estrutura

```text
copa-chatbot/
├── backend/
│   ├── app.py
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── .env.example
│   ├── .python-version
│   └── render.yaml
├── frontend/
│   ├── index.html
│   ├── style.css
│   ├── app.js
│   └── netlify.toml
├── .gitignore
└── README.md
```

## 2. Rodando localmente

### Backend

Entre na pasta:

```bash
cd backend
```

Instale/sincronize as dependências:

```bash
uv sync
```

Crie `.env` a partir de `.env.example` e informe sua chave:

```env
GROQ_API_KEY=sua_chave
GROQ_MODEL=llama-3.3-70b-versatile
FRONTEND_ORIGINS=http://localhost:5500
```

Inicie:

```bash
uv run python app.py
```

A API ficará em:

```text
http://localhost:5000
```

### Frontend

O frontend não deve ser aberto via `file://` em um cenário real. Rode um servidor
estático dentro da pasta `frontend`:

```bash
cd frontend
python -m http.server 5500
```

Abra:

```text
http://localhost:5500
```

Se o backend estiver em outro endereço, no console do navegador execute:

```js
localStorage.setItem("copabot_api_url", "https://SEU-BACKEND.onrender.com");
location.reload();
```

## 3. Filtro de escopo

A validação acontece no Flask antes da chamada ao Groq.

O backend procura sinais de futebol, Copas e esportes. Perguntas fora do escopo
recebem uma resposta de recusa sem consumir uma chamada ao modelo.

Perguntas de continuidade, como "e ele?" ou "quantos títulos?", podem ser aceitas
quando existe histórico recente claramente relacionado a esporte.

Este filtro é propositalmente conservador e baseado em regras. Para uma aplicação
maior, pode ser substituído ou complementado por um classificador próprio.

## 4. Segurança

Nunca coloque `GROQ_API_KEY` no JavaScript, HTML ou variáveis públicas do Netlify.

A chave deve existir somente como variável de ambiente no backend.

O frontend conhece apenas a URL pública da API.

## 5. Deploy no Render

> Observação: o ambiente desta entrega não possui acesso à internet para baixar os pacotes do PyPI, portanto o `uv.lock` não foi gerado automaticamente aqui. Antes do primeiro deploy, execute `uv lock` dentro de `backend` e faça commit do `backend/uv.lock`. O Render exige o `uv.lock` quando o build usa `uv sync --frozen`.

1. Suba o projeto para GitHub.
2. No Render, crie um Web Service apontando para o repositório.
3. Use `backend` como Root Directory.
4. Build Command:

```bash
uv sync --frozen
```

5. Start Command:

```bash
uv run gunicorn --bind 0.0.0.0:$PORT app:app
```

6. Configure:
   - `GROQ_API_KEY`
   - `GROQ_MODEL=llama-3.3-70b-versatile`
   - `FRONTEND_ORIGINS=https://SEU-SITE.netlify.app`
   - `PYTHON_VERSION=3.13.5`

Depois do deploy, teste:

```text
https://SEU-BACKEND.onrender.com/api/health
```

Deve retornar JSON com `status: ok`.

## 6. Deploy no Netlify

1. Crie um novo site no Netlify conectado ao GitHub.
2. Selecione a pasta `frontend` como diretório publicado, ou configure o publish
   directory conforme a interface do Netlify.
3. Não coloque `GROQ_API_KEY` no Netlify.
4. Após descobrir a URL do Render, configure no navegador ou altere a constante
   `API_URL` do frontend para a URL pública do backend.

Para produção, a opção mais limpa é definir a URL do backend diretamente no frontend:

```js
const API_URL = "https://SEU-BACKEND.onrender.com";
```

## 7. CORS

No Render:

```env
FRONTEND_ORIGINS=https://SEU-SITE.netlify.app
```

Para mais de um domínio:

```env
FRONTEND_ORIGINS=https://SEU-SITE.netlify.app,https://www.seudominio.com
```

Não use `*` em produção quando você já souber o domínio do frontend.

## 8. Observações de produção

- O histórico atual é localStorage; não existe conta/login nem banco de dados.
- Para histórico sincronizado entre dispositivos, adicione autenticação + banco.
- Para proteção contra abuso, adicione rate limiting, autenticação e/ou CAPTCHA.
- O streaming usa Server-Sent Events sobre HTTP.
- Em produção, use HTTPS.
- Nunca registre a chave Groq nos logs.

## 9. Teste rápido da API

```bash
curl -X POST http://localhost:5000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Quem tem mais títulos de Copa do Mundo?","history":[]}'
```

Teste fora do escopo:

```bash
curl -X POST http://localhost:5000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Me ajude com uma receita de bolo","history":[]}'
```
