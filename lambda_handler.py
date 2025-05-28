from mangum import Mangum
from app.main import app  # Import your existing FastAPI app

handler = Mangum(app)  # Lambda-compatible handler
