import os
import json
import sys
import zipfile
import grpc
import logging
from concurrent import futures

from container import container_pb2
from container import container_pb2_grpc

class ContainerSever(container_pb2_grpc.ContainerServicer):
    def Invoke(self, request, context: grpc.RpcContext):
        return container_pb2.InvokeResponse(code=0, )
    
    def SetEnvs(self, request, context):
        pass

    def LoadCode(self, request, context):
        zf = zipfile.ZipFile("/tmp/code/source")
        try:
            zf.extractall(path="/tmp/code")
        except RuntimeError as e:
            print(e)

    def Stop(self, request, context):
        return

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    container_pb2_grpc.add_ContainerServicer_to_server(
        ContainerSever(), server)
    server.add_insecure_port('[::]:50051')
    server.start()
    server.wait_for_termination()


if __name__ == '__main__':
    logging.basicConfig()
    serve()
