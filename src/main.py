import os
import json
import sys
import zipfile
import grpc
import logging
import requests
import threading
import tempfile
import importlib.util
from importlib import reload

from concurrent import futures

from container import container_pb2, container_pb2_grpc
from worker import worker_pb2, worker_pb2_grpc
class ContainerSever(container_pb2_grpc.ContainerServicer):
    def __init__(self):
        super().__init__()
        self.loadCodeLock = threading.Lock()
        self.funcName = os.environ['FUNC_NAME']
        self.func = None
        self.d = None

    def Invoke(self, request, context: grpc.RpcContext):
        try:
            if self.func is None:
                return container_pb2.InvokeResponse(code=1)
            elif self.funcName != request.funcName:
                return container_pb2.InvokeResponse(code=2)

            output = self.func.handler(request.payload)
            if isinstance(output, bytes):
                pass
            elif isinstance(output, str):
                output = bytes(output, encoding='utf8')
            else:
                return container_pb2.InvokeResponse(code=3)
            return container_pb2.InvokeResponse(code=0, output=output)
        except Exception as e:
            logging.warn(e)
            return container_pb2.InvokeResponse(code=3)
    
    def SetEnvs(self, request, context):
        try:
            for env in request.env:
                envs = env.split('=')
                if len(envs) != 2:
                    return container_pb2.SetEnvsResponse(code=1)
                os.environ[envs[0]] = envs[1]
        except Exception as e:
            logging.warn(e)
            return container_pb2.SetEnvsResponse(code=1)
        return container_pb2.SetEnvsResponse(code=0)

    def LoadCode(self, request, context):
        with self.loadCodeLock:
            try:
                r = requests.get(request.url)
                d = tempfile.mkdtemp('', '', '/tmp')
                with open(d + "/func" , "wb") as code:
                    code.write(r.content)
                zf = zipfile.ZipFile(d + "/func")
                zf.extractall(path=d)
                zf.close()
                sys.path.append(d)
                if self.d is not None:
                    sys.path.remove(self.d)
                if self.func is None:
                    self.func = importlib.import_module('index')
                else:
                    self.func = reload(self.func)
                # TODO: unlink the last directory
                self.d = d
                self.funcName = request.funcName
                return container_pb2.LoadCodeResponse(code=0)
            except RuntimeError as e:
                print(e)
                return container_pb2.LoadCodeResponse(code=1)

    def Stop(self, request, context):
        return

def readAddr():
    with open('/etc/hosts') as hosts:
        return hosts.readlines[-1].split('\t')[0]

def registerToWorker():
    channel = grpc.insecure_channel(os.environ['WORK_HOST'])
    stub = worker_pb2_grpc.WorkerStub(channel)
    res = stub.Register(worker_pb2.RegisterRequest(
        id='undefined',
        addr=readAddr() + ':50051',
        runtime=os.environ['RUNTIME'],
        funcName=os.environ['FUNC_NAME'],
        memory=int(os.environ['MEMORY']),
        disk=0,
    ))

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    container_pb2_grpc.add_ContainerServicer_to_server(
        ContainerSever(), server)
    server.add_insecure_port('[::]:50051')
    server.start()
    # TODO: need wait_for_ready?
    registerToWorker()
    server.wait_for_termination()

if __name__ == '__main__':
    logging.basicConfig()
    serve()
