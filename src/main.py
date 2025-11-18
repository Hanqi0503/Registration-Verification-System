from app.config.config import Config
from app import create_app

app = create_app()


@app.route('/', methods=['GET'])
def landing_page():
    return "The Backend Website is Alive! 🚀"


if __name__ == "__main__":
    host = Config.FLASK_HOST
    port = Config.FLASK_PORT
    debug = Config.FLASK_DEBUG

    app.run(host=host, port=port, debug=debug)
