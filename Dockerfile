FROM python:3.6

RUN pip install requests protobuf grpcio==1.27.2 jaeger-client waiting tornado

ENV RUNTIME python3
ENV FUNC_NAME ""
ENV PROVIDER hcloud
ENV POLICY  simple
ENV CODE_PATH /tmp/index

EXPOSE 50051
EXPOSE 40041

ADD src /env

WORKDIR /env

ENTRYPOINT [ "python", "/env/main.py" ]