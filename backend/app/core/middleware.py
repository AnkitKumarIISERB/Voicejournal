import time
import json
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request

# Setup basic logger
logger = logging.getLogger("api_logger")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(message)s')
handler.setFormatter(formatter)
if not logger.handlers:
    logger.addHandler(handler)

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Process the request
        response = await call_next(request)
        
        process_time = (time.time() - start_time) * 1000
        
        log_dict = {
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "latency_ms": round(process_time, 2),
            "client_ip": request.client.host if request.client else "unknown"
        }
        
        logger.info(json.dumps(log_dict))
        
        return response
