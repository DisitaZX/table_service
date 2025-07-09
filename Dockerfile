#FROM python:3.12
FROM table_service-app:latest
ENV PYTHONUNBUFFERED 1

#RUN mkdir /app
WORKDIR /app
COPY table_service/req.txt /app/
#RUN pip install --upgrade pip && pip install -r req.txt
ADD table_service /app/
WORKDIR /app/table_service/
RUN chmod +x run.sh

ENTRYPOINT ["/app/table_service/run.sh"]
