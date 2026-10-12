from market_briefing import grounding

SOURCE = ["2월 2일부터 2월 23일까지 즉시 구매가는 189,000원에서 231,000원으로 +22.2% 변했다."]


def test_numbers_copied_from_source_pass():
    assert grounding.ungrounded("2월 23일 231,000원으로 22.2% 올랐습니다 [1]", SOURCE) == set()


def test_invented_price_is_flagged():
    assert grounding.ungrounded("다음 달에는 250,000원까지 오를 수 있습니다", SOURCE) == {"250000"}


def test_comma_and_sign_do_not_matter():
    assert grounding.ungrounded("+22.2%, 231000원", SOURCE) == set()
