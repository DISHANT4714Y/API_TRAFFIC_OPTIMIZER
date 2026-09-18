from fastapi import FastAPI

app = FastAPI(title="Mock External API")

@app.get("/health")
async def health():
    return {"status": "mock-api-ok"}
