import os
import urllib.parse
from pathlib import Path
import uvicorn
import httpx
import xml.etree.ElementTree as ET
from fastapi import FastAPI, Request, Body
from fastapi.responses import FileResponse, JSONResponse

app = FastAPI(title="Sandbrain Core API")

BASE_DIR = Path(__file__).resolve().parent
HTML_PATH = BASE_DIR / "templates" / "index.html"

# Correção na leitura da chave API
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

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
    
    headers_padrao = {
        "User-Agent": "SandbrainApp/1.0 (https://github.com/sandreque1970/sandbrain; sandreque1970@gmail.com)"
    }

    # 1. PREVISÃO DO TEMPO (Comandos Rápidos)
    if any(k in termo_lower for k in ["tempo em", "clima em", "previsão em", "temperatura em"]):
        try:
            cidade = termo_lower
            for p in ["tempo em", "clima em", "previsão em", "temperatura em"]:
                cidade = cidade.replace(p, "").strip()
            
            if not cidade:
                cidade = "São Paulo"

            async with httpx.AsyncClient(timeout=6.0, headers=headers_padrao) as client:
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
                            "detalhe": f"A temperatura atual em {nome_cidade} é de {temp}°C, com vento de {vento} km/h."
                        })
        except Exception as e:
            print(f"Erro ao buscar previsão do tempo: {e}")

    # 2. COTAÇÃO DO DÓLAR
    elif "dolar" in termo_lower or "dólar" in termo_lower:
        try:
            async with httpx.AsyncClient(timeout=5.0, headers=headers_padrao) as client:
                res = await client.get("https://economia.awesomeapi.com.br/last/USD-BRL")
                if res.status_code == 200:
                    dados = res.json().get("USDBRL", {})
                    resultados.append({
                        "titulo": "💵 Cotação Comercial do Dólar",
                        "detalhe": f"O Dólar está cotado a R$ {dados.get('bid', 'N/A')}. Máxima do dia: R$ {dados.get('high', 'N/A')} e Mínima: R$ {dados.get('low', 'N/A')}."
                    })
        except Exception as e:
            print(f"Erro no Dólar: {e}")

    # 3. RESPOSTA VIA INTELIGÊNCIA ARTIFICIAL (Groq API - Llama 3)
    if len(resultados) == 0 and GROQ_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                groq_headers = {
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json"
                }
                groq_payload = {
                    "model": "llama-3.3-70b-versatile",
                    "messages": [
                        {
                            "role": "system", 
                            "content": "Você é o Sandbrain, um assistente virtual inteligente e prestativo. Responda em português de forma clara, direta e objetiva (máximo 3 a 4 frases), ideal para leitura por síntese de voz."
                        },
                        {"role": "user", "content": termo}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 250
                }
                
                res_ia = await client.post("https://api.groq.com/openai/v1/chat/completions", json=groq_payload, headers=groq_headers)
                print(f"Status Groq API: {res_ia.status_code}")
                
                if res_ia.status_code == 200:
                    resposta_texto = res_ia.json()["choices"][0]["message"]["content"]
                    resultados.append({
                        "titulo": f"🤖 Sandbrain AI",
                        "detalhe": resposta_texto
                    })
        except Exception as e:
            print(f"Erro na IA Groq: {e}")

    # 4. FALLBACK CASO A CHAVE NÃO ESTEJA CONFIGURADA OU A IA FALHE
    if len(resultados) == 0:
        resultados.append({
            "titulo": f"Pesquisa: '{termo}'",
            "detalhe": f"Nenhum resultado direto encontrado para '{termo}'. Verifique se a chave GROQ_API_KEY está configurada no main.py."
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
