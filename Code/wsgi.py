import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from app import app, init_app
init_app()

if __name__ == "__main__":
    app.run()
