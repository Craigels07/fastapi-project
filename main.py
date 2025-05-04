from fastapi import FastAPI
from app.routers import documents, file, user
import uvicorn  

app = FastAPI()

@app.get("/")
def read_root():
    return {"Hello": "World"}

app.include_router(user.router)
# app.include_router(file.router)
app.include_router(documents.router)


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)