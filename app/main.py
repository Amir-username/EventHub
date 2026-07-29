from .factory import create_app
from .config import get_settings

app = create_app(settings=get_settings())


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
