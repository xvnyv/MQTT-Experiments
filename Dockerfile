FROM python:3.9-slim

WORKDIR /src

COPY requirements.txt requirements.txt

RUN pip install -r requirements.txt

COPY pub-client.py pub-client.py

COPY sub-client.py sub-client.py

COPY run-client.sh run-client.sh

RUN chmod +x run-client.sh

EXPOSE 5001

EXPOSE 5002

ENTRYPOINT ["./run-client.sh"]