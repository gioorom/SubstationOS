from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import documents


app = FastAPI(
    title="SubstationOS API"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000"
    ],
    allow_credentials=True,
    allow_methods=[
        "*"
    ],
    allow_headers=[
        "*"
    ],
)


app.include_router(
    documents.router
)


@app.get("/")
def root():

    return {
        "message": "SubstationOS API running"
    }