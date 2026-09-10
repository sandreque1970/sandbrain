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
    
    # User-Agent no padrão oficial exigido pela API da Wikipédia para evitar erro 403
    headers = {
        "User-Agent": "SandbrainApp/1.0 (https://github.com/sandreque1970/sandbrain; sandreque1970@gmail.com)"
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

    # 2. Busca Wikipédia (Rest API Summary)
    termo_wiki = termo.capitalize()
    termo_encoded = urllib.parse.quote(termo_wiki.replace(" ", "_"))
    
    try:
        async with httpx.AsyncClient(timeout=6.0, headers=headers, follow_redirects=True) as client:
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

    # 3. Busca de Contingência na Wikipédia (Opensearch API)
    if len(resultados) == 0:
        try:
            async with httpx.AsyncClient(timeout=6.0, headers=headers) as client:
                url_opensearch = f"https://pt.wikipedia.org/w/api.php?action=opensearch&search={urllib.parse.quote(termo)}&limit=1&namespace=0&format=json"
                res_open = await client.get(url_opensearch)
                print(f"Status Opensearch: {res_open.status_code}")
                
                if res_open.status_code == 200:
                    dados = res_open.json()
                    if len(dados) >= 3 and len(dados[2]) > 0 and dados[2][0]:
                        resultados.append({
                            "titulo": f"📖 Wikipédia: {dados[1][0]}",
                            "detalhe": dados[2][0]
                        })
        except Exception as e:
            print(f"Erro na Opensearch: {e}")

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