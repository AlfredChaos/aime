from dotenv import load_dotenv
from aime_app.entrypoints.chat_cli import main as _main
from aime_app.infrastructure.patches import apply_all

load_dotenv()
apply_all()

if __name__ == "__main__":
    _main()
