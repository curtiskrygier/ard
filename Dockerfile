FROM python:3.12-slim

RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*
RUN pip install pyyaml

WORKDIR /app
COPY . .

RUN chmod +x build.sh && ./build.sh

EXPOSE 8080
CMD ["python3", "-m", "http.server", "8080"]
