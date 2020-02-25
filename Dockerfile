FROM python:3.7

ADD src /env

WORKDIR /env

ENTRYPOINT [ "python", "/env/main.py" ]