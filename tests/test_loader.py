"""시·도 / 시·군·구 표기 정규화."""

import pandas as pd
import pytest

from hri.loader import _normalize_one_sgg, apply_admin_changes, normalize_sgg, normalize_sido


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("서울", "서울특별시"),
        ("서울특별시", "서울특별시"),
        ("강원도", "강원특별자치도"),
        ("전라북도", "전북특별자치도"),
        ("세종시", "세종특별자치시"),
        ("제주도", "제주특별자치도"),
        (" 경북 ", "경상북도"),
    ],
)
def test_normalize_sido(raw, expected):
    assert normalize_sido(pd.Series([raw])).iloc[0] == expected


@pytest.mark.parametrize(
    "old, new",
    [
        (("경상북도", "군위군"), ("대구광역시", "군위군")),
        (("충청북도", "청원군"), ("충청북도", "청주시")),
        (("인천광역시", "남구"), ("인천광역시", "미추홀구")),
    ],
)
def test_admin_changes(old, new):
    assert apply_admin_changes(*old) == new


def test_admin_changes_leaves_others_alone():
    assert apply_admin_changes("부산광역시", "남구") == ("부산광역시", "남구")


def test_sejong_is_single_tier():
    for name in ["세종시", "소계", "세종특별자치시"]:
        assert _normalize_one_sgg("세종특별자치시", name) == "세종특별자치시"


def test_jeju_administrative_cities_kept():
    assert _normalize_one_sgg("제주특별자치도", "제주시") == "제주시"
    assert _normalize_one_sgg("제주특별자치도", "서귀포시") == "서귀포시"


@pytest.mark.parametrize(
    "sido, raw, expected",
    [
        ("대구광역시", "대구중구", "중구"),       # HIRA 표기: 시도 prefix 붙음
        ("광주광역시", "광주광산구", "광산구"),
        ("부산광역시", "부산진구", "부산진구"),   # prefix처럼 보이지만 실제 구 이름
        ("경기도", "수원권선구", "수원시"),       # 특례시 일반구 → 시
        ("경기도", "수원시권선구", "수원시"),
        ("경기도", "수원시 권선구", "수원시"),
        ("경기도", "수원시", "수원시"),
        ("경상남도", "창원마산합포구", "창원시"),
        ("경기도", "화성시 동탄구", "화성시"),
        ("경기도", "안성시", "안성시"),           # 특례시 prefix와 무관한 시
        ("강원특별자치도", "고성군", "고성군"),
    ],
)
def test_normalize_one_sgg(sido, raw, expected):
    assert _normalize_one_sgg(sido, raw) == expected


def test_normalize_sgg_sums_districts_into_city():
    df = pd.DataFrame(
        {
            "sido": ["경기도", "경기도", "경기도"],
            "sgg": ["수원시 권선구", "수원시 영통구", "화성시"],
            "n": [10, 5, 7],
        }
    )
    out = normalize_sgg(df).set_index("sgg")["n"]
    assert out.to_dict() == {"수원시": 15, "화성시": 7}
