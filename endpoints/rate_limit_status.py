from typing import Mapping
from werkzeug import Request, Response
from dify_plugin import Endpoint
from flask import jsonify
from utils.rate_limiter_algorithms import RateLimiterAlgorithm

class RateLimitStatusEndpoint(Endpoint):
    def _invoke(self, r: Request, values: Mapping, settings: Mapping) -> Response:
        # 获取请求参数
        user_id = r.args.get(RateLimiterAlgorithm.USER_ID_KEY)
        unique_id = r.args.get(RateLimiterAlgorithm.UNIQUE_ID_KEY)
        if not user_id or not unique_id:
            return jsonify({
                'error': f'Missing required parameters: {RateLimiterAlgorithm.USER_ID_KEY} and {RateLimiterAlgorithm.UNIQUE_ID_KEY}'
            }), 400
            
        try:
            rate_limiter_status = self.session.tool.invoke_builtin_tool("axdlee/safety_chat", "rate_limiter_status", {
                RateLimiterAlgorithm.UNIQUE_ID_KEY: unique_id,
                RateLimiterAlgorithm.USER_ID_KEY: user_id
            })
            
            return jsonify({
                RateLimiterAlgorithm.ALLOWED_KEY: rate_limiter_status.get(RateLimiterAlgorithm.ALLOWED_KEY),
                RateLimiterAlgorithm.REMAINING_KEY: rate_limiter_status.get(RateLimiterAlgorithm.REMAINING_KEY),
                RateLimiterAlgorithm.RESET_TIME_KEY: rate_limiter_status.get(RateLimiterAlgorithm.RESET_TIME_KEY),
                RateLimiterAlgorithm.ALGORITHM_TYPE_KEY: rate_limiter_status.get(RateLimiterAlgorithm.ALGORITHM_TYPE_KEY),
                RateLimiterAlgorithm.ACTION_TYPE_KEY: rate_limiter_status.get(RateLimiterAlgorithm.ACTION_TYPE_KEY),
                RateLimiterAlgorithm.RATE_KEY: rate_limiter_status.get(RateLimiterAlgorithm.RATE_KEY),
                RateLimiterAlgorithm.CAPACITY_KEY: rate_limiter_status.get(RateLimiterAlgorithm.CAPACITY_KEY),
                RateLimiterAlgorithm.MAX_REQUESTS_KEY: rate_limiter_status.get(RateLimiterAlgorithm.MAX_REQUESTS_KEY),
                RateLimiterAlgorithm.WINDOW_SIZE_KEY: rate_limiter_status.get(RateLimiterAlgorithm.WINDOW_SIZE_KEY),
                RateLimiterAlgorithm.REASON_KEY: rate_limiter_status.get(RateLimiterAlgorithm.REASON_KEY),
                RateLimiterAlgorithm.REASON_CN_KEY: rate_limiter_status.get(RateLimiterAlgorithm.REASON_CN_KEY),
                RateLimiterAlgorithm.REASON_CODE_KEY: rate_limiter_status.get(RateLimiterAlgorithm.REASON_CODE_KEY)
            }), 200
            
        except Exception as e:
            return jsonify({
                'error': f'Failed to get rate limit status: {str(e)}'
            }), 500 