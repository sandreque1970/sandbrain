import os
import urllib.parse
from pathlib import Path
import uvicorn
import httpx
from fastapi import FastAPI, Request, Body
from fastapi.responses import FileResponse, JSONResponse

app = FastAPI(title="Sandbrain Core API")

BASE_DIR = Path(__file__).resolve().parent
HTML_PATH = BASE_DIR / "templates" / "index.html"

@app.get("/")
async def home():
    if HTML_PATH.exists():
        return FileResponse(HTML_PATH)
    return JSONResponse(status_code=404, content={"mensagem": "index.html não encontrado"})

@app.post("/api/pesquisar")
async def pesquisar(payload: dict = Body(...)):
    termo = payload.get("termo", "").strip()
    
    if not termo:
        return JSONResponse(status_code=400, content={"status": "erro", "mensagem": "Termo de pesquisa vazio."})

    resultados = []
    termo_lower = termo.lower()
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    # 1. Cotação do Dólar
    if "dolar" in termo_lower or "dólar" in termo_lower:
        try:
            async with httpx.AsyncClient(timeout=4.0, headers=headers) as client:
                res = await client.get("https://economia.awesomeapi.com.br/last/USD-BRL")
                if res.status_code == 200:
                    dados = res.json().get("USDBRL", {})
                    resultados.append({
                        "titulo": "💵 Cotação Comercial do Dólar (USD/BRL)",
                        "detalhe": f"Valor Atual: R$ {dados.get('bid', 'N/A')} | Máxima: R$ {dados.get('high', 'N/A')} | Mínima: R$ {dados.get('low', 'N/A')}"
                    })
        except Exception:
            pass

    # 2. Busca Wikipédia (com tratamento de singular/plural)
    variacoes_termo = [termo]
    if termo_lower.endswith("s") and len(termo) > 3:
        variacoes_termo.append(termo[:-1])  # Exemplo: "Carros" -> "Carro"

    for t in variacoes_termo:
        termo_encoded = urllib.parse.quote(t.replace(" ", "_"))
        try:
            async with httpx.AsyncClient(timeout=4.0, headers=headers) as client:
                url_wiki = f"https://pt.wikipedia.org/api/rest_v1/page/summary/{termo_encoded}"
                res_wiki = await client.get(url_wiki)
                if res_wiki.status_code == 200:
                    dados_wiki = res_wiki.json()
                    if dados_wiki.get("extract") and dados_wiki.get("type") != "disambiguation":
                        resultados.append({
                            "titulo": f"📖 {dados_wiki.get('title', t)}",
                            "detalhe": dados_wiki.get("extract")
                        })
                        break
        except Exception:
            pass

    # 3. Busca DuckDuckGo (Resumos e Tópicos Gerais da Web)
    if len(resultados) == 0 or (len(resultados) == 1 and ("dolar" in termo_lower or "dólar" in termo_lower)):
        try:
            async with httpx.AsyncClient(timeout=4.0, headers=headers) as client:
                url_ddg = f"https://api.duckduckgo.com/?q={urllib.parse.quote(termo)}&format=json&no_redirect=1&no_html=1&kl=br-pt"
                res_ddg = await client.get(url_ddg)
                if res_ddg.status_code == 200:
                    data_ddg = res_ddg.json()
                    if data_ddg.get("AbstractText"):
                        resultados.append({
                            "titulo": f"🔍 {data_ddg.get('Heading', termo)}",
                            "detalhe": data_ddg.get("AbstractText")
                        })
                    for topic in data_ddg.get("RelatedTopics", []):
                        if isinstance(topic, dict) and topic.get("Text"):
                            texto_topico = topic.get("Text")
                            if not any(texto_topico in r["detalhe"] for r in resultados):
                                resultados.append({
                                    "titulo": f"Informação sobre '{termo}'",
                                    "detalhe": texto_topico
                                })
                            if len(resultados) >= 3:
                                break
        except Exception:
            pass

    # 4. Fallback final caso nada seja localizado
    if len(resultados) == 0:
        resultados.append({
            "titulo": f"Pesquisa: '{termo}'",
            "detalhe": f"Nenhum resultado direto encontrado para '{termo}'."
        })

    return {
        "status": "sucesso",
        "termo": termo,
        "total": len(resultados),
        "resultados": resultados
    }

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)