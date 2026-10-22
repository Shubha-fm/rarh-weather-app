"""Start the API for local development:  python run.py

For production use a real server instead, for example:  gunicorn "app:create_app()" --bind 0.0.0.0:8000
"""

import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "8000")), debug=False)
