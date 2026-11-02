from flat_bot.extract import (
    listing_from_text, parse_floor, parse_kitchen, parse_material, parse_metro_walk,
    parse_price, parse_range_minutes, parse_rooms, parse_year,
)
from flat_bot.models import Material


def test_price():
    assert parse_price("11 500 000 ₽") == 11_500_000
    assert parse_price("Цена 9 990 000 руб.") == 9_990_000
    assert parse_price("10,5 млн") == 10_500_000
    assert parse_price("3 мин пешком") is None


def test_rooms():
    assert parse_rooms("2-к. квартира, 54 м², 5/9 эт.") == (2, False)
    assert parse_rooms("Квартира-студия, 25 м²") == (0, False)
    assert parse_rooms("Евро-2, 40 м²") == (1, True)
    assert parse_rooms("Продаётся трёхкомнатная квартира") == (3, False)
    assert parse_rooms("1-комн. квартира") == (1, False)


def test_floor_kitchen_year_material():
    assert parse_floor("2-к. квартира, 54 м², 5/9 эт.") == (5, 9)
    assert parse_floor("Этаж: 3 из 12") == (3, 12)
    assert parse_kitchen("Площадь кухни: 12,5 м²") == 12.5
    assert parse_kitchen("Кухня 14 м²") == 14
    assert parse_year("Год постройки: 1978") == 1978
    assert parse_material("Тип дома: кирпичный") == Material.BRICK
    assert parse_material("Тип дома: панельный") == Material.PANEL
    assert parse_material("Тип дома: монолитно-кирпичный") == Material.MONOLITH_BRICK
    assert parse_material("Продаётся квартира в кирпичном доме") == Material.BRICK


def test_metro():
    assert parse_metro_walk("Пионерская, 7 мин. пешком; Удельная 20 минут пешком") == 7
    assert parse_range_minutes("Московская 6–10 мин.") == 10
    assert parse_range_minutes("до 5 мин.") == 5
    assert parse_range_minutes("от 31 мин.") == 46


def test_listing_from_detail_text():
    text = ("1-к. квартира, 42 м², 4/9 эт. 11 200 000 ₽ Общая площадь: 42 м² "
            "Площадь кухни: 15 м² Тип дома: панельный Год постройки: 1985 "
            "Звёздная, 9 мин. пешком")
    l = listing_from_text("x", "1", "u", text)
    assert (l.rooms, l.total_area, l.kitchen_area, l.floor, l.floors_total) == (1, 42, 15, 4, 9)
    assert (l.material, l.build_year, l.price, l.metro_walk_min) == (Material.PANEL, 1985, 11_200_000, 9)
