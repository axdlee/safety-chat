# 安全访问控制插件

这是一个为 Dify 应用提供安全访问控制功能的插件，支持多种限流算法和存储方式。

## 功能特点

- 支持多种限流算法：
  - 令牌桶算法（Token Bucket）
  - 固定窗口算法（Fixed Window）
  - 滑动窗口算法（Sliding Window）
  - 漏桶算法（Leaky Bucket）
  - 混合多桶限制（Multiple Buckets）

- 支持多种存储方式：
  - Redis 存储
  - Dify 插件内置 Storage

- 基于多维度的用户信息：
  - 用户ID
  - 操作类型

## 许可证

MIT License



