FROM python:3.10.1-slim-bullseye

RUN apt-get update && \
    apt-get install -y p7zip bash

RUN pip install --upgrade pip && \
    pip install --upgrade \
        boto3 \
        jsonschema \
        pyrvt \
        pyexcel \
        pandas \
        dill && \
    # Use the main branch of pyStrata
    pip install https://github.com/arkottke/pystrata/archive/main.zip

COPY scripts /opt/cloudburst
RUN mkdir /work
WORKDIR /work

ENTRYPOINT ["python3", "/opt/cloudburst/fw_entrypoint.py"]
