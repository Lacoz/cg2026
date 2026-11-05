import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from game_sim import Board, BotSession, SEED_4034019036303909000

BOT = ROOT / "bot.py"

# square 0-1-2-3 with diagonal 0-2, plus house 4 right of the 1-2 edge
SQUARE = """seed=1
units=0,0_1,0_1,0_0,0_1,0
edges=0,1_1,2_2,3_0,3_0,2_1,4_2,4
nodes=0,0_100,0_100,100_0,100_200,50"""


def tri(b, *cs):
    return next((t for t in b.triangles if set(t.corners()) == set(cs)), None)


def own(t, pid=0):
    t.owner = pid
    t.initial_owner = pid


class PathRuleTests(unittest.TestCase):
    def test_remove_path_destroys_triangles(self):
        b = Board.from_game_options(SQUARE)
        own(tri(b, 1, 2, 4))
        b.play_turn("REMOVE_PATH 2 1 4 0", "")
        self.assertNotIn(0, b.adj[2])
        self.assertIsNone(tri(b, 0, 1, 2))
        self.assertIsNone(tri(b, 0, 2, 3))
        self.assertIsNone(tri(b, 1, 2, 4).owner)
        self.assertEqual([b.units[n][0] for n in (1, 2, 4)], [0, 0, 0])

    def test_remove_path_cannot_cut_own_triangle(self):
        b = Board.from_game_options(SQUARE)
        own(tri(b, 1, 2, 4))
        b.play_turn("REMOVE_PATH 1 2 4 2", "")
        self.assertIn(2, b.adj[1])
        self.assertEqual(tri(b, 1, 2, 4).owner, 0)

    def test_add_path_creates_fresh_triangles(self):
        b = Board.from_game_options(SQUARE)
        b.disconnect(0, 2)
        self.assertIn("0 2", b.bot_input(0).splitlines())
        own(tri(b, 1, 2, 4))
        b.play_turn("ADD_PATH 1 2 4 3", "")
        self.assertIn(3, b.adj[1])
        for cs in ((0, 1, 3), (1, 2, 3)):
            t = tri(b, *cs)
            self.assertIsNotNone(t)
            self.assertIsNone(t.owner)
            self.assertEqual(t.can_capture, [True, True])

    def test_add_path_rejects_crossing(self):
        b = Board.from_game_options(SQUARE)
        own(tri(b, 1, 2, 4))
        b.play_turn("ADD_PATH 1 2 4 3", "")
        self.assertNotIn(3, b.adj[1])
        self.assertEqual(tri(b, 1, 2, 4).owner, 0)


class BotPathChurnTests(unittest.TestCase):
    def test_bot_survives_changing_paths(self):
        """Paths change every turn (triangles appear and disappear): the bot must keep answering
        and only use triangles that exist and that it owns."""
        b = Board.from_game_options(SEED_4034019036303909000)
        rng = random.Random(7)
        bot = BotSession(BOT)
        bot.start(b)
        drops = 0
        try:
            for turn in range(60):
                cmd = bot.turn(b)
                for part in cmd.split(";"):
                    f = part.split()
                    if f and f[0] in ("SPAWN", "ATTACK", "ADD_PATH", "REMOVE_PATH"):
                        t = tri(b, *map(int, f[1:4]))
                        self.assertIsNotNone(t, f"turn {turn}: unknown triangle in {part}")
                        self.assertEqual(t.owner, 0, f"turn {turn}: not our triangle in {part}")
                b.play_turn(cmd, "")
                before = len(b.triangles)
                if rng.random() < 0.5:
                    edges = b.edges()
                    b.disconnect(*edges[rng.randrange(len(edges))])
                else:
                    links = b.linkable()
                    if links:
                        b.connect(*links[rng.randrange(len(links))])
                drops += len(b.triangles) < before
        finally:
            bot.close()
        self.assertGreater(drops, 0)


if __name__ == "__main__":
    unittest.main()
