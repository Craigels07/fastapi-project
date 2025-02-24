from fastapi import FastAPI
from app.routers import user


app = FastAPI()

@app.get("/")
def read_root():
    return {"Hello": "World"}

app.include_router(user.router)
