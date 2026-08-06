FROM python:3.13-slim
WORKDIR /app
COPY cart/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY shared/ shared/
COPY cart/main.py main.py
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
