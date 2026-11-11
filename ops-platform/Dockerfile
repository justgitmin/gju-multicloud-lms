FROM public.ecr.aws/aws-cli/aws-cli:2 AS awscli
FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OPS_DATA_DIR=/data
COPY --from=awscli /usr/local/aws-cli /usr/local/aws-cli
RUN ln -s /usr/local/aws-cli/v2/current/bin/aws /usr/local/bin/aws && useradd -u 10001 -m ops && mkdir /data && chown ops:ops /data
WORKDIR /app
COPY ops-platform/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY ops-platform/cloudops ./cloudops
COPY ops-platform/backup.py ./backup.py
COPY infra/aws-lab/lab.py /infra/aws-lab/lab.py
USER ops
EXPOSE 8780
CMD ["uvicorn","cloudops.main:app","--host","0.0.0.0","--port","8780","--workers","1","--no-proxy-headers","--no-access-log"]
