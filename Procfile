web: bash analysis/build.sh && cd analysis && gunicorn --bind 0.0.0.0:$PORT --timeout 120 --workers 1 api_server:app
