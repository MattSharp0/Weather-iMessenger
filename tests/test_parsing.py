from app.parsing import parse_coordinates, parse_request


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


def test_request_no_option_defaults():
    assert parse_request("47.6062,-122.3321") == (47.6062, -122.3321, "default")


def test_request_space_separated_no_option():
    assert parse_request("47.6062 -122.3321") == (47.6062, -122.3321, "default")


def test_request_with_forecast_option():
    assert parse_request("47.6062,-122.3321 forecast") == (47.6062, -122.3321, "forecast")


def test_request_with_tonight_option():
    assert parse_request("47.6062,-122.3321 tonight") == (47.6062, -122.3321, "tonight")


def test_request_with_tomorrow_option_case_insensitive():
    assert parse_request("47.6062,-122.3321 Tomorrow") == (47.6062, -122.3321, "tomorrow")


def test_request_space_separated_coords_with_option():
    assert parse_request("47.6062 -122.3321 tonight") == (47.6062, -122.3321, "tonight")


def test_request_extra_whitespace_before_option():
    assert parse_request("  47.6062,-122.3321   tonight  ") == (47.6062, -122.3321, "tonight")


def test_request_unrecognized_option_is_invalid():
    assert parse_request("47.6062,-122.3321 xyz") is None


def test_request_junk_text():
    assert parse_request("hey what's the weather like") is None
