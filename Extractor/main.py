from fastapi import FastAPI
from app.routes.extractor_routes import router

app = FastAPI(title="BITE - Extractor Agent", version="1.0.0")
app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "extractor"}
