from .base import PublicJsonMixin, Signal


class GameMarketAdapter(PublicJsonMixin):
    key = "game_market"
    name = "游戏市场公开信号示例"
    category = "game"

    def collect(self, config):
        if config.get("public_json_url"):
            return [Signal(**item) for item in self.read_public_json(config["public_json_url"])]
        return [
            Signal("独立游戏团队缺少轻量竞品情报流水线", "榜单、更新、评价和商业化证据分散；本条仅用于演示。", "game", "内置游戏示例数据", "https://example.com/demo/game-intel", "演示场景，无实际观察期", "全球", "需求信号", "演示值", "非市场统计", "demo", "E", True),
            Signal("AI NPC 工具需先验证创作效率与玩家留存", "技术展示不等于付费与留存，应先做可量化垂直切片；本条为演示假设。", "ai_game", "内置游戏示例数据", "https://example.com/demo/ai-npc", "演示场景，无实际观察期", "全球", "验证优先级", "高", "演示判断", "demo", "E", True),
        ]

