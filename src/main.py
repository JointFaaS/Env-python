import socket
import os
import threading
import json
import sys

UNIX_SOCK_PIPE_PATH = "/var/run/worker.sock"


def register(sock):
    msg = {}
    msg['funcName'] = os.getenv('funcName')
    msg['envID'] = os.getenv('envID')
    sendRequest(sock, 0, str.encode(json.dumps(msg)))


def clientSocket():
    # crate socket
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    if sock == 0:
        print('socket create error')
        return

    # connect server
    sock.connect(UNIX_SOCK_PIPE_PATH)

    # register the env into Worker
    register(sock)

    # start working
    t = threading.Thread(target=onMessageReceived, args=(sock,))
    t.start()
    t.join()


# Send request to server, you can define your own proxy
# conn: conn handler
def sendRequest(sock, callID, data):
    header = callID.to_bytes(8, byteorder="big") + len(data).to_bytes(8, byteorder="big")
    sock.sendall(header+data)


def onMessageReceived(sock):
    while True:
        callID, data = parseResponse(sock)
        res = index.handler(data)
        sendRequest(sock, callID, str.encode(json.dumps(res)))
    #   break


# Parse request of unix socket
# conn: conn handler
# TODO: err handle
def parseResponse(sock):
    callID = sock.recv(8)
    length = sock.recv(8)
    length = int.from_bytes(length, byteorder="big")
    callID = int.from_bytes(callID, byteorder="big")
    data = sock.recv(length)
    return callID, data


if __name__ == "__main__":
    sys.path.append("/tmp/code/") 
    import index
    clientSocket()
