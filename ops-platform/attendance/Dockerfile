FROM python:3.12-slim-bookworm
RUN pip install --no-cache-dir fastapi==0.141.1 uvicorn==0.52.1 'psycopg[binary]>=3.2,<4'
RUN useradd -u 10001 -m attendance
WORKDIR /app
COPY ops-platform/attendance/service.py ./service.py
USER attendance
CMD ["uvicorn","service:app","--host","0.0.0.0","--port","8781","--no-access-log"]
