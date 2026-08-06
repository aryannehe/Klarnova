FROM python:3.13-slim
WORKDIR /app
COPY checkout/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY shared/ shared/
COPY checkout/main.py main.py
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
