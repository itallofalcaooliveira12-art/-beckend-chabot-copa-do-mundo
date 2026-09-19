import json
import os
import re
from collections.abc import Generator
from typing import Any

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request
from flask_cors import CORS
from groq import Groq

load_dotenv()

app = Flask(__name__)

allowed_origins = [
    origin.strip()
    for origin in os.getenv("FRONTEND_ORIGINS", "*").split(",")
    if origin.strip()
]
CORS(app, resources={r"/api/*": {"origins": allowed_origins}})

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
MAX_HISTORY = int(os.getenv("MAX_HISTORY", "16"))
MAX_MESSAGE_CHARS = int(os.getenv("MAX_MESSAGE_CHARS", "4000"))

client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

SYSTEM_PROMPT = """
Você é o CopaBot, um especialista em Copas do Mundo, futebol e esportes diretamente relacionados.

ESCOPO:
- Copas do Mundo FIFA masculina e feminina, incluindo história, seleções, jogadores,
  técnicos, partidas, grupos, regulamentos, estádios, sedes, estatísticas e recordes.
- Futebol de clubes e seleções, competições nacionais e internacionais, tática,
  regras, arbitragem, transferências e história do futebol.
- Esportes relacionados podem ser respondidos quando a relação com futebol/Copa for clara.
- Perguntas esportivas sobre outros esportes também podem ser respondidas de forma factual.

FORA DO ESCOPO:
Não responda assuntos sem relação com futebol, Copas do Mundo ou esportes.
Se a pergunta estiver fora do escopo, diga de forma breve:
"Desculpa, mas isso está fora do meu escopo. Sou especializado em Copas do Mundo,
futebol e esportes."

REGRAS:
1. Nunca invente placares, datas, títulos, estatísticas ou acontecimentos.
2. Quando a pergunta depender de informação atual, deixe claro que seu conhecimento pode
   não refletir acontecimentos posteriores ao seu conhecimento disponível.
3. Responda em português do Brasil, salvo se o usuário pedir outro idioma.
4. Seja claro, objetivo e contextual. Use listas e tabelas em Markdown quando ajudarem.
5. Não transforme uma pergunta esportiva em uma resposta sobre assuntos não esportivos.
"""

# Termos deliberadamente amplos: o filtro local é uma primeira barreira, não um sistema
# semântico perfeito. O histórico permite perguntas de continuidade como "e ele?".
FOOTBALL_TERMS = {
    "futebol", "football", "soccer", "copa", "copas", "mundial", "mundiais",
    "fifa", "seleção", "selecoes", "seleção", "jogador", "jogadores", "técnico",
    "tecnico", "treinador", "gol", "gols", "golpe", "partida", "partidas", "jogo",
    "jogos", "placar", "campeão", "campeao", "vice", "grupo", "oitavas",
    "quartas", "semifinal", "final", "eliminatória", "eliminatorias", "classificação",
    "classificacao", "estádio", "estadio", "sede", "sedes", "arbitragem", "árbitro",
    "arbitro", "cartão", "cartao", "pênalti", "penalti", "impedimento", "escanteio",
    "falta", "titulos", "títulos", "troféu", "trofeu", "camisa", "zagueiro",
    "lateral", "volante", "meia", "atacante", "goleiro", "defesa", "ataque",
    "tática", "tatica", "formação", "formacao", "4-3-3", "4-4-2", "var", "var",
    "libertadores", "champions", "uefa", "conmebol", "premier league", "la liga",
    "brasileirão", "brasileirao", "serie a", "série a", "carioca", "paulista",
    "mercado da bola", "transferência", "transferencias", "transferência",
    "real madrid", "barcelona", "flamengo", "palmeiras", "corinthians",
    "santos", "são paulo", "sao paulo", "cruzeiro", "vasco", "botafogo",
    "manchester", "liverpool", "arsenal", "chelsea", "messi", "cristiano",
    "cr7", "neymar", "pelé", "pele", "mbappé", "mbappe", "vini", "vinicius",
    "ronaldo", "romário", "romario", "ronaldinho", "maradona", "zidane",
    "beckenbauer", "cafú", "cafu", "ronaldo fenômeno", "ronaldo fenomeno",
}

SPORT_TERMS = {
    "esporte", "esportes", "basquete", "basketball", "nba", "nfl", "fórmula 1",
    "formula 1", "f1", "tênis", "tenis", "vôlei", "volei", "olimpíadas",
    "olimpiadas", "atletismo", "boxe", "mma", "ufc", "beisebol", "baseball",
    "ciclismo", "natação", "natacao", "surfe", "surf", "skate", "handebol",
    "rugby", "críquete", "criquete", "motogp", "automobilismo",
}

FOLLOWUP_TERMS = {
    "ele", "ela", "eles", "elas", "esse", "essa", "isso", "isto", "aquele",
    "aquela", "qual", "quais", "quanto", "quantos", "quando", "onde", "porquê",
    "porque", "como", "e aí", "e ai", "também", "tambem", "sim", "não", "nao",
    "verdade", "entendi", "continua", "continue", "mais", "outro", "outra",
}


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def topic_allowed(message: str, history: list[dict[str, Any]]) -> bool:
    text = normalize(message)
    if any(term in text for term in FOOTBALL_TERMS | SPORT_TERMS):
        return True

    # Continuidade contextual: só é aceita se houver histórico recente que contenha
    # sinais claros de esporte. Isso permite "e ele?" sem abrir a porta para qualquer tema.
    if history and any(
        any(term in normalize(str(item.get("content", ""))) for term in FOOTBALL_TERMS | SPORT_TERMS)
        for item in history[-6:]
    ):
        words = set(re.findall(r"\b[\wÀ-ÿ-]+\b", text))
        if words & FOLLOWUP_TERMS or len(words) <= 8:
            return True

    return False


def clean_history(history: Any) -> list[dict[str, str]]:
    if not isinstance(history, list):
        return []
    cleaned = []
    for item in history[-MAX_HISTORY:]:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if role in {"user", "assistant"} and isinstance(content, str) and content.strip():
            cleaned.append({"role": role, "content": content[:MAX_MESSAGE_CHARS]})
    return cleaned


def refusal() -> str:
    return (
        "Desculpa, mas isso está fora do meu escopo. "
        "Sou especializado em Copas do Mundo, futebol e esportes."
    )


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "service": "copa-chatbot"})


@app.post("/api/chat")
def chat():
    if not client:
        return jsonify({"error": "GROQ_API_KEY não configurada no servidor."}), 500

    payload = request.get_json(silent=True) or {}
    message = payload.get("message", "")
    history = clean_history(payload.get("history", []))

    if not isinstance(message, str) or not message.strip():
        return jsonify({"error": "Mensagem inválida."}), 400

    message = message.strip()
    if len(message) > MAX_MESSAGE_CHARS:
        return jsonify({"error": f"A mensagem deve ter no máximo {MAX_MESSAGE_CHARS} caracteres."}), 400

    if not topic_allowed(message, history):
        return jsonify({"allowed": False, "reply": refusal()}), 200

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": message})

    try:
        completion = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            temperature=0.35,
            max_tokens=1200,
            stream=False,
        )
        reply = completion.choices[0].message.content or "Não consegui gerar uma resposta."
        return jsonify({"allowed": True, "reply": reply})
    except Exception as exc:
        app.logger.exception("Groq request failed")
        return jsonify({"error": "Falha ao consultar o modelo.", "detail": str(exc) if app.debug else None}), 502


@app.post("/api/chat/stream")
def chat_stream():
    if not client:
        return jsonify({"error": "GROQ_API_KEY não configurada no servidor."}), 500

    payload = request.get_json(silent=True) or {}
    message = payload.get("message", "")
    history = clean_history(payload.get("history", []))

    if not isinstance(message, str) or not message.strip():
        return jsonify({"error": "Mensagem inválida."}), 400

    message = message.strip()
    if len(message) > MAX_MESSAGE_CHARS:
        return jsonify({"error": f"A mensagem deve ter no máximo {MAX_MESSAGE_CHARS} caracteres."}), 400

    if not topic_allowed(message, history):
        def reject_stream() -> Generator[str, None, None]:
            yield f"data: {json.dumps({'type': 'done', 'reply': refusal(), 'allowed': False}, ensure_ascii=False)}\n\n"
        return Response(reject_stream(), mimetype="text/event-stream")

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": message})

    def generate() -> Generator[str, None, None]:
        try:
            stream = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                temperature=0.35,
                max_tokens=1200,
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if delta:
                    yield f"data: {json.dumps({'type': 'token', 'content': delta}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'allowed': True}, ensure_ascii=False)}\n\n"
        except Exception:
            app.logger.exception("Groq streaming request failed")
            yield f"data: {json.dumps({'type': 'error', 'error': 'Falha ao consultar o modelo.'}, ensure_ascii=False)}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True)
