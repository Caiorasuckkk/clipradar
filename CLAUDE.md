# ClipRadar / DarkFlow — guia do agente

Pipeline local de produção de vídeo short-form: descobre tendências, valida vídeos,
transcreve (Whisper), corta clipes e gera vídeos com IA (persona-creator). Backend
FastAPI (Python) + app de revisão em Flutter. Tudo roda local; sem deploy em produção.

## Como trabalhar comigo (prioridade máxima)

- **Seja honesto, nunca puxa-saco.** Não concorde com uma ideia só porque eu propus.
  Antes de implementar algo que eu pedi, se houver um problema real, diga primeiro.
- **Pensamento crítico ativo.** Quando eu propuser uma abordagem, apresente o caso mais
  forte CONTRA ela antes de seguir. Aponte trade-offs, riscos e premissas frágeis.
- **Me dê insights.** Se você notar algo melhor, mais simples ou um bug latente que eu
  não pedi pra olhar, fale — mesmo que fuja do escopo imediato.
- **Não seja preguiçoso.** Resolva a causa-raiz, não o sintoma. Nada de gambiarra pra
  "fazer passar". Se a solução certa dá mais trabalho, me diga e faça a certa.
- **Quando não souber, diga "não sei".** Nunca invente fatos, APIs, nomes de função ou
  resultados. Mostre evidência (saída de comando/teste) em vez de afirmar que funcionou.
- **Direto e conciso.** Sem elogios, sem repetir meu pedido de volta, sem encheção.
- Responda em português.

## Comandos (backend, a partir de `backend/`)

A venv ativa é `.ven` (não `.venv`). Sempre use o python da venv:

- API local: `.\.ven\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000`
- Scanner de tendências: `python -m app.jobs.run_scanner`
- Processar fila (download + Whisper + clipes): `python -m app.jobs.process_queue`
- Limpar fila: `python -m app.jobs.cleanup_queue`
- Revisar clipe: `python -m app.jobs.review_clip --video-id <id> --rank 1 --status approved --rating 4 --reason "..."`
- Listar revisões pendentes: `python -m app.jobs.list_pending_reviews`
- `.env` a partir de `.env.example` (`Copy-Item .env.example .env`); chaves: `YOUTUBE_API_KEY(S)`, `OPENAI_API_KEY`, `WHISPER_MODEL_SIZE`.

## Comandos (app Flutter, a partir de `review_app/`)

- Rodar: `flutter run`
- Analisar: `flutter analyze`   |   Testes: `flutter test`
- O app fala com a API em `http://localhost:8000`.

## Estrutura

- `backend/app/api/` — routers FastAPI (`generation_api`, `review_api`, `posts_api`, `analytics_api`, `ops_api`).
- `backend/app/services/` — lógica de negócio, incluindo o pipeline de geração (`generation_*`).
- `backend/app/jobs/` — entrypoints CLI (`python -m app.jobs.<nome>`).
- `backend/app/scanners/` — coleta de tendências (Google Trends RSS, YouTube, RSS).
- `backend/app/storage/` — dados/artefatos locais (relatórios, fila, clipes, música em `generation/music/`).
- `review_app/lib/screens/` — telas Flutter (`generation_*`, `home_screen`, etc.).

## Convenções

- Python: `from __future__ import annotations`, type hints, imports absolutos `from app...`.
  Mantenha o estilo do arquivo vizinho; não reformate código não relacionado.
- Providers são plugáveis: LLM (OpenAI primário, Gemini fallback), voz/TTS (edge-tts/OpenAI/ElevenLabs
  por prefixo de voz), com fallback gracioso. Ao adicionar, preserve esse padrão.
- Whisper roda **local**; OpenAI/Gemini só para texto e (opcional) metadados/TTS.
- Não comite segredos. `.env` é local; chaves de API nunca vão pro git.

## Fluxo de trabalho

- Mudança pequena e óbvia (typo, log, rename): faça direto.
- Mudança multi-arquivo ou em código que não conheço: proponha um plano curto antes.
- Requisito ambíguo: pergunte **uma** coisa objetiva antes de codar, não chute.
- Depois de mexer: rode o job/endpoint afetado ou `flutter analyze` e mostre a saída real.
- Não há suíte de testes do projeto ainda; valide rodando o caminho de fato.
- Git: não faça commit/push a menos que eu peça. Branch a partir de `main`; mensagens descritivas.

<!-- Manter este arquivo abaixo de ~150 linhas. Cortar tudo que o Claude descobriria lendo o código.
     Regras determinísticas (lint/format obrigatório) vão em hooks, não aqui. -->
