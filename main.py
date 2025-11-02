from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List, Dict, Any
import pandas as pd
import os
from dotenv import load_dotenv
import json
import asyncio
import traceback

# Charger les variables d'environnement depuis .env
load_dotenv()

import get_weather
import analyze_weather
try:
    import openai
except Exception:
    openai = None

app = FastAPI(
    title="Assistant Agricole Backend",
    description="Backend pour l'assistant agricole intelligent - Recommandations basées sur la météo",
    version="1.0.0"
)

# Configuration CORS depuis .env ou valeurs par défaut
CORS_ORIGINS = json.loads(os.getenv("CORS_ORIGINS", '["http://localhost:8000", "http://127.0.0.1:8000", "null"]'))
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    """Endpoint de vérification de santé - utilisé pour confirmer que le serveur fonctionne."""
    return {"status": "ok", "version": "1.0.0"}


# --- Shared runtime state exposed to frontend ---
state: Dict[str, Any] = {
    "temperature": 24,
    "rain": False,
    "soil": "جيدة",
    "wind": 10,
    "humidity": 65,
    "rainProb": 10,
    "forecast": "غائم جزئياً",
    "realtime": False,
    "pumpOn": False,
    "motorOn": False,
    "pumpAdvice": "",
    "protectionAdvice": "",
}


# --- WebSocket connection manager ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        try:
            self.active_connections.remove(websocket)
        except ValueError:
            pass

    async def broadcast(self, message: Dict[str, Any]):
        data = json.dumps(message, ensure_ascii=False)
        to_remove = []
        for connection in list(self.active_connections):
            try:
                await connection.send_text(data)
            except Exception:
                to_remove.append(connection)
        for c in to_remove:
            self.disconnect(c)


manager = ConnectionManager()


def _safe_state_copy():
    return {k: v for k, v in state.items()}


async def _generate_chat_response(user_text: str) -> str:
    """Generate a chat reply. Prefer OpenAI if configured, otherwise use a simple heuristic reply."""
    # Try to use OpenAI via analyze_weather helper functions when available
    api_key = analyze_weather.load_api_key()
    data_string = None
    try:
        df = analyze_weather.read_latest_forecast(analyze_weather.CSV_FILE_PATH)
        if df is not None:
            data_string = analyze_weather.format_data_for_prompt(df)
    except Exception:
        data_string = None

    if api_key and openai is not None:
        try:
            client = openai.OpenAI(api_key=api_key)
            prompt = (
                f"User: {user_text}\n\nForecast data (if available):\n{data_string or 'no data'}\n\n"
                "Réponds en arabe tunisien ou arabe simple en donnant un conseil agricole concis."
            )
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Vous êtes un assistant agricole professionnel."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=150,
                temperature=0.5,
            )
            return resp.choices[0].message.content
        except Exception as e:
            print("OpenAI chat error:", e)
            traceback.print_exc()

    # Fallback simple rule-based reply in Arabic
    text = user_text.lower()
    if "مطر" in text or "أمطار" in text or "pluie" in text:
        return "إذا كان هناك احتمال أمطار عالي، لا تحتاج للنقاس فورا. احمي النباتات فقط إذا كانت الأمطار قوية."
    if "رطوبة" in text or "humidity" in text:
        return f"الرطوبة الحالية {state.get('humidity')}%، {'جافة' if state.get('humidity',0)<40 else 'رطبة'} - اضبط الري وفق الحاجة."
    if "مضخة" in text or "pump" in text:
        return f"المضخة حالياً {'مشتغلة' if state.get('pumpOn') else 'مطفأة'}. يمكنك تغيير الحالة من لوحة التحكم."
    # Default reply
    return "شكراً لسؤالك. لا تتردد في طرح المزيد من التفاصيل حول المحصول أو الموقع للحصول على نصيحة دقيقة."




@app.get("/get-recommendation")
async def get_recommendation(lat: Optional[float] = None, lon: Optional[float] = None):
    """Endpoint principal qui récupère la météo pour la position fournie,
    sauvegarde les données, puis appelle l'IA pour obtenir une recommandation.
    """
    try:
        # Validation des clés d'API
        if not get_weather.API_KEY:
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "OPENWEATHERMAP_API_KEY non défini sur le serveur.",
                    "help": "Créez un fichier .env avec OPENWEATHERMAP_API_KEY=votre_cle"
                }
            )

        openai_key = analyze_weather.load_api_key()
        if not openai_key:
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "OPENAI_API_KEY non défini sur le serveur.",
                    "help": "Créez un fichier .env avec OPENAI_API_KEY=votre_cle"
                }
            )

        # Position : si non fournie, utiliser les valeurs par défaut
        if lat is None:
            lat = get_weather.LATITUDE
        if lon is None:
            lon = get_weather.LONGITUDE

        # 1) Récupérer les données depuis l'API météo
        weather_list = get_weather.fetch_weather_api(lat, lon, get_weather.API_KEY)
        if not weather_list:
            raise HTTPException(
                status_code=502,
                detail={
                    "message": "Impossible de récupérer les données météo.",
                    "help": "Vérifiez votre connexion et la validité de OPENWEATHERMAP_API_KEY"
                }
            )

        # 2) Sauvegarder dans le CSV (append)
        try:
            get_weather.save_to_csv(weather_list, get_weather.CSV_FILE_PATH)
        except Exception as e:
            print(f"Warning: échec enregistrement CSV: {e}")

        # 3) Préparer un DataFrame et formatter le prompt
        try:
            df = pd.DataFrame(weather_list)
            data_string = analyze_weather.format_data_for_prompt(df)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail={
                    "message": f"Erreur préparation des données: {e}",
                    "help": "Problème de format des données météo"
                }
            )

        # 4) Interroger l'IA
        recommendation = analyze_weather.get_ai_recommendation(openai_key, data_string)
        if not recommendation:
            raise HTTPException(
                status_code=502,
                detail={
                    "message": "L'IA n'a pas renvoyé de recommandation.",
                    "help": "Vérifiez la validité de OPENAI_API_KEY et réessayez"
                }
            )

        # 5) Sauvegarder la dernière recommandation
        try:
            with open("recommendation.txt", "w", encoding="utf-8") as f:
                f.write(recommendation)
        except Exception as e:
            print(f"Warning: échec sauvegarde recommendation.txt: {e}")

        # 6) Répondre au front
        return JSONResponse(content={
            "recommendation": recommendation,
            "timestamp": pd.Timestamp.now().isoformat()
        })

    except HTTPException:
        raise  # Remonter les erreurs HTTP déjà formatées
    except Exception as e:
        # Capturer les autres erreurs et les formater proprement
        raise HTTPException(
            status_code=500,
            detail={
                "message": f"Erreur inattendue: {str(e)}",
                "help": "Contactez l'administrateur si le problème persiste"
            }
        )


@app.get("/state")
async def get_state():
    """Return the current device/sensor state."""
    return JSONResponse(content=_safe_state_copy())


@app.post("/state")
async def post_state(payload: Dict[str, Any]):
    """Update parts of the shared state. Broadcasts to connected WebSocket clients."""
    updated = {}
    for k, v in payload.items():
        if k in state:
            state[k] = v
            updated[k] = v
    # Re-run lightweight analyze logic if humidity/pump/realtime changed
    try:
        # simple local analyze: update pumpAdvice/protectionAdvice
        if 'humidity' in updated or 'realtime' in updated or 'wind' in updated or 'temperature' in updated:
            # very small logic to set pumpAdvice
            if state.get('realtime'):
                state['pumpAdvice'] = 'المطر يهطل. توقف.'
            else:
                state['pumpAdvice'] = 'اسقي إذا كانت التربة جافة.' if state.get('humidity',0) < 40 else 'رطوبة كافية.'
    except Exception:
        pass

    # Broadcast updated state
    asyncio.create_task(manager.broadcast({"type": "state", "state": _safe_state_copy()}))
    return JSONResponse(content={"updated": updated})


@app.websocket('/ws')
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    # send initial state
    try:
        await websocket.send_text(json.dumps({"type": "state", "state": _safe_state_copy()}, ensure_ascii=False))
        while True:
            text = await websocket.receive_text()
            try:
                data = json.loads(text)
            except Exception:
                data = {"type": "raw", "text": text}

            # Handle incoming message types
            if data.get('type') == 'chat':
                user_text = data.get('text', '')
                reply = await _generate_chat_response(user_text)
                # send reply back to sender
                await websocket.send_text(json.dumps({"type": "chat", "text": reply}, ensure_ascii=False))
            elif data.get('type') == 'set_state':
                payload = data.get('payload', {})
                for k, v in payload.items():
                    if k in state:
                        state[k] = v
                # broadcast new state to all
                await manager.broadcast({"type": "state", "state": _safe_state_copy()})
            else:
                # Unknown type: echo
                await websocket.send_text(json.dumps({"type": "echo", "text": data.get('text', '')}, ensure_ascii=False))

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        manager.disconnect(websocket)
        print('WebSocket error:', e)
        traceback.print_exc()


if __name__ == "__main__":
    import uvicorn
    
    # Configuration depuis .env ou valeurs par défaut
    HOST = os.getenv("HOST", "127.0.0.1")
    PORT = int(os.getenv("PORT", "8000"))
    
    print(f"\n{'='*50}")
    print("Assistant Agricole Backend")
    print(f"{'='*50}")
    print(f"Documentation API : http://{HOST}:{PORT}/docs")
    print(f"Santé du serveur: http://{HOST}:{PORT}/health")
    print(f"{'='*50}\n")
    
    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        reload=True
    )
