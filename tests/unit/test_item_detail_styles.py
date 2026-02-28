from pathlib import Path


def test_mobile_item_detail_image_has_no_max_height():
    css = Path("app/static/css/style.css").read_text()

    mobile_css_start = css.find("@media (max-width: 992px)")
    assert mobile_css_start != -1

    mobile_css = css[mobile_css_start:]
    assert ".item-detail-image" in mobile_css
    assert "max-height: none;" in mobile_css
    assert "max-height: 300px;" not in mobile_css
