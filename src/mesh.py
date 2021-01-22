import _thread
import logging
import grpc
import json
import discovery.discovery_pb2 as discovery_pb2
import discovery.discovery_pb2_grpc as discovery_pb2_grpc
import discovery.model_pb2 as  model_pb2
from google.protobuf.json_format import MessageToJson
import queue
import os
import time
import copy
import random
import requests
import tracer
import importlib.util
from importlib import reload
import threading

import tornado
import tornado.web
from tornado.web import RequestHandler
from tornado.escape import json_decode
from opentracing import Format

from prometheus_client.exposition import choose_encoder
from prometheus_client import CollectorRegistry, Gauge


UNDEFIEND = 0
NONE = 1
OK = 2

app = None

def is_mesh_init_over(mesh_config):
    return mesh_config.get("functions", None) != None

def mesh_initializer():
    init_mesh()

def is_first(mesh_config):
    self_name = os.getenv("FUNC_NAME")
    application = mesh_config.get("application", None)
    if application == None:
        return True
    if len(application.stepChains) == 0:
        return True

    return application.stepChains[0].functionName == self_name
        
def simple_policy(func) :
    global OK, UNDEFIEND, NONE
    infos = func["infos"]
    provider = os.getenv("PROVIDER")
    logging.info("provider:" + provider)
    info = None
    if infos != None :
        internal = infos.get(provider, None)
        logging.info("infos:" + str(infos))
        if internal != None :
            # the internal instance is not existed
            info = infos[provider]
            logging.info("info.instances:" + str(info["instances"]))
            if info["instances"] != None and len(info["instances"]) > 0:
                return ({
                    "url":random.sample(info["instances"], 1)[0] + "/invoke",
                    "method": func["method"]
                    }, OK)
        else:
            # choose the first one
            for key in infos.keys():
                info = infos[key]
                break
        if info == None:
            logging.info("final info:" + str(info))
            return (None, UNDEFIEND)
        chosen_url = info["url"]
        method = func["method"]
        return ({"url": chosen_url, "method": method}, OK)
    else:
        logging.info("infos is NONE")
        return (None, UNDEFIEND)
    return (None, NONE)

policies = {
    "simple": simple_policy
}

def get_callee(mesh_config):
    global OK, UNDEFIEND, NONE
    application = mesh_config.get("application", None)
    logging.info("get_callee:" + str(mesh_config))
    if application == None:
        logging.info('["callee -1"]')
        return (None, UNDEFIEND)
    steps = application.stepChains
    self_name = os.getenv("FUNC_NAME")
    callee = None
    for i in range(0, len(steps)):
        if steps[i].functionName == self_name:
            if i + 1 < len(steps):
                callee = steps[i + 1].functionName
                break
            else :
                logging.info('["callee 0"]')
                logging.info("self name:" + self_name)
                logging.info("steps:" + str(steps))
                return (None,NONE)
    if callee == None:
        logging.info('["callee 1"]')
        return (callee, NONE)
    functions = mesh_config.get("functions", None)
    if functions == None:
        logging.info('["callee 2"]')
        return (None, UNDEFIEND)
    callee_func = functions.get(callee, None)
    if callee_func == None:
        logging.info('["callee 3"]')
        return (None, UNDEFIEND)
    logging.info("callee functions:" + str(functions))
    chosen_policy = os.getenv("POLICY")
    global policies
    return policies[chosen_policy](callee_func)
    
def watch(mesh_config, mesh_tracer) :
    # read config file first
    config = mesh_config["info"]
    with grpc.insecure_channel(config["target"]) as channel:
        stub = discovery_pb2_grpc.DiscoveryServerStub(channel)
        self_name = os.getenv("FUNC_NAME")
        provider = os.getenv("PROVIDER")
        instance = discovery_pb2.Instance(provider=provider, functionName=self_name, applicationName="", url="")
        while True:
            que = queue.Queue()
            que.put("start")
            try:
                resp = stub.XDS(xds_handler(que, instance, stub, mesh_config, mesh_tracer))
                for r in resp:
                    que.put(r)
            except Exception as e:
                logging.info("unknown err:" + str(e))
            finally:
                que.put("exit")

def xds_handler(que, instance, stub, mesh_config, mesh_tracer) :
    # todo no update logic
    while True:
        item = que.get()
        if isinstance(item, str) and item == "start":
            # init connection
            yield discovery_pb2.XDSRequest( instance=instance,
                                            resourceType="ads",
                                            resourcesName=[""],
                                            responseNonce="")
        else :
            # XDSResponse
            typ = item.resourceType
            if typ == "ads" :
                # store the data in mesh_config and yield request about fds
                resource = item.resources[0]
                app = model_pb2.Application()
                resource.Unpack(app)
                mesh_config["application"] = copy.deepcopy(app)
                logging.info("app:" +  str(app))
                instance.applicationName = app.name
                mesh_config["trace"]["config"]["serviceName"] = app.name
                # todo thinking about the method when application is changed
                logging.info("mesh get ads:" + str(mesh_config))
                mesh_tracer = tracer.init_tracer(mesh_config)
                steps = mesh_config["application"].stepChains
                funcName = []
                for step in steps :
                    funcName.append(step.functionName)
                logging.info("mesh request steps:" + str(funcName))
                yield discovery_pb2.XDSRequest( instance=instance, 
                                                resourceType="fds",
                                                resourcesName=funcName,
                                                responseNonce="")
            elif typ == "fds":
                if mesh_config.get("functions", None) == None:
                    mesh_config["functions"] = {}
                resources = item.resources
                for resource in resources:
                    func = model_pb2.Function()
                    resource.Unpack(func)
                    mesh_config["functions"][func.name] = json.loads(MessageToJson(func))
                    # ugly info covert, strange error about use MessageToJson
                    logging.info("function "+ func.name + " to json:" + MessageToJson(func))
                    # infos = mesh_config["functions"][func.name].get("infos", None)
                    # covert_infos = {}
                    # if infos == None:
                    #     mesh_config["functions"][func.name]["infos"] = {}
                    # for provider in infos :
                    #     covert_infos[provider] = {}
                    #     covert_infos[provider]["url"] = infos[provider]["url"]
                    #     covert_infos[provider]["internalUrl"] = infos[provider]["internalUrl"]
                    #     covert_infos[provider]["instances"] = copy.deepcopy(infos[provider]["instances"]) 
                    # mesh_config["functions"][func.name]["infos"] = covert_infos
                logging.info("get fds:" + str(mesh_config.get("functions", None)))
            else :
                logging.error("unsupported type {}" % (typ))

def get_data(opts, data) :
    needPost = opts["method"] == 'DELETE' or opts["method"] == 'POST' or opts["method"] == 'PUT'
    resp = None
    if not opts["url"].startswith("http://") and not opts["url"].startswith("https://"):
        opts["url"] = "http://" + opts["url"]
    if needPost :
        resp = requests.request(opts["method"], opts["url"], headers=opts["headers"], data=data)
    else :
        resp = requests.request(opts["method"], opts["url"], headers=opts["headers"])
    if resp.status_code == 200 :
        return resp.text
    return ""

def start_http_invoke():
    global app
    app = Application()
    logging.info("torando start 1")
    httpServer = tornado.httpserver.HTTPServer(app)
    logging.info("torando start 2")
    httpServer.bind(40041)
    logging.info("torando start 3")
    io_loop = tornado.ioloop.IOLoop()
    io_loop.make_current()
    httpServer.start()
    logging.info("torando start 4")
    tornado.ioloop.IOLoop.current().start()

def init_mesh():
    _thread.start_new_thread(start_http_invoke, ())

def shutdown_tornado():
    time.sleep(1)
    tornado.ioloop.IOLoop.current().stop()

def shutdown():
    if tornado.ioloop.IOLoop.current() != None:
        shutdown_tornado()

class MetricsHandler(RequestHandler):
    def get(self, *args, **kwargs):
        encoder, content_type = choose_encoder(self.request.headers.get('accept'))
        self.set_header("Content-Type", content_type)
        self.write("# HELP qps the number of requests\n")
        self.write("# TYPE qps counter\n")
        self.write("qps " + str(self.application.qps) + "\n")
        self.write("# EOF\n")
        self.flush()
        self.finish()

class InvokeHandler(RequestHandler):
    def get(self, *args, **kwargs):
        try:
            self.application.share_lock.acquire()
            self.application.qps += 1
            self.application.share_lock.release()
        except Exception as e:
            logging.info(e)
        logging.info("handle get, check information:" + str(self.application.mesh_config))
        mesh_config = self.application.mesh_config
        mesh_tracer = self.application.mesh_tracer
        span = None
        localSpan = None
        trace_headers = self.request.headers
        if is_first(mesh_config) and mesh_tracer != None :
            span = mesh_tracer.start_span('ParentSpan')
        elif mesh_tracer != None :
            span = mesh_tracer.extract(Format.TEXT_MAP, trace_headers)
            localSpan = mesh_tracer.start_span("ChildSpan", child_of=span)
        data = tornado.escape.json_decode(self.request.body)
        local_result = self.application.func.handler(data)
        logging.info("before callee:" + str(mesh_config))
        callee = get_callee(mesh_config)
        next_headers = {}
        if mesh_tracer != None:
            mesh_tracer.inject(span, Format.TEXT_MAP, next_headers)
        result = ""
        logging.info("get callee:"+ str(callee))
        if callee[0] != None :
            callee["headers"] = next_headers
            logging.info("callee:" + str(callee))
            result = get_data(callee, local_result)
        elif callee[1] == NONE:
            result = local_result
        elif callee[1] == UNDEFIEND:
            # retry here
            retry_time = 50
            for t in range(retry_time):
                callee = callee = get_callee(mesh_config)
                if callee[0] != None :
                    callee["headers"] = next_headers
                    logging.info("callee:" + str(callee))
                    result = get_data(callee, local_result)
                    break
                else :
                    time.sleep(0.05)
        if localSpan != None:
            localSpan.finish()
            span.finish()
        self.write(result)
        self.finish()

class Application(tornado.web.Application):
    def __init__(self):
        # 路由
        with open("./config.json", encoding="utf-8") as f:
            data = json.load(f)
            self.mesh_config = data
        self.mesh_tracer = None
        _thread.start_new_thread(watch,(self.mesh_config,self.mesh_tracer))
        self.func = importlib.import_module('index')
        self.share_lock = threading.Lock()
        self.qps = 0
        handlers = [
            ("/invoke", InvokeHandler),
            ("/metrics", MetricsHandler),
        ]
        super(Application, self).__init__(handlers)