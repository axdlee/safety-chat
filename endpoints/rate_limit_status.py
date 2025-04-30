from typing import Mapping
from werkzeug import Request, Response
from dify_plugin import Endpoint
from flask import jsonify
from tools.rate_limiter_check import RateLimiterCheckTool

class RateLimitStatusEndpoint(Endpoint):
    def _invoke(self, r: Request, values: Mapping, settings: Mapping) -> Response:
        # 获取请求参数
        user_id = r.args.get('user_id')
        unique_id = r.args.get('unique_id')
        if not user_id or not unique_id:
            return jsonify({
                'error': 'Missing required parameters: user_id and unique_id'
            }), 400
            
        try:
            config = self.session.tool.invoke_builtin_tool("axdlee/safety_chat", "rate_limiter_check", {
                "unique_id": unique_id,
                "user_id": user_id
            })
            parameters = {
                "algorithm_type": config.get('algorithm_type'),
                "rate": config.get('rate'),
                "capacity": config.get('capacity'),
                "max_requests": config.get('max_requests'),
                "window_size": config.get('window_size')
            }
            algorithm = self.session.tool.invoke_builtin_tool("axdlee/safety_chat", "rate_limiter_check", parameters)
            
            # 生成限流 key
            key = f"{user_id}:{action_type}"
            
            # 获取状态
            status = algorithm.get_status(key)
            
            return jsonify({
                'user_id': user_id,
                'action_type': action_type,
                'algorithm_type': settings.get('algorithm_type'),
                'allowed': status['allowed'],
                'remaining': status['remaining'],
                'reset_time': status['reset_time']
            }), 200
            
        except Exception as e:
            return jsonify({
                'error': f'Failed to get rate limit status: {str(e)}'
            }), 500 