from app.parsing import parse_coordinates


def test_comma_separated():
    assert parse_coordinates("47.6062,-122.3321") == (47.6062, -122.3321)


def test_space_separated():
    assert parse_coordinates("47.6062 -122.3321") == (47.6062, -122.3321)


def test_extra_whitespace():
    assert parse_coordinates("  47.6062 , -122.3321  ") == (47.6062, -122.3321)


def test_out_of_range_lat():
    assert parse_coordinates("95,-122.3321") is None


def test_out_of_range_lon():
    assert parse_coordinates("47.6062,-185") is None


def test_junk_text():
    assert parse_coordinates("hey what's the weather like") is None


def test_single_number():
    assert parse_coordinates("47.6062") is None
