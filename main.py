import os
import urllib.parse
from pathlib import Path
import uvicorn
import httpx
import xml.etree.ElementTree as ET
from fastapi import FastAPI, Body
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
    print(f"=== PESQUISA RECEBIDA: {termo} ===")
    
    if not termo:
        return JSONResponse(status_code=400, content={"status": "erro", "mensagem": "Termo de pesquisa vazio."})

    resultados = []
    termo_lower = termo.lower()
    
    headers = {
        "User-Agent": "SandbrainApp/1.0 (https://github.com/sandreque1970/sandbrain)"
    }

    # 1. PREVISÃO DO TEMPO
    if any(k in termo_lower for k in ["tempo em", "clima em", "previsão em", "temperatura em", "tempo", "clima"]):
        try:
            cidade = termo_lower
            for p in ["tempo em", "clima em", "previsão em", "temperatura em", "tempo", "clima"]:
                cidade = cidade.replace(p, "").strip()
            
            if not cidade:
                cidade = "São Paulo"

            async with httpx.AsyncClient(timeout=6.0, headers=headers) as client:
                geo_url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(cidade)}&format=json&limit=1"
                geo_res = await client.get(geo_url)
                
                if geo_res.status_code == 200 and len(geo_res.json()) > 0:
                    local = geo_res.json()[0]
                    lat, lon = local["lat"], local["lon"]
                    nome_cidade = local.get("display_name", cidade).split(",")[0]

                    clima_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
                    clima_res = await client.get(clima_url)
                    
                    if clima_res.status_code == 200:
                        cw = clima_res.json().get("current_weather", {})
                        temp = cw.get("temperature")
                        vento = cw.get("windspeed")
                        
                        resultados.append({
                            "titulo": f"🌤️ Previsão do Tempo: {nome_cidade}",
                            "detalhe": f"A temperatura atual em {nome_cidade} é de {temp}°C, com velocidade do vento de {vento} km/h."
                        })
        except Exception as e:
            print(f"Erro Clima: {e}")

    # 2. COTAÇÃO DO DÓLAR
    if "dolar" in termo_lower or "dólar" in termo_lower:
        try:
            async with httpx.AsyncClient(timeout=5.0, headers=headers) as client:
                res = await client.get("https://economia.awesomeapi.com.br/last/USD-BRL")
                if res.status_code == 200:
                    dados = res.json().get("USDBRL", {})
                    resultados.append({
                        "titulo": "💵 Cotação Comercial do Dólar",
                        "detalhe": f"Valor Atual: R$ {dados.get('bid', 'N/A')} | Máxima: R$ {dados.get('high', 'N/A')} | Mínima: R$ {dados.get('low', 'N/A')}"
                    })
        except Exception as e:
            print(f"Erro Dólar: {e}")

    # 3. NOTÍCIAS
    if "noticia" in termo_lower or "notícia" in termo_lower or "manchete" in termo_lower:
        try:
            assunto = termo_lower
            for p in ["noticias sobre", "notícias sobre", "noticia de", "notícias de", "noticias", "notícias", "manchetes"]:
                assunto = assunto.replace(p, "").strip()

            rss_url = f"https://news.google.com/rss/search?q={urllib.parse.quote(assunto or 'Brasil')}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
            
            async with httpx.AsyncClient(timeout=6.0, headers=headers, follow_redirects=True) as client:
                res_news = await client.get(rss_url)
                if res_news.status_code == 200:
                    root = ET.fromstring(res_news.content)
                    items = root.findall(".//item")[:3]
                    
                    if items:
                        noticias_txt = [f"{idx}. {item.find('title').text}" for idx, item in enumerate(items, 1) if item.find('title') is not None]
                        resultados.append({
                            "titulo": f"📰 Principais Notícias: {assunto.capitalize() if assunto else 'Destaques'}",
                            "detalhe": " | ".join(noticias_txt)
                        })
        except Exception as e:
            print(f"Erro Notícias: {e}")

    # 4. BUSCA WIKIPÉDIA (Geral/Conceitos)
    if len(resultados) == 0:
        termo_wiki = termo.capitalize()
        termo_encoded = urllib.parse.quote(termo_wiki.replace(" ", "_"))
        
        try:
            async with httpx.AsyncClient(timeout=6.0, headers=headers, follow_redirects=True) as client:
                url_wiki = f"https://pt.wikipedia.org/api/rest_v1/page/summary/{termo_encoded}"
                res_wiki = await client.get(url_wiki)
                
                if res_wiki.status_code == 200:
                    dados_wiki = res_wiki.json()
                    if dados_wiki.get("extract") and dados_wiki.get("type") != "disambiguation":
                        resultados.append({
                            "titulo": f"📖 Wikipédia: {dados_wiki.get('title', termo)}",
                            "detalhe": dados_wiki.get("extract")
                        })
        except Exception as e:
            print(f"Erro Wikipédia: {e}")

    # 5. FALLBACK PADRÃO
    if len(resultados) == 0:
        resultados.append({
            "titulo": f"Pesquisa: '{termo}'",
            "detalhe": f"Nenhum resultado direto encontrado para '{termo}'."
        })

    print(f"Total de resultados retornados: {len(resultados)}")

    return {
        "status": "sucesso",
        "termo": termo,
        "total": len(resultados),
        "resultados": resultados
    }

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
