import unittest
from radar.scoring import DIMENSIONS, asset_level, asset_pool, investment_level, normalized_scores

class ScoringTests(unittest.TestCase):
    def test_best_case_is_100(self):
        scores,total=normalized_scores({key:5 for key in DIMENSIONS})
        self.assertEqual(100,total);self.assertEqual(11,len(scores))
    def test_profile_blends_reuse_dimensions(self):
        profile={"channel_capability":5,"ua_capability":5,"creative_capability":5,"localization_ops_capability":5}
        scores,_=normalized_scores({key:1 for key in DIMENSIONS},profile)
        self.assertEqual(3,scores["channel_reuse"]);self.assertEqual(1,scores["product_access"])
    def test_values_are_clamped(self):
        scores,_=normalized_scores({"product_access":99,"cash_exposure":-4})
        self.assertEqual(5,scores["product_access"]);self.assertEqual(1,scores["cash_exposure"])
    def test_levels_and_backward_pool(self):
        self.assertEqual("L1",investment_level(50000,4,2));self.assertEqual("L4",investment_level(100000,4,13));self.assertEqual("light",asset_level(50000,100000));self.assertEqual("medium",asset_level(150000,500000));self.assertEqual("heavy",asset_level(300000,500001));self.assertEqual("light",asset_pool("L2"))

if __name__=="__main__":unittest.main()
