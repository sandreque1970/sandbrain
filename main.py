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
    print(f"=== NOVA PESQUISA RECEBIDA: {termo} ===")
    
    if not termo:
        return JSONResponse(status_code=400, content={"status": "erro", "mensagem": "Termo de pesquisa vazio."})

    resultados = []
    termo_lower = termo.lower()
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }

    # 1. Cotação do Dólar
    if "dolar" in termo_lower or "dólar" in termo_lower:
        try:
            async with httpx.AsyncClient(timeout=5.0, headers=headers) as client:
                res = await client.get("https://economia.awesomeapi.com.br/last/USD-BRL")
                if res.status_code == 200:
                    dados = res.json().get("USDBRL", {})
                    resultados.append({
                        "titulo": "💵 Cotação Comercial do Dólar (USD/BRL)",
                        "detalhe": f"Valor Atual: R$ {dados.get('bid', 'N/A')} | Máxima: R$ {dados.get('high', 'N/A')} | Mínima: R$ {dados.get('low', 'N/A')}"
                    })
        except Exception as e:
            print(f"Erro no Dólar: {e}")

    # 2. Busca Wikipédia (Formatando Primeira Letra Maiúscula)
    termo_wiki = termo.capitalize()
    termo_encoded = urllib.parse.quote(termo_wiki.replace(" ", "_"))
    
    try:
        async with httpx.AsyncClient(timeout=5.0, headers=headers, follow_redirects=True) as client:
            url_wiki = f"https://pt.wikipedia.org/api/rest_v1/page/summary/{termo_encoded}"
            res_wiki = await client.get(url_wiki)
            print(f"Status Wikipédia: {res_wiki.status_code}")
            
            if res_wiki.status_code == 200:
                dados_wiki = res_wiki.json()
                if dados_wiki.get("extract") and dados_wiki.get("type") != "disambiguation":
                    resultados.append({
                        "titulo": f"📖 Wikipédia: {dados_wiki.get('title', termo)}",
                        "detalhe": dados_wiki.get("extract")
                    })
    except Exception as e:
        print(f"Erro na Wikipédia: {e}")

    # 3. DuckDuckGo Instant Answer API (Fallback Geral)
    if len(resultados) == 0:
        try:
            async with httpx.AsyncClient(timeout=5.0, headers=headers) as client:
                url_ddg = f"https://api.duckduckgo.com/?q={urllib.parse.quote(termo)}&format=json&no_html=1&kl=br-pt"
                res_ddg = await client.get(url_ddg)
                print(f"Status DuckDuckGo: {res_ddg.status_code}")
                
                if res_ddg.status_code == 200:
                    dados_ddg = res_ddg.json()
                    abstract = dados_ddg.get("AbstractText")
                    if abstract:
                        resultados.append({
                            "titulo": f"🔍 {dados_ddg.get('Heading', termo)}",
                            "detalhe": abstract
                        })
                    else:
                        # Tenta pegar dos tópicos relacionados
                        topics = dados_ddg.get("RelatedTopics", [])
                        for topic in topics:
                            if isinstance(topic, dict) and topic.get("Text"):
                                resultados.append({
                                    "titulo": f"🔍 Resumo: {termo}",
                                    "detalhe": topic.get("Text")
                                })
                                break
        except Exception as e:
            print(f"Erro no DuckDuckGo: {e}")

    # 4. Fallback final
    if len(resultados) == 0:
        resultados.append({
            "titulo": f"Pesquisa: '{termo}'",
            "detalhe": f"Nenhum resultado direto encontrado para '{termo}'."
        })

    print(f"Total de resultados encontrados: {len(resultados)}")

    return {
        "status": "sucesso",
        "termo": termo,
        "total": len(resultados),
        "resultados": resultados
    }

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)