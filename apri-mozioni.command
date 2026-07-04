#!/bin/bash
cd "$(dirname "$0")"
# ferma eventuale server già in ascolto sulla 8000
lsof -ti:8000 | xargs kill -9 2>/dev/null
python3 -m http.server 8000 &
sleep 0.8
open "http://localhost:8000/mozioni.html"
wait
