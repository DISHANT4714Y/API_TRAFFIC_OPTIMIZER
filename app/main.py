from fastapi import FastAPI

app = FastAPI(title="API Traffic Optimizer Prototype")

@app.get("/health")
async def health():
    return {"status": "ok"}
