from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import api_router
from app.db.database import init_db

import uvicorn






@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

    # Retrain tự động mỗi 7 ngày
    from app.api.api_retrain import do_retrain
    scheduler = BackgroundScheduler()
    scheduler.add_job(do_retrain, "interval", days=7, id="retrain_weekly")
    scheduler.start()

    yield

    scheduler.shutdown(wait=False)

origins = [
    "http://localhost:3000",  # Ví dụ cho React app
    "http://localhost:5173",  # Ví dụ cho Vue app
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173"
]

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router.router)



if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
