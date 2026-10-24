FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 GATEWAY_HOST=0.0.0.0
WORKDIR /opt/open-mirror
RUN pip install --no-cache-dir requests==2.32.3
COPY server.py index.html app.js style.css ./
USER 10001:10001
EXPOSE 8787
CMD ["python", "server.py"]
