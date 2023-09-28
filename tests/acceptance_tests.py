from playwright.sync_api import Page, expect


def svg_by_file_name(value: str):
    return f"object[data=\"./{value}.svg\"]"


def raise_(ex):
    raise ex


def test_page_has_required_files(page: Page):
    page.goto("/")
    expected_filenames = ['EXAMPLE_svg', "Get a single user's data_svg", "Get all user's data_svg",
                          "Get a post_svg"]
    for filename in expected_filenames:
        expect(page.locator(svg_by_file_name(filename))).to_be_visible()


def test_browser_console_clear_of_errors(page: Page):
    page.on("console", lambda msg: raise_(
        AssertionError(f"Console error: {msg.text}, {msg.location}") if msg.type == "error" else None))
    page.goto('/')


def expect_only_200_response(response):
    if response.status != 200:
        raise AssertionError(f"Failed response: {response.status} {response.url}")


def test_network_responses_all_200(page: Page):
    page.on("response", expect_only_200_response)
    page.goto('/')


def test_screenshot(page: Page, assert_snapshot):
    page.set_viewport_size(viewport_size={'width': 1920, 'height': 1080})
    page.goto('/')
    assert_snapshot(page.screenshot(), "behaviors.png")
