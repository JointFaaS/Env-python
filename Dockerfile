FROM python:3.6

RUN pip install requests protobuf grpcio

ENV RUNTIME python3
ENV FUNC_NAME ""
ENV CODE_PATH /tmp/index

EXPOSE 50051

ADD src /env

WORKDIR /env

ENTRYPOINT [ "python", "/env/main.py" ]