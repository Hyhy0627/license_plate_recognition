# Entrypoint phụ tương thích
from main import app

if __name__ == "__main__":
    import uvicorn
    from src.config import settings
    uvicorn.run("main:app", host=settings.API_HOST, port=settings.API_PORT, reload=settings.DEBUG)
