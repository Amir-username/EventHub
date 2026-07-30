from .config import get_settings
from .factory import create_app

app = create_app(settings=get_settings())


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
