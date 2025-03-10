from fastapi import FastAPI
from app.routers import file, user


app = FastAPI()

@app.get("/")
def read_root():
    return {"Hello": "World"}

app.include_router(user.router)
app.include_router(file.router)
