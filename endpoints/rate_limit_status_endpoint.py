import json
from typing import Mapping
from werkzeug import Request, Response
from dify_plugin import Endpoint
from flask import jsonify
from utils.rate_limiter_algorithms import RateLimiterAlgorithm

class RateLimitStatusEndpoint(Endpoint):
    def _invoke(self, r: Request, values: Mapping, settings: Mapping) -> Response:
        # 获取请求参数
        user_id = r.args.get(RateLimiterAlgorithm.USER_ID_KEY)
        unique_id = settings.get(RateLimiterAlgorithm.UNIQUE_ID_KEY)
        print(f"user_id: {user_id}, unique_id: {unique_id}")
        if not unique_id:
            return Response(
                response=json.dumps({"error": f'Missing required parameters: {RateLimiterAlgorithm.UNIQUE_ID_KEY}'}),
                status=400,
                content_type="application/json"
            )
        if not user_id:
            return Response(
                response=json.dumps({"error": f'Missing required parameters: {RateLimiterAlgorithm.USER_ID_KEY}'}),
                status=400,
                content_type="application/json"
            )
        
        try:
            rate_limiter_status = self.session.tool.invoke_builtin_tool("axdlee/safety_chat/safety_chat", "rate_limiter_status", parameters={
                RateLimiterAlgorithm.UNIQUE_ID_KEY: unique_id,
                RateLimiterAlgorithm.USER_ID_KEY: user_id
            })

            def generator():
                for chunk in rate_limiter_status:
                    yield json.dumps(chunk) + "\n\n"
            return Response(
                response=generator(),
                status=200,
                content_type="application/json"
            )
            
        except Exception as e:
            return Response(
                response=json.dumps({"error": f'Failed to get rate limit status: {str(e)}'}),
                status=500,
                content_type="application/json"
            ) 