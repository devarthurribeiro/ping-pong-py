#!/bin/bash

cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
    echo "Criando virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -q pygame
else
    source venv/bin/activate
fi

if [ "$1" = "server" ]; then
    echo "Iniciando servidor..."
    python3 server.py
elif [ "$1" = "client" ]; then
    protocol=${2:-TCP}
    player=${3:-0}
    echo "Iniciando cliente ($protocol - Player $player)..."
    python3 client_gui.py "$protocol" "$player"
else
    echo "Uso:"
    echo "  ./run.sh server                    - Inicia o servidor"
    echo "  ./run.sh client [TCP|UDP] [0|1]   - Inicia cliente gráfico"
    echo ""
    echo "Exemplos:"
    echo "  ./run.sh server"
    echo "  ./run.sh client TCP 0"
    echo "  ./run.sh client UDP 1"
fi
