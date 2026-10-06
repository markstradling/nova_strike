"""Enemy obstacle avoidance."""

from __future__ import annotations

import pytest

from nova_strike import config as cfg
from nova_strike.ai import PLAN_HORIZON, Plan, Track, crossing_window, plan_route
from nova_strike.enemies import Enemy
from nova_strike.game import Game
from nova_strike.obstacles import Asteroid, LaserGate, Mine, SlidingWall, Spinner, Wall

from .conftest import step


def enemy(kind: str, x: float, y: float, speed: float = 60) -> Enemy:
    e = Enemy(kind, 1)
    e.x, e.y, e.speed, e.fire_cooldown = x, y, speed, 1e9
    return e


def wall_with_gap(y: float, gap: tuple[int, int], speed: float = 0) -> Wall:
    wall = Wall(1, speed)
    wall.y = y
    wall.segments = [(0, gap[0]), (gap[1], cfg.WIDTH)]
    return wall


class TestCrossingWindow:
    def test_approaching_from_above(self) -> None:
        # obstacle 100px below, closing at 100px/s, combined half-heights 20: overlaps from 0.8s to 1.2s
        assert crossing_window(Track(0, 100, 20), Track(100, 0, 20)) == pytest.approx((0.8, 1.2))

    def test_overtaken_from_behind(self) -> None:
        # a faster obstacle catching up from above counts too
        assert crossing_window(Track(100, 50, 20), Track(0, 150, 20)) == pytest.approx((0.8, 1.2))

    def test_out_of_range_or_moving_apart(self) -> None:
        assert crossing_window(Track(0, 100, 20), Track(1000, 0, 20)) is None
        assert crossing_window(Track(0, 0, 20), Track(100, 100, 20)) is None

    def test_already_overlapping_and_matched_speed(self) -> None:
        assert crossing_window(Track(0, 50, 20), Track(5, 50, 20)) == pytest.approx((0.0, 1.6))


def test_steers_for_the_gap_in_a_wall_ahead(display: None) -> None:
    e = enemy("fighter", 100, 200, speed=100)
    plan = plan_route(e, [wall_with_gap(250, (300, 420))], [], [])
    assert plan.reason == "wall"
    assert plan.target_x is not None
    assert 300 < plan.target_x < 420
    half = e.hitbox().width / 2
    assert 300 + half <= plan.target_x <= 420 - half  # the whole ship fits


def test_picks_the_nearest_gap(display: None) -> None:
    wall = Wall(1, 0)
    wall.y = 250
    wall.segments = [(0, 60), (180, 300), (420, cfg.WIDTH)]  # gaps at 60-180 and 300-420
    plan = plan_route(enemy("scout", 270, 200, speed=100), [wall], [], [])  # behind the solid 180-300 span
    assert plan.target_x is not None
    assert 300 < plan.target_x < 420


def test_ignores_a_wall_it_is_already_lined_up_with(display: None) -> None:
    plan = plan_route(enemy("fighter", 360, 200, speed=100), [wall_with_gap(250, (300, 420))], [], [])
    assert plan == Plan()


def test_ignores_walls_too_far_ahead(display: None) -> None:
    plan = plan_route(enemy("fighter", 100, 0, speed=50), [wall_with_gap(600, (300, 420))], [], [])
    assert plan.target_x is None


def test_reacts_to_a_wall_catching_up_from_behind(display: None) -> None:
    heavy = enemy("heavy", 100, 400, speed=50)
    plan = plan_route(heavy, [wall_with_gap(250, (300, 420), speed=180)], [], [])
    assert plan.reason == "wall"


def test_aims_for_where_a_sliding_gap_will_be(display: None) -> None:
    wall = SlidingWall(3, 0)
    wall.y = 300
    e = enemy("scout", 10, 150, speed=200)
    plan = plan_route(e, [wall], [], [])
    assert plan.target_x is not None
    # where the gap will be when the enemy, at the speed it chose, reaches the wall
    me = Track(e.y, e.speed * plan.speed_scale, e.hitbox().height)
    window = crossing_window(me, Track(wall.y + wall.H / 2, 0, wall.H), PLAN_HORIZON)
    assert window is not None
    (_, left), (right, _) = wall.segments_at(window[0])
    assert left < plan.target_x < right


def test_times_a_laser_gate_to_cross_while_it_is_off(display: None) -> None:
    gate = LaserGate(1, 0)
    gate.y, gate.phase = 300, 0.0
    gate.age = gate.off_time - gate.WARN - 0.2  # about to warn, then fire
    e = enemy("fighter", 240, 200, speed=100)
    plan = plan_route(e, [], [gate], [])
    assert plan.speed_scale != 1.0
    assert plan.reason == "gate"
    window = crossing_window(Track(e.y, e.speed * plan.speed_scale, e.hitbox().height), Track(gate.y, 0, 8))
    # either it now crosses while the beam is off, or it hangs back far enough not to cross yet
    assert window is None or gate.state(ahead=window[0]) == "off"


def test_full_speed_when_the_gate_will_be_off(display: None) -> None:
    gate = LaserGate(1, 0)
    gate.y, gate.phase, gate.age = 300, 0.0, 0.0
    gate.off_time = 10.0  # off for a long while
    assert plan_route(enemy("fighter", 240, 200, speed=100), [], [gate], []).speed_scale == 1.0


@pytest.mark.parametrize(
    ("obstacle", "reason"),
    [
        (lambda: Asteroid("large", 240, 300, 0, 0), "asteroid"),
        (lambda: Mine(240, 300, 0), "mine"),
    ],
)
def test_sidesteps_obstacles_in_its_path(display: None, obstacle: object, reason: str) -> None:
    thing = obstacle()  # type: ignore[operator]
    e = enemy("fighter", 250, 200, speed=100)
    hazards = [thing] if isinstance(thing, Mine) else []
    asteroids = [thing] if isinstance(thing, Asteroid) else []
    plan = plan_route(e, [], hazards, asteroids)
    assert plan.reason == reason
    assert plan.target_x is not None
    assert plan.target_x > 250  # moves away on the side it's already leaning towards


def test_gives_a_mine_room_for_its_blast(display: None) -> None:
    e = enemy("fighter", 240 + Mine.BLAST - 5, 200, speed=100)  # would clear the mine but not its blast
    plan = plan_route(e, [], [Mine(240, 300, 0)], [])
    assert plan.reason == "mine"


def test_steers_clear_of_a_spinner(display: None) -> None:
    spinner = Spinner(1, 0)
    spinner.x, spinner.y = 240, 350
    plan = plan_route(enemy("scout", 200, 150, speed=150), [], [spinner], [])
    assert plan.reason == "spinner"
    assert plan.target_x is not None
    assert abs(plan.target_x - 240) > spinner.arm_len


def test_slows_down_to_buy_time_when_the_gap_is_too_far(display: None) -> None:
    fighter = enemy("fighter", 60, 150, speed=110)  # ~260px from the gap: too far at full speed
    plan = plan_route(fighter, [wall_with_gap(300, (300, 420))], [], [])
    assert plan.reason == "wall"
    assert plan.speed_scale < 1.0


def test_speeds_up_when_a_wall_is_catching_up_from_behind(display: None) -> None:
    heavy = enemy("heavy", 60, 400, speed=50)
    plan = plan_route(heavy, [wall_with_gap(150, (300, 420), speed=200)], [], [])
    assert plan.reason == "wall"
    assert plan.speed_scale > 1.0


def test_a_plan_moves_the_enemy_at_its_agility(display: None) -> None:
    e = enemy("heavy", 100, 100)
    e.update(0.1, 0.0, Plan(target_x=200))
    assert e.x == pytest.approx(100 + e.agility * 0.1)
    e.update(0.1, 0.0, Plan(speed_scale=0.5))
    assert e.y == pytest.approx(100 + e.speed * 0.1 + e.speed * 0.5 * 0.1)


def test_scouts_are_nimbler_than_heavies(display: None) -> None:
    assert Enemy("scout", 1).agility > Enemy("fighter", 1).agility > Enemy("heavy", 1).agility


def test_enemies_fly_through_a_wall_gap_unharmed(game: Game) -> None:
    fighter = enemy("fighter", 60, 100, speed=110)
    fighter.sway = 0
    game.enemies = [fighter]
    game.walls = [wall_with_gap(300, (300, 420))]
    step(game, 60 * 4)
    assert fighter.y > 340  # got past the wall
    assert fighter.health == fighter.max_health
