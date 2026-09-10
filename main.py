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
    
    # Headers completos para evitar bloqueio do servidor na nuvem
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"
    }

    # 1. Cotação do Dólar
    if "dolar" in termo_lower or "dólar" in termo_lower:
        try:
            async with httpx.AsyncClient(timeout=8.0, headers=headers, follow_redirects=True) as client:
                res = await client.get("https://economia.awesomeapi.com.br/last/USD-BRL")
                if res.status_code == 200:
                    dados = res.json().get("USDBRL", {})
                    resultados.append({
                        "titulo": "💵 Cotação Comercial do Dólar (USD/BRL)",
                        "detalhe": f"Valor Atual: R$ {dados.get('bid', 'N/A')} | Máxima: R$ {dados.get('high', 'N/A')} | Mínima: R$ {dados.get('low', 'N/A')}"
                    })
        except Exception as e:
            print(f"Erro ao buscar dólar: {e}")

    # 2. Busca Wikipédia (com variações de termo e suporte a nuvem)
    variacoes_termo = [termo, termo.capitalize(), termo.title()]
    if termo_lower.endswith("s") and len(termo) > 3:
        variacoes_termo.append(termo[:-1])

    for t in variacoes_termo:
        termo_encoded = urllib.parse.quote(t.replace(" ", "_"))
        try:
            async with httpx.AsyncClient(timeout=8.0, headers=headers, follow_redirects=True) as client:
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
        except Exception as e:
            print(f"Erro na Wikipédia ({t}): {e}")

    # 3. Busca de Contingência (Wikipédia Opensearch API)
    if len(resultados) == 0:
        try:
            async with httpx.AsyncClient(timeout=8.0, headers=headers, follow_redirects=True) as client:
                url_search = f"https://pt.wikipedia.org/w/api.php?action=opensearch&search={urllib.parse.quote(termo)}&limit=1&namespace=0&format=json"
                res_search = await client.get(url_search)
                if res_search.status_code == 200:
                    dados = res_search.json()
                    if len(dados) >= 3 and len(dados[2]) > 0 and dados[2][0]:
                        resultados.append({
                            "titulo": f"🔍 {dados[1][0]}",
                            "detalhe": dados[2][0]
                        })
        except Exception as e:
            print(f"Erro na busca opensearch: {e}")

    # 4. Fallback final
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