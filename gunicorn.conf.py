import os

# Production Gunicorn Server Configuration
bind = "0.0.0.0:" + os.getenv("PORT", "5000")
workers = int(os.getenv("WEB_CONCURRENCY", "2"))
threads = 4
timeout = 120
keepalive = 5

accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info")
