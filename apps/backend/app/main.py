from fastapi import FastAPI

app = FastAPI(
    title="SubstationOS API",
    version="0.1.0"
)


@app.get("/")
def root():
    return {
        "app": "SubstationOS",
        "version": "0.1.0",
        "status": "running"
    }


@app.get("/health")
def health():
    return {
        "status": "ok"
    }