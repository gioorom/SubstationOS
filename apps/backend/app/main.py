from fastapi import FastAPI

from app.routers import documents


app = FastAPI(
    title="SubstationOS API"
)


app.include_router(
    documents.router
)


@app.get("/")
def root():

    return {
        "message": "SubstationOS API running"
    }