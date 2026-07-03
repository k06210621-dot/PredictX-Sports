#!/usr/bin/env python3
"""
ingest/npb_players.py
=====================
NPB 球員資料匯入腳本（手動資料源版本）
ESPN/NPB 官方均無公開 API，使用者提供 CSV/TSV 格式的 sabermetrics 資料
包含 157 位野手 + 82 位投手

執行方式：
  DATABASE_URL=xxx python3 analysis/ingest/npb_players.py
"""
import os
import sys
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

LEAGUE_CODE = "NPB"

# 球隊英文簡稱 → DB english_name
TEAM_MAP = {
    "Marines": "Chiba Lotte Marines",
    "Hawks": "Fukuoka SoftBank Hawks",
    "Tigers": "Hanshin Tigers",
    "Lions": "Saitama Seibu Lions",
    "Fighters": "Hokkaido Nippon-Ham Fighters",
    "Swallows": "Tokyo Yakult Swallows",
    "Dragons": "Chunichi Dragons",
    "BayStars": "Yokohama DeNA BayStars",
    "Giants": "Yomiuri Giants",
    "Buffaloes": "ORIX Buffaloes",
    "Golden Eagles": "Tohoku Rakuten Golden Eagles",
    "Carp": "Hiroshima Toyo Carp",
}

# 🆕 野手資料（157 位）— 從 user 提供
BATTERS = [
    # (rank, name, team_key, age, pa, avg, obp, slg, ops, wrc_plus)
    (1, "Koki Yamaguchi", "Marines", 25, 150, 0.270, 0.307, 0.596, 0.902, 164),
    (2, "Ryoya Kurihara", "Hawks", 29, 319, 0.268, 0.346, 0.579, 0.924, 169),
    (3, "Shota Morishita", "Tigers", 25, 309, 0.306, 0.385, 0.605, 0.990, 203),
    (4, "Tyler Nevin", "Lions", 29, 159, 0.291, 0.352, 0.589, 0.941, 174),
    (5, "Teruaki Sato", "Tigers", 27, 301, 0.344, 0.425, 0.637, 1.062, 221),
    (6, "Kensuke Kondoh", "Hawks", 32, 301, 0.297, 0.412, 0.586, 0.998, 191),
    (7, "Franmil Reyes", "Fighters", 30, 305, 0.326, 0.387, 0.604, 0.991, 187),
    (8, "Tomoya Masaki", "Hawks", 26, 170, 0.297, 0.394, 0.559, 0.953, 179),
    (9, "Domingo Santana", "Swallows", 33, 257, 0.259, 0.385, 0.514, 0.899, 175),
    (10, "Ruan Ohtsuka", "Fighters", 22, 80, 0.257, 0.342, 0.500, 0.842, 147),
    (11, "Miguel Sanó", "Dragons", 33, 109, 0.216, 0.284, 0.454, 0.738, 123),
    (12, "Shugo Maki", "BayStars", 28, 165, 0.303, 0.382, 0.524, 0.906, 179),
    (13, "Takumi Ohshiro", "Giants", 33, 165, 0.287, 0.352, 0.507, 0.858, 161),
    (14, "Chusei Mannami", "Fighters", 26, 285, 0.246, 0.327, 0.464, 0.792, 132),
    (15, "Toshiya Satoh", "Marines", 28, 214, 0.256, 0.364, 0.467, 0.831, 145),
    (16, "Shinya Hasegawa", "Lions", 24, 236, 0.286, 0.343, 0.490, 0.834, 145),
    (17, "Carson McCusker", "Golden Eagles", 28, 127, 0.265, 0.339, 0.469, 0.808, 137),
    (18, "Hotaka Yamakawa", "Hawks", 34, 168, 0.175, 0.292, 0.378, 0.669, 100),
    (19, "Naoki Satoh", "Golden Eagles", 27, 170, 0.274, 0.294, 0.470, 0.764, 121),
    (20, "Yutaro Itayama", "Dragons", 32, 130, 0.261, 0.315, 0.454, 0.769, 133),
    (21, "Shun Mizutani", "Fighters", 25, 121, 0.272, 0.298, 0.465, 0.762, 120),
    (22, "Bobby Dalbec", "Giants", 31, 275, 0.249, 0.327, 0.441, 0.768, 135),
    (23, "Neftali Soto", "Marines", 37, 209, 0.250, 0.321, 0.441, 0.762, 123),
    (24, "Takaya Ishikawa", "Dragons", 25, 122, 0.287, 0.328, 0.478, 0.806, 146),
    (25, "Kota Yazawa", "Fighters", 25, 94, 0.213, 0.255, 0.404, 0.660, 90),
    (26, "Trey Cabbage", "Giants", 29, 261, 0.249, 0.284, 0.438, 0.721, 119),
    (27, "Yusuke Ohyama", "Tigers", 31, 287, 0.266, 0.362, 0.452, 0.815, 146),
    (28, "Rodolfo Castro", "Fighters", 27, 154, 0.239, 0.299, 0.420, 0.719, 109),
    (29, "Yuki Nomura", "Fighters", 26, 222, 0.256, 0.284, 0.431, 0.715, 107),
    (30, "Gregory Polanco", "Marines", 34, 149, 0.188, 0.262, 0.361, 0.623, 81),
    (31, "Isami Nomura", "Hawks", 29, 102, 0.221, 0.275, 0.389, 0.664, 91),
    (32, "Kazunari Ishii", "Lions", 32, 131, 0.248, 0.282, 0.416, 0.698, 103),
    (33, "Tatsuki Mizuno", "Fighters", 25, 301, 0.311, 0.355, 0.476, 0.831, 142),
    (34, "Shogo Sakakura", "Carp", 28, 271, 0.269, 0.351, 0.433, 0.783, 137),
    (35, "Kotaro Kurebayashi", "Buffaloes", 24, 256, 0.247, 0.319, 0.410, 0.729, 113),
    (36, "Shunsuke Sasaki", "Giants", 26, 173, 0.242, 0.287, 0.404, 0.690, 105),
    (37, "Kazuya Maruyama", "Swallows", 26, 82, 0.358, 0.366, 0.519, 0.884, 171),
    (38, "Ryuya Taira", "Golden Eagles", 27, 168, 0.250, 0.299, 0.410, 0.710, 109),
    (39, "Seiya Hosokawa", "Dragons", 27, 308, 0.223, 0.357, 0.378, 0.736, 125),
    (40, "Cooper Hummel", "BayStars", 31, 148, 0.209, 0.304, 0.364, 0.668, 105),
    (41, "Elehuris Montero", "Carp", 27, 178, 0.222, 0.281, 0.377, 0.657, 96),
    (42, "Yuki Yanagita", "Hawks", 37, 245, 0.246, 0.302, 0.393, 0.695, 104),
    (43, "Sandro Fabian", "Carp", 28, 145, 0.194, 0.269, 0.341, 0.610, 85),
    (44, "Tomoya Mori", "Buffaloes", 30, 179, 0.256, 0.318, 0.402, 0.721, 112),
    (45, "Kosuke Ukai", "Dragons", 27, 153, 0.262, 0.301, 0.407, 0.708, 115),
    (46, "Alexander Canario", "Lions", 26, 276, 0.258, 0.312, 0.398, 0.710, 106),
    (47, "Yuta Ishii", "Dragons", 25, 198, 0.270, 0.303, 0.411, 0.713, 115),
    (48, "Kota Hirayama", "Giants", 22, 83, 0.291, 0.325, 0.430, 0.756, 129),
    (49, "Norihiko Nabara", "Carp", 26, 134, 0.296, 0.326, 0.432, 0.758, 128),
    (50, "Kotaro Kiyomiya", "Fighters", 27, 283, 0.239, 0.322, 0.375, 0.696, 104),
    (51, "Shogo Akiyama", "Carp", 38, 77, 0.243, 0.273, 0.378, 0.651, 95),
    (52, "Toshiro Miyazaki", "BayStars", 37, 200, 0.257, 0.330, 0.391, 0.721, 121),
    (53, "Ryo Ohta", "Buffaloes", 25, 247, 0.276, 0.360, 0.410, 0.770, 127),
    (54, "Takuma Hayashi", "BayStars", 25, 85, 0.234, 0.286, 0.364, 0.649, 90),
    (55, "Taiki Mochimaru", "Carp", 24, 158, 0.212, 0.305, 0.341, 0.646, 98),
    (56, "Yuma Mune", "Buffaloes", 30, 278, 0.238, 0.338, 0.364, 0.702, 110),
    (57, "Yuta Izuguchi", "Giants", 27, 228, 0.233, 0.313, 0.356, 0.669, 104),
    (58, "Shu Masuda", "Swallows", 27, 186, 0.278, 0.355, 0.401, 0.756, 132),
    (59, "An-ko Lin", "Lions", 29, 134, 0.189, 0.261, 0.311, 0.573, 68),
    (60, "Taiki Narama", "Fighters", 26, 146, 0.256, 0.317, 0.376, 0.693, 104),
    (61, "Kaito Muramatsu", "Dragons", 25, 296, 0.255, 0.361, 0.374, 0.735, 124),
    (62, "Tomoya Noguchi", "Buffaloes", 26, 91, 0.214, 0.247, 0.333, 0.581, 66),
    (63, "Ryusei Takeoka", "Swallows", 25, 203, 0.231, 0.302, 0.346, 0.648, 92),
    (64, "Souma Uchiyama", "Swallows", 24, 149, 0.223, 0.322, 0.338, 0.661, 104),
    (65, "Minoru Ohmori", "Carp", 29, 204, 0.240, 0.270, 0.354, 0.624, 84),
    (66, "Yuudai Yamamoto", None, 27, 153, 0.267, 0.368, 0.382, 0.750, 130),  # 無球隊
    (67, "Misho Nishikawa", "Marines", 23, 309, 0.296, 0.362, 0.411, 0.773, 128),
    (68, "Ryuki Watarai", "BayStars", 23, 261, 0.278, 0.331, 0.390, 0.721, 120),
    (69, "Kyo Suzuki", "Swallows", 20, 83, 0.198, 0.217, 0.309, 0.526, 51),
    (70, "Daisuke Nakashima", "Golden Eagles", 25, 162, 0.222, 0.282, 0.333, 0.615, 79),
    (71, "Yua Tamiya", "Fighters", 26, 196, 0.291, 0.317, 0.401, 0.719, 108),
    (72, "Yoshi Tsutsugo", "BayStars", 34, 162, 0.226, 0.340, 0.336, 0.675, 110),
    (73, "Ukyo Maegawa", "Tigers", 23, 72, 0.234, 0.319, 0.344, 0.663, 104),
    (74, "Hideto Asamura", "Golden Eagles", 35, 251, 0.227, 0.315, 0.336, 0.651, 92),
    (75, "Ryosuke Tatsumi", "Golden Eagles", 29, 307, 0.282, 0.373, 0.391, 0.764, 125),
    (76, "Keita Sano", "BayStars", 31, 290, 0.249, 0.334, 0.358, 0.692, 113),
    (77, "José Osuna", "Swallows", 33, 222, 0.227, 0.284, 0.335, 0.619, 86),
    (78, "Yuto Koga", "Lions", 26, 155, 0.298, 0.380, 0.405, 0.785, 133),
    (79, "Seiya Watanabe", "Lions", 23, 315, 0.253, 0.289, 0.360, 0.649, 89),
    (80, "Keita Nakagawa", "Buffaloes", 30, 268, 0.261, 0.322, 0.365, 0.687, 101),
    (81, "Yoshihiro Akahane", "Swallows", 26, 116, 0.241, 0.281, 0.343, 0.623, 87),
    (82, "Asahi Miyashita", "BayStars", 22, 72, 0.203, 0.225, 0.304, 0.530, 50),
    (83, "Junichiro Kishi", "Lions", 29, 113, 0.202, 0.257, 0.303, 0.560, 61),
    (84, "Ryoma Nishikawa", "Buffaloes", 31, 319, 0.297, 0.333, 0.397, 0.730, 113),
    (85, "Riku Masuda", "Giants", 26, 113, 0.255, 0.265, 0.355, 0.620, 83),
    (86, "Yukinori Kishida", "Giants", 29, 149, 0.267, 0.324, 0.366, 0.691, 108),
    (87, "Toshiki Abe", "Dragons", 36, 97, 0.284, 0.385, 0.383, 0.768, 135),
    (88, "Masayuki Kuwahara", "Lions", 32, 214, 0.242, 0.310, 0.340, 0.650, 91),
    (89, "Taiga Hirasawa", "Lions", 28, 172, 0.277, 0.339, 0.374, 0.713, 110),
    (90, "Itsuki Murabayashi", "Golden Eagles", 28, 288, 0.282, 0.340, 0.378, 0.719, 106),
    (91, "Daito Yamamoto", "Marines", 23, 83, 0.178, 0.265, 0.274, 0.539, 60),
    (92, "Ryui Itoh", "Swallows", 23, 106, 0.160, 0.240, 0.255, 0.496, 39),
    (93, "Bob Seymour", "Buffaloes", 27, 141, 0.162, 0.184, 0.257, 0.442, 23),
    (94, "Masahiro Tateishi", "Tigers", 22, 86, 0.202, 0.221, 0.298, 0.519, 50),
    (95, "Jason Vosler", "Dragons", 32, 162, 0.203, 0.265, 0.297, 0.563, 69),
    (96, "Yoshiaki Watanabe", "Golden Eagles", 29, 119, 0.264, 0.316, 0.358, 0.674, 97),
    (97, "Tatsuo Ebina", "BayStars", 28, 238, 0.239, 0.316, 0.333, 0.650, 98),
    (98, "Haruto Watanabe", "Buffaloes", 26, 167, 0.264, 0.356, 0.357, 0.713, 113),
    (99, "Raito Ikeda", "Marines", 26, 70, 0.269, 0.279, 0.358, 0.638, 82),
    (100, "Kyota Fujiwara", "Marines", 26, 163, 0.294, 0.405, 0.382, 0.787, 137),
    (101, "Tai Sasaki", "Carp", 23, 170, 0.220, 0.266, 0.308, 0.574, 72),
    (102, "Hayato Sakamoto", "Giants", 37, 92, 0.145, 0.217, 0.229, 0.446, 32),
    (103, "Yuya Gunji", "Fighters", 28, 218, 0.221, 0.317, 0.305, 0.622, 86),
    (104, "Takashi Umino", "Hawks", 28, 174, 0.189, 0.244, 0.270, 0.514, 48),
    (105, "Kenya Wakatsuki", "Buffaloes", 30, 188, 0.216, 0.282, 0.296, 0.579, 66),
    (106, "Nozomu Takatera", "Tigers", 23, 204, 0.227, 0.322, 0.307, 0.629, 91),
    (107, "Manaya Nishikawa", "Lions", 27, 191, 0.212, 0.230, 0.291, 0.520, 46),
    (108, "Taiki Ishikami", "BayStars", 25, 72, 0.188, 0.243, 0.266, 0.508, 39),
    (109, "Ryosuke Kikuchi", "Carp", 36, 251, 0.244, 0.332, 0.321, 0.653, 100),
    (110, "Taiga Kojima", "Lions", 22, 166, 0.247, 0.265, 0.321, 0.586, 66),
    (111, "Shion Matsuo", "BayStars", 21, 147, 0.263, 0.303, 0.336, 0.639, 86),
    (112, "Atsushi Katsumata", "BayStars", 26, 185, 0.313, 0.326, 0.385, 0.712, 113),
    (113, "Tatsuru Yanagimachi", "Hawks", 29, 159, 0.239, 0.323, 0.312, 0.634, 87),
    (114, "Seishiro Sakamoto", "Tigers", 32, 144, 0.195, 0.250, 0.266, 0.516, 52),
    (115, "Yota Kyoda", "BayStars", 32, 108, 0.250, 0.299, 0.320, 0.619, 87),
    (116, "Ukyo Shuto", "Hawks", 30, 285, 0.271, 0.339, 0.340, 0.679, 100),
    (117, "Ren Hirakawa", "Carp", 22, 109, 0.186, 0.231, 0.255, 0.486, 39),
    (118, "Kaito Kozono", "Carp", 26, 278, 0.241, 0.303, 0.308, 0.612, 85),
    (119, "Taisei Makihara", "Hawks", 33, 269, 0.287, 0.330, 0.352, 0.682, 98),
    (120, "Kein Fukushima", "Tigers", 24, 122, 0.241, 0.322, 0.306, 0.628, 91),
    (121, "Ryusei Terachi", "Marines", 20, 217, 0.175, 0.245, 0.237, 0.482, 40),
    (122, "Hideki Nagaoka", "Swallows", 24, 237, 0.239, 0.306, 0.300, 0.607, 84),
    (123, "Raito Nakayama", "Giants", 24, 96, 0.174, 0.250, 0.233, 0.483, 44),
    (124, "Sosuke Genda", "Lions", 33, 183, 0.192, 0.273, 0.250, 0.523, 54),
    (125, "Kenta Imamiya", "Hawks", 34, 117, 0.208, 0.261, 0.264, 0.525, 52),
    (126, "Ryoto Kita", "Buffaloes", 23, 101, 0.242, 0.283, 0.297, 0.580, 66),
    (127, "Yukihiro Iwata", "Swallows", 28, 238, 0.262, 0.308, 0.317, 0.625, 88),
    (128, "Ryoma Yamanaka", "Buffaloes", 25, 126, 0.327, 0.389, 0.381, 0.769, 127),
    (129, "Seiya Kinami", "Tigers", 32, 126, 0.252, 0.310, 0.304, 0.614, 86),
    (130, "Yuki Okabayashi", "Dragons", 24, 110, 0.302, 0.352, 0.354, 0.706, 113),
    (131, "Yudai Koga", "Swallows", 27, 174, 0.275, 0.312, 0.325, 0.637, 90),
    (132, "Takumu Nakano", "Tigers", 30, 297, 0.303, 0.350, 0.352, 0.702, 113),
    (133, "Mikiya Tanaka", "Dragons", 25, 213, 0.235, 0.300, 0.284, 0.585, 72),
    (134, "Fumiya Kurokawa", "Golden Eagles", 25, 293, 0.263, 0.346, 0.310, 0.656, 96),
    (135, "Shunsuke Urata", "Giants", 23, 219, 0.267, 0.316, 0.313, 0.629, 88),
    (136, "Hiroki Fukunaga", "Dragons", 29, 173, 0.235, 0.324, 0.281, 0.605, 86),
    (137, "Luke Voit", "Golden Eagles", 35, 74, 0.119, 0.189, 0.164, 0.353, -3),
    (138, "Go Matsumoto", "Giants", 32, 183, 0.286, 0.343, 0.329, 0.672, 106),
    (139, "Koji Chikamoto", "Tigers", 31, 110, 0.250, 0.336, 0.292, 0.628, 94),
    (140, "Natsuo Takizawa", "Lions", 22, 264, 0.279, 0.371, 0.320, 0.690, 108),
    (141, "Yuya Ogoh", "Golden Eagles", 29, 110, 0.231, 0.266, 0.269, 0.535, 54),
    (142, "Hiroto Kobukata", "Golden Eagles", 30, 120, 0.198, 0.261, 0.236, 0.497, 45),
    (143, "Atsuki Tomosugi", "Marines", 25, 233, 0.252, 0.292, 0.290, 0.582, 69),
    (144, "Hikaru Ohta", "Golden Eagles", 29, 158, 0.239, 0.301, 0.275, 0.576, 70),
    (145, "Ryuhei Obata", "Tigers", 25, 96, 0.233, 0.290, 0.267, 0.558, 61),
    (146, "Takahiro Kumagai", "Tigers", 30, 100, 0.236, 0.269, 0.270, 0.538, 59),
    (147, "Ryusei Ogawa", "Marines", 28, 248, 0.273, 0.303, 0.303, 0.606, 76),
    (148, "Yudai Shoji", "Hawks", 23, 128, 0.250, 0.358, 0.279, 0.637, 93),
    (149, "Masaki Mimori", "BayStars", 27, 116, 0.259, 0.302, 0.287, 0.589, 76),
    (150, "Torai Fushimi", "Tigers", 36, 88, 0.195, 0.250, 0.221, 0.471, 39),
    (151, "Masahiro Nishino", "Buffaloes", 35, 85, 0.182, 0.241, 0.208, 0.449, 31),
    (152, "Naoki Yoshikawa", "Giants", 31, 129, 0.215, 0.264, 0.240, 0.503, 47),
    (153, "Naru Katsuda", "Carp", 23, 110, 0.184, 0.252, 0.204, 0.456, 30),
    (154, "Akito Takabe", "Marines", 28, 130, 0.213, 0.262, 0.230, 0.491, 42),
    (155, "Takayoshi Noma", "Carp", 33, 81, 0.225, 0.309, 0.239, 0.548, 68),
    (156, "Shosei Nakamura", "Carp", 27, 81, 0.181, 0.213, 0.194, 0.408, 16),
    (157, "Shuhei Takahashi", "Dragons", 32, 83, 0.274, 0.354, 0.288, 0.641, 99),
]

# 🆕 投手資料（82 位）
PITCHERS = [
    (1, "Naruki Teranishi", "Buffaloes", 23, 34.0, 4.76, 2.19, 7.68, 1.44),
    (2, "Taisei Irie", "BayStars", 27, 30.0, 7.50, 4.97, 9.30, 1.73),
    (3, "Hiroto Takahashi", "Dragons", 23, 53.2, 4.86, 2.61, 9.73, 1.51),
    (4, "Yorinosuke Sakurai", "Dragons", 22, 47.2, 5.66, 3.50, 9.82, 1.51),
    (5, "Freddy Tarnok", "Carp", 27, 42.2, 4.22, 2.06, 8.86, 1.38),
    (6, "Kohei Arihara", "Fighters", 33, 40.1, 6.47, 4.52, 5.80, 1.54),
    (7, "Kentaro Shinogi", "BayStars", 24, 34.0, 4.50, 2.83, 8.21, 1.38),
    (8, "Carter Stewart, Jr.", "Hawks", 26, 41.1, 5.66, 4.21, 8.71, 1.69),
    (9, "Daiki Tajima", "Buffaloes", 29, 41.2, 5.83, 4.54, 6.05, 1.39),
    (10, "Kentaro Taira", "BayStars", 30, 50.0, 4.14, 2.95, 9.36, 1.22),
    (11, "Hiroto Saiki", "Tigers", 27, 82.1, 3.06, 2.04, 11.48, 1.03),
    (12, "Yasuhiro Ogawa", "Swallows", 36, 38.0, 5.45, 4.62, 6.39, 1.39),
    (13, "Masahiro Tanaka", "Giants", 37, 53.2, 3.52, 2.72, 6.71, 1.40),
    (14, "Yutaro Ishida", "BayStars", 24, 78.0, 3.00, 2.26, 8.88, 1.14),
    (15, "Haruya Tanaka", "Marines", 22, 50.1, 4.83, 4.12, 7.33, 1.45),
    (16, "Jo-Hsi Hsu", "Hawks", 25, 30.2, 4.99, 4.30, 8.22, 1.60),
    (17, "Kaito Mouri", "Marines", 22, 48.0, 5.25, 4.56, 5.81, 1.40),
    (18, "Tomohisa Ohzeki", "Hawks", 28, 47.0, 5.55, 4.88, 5.36, 1.55),
    (19, "Taito Takashima", "Buffaloes", 26, 43.2, 3.71, 3.06, 7.63, 1.42),
    (20, "Kota Tatsu", "Fighters", 22, 63.2, 3.82, 3.23, 7.77, 1.10),
    (21, "Kosei Shoji", "Golden Eagles", 25, 79.0, 4.22, 3.69, 9.68, 1.22),
    (22, "Allen Kuri", "Buffaloes", 34, 88.0, 3.07, 2.58, 9.00, 1.11),
    (23, "Sam Long", "Marines", 30, 31.2, 3.98, 3.62, 6.25, 1.33),
    (24, "Haru Matsumoto", "Hawks", 25, 60.1, 3.88, 3.53, 10.14, 1.36),
    (25, "Natsuki Takeuchi", "Lions", 24, 74.2, 2.77, 2.51, 8.08, 1.04),
    (26, "Masato Morishita", "Carp", 28, 72.2, 4.21, 3.96, 7.56, 1.35),
    (27, "Haruki Hosono", "Fighters", 24, 50.0, 3.06, 2.81, 10.80, 0.92),
    (28, "Kyle Muller", "Dragons", 28, 57.0, 2.84, 2.64, 7.11, 0.98),
    (29, "Masaru Fujii", "Golden Eagles", 29, 39.0, 3.69, 3.50, 5.77, 1.28),
    (30, "Yuji Nishino", "Marines", 35, 34.2, 4.41, 4.28, 4.67, 1.27),
    (31, "Tatsuki Koja", "Golden Eagles", 24, 56.0, 4.02, 3.90, 7.39, 1.18),
    (32, "Sean Reynolds", "BayStars", 28, 32.0, 1.41, 1.33, 12.38, 0.81),
    (33, "Chihiro Sumida", "Lions", 26, 90.0, 2.30, 2.23, 8.70, 0.96),
    (34, "Anderson Espinoza", "Buffaloes", 28, 76.0, 2.49, 2.44, 8.41, 1.07),
    (35, "Takahiro Norimoto", "Giants", 35, 46.0, 3.91, 3.92, 6.26, 1.37),
    (36, "Kazuyuki Takemaru", "Giants", 24, 67.0, 2.96, 2.98, 9.00, 1.22),
    (37, "Yutaro Watanabe", "Lions", 25, 79.1, 3.18, 3.22, 6.01, 1.10),
    (38, "Ryuhei Sotani", "Buffaloes", 25, 49.2, 3.08, 3.13, 8.15, 1.05),
    (39, "Haruto Inoue", "Giants", 25, 74.0, 2.31, 2.37, 9.12, 0.99),
    (40, "Allan Winans", "Lions", 30, 38.2, 4.19, 4.26, 8.15, 1.34),
    (41, "Koshiro Hiroike", "Marines", 23, 60.0, 3.30, 3.37, 6.30, 1.10),
    (42, "Kojiro Yoshimura", "Swallows", 28, 55.1, 3.74, 3.81, 6.18, 1.01),
    (43, "Shosei Togo", "Giants", 26, 47.1, 2.47, 2.60, 9.51, 1.08),
    (44, "Kenta Maeda", "Golden Eagles", 38, 30.2, 3.52, 3.68, 7.63, 1.37),
    (45, "Haruto Takahashi", "Tigers", 30, 90.2, 1.39, 1.61, 8.44, 0.74),
    (46, "Yuya Yanagi", "Dragons", 32, 88.2, 2.33, 2.57, 8.12, 1.22),
    (47, "José Ureña", "Golden Eagles", 34, 38.2, 3.49, 3.74, 6.75, 1.45),
    (48, "Yasunobu Okugawa", "Swallows", 25, 73.1, 2.70, 2.96, 7.24, 1.06),
    (49, "Yumeto Kanemaru", "Dragons", 23, 82.1, 2.62, 2.91, 7.43, 1.25),
    (50, "Hiromi Itoh", "Fighters", 28, 94.1, 2.96, 3.25, 8.40, 1.22),
    (51, "Koki Kitayama", "Fighters", 27, 86.1, 1.98, 2.28, 8.44, 0.95),
    (52, "Andre Jackson", "Marines", 30, 79.2, 3.28, 3.59, 8.59, 1.15),
    (53, "Sean Hjelle", "Buffaloes", 29, 65.0, 2.08, 2.40, 7.48, 1.18),
    (54, "Takahisa Hayakawa", "Golden Eagles", 27, 67.0, 2.28, 2.62, 9.40, 0.94),
    (55, "Ren Fukushima", "Fighters", 23, 51.2, 2.26, 2.64, 8.71, 1.14),
    (56, "Kazuya Ojima", "Marines", 29, 51.0, 3.00, 3.40, 7.06, 1.18),
    (57, "Katsuki Azuma", "BayStars", 30, 83.1, 2.27, 2.69, 6.91, 0.97),
    (58, "Forrest Whitley", "Giants", 28, 58.2, 2.61, 3.05, 9.97, 0.97),
    (59, "Shun Okamoto", "Carp", 24, 74.0, 2.68, 3.18, 7.66, 1.15),
    (60, "Kengo Matsumoto", "Swallows", 27, 60.2, 2.52, 3.03, 8.16, 1.17),
    (61, "Shuto Ogata", None, 27, 31.2, 3.13, 3.65, 12.22, 1.11),  # 無球隊
    (62, "Hiroki Tokoda", "Carp", 31, 74.1, 2.54, 3.09, 6.05, 1.22),
    (63, "Ryoji Kuribayashi", "Carp", 29, 47.0, 1.15, 1.73, 8.23, 0.55),
    (64, "Hirotoshi Takanashi", "Swallows", 35, 59.1, 2.73, 3.37, 7.89, 1.10),
    (65, "Taichi Yamano", "Swallows", 27, 82.1, 2.08, 2.81, 7.98, 1.01),
    (66, "Shinya Sugai", "Lions", 23, 38.1, 3.05, 3.80, 4.70, 1.23),
    (67, "Shogo Tamamura", "Carp", 25, 47.0, 2.30, 3.05, 5.94, 0.98),
    (68, "Shoki Murakami", "Tigers", 28, 97.1, 2.13, 2.96, 7.49, 0.95),
    (69, "Ryota Takinaka", "Golden Eagles", 31, 60.0, 2.25, 3.10, 6.15, 1.23),
    (70, "Koutaro Ohtake", "Tigers", 31, 62.0, 2.18, 3.06, 5.66, 1.06),
    (71, "Yuji Akahoshi", "Giants", 26, 31.2, 1.71, 2.67, 6.82, 0.95),
    (72, "Takayuki Katoh", "Fighters", 34, 68.1, 2.50, 3.48, 4.08, 0.85),
    (73, "Naoyuki Uwasawa", "Hawks", 32, 60.1, 2.54, 3.55, 7.61, 1.14),
    (74, "Yudai Ohno", "Dragons", 37, 73.0, 2.10, 3.23, 6.53, 0.93),
    (75, "Ryosuke Ohtsu", "Hawks", 27, 83.1, 1.73, 2.93, 7.99, 0.92),
    (76, "Kaima Taira", "Lions", 26, 77.0, 1.05, 2.44, 8.30, 0.88),
    (77, "Kona Takahashi", "Lions", 29, 86.1, 1.36, 2.79, 7.19, 0.87),
    (78, "Yugo Maeda", "Hawks", 20, 44.0, 1.84, 3.54, 7.36, 1.05),
    (79, "Akira Yagi", "Marines", 29, 32.1, 1.39, 3.11, 5.57, 1.02),
    (80, "Yuki Nishi", "Tigers", 35, 30.0, 2.40, 4.20, 5.10, 1.13),
    (81, "Taiga Kamichatani", "Hawks", 29, 30.2, 2.35, 4.43, 6.75, 1.30),
    (82, "Rikuto Yokoyama", "Marines", 24, 33.0, 1.36, 3.62, 6.55, 0.97),
]


def map_team_id(team_key, cur) -> str:
    if not team_key:
        return None
    db_name = TEAM_MAP.get(team_key)
    if not db_name:
        return None
    cur.execute("SELECT team_id FROM predictx.teams WHERE league = %s AND english_name = %s",
                (LEAGUE_CODE, db_name))
    row = cur.fetchone()
    return row["team_id"] if row else None


def upsert_player(cur, external_id: str, name: str, position: str, jersey=None) -> str:
    cur.execute("SELECT player_id FROM predictx.players WHERE external_id = %s", (external_id,))
    if cur.fetchone():
        return cur.fetchone()["player_id"]
    cur.execute(
        """
        INSERT INTO predictx.players (external_id, player_name, position, jersey_number, created_at, updated_at)
        VALUES (%s, %s, %s, %s, NOW(), NOW())
        RETURNING player_id
        """,
        (external_id, name, position, jersey),
    )
    return cur.fetchone()["player_id"]


def upsert_player_team(cur, player_id: str, team_id: str) -> bool:
    cur.execute(
        "SELECT id FROM predictx.player_teams WHERE player_id = %s::uuid AND team_id = %s::uuid",
        (player_id, team_id),
    )
    if cur.fetchone():
        return False
    cur.execute(
        "INSERT INTO predictx.player_teams (player_id, team_id, is_active) VALUES (%s::uuid, %s::uuid, true)",
        (player_id, team_id),
    )
    return True


def run(dry_run: bool = False) -> dict:
    result = {"teams_processed": 0, "batters_inserted": 0, "pitchers_inserted": 0, "errors": []}

    if dry_run:
        logger.info(f"野手: {len(BATTERS)} 位")
        logger.info(f"投手: {len(PITCHERS)} 位")
        # 統計球隊
        teams = set()
        for r in BATTERS:
            if r[2]: teams.add(r[2])
        for r in PITCHERS:
            if r[2]: teams.add(r[2])
        logger.info(f"涵蓋球隊: {len(teams)} 隊 ({sorted(teams)})")
        return result

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL 未設定")
    import psycopg2, psycopg2.extras
    conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()

    # 處理野手
    logger.info("=== 野手匯入 ===")
    team_processed = set()
    for rank, name, team_key, age, pa, avg, obp, slg, ops, wrc in BATTERS:
        try:
            team_id = map_team_id(team_key, cur)
            if not team_id:
                result["errors"].append(f"野手 {name} (rank={rank}): 球隊 {team_key} 不存在")
                continue
            ext_id = f"NPB-B-{rank:03d}"
            pid = upsert_player(cur, ext_id, name, "野手")
            if upsert_player_team(cur, pid, team_id):
                result["batters_inserted"] += 1
                team_processed.add(team_id)
        except Exception as e:
            result["errors"].append(f"野手 {name}: {e}")
    conn.commit()

    # 處理投手
    logger.info("=== 投手匯入 ===")
    for rank, name, team_key, age, ip, era, fip, k9, whip in PITCHERS:
        try:
            team_id = map_team_id(team_key, cur)
            if not team_id:
                result["errors"].append(f"投手 {name} (rank={rank}): 球隊 {team_key} 不存在")
                continue
            ext_id = f"NPB-P-{rank:03d}"
            pid = upsert_player(cur, ext_id, name, "投手")
            if upsert_player_team(cur, pid, team_id):
                result["pitchers_inserted"] += 1
                team_processed.add(team_id)
        except Exception as e:
            result["errors"].append(f"投手 {name}: {e}")
    conn.commit()

    result["teams_processed"] = len(team_processed)
    cur.close()
    conn.close()
    return result


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    out = run(dry_run=args.dry_run)
    print("\n=== 結果 ===")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    sys.exit(0 if not out.get("errors") else 1)
