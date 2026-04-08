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
    host=${2:-localhost}
    protocol=${3:-TCP}
    player=${4:-0}
    delay=${5:-0}
    echo "Iniciando cliente ($protocol - Player $player) conectando a $host (delay: ${delay}ms)..."
    python3 client_gui.py "$host" "$protocol" "$player" "$delay"
else
    echo "Uso:"
    echo "  ./run.sh server                              - Inicia o servidor"
    echo "  ./run.sh client [host] [TCP|UDP] [0|1] [delay_ms]  - Inicia cliente gráfico"
    echo ""
    echo "Exemplos:"
    echo "  ./run.sh server"
    echo "  ./run.sh client localhost TCP 0              - Mesma máquina"
    echo "  ./run.sh client 192.168.1.100 TCP 0          - Outra máquina"
    echo "  ./run.sh client 192.168.1.100 UDP 1          - Outra máquina com UDP"
fi
