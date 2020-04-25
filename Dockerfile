FROM python:3.6

ENV RUNTIME python3
ENV FUNC_NAME ""
ENV CODE_PATH /tmp/index

EXPOSE 50051

ADD src /env

WORKDIR /env

RUN pip install grpcio

ENTRYPOINT [ "python", "/env/main.py" ]