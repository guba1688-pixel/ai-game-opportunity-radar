from .base import PublicJsonMixin, Signal


class AIMarketAdapter(PublicJsonMixin):
    key = "ai_market"
    name = "AI 市场公开信号示例"
    category = "ai"

    def collect(self, config):
        if config.get("public_json_url"):
            return [Signal(**item) for item in self.read_public_json(config["public_json_url"])]
        return [
            Signal("中小团队需要可追溯的 AI 成本看板", "多模型调用让成本、质量和延迟难以统一复盘；本条仅用于演示采集闭环。", "ai", "内置 AI 示例数据", "https://example.com/demo/ai-cost", "演示场景，无实际观察期", "全球", "需求信号", "演示值", "非市场统计", "demo", "E", True),
            Signal("垂直 AI 工作流需要证据留痕", "企业买方关注输出依据、人工复核和可审计性；本条为模型化演示假设。", "ai", "内置 AI 示例数据", "https://example.com/demo/ai-evidence", "演示场景，无实际观察期", "中国", "痛点强度", "4", "演示评分/5", "demo", "E", True),
        ]

