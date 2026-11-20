"""手游发行机会的可解释适配度评分与投入分级。"""

DIMENSIONS = (
    "channel_reuse", "ua_reuse", "creative_reuse", "localization_ops_reuse",
    "product_access", "unit_economics_verifiability", "cash_exposure",
    "payback_speed", "copyright_compliance", "delivery_simplicity",
    "strategic_synergy",
)

PROFILE_BLEND = {
    "channel_reuse": "channel_capability",
    "ua_reuse": "ua_capability",
    "creative_reuse": "creative_capability",
    "localization_ops_reuse": "localization_ops_capability",
}


def _score(value):
    try:
        return min(5, max(1, int(value)))
    except (TypeError, ValueError):
        return 3


def normalized_scores(values, profile=None):
    """11 项均为越高越适配；前四项与公司能力画像各占一半。"""
    scores = {key: _score((values or {}).get(key, 3)) for key in DIMENSIONS}
    if profile:
        for dimension, capability in PROFILE_BLEND.items():
            scores[dimension] = round((scores[dimension] + _score(profile.get(capability, 3))) / 2)
    return scores, round(sum(scores.values()) * 100 / 55, 1)


def investment_level(budget_cny, cycle_weeks, team_size):
    budget_cny = max(0, float(budget_cny or 0)); cycle_weeks = max(0, int(cycle_weeks or 0)); team_size = max(0, int(team_size or 0))
    for budget, weeks, people, level in ((50000,4,2,"L1"),(200000,12,5,"L2"),(800000,24,12,"L3")):
        if budget_cny <= budget and cycle_weeks <= weeks and team_size <= people:
            return level
    return "L4"


def asset_level(budget_30d, budget_scale):
    """以 30 天试验和扩大验证预算确定轻/中/重资产。"""
    peak = max(float(budget_30d or 0), float(budget_scale or 0))
    if peak <= 100000: return "light"
    if peak <= 500000: return "medium"
    return "heavy"


def asset_pool(level):
    return "light" if level in {"light", "L1", "L2"} else "heavy"
