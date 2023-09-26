import os
import shutil

import pytest


@pytest.fixture()
def images_directory():
    try:
        os.mkdir('images')
    except FileExistsError:
        pass
    yield
    # Cleanup
    shutil.rmtree('tests/images')


def test_creates_required_files(images_directory):
    from allure_behavior_snippets import main
    main.generate_image_per_story("allure-report/data/behaviors.json", "tests/images")
    files = os.listdir('images')
    assert {'EXAMPLE.svg', "Get a single user's data.svg", "Get all user's data.svg", "Get a post.svg"} <= set(files)
