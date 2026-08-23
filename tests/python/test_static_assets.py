import hashlib
from importlib import resources


def test_vendored_htmx_has_reviewed_digest() -> None:
    data = resources.files("dofus_touch_economy").joinpath("static/htmx.min.js").read_bytes()

    assert (
        hashlib.sha256(data).hexdigest()
        == "71ea67185bfa8c98c39d31717c6fce5d852370fcdfd129db4543774d3145c0de"
    )


def test_vendored_htmx_license_has_reviewed_digest() -> None:
    data = resources.files("dofus_touch_economy").joinpath("static/htmx-LICENSE").read_bytes()

    assert (
        hashlib.sha256(data).hexdigest()
        == "d3d2456f76414f2456104660ebd65aff1c04cd7966b942bdabd63f3cdb316a38"
    )


def test_base_template_uses_only_local_assets() -> None:
    template = (
        resources.files("dofus_touch_economy")
        .joinpath("templates/base.html")
        .read_text(encoding="utf-8")
    )

    assert "/static/app.css" in template
    assert "/static/htmx.min.js" in template
    assert "https://" not in template


def test_bulk_sale_buttons_share_text_button_geometry() -> None:
    stylesheet = (
        resources.files("dofus_touch_economy")
        .joinpath("static/app.css")
        .read_text(encoding="utf-8")
    )

    bulk_button_rule = stylesheet.split(".bulk-actions button {", maxsplit=1)[1].split(
        "}", maxsplit=1
    )[0]
    assert "align-items: center;" in bulk_button_rule
    assert "font-size: inherit;" in bulk_button_rule
    assert "line-height: inherit;" in bulk_button_rule
    assert "min-height: 2.6rem;" in bulk_button_rule
    assert "padding: 0.55rem 0.7rem;" in bulk_button_rule
