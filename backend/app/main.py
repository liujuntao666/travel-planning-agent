from fastapi import FastAPI

app = FastAPI(title="Travel Planning Agent")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
