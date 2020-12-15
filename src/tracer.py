from jaeger_client import Config
import json

def init_tracer(mesh_config):
    tracer_config = mesh_config["trace"]
    config = Config(
        config={ # usually read from some yaml config
            "sampler": tracer_config["config"]["sampler"],
            'local_agent': {
                'reporting_host': tracer_config["config"]["reporter"]["agentHost"],
                'reporting_port': tracer_config["config"]["reporter"]["agentPort"],
            },
            'logging': True,
        },
        service_name= tracer_config["config"]["serviceName"],
        validate=True,
    )
    tracer = config.initialize_tracer()
    return tracer

def wsgi_header_handle(raw_headers) :
    headers = {}
    version = raw_headers.get("HTTP_UBER_VERSION", "")
    trace_id = raw_headers.get("HTTP_UBER_TRACE_ID", "")
    parent_id = raw_headers.get("HTTP_UBER_PARENT_ID", "")
    trace_flags = raw_headers.get("HTTP_UBER_TRACE_FLAGS", "")
    headers["uber-version"] = version
    headers["uber-trace-id"] = trace_id
    headers["uber-parent-id"] = parent_id
    headers["uber-trace-flags"] = trace_flags
    return headers