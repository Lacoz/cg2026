import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from game_sim import Board, BotSession, SEED_4034019036303909000, run_bot_once

BOT = ROOT / "bot.py"


class SimTests(unittest.TestCase):
    def test_sequential_move_budget(self):
        opts = """seed=1
units=2,0_2,0_2,0_0,0_0,3_0,3
edges=0,1_0,2_0,3_1,3_2,3_3,4_3,5_4,5
nodes=500,500_600,400_600,600_700,500_800,300_800,500"""
        b = Board.from_game_options(opts)
        b.play_turn("MOVE 3 4 1;MOVE 1 3 2;MOVE 3 5 2", "")
        self.assertEqual(b.units[1][0], 0)
        self.assertEqual(b.units[3][0], 2)
        self.assertGreaterEqual(b.units[5][0], 0)

    def test_seed_start_units(self):
        b = Board.from_game_options(SEED_4034019036303909000)
        self.assertEqual(b.units[14], [1, 0])
        self.assertEqual(b.units[33], [1, 0])
        self.assertEqual(b.units[44], [1, 0])

    def test_seed_best_triangle_is_3_33_44(self):
        b = Board.from_game_options(SEED_4034019036303909000)
        starts = [14, 33, 44]

        def reach(t):
            a, bb, c = t.corners()
            s = 0
            for corner in (a, bb, c):
                s += min(b.bfs_dist(corner).get(u, 999) for u in starts)
            return s

        tris = sorted(b.triangles, key=reach)
        self.assertEqual(frozenset(tris[0].corners()), frozenset((3, 33, 44)))
        self.assertLessEqual(reach(tris[0]), 2)

    def test_bot_turn1_targets_local_triangle(self):
        b = Board.from_game_options(SEED_4034019036303909000)
        out = run_bot_once(b, BOT)
        self.assertIn("MOVE 14 3 1", out)

    def test_solo_capture_and_spawn(self):
        b = Board.from_game_options(SEED_4034019036303909000)
        bot = BotSession(BOT)
        bot.start(b)
        try:
            captured = False
            for _ in range(12):
                cmd = bot.turn(b)
                b.play_turn(cmd, "")
                if any(t.owner == 0 for t in b.triangles):
                    captured = True
                if captured and b.total_units(0) > 3:
                    break
        finally:
            bot.close()
        self.assertTrue(captured, "bot never captured triangle solo")
        self.assertGreater(b.total_units(0), 3)

    def test_contested_allows_move_in_referee(self):
        opts = """seed=1
units=1,1_0,0_0,0
edges=0,1_1,2
nodes=0,0_100,0_200,0"""
        b = Board.from_game_options(opts)
        b.play_turn("MOVE 0 1 1", "")
        self.assertEqual(b.units[0][0], 0)
        self.assertEqual(b.units[1][0], 1)


if __name__ == "__main__":
    unittest.main()
