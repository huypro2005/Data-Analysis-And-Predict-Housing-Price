from fastapi import FastAPI
from app.api import api_router
import uvicorn

app = FastAPI()
app.include_router(api_router.router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
