import grpc
import sys
from container import container_pb2
from container import container_pb2_grpc

if __name__ == "__main__":
    channel = grpc.insecure_channel('localhost:50051')
    stub = container_pb2_grpc.ContainerStub(channel)
    res = stub.LoadCode(container_pb2.LoadCodeRequest(
        funcName='test',
        url=sys.argv[1],
    ))
    print(res)
    res = stub.Invoke(container_pb2.InvokeRequest(
        funcname='test',
        payload=bytes('hello', encoding = "utf8")
    ))
    print(res)