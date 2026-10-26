FROM python:3.12-slim
WORKDIR /srv
COPY digital-bank-deploy/pyproject.toml /opt/bank-common/pyproject.toml
COPY digital-bank-deploy/bank_common /opt/bank-common/bank_common
RUN pip install --no-cache-dir /opt/bank-common
COPY digital-bank-core/requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r /srv/requirements.txt
COPY digital-bank-core /srv
ENV PYTHONPATH=/srv
EXPOSE 8001
CMD ["uvicorn", "host:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "2"]
