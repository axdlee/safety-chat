import json
from typing import Mapping
from werkzeug import Request, Response
from dify_plugin import Endpoint
from utils.rate_limiter_algorithms import RateLimiterAlgorithm

class RateLimitStatusEndpoint(Endpoint):
    def _invoke(self, r: Request, values: Mapping, settings: Mapping) -> Response:
        # 获取请求参数
        user_id = r.args.get(RateLimiterAlgorithm.USER_ID_KEY)
        unique_id = settings.get(RateLimiterAlgorithm.UNIQUE_ID_KEY)
        
        if not unique_id:
            return Response(
                response=json.dumps({
                    "code": -400,
                    "message": f'Missing required parameters: {RateLimiterAlgorithm.UNIQUE_ID_KEY}',
                    "data": None
                }),
                status=400,
                content_type="application/json"
            )
        if not user_id:
            return Response(
                response=json.dumps({
                    "code": -400,
                    "message": f'Missing required parameters: {RateLimiterAlgorithm.USER_ID_KEY}',
                    "data": None
                }),
                status=400,
                content_type="application/json"
            )
        
        try:
            rate_limiter_status = self.session.tool.invoke_builtin_tool("axdlee/safety_chat/safety_chat", "rate_limiter_status", parameters={
                RateLimiterAlgorithm.UNIQUE_ID_KEY: unique_id,
                RateLimiterAlgorithm.USER_ID_KEY: user_id
            })

            response_data = {}
            for chunk in rate_limiter_status:
                if chunk.type.value == 'variable':
                    response_data[chunk.message.variable_name] = chunk.message.variable_value
                elif chunk.type.value == 'text':
                    return Response(
                        response=json.dumps({
                            "code": 400,
                            "message": chunk.message.text,
                            "data": None
                        }),
                        status=400,
                        content_type="application/json"
                    )
                else:
                    return Response(
                        response=json.dumps({
                            "code": 500,
                            "message": "Unknown message type",
                            "data": None
                        }),
                        status=400,
                        content_type="application/json"
                    )

            return Response(
                response=json.dumps({
                    "code": 200,
                    "message": "success",
                    "data": response_data
                }),
                status=200,
                content_type="application/json"
            )
            
        except Exception as e:
            return Response(
                response=json.dumps({
                    "code": -500,
                    "message": f'Failed to get rate limit status: {str(e)}',
                    "data": None
                }),
                status=500,
                content_type="application/json"
            ) 