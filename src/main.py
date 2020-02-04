import socket
import os
import threading
import json
from pyenv import invoke


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
    register()

    # start working
    t = threading.Thread(target=onMessageReceived, args=(sock,))
    t.start()
    t.wait()


# Send request to server, you can define your own proxy
# conn: conn handler
def sendRequest(sock, callID, data):
    header = callID.to_bytes(8) + len(data).to_bytes(8, byteorder="big")
    sock.sendall(header+data)


def onMessageReceived(sock):
    while True:
        callID, data = parseResponse(sock)
        res = invoke(data)
        sendRequest(sock, callID, res)
    #   break


# Parse request of unix socket
# conn: conn handler
def parseResponse(sock):
    callID = sock.recv(8)
    lenStr = sock.recv(8)
    length = int.from_bytes(lenStr, byteorder="big")
    data = sock.recv(length)
    return callID, data


if __name__ == "__main__":
    clientSocket()
