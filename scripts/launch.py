"""Servidor local, com instalação inicial já concluída pelo lançador."""
import sys
import threading
import webbrowser
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from waitress import serve
from app import create_app

if __name__ == '__main__':
    app = create_app()
    print('\nManá do Céu: http://127.0.0.1:5000\nPainel: http://127.0.0.1:5000/login\nMantenha esta janela aberta. Ctrl+C encerra a loja local.\n', flush=True)
    opener = threading.Timer(1.0, lambda: webbrowser.open('http://127.0.0.1:5000'))
    opener.daemon = True
    opener.start()
    serve(app, host='127.0.0.1', port=5000, threads=4)
