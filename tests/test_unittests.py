import json
import os
import shutil

import pytest

from allure_behavior_snippets import main


@pytest.fixture()
def images_directory():
    try:
        os.mkdir('images')
    except FileExistsError:
        pass
    yield
    # Cleanup
    shutil.rmtree('images')


def test_creates_required_files(images_directory):
    main.generate_image_per_story("allure-report/data/behaviors.json", "images")
    files = os.listdir('images')
    assert {'EXAMPLE.svg', "Get a single user's data.svg", "Get all user's data.svg", "Get a post.svg"} <= set(files)


def test_parse_behavior_data_empty():
    assert list(main.parse_behavior_data("")) == []


def test_parse_behavior_data_test_without_epic_is_ignored():
    behaviors_data = {
        "uid": "b1a8273437954620fa374b796ffaacdd",
        "name": "behaviors",
        "children": [
            {
                "name": "Test without Epic",
                "uid": "933e13e291f105dc",
                "parentUid": "b1a8273437954620fa374b796ffaacdd",
                "status": "passed",
                "time": {
                    "start": 1702919526786,
                    "stop": 1702919532819,
                    "duration": 6033
                },
                "flaky": False,
                "newFailed": False,
                "newPassed": False,
                "newBroken": False,
                "retriesCount": 0,
                "retriesStatusChange": False,
                "parameters": [],
                "tags": []
            }
        ]
    }

    assert list(main.parse_behavior_data(json.dumps(behaviors_data))) == []


def test_parse_behavior_data_test_without_feature_is_ignored():
    behaviors_data = {
        "uid": "b1a8273437954620fa374b796ffaacdd",
        "name": "behaviors",
        "children": [
            {
                "name": "Epic",
                "children": [
                    {
                        "name": "Test without Feature",
                        "uid": "933e13e291f105dc",
                        "parentUid": "b1a8273437954620fa374b796ffaacdd",
                        "status": "passed",
                        "time": {
                            "start": 1702919526786,
                            "stop": 1702919532819,
                            "duration": 6033
                        },
                        "flaky": False,
                        "newFailed": False,
                        "newPassed": False,
                        "newBroken": False,
                        "retriesCount": 0,
                        "retriesStatusChange": False,
                        "parameters": [],
                        "tags": []
                    }
                ]
            }
        ]
    }

    assert list(main.parse_behavior_data(json.dumps(behaviors_data))) == []


def test_parse_behavior_data_test_without_story_is_ignored():
    behaviors_data = {
        "uid": "b1a8273437954620fa374b796ffaacdd",
        "name": "behaviors",
        "children": [
            {
                "name": "Epic",
                "children": [
                    {
                        "name": "Feature",
                        "children": [
                            {

                                "name": "Test without Story",
                                "uid": "933e13e291f105dc",
                                "parentUid": "b1a8273437954620fa374b796ffaacdd",
                                "status": "passed",
                                "time": {
                                    "start": 1702919526786,
                                    "stop": 1702919532819,
                                    "duration": 6033
                                },
                                "flaky": False,
                                "newFailed": False,
                                "newPassed": False,
                                "newBroken": False,
                                "retriesCount": 0,
                                "retriesStatusChange": False,
                                "parameters": [],
                                "tags": []
                            }
                        ]
                    }
                ]
            }
        ]
    }

    assert list(main.parse_behavior_data(json.dumps(behaviors_data))) == []


def test_parse_behavior_data_valid():
    foo = {
        "uid": "b1a8273437954620fa374b796ffaacdd",
        "name": "behaviors",
        "children": [
            {
                "name": "/posts",
                "children": [
                    {
                        "name": "/posts/{}",
                        "children": [
                            {
                                "name": "Get a post",
                                "uid": "da00cba2c8f31eb464f743e786be8cd4",
                                "children": [
                                    {
                                        "name": "Given: a post exists; When: a post is queried; Then: correct response is returned ",
                                        "uid": "b5b9fe7670327db2",
                                        "parentUid": "35bb78435f56b2898177ce432cbb7cf2",
                                        "status": "passed",
                                        "time": {
                                            "start": 1693221123612,
                                            "stop": 1693221123813,
                                            "duration": 201
                                        },
                                        "flaky": False,
                                        "newFailed": False,
                                        "newPassed": False,
                                        "newBroken": False,
                                        "retriesCount": 0,
                                        "retriesStatusChange": False,
                                        "parameters": [],
                                        "tags": []
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ]
    }

    assert list(main.parse_behavior_data(json.dumps(foo))) == [
        main.Story(
            **{"name": "Get a post",
               "uid": "da00cba2c8f31eb464f743e786be8cd4",
               "children": [
                   {
                       "name": "Given: a post exists; When: a post is queried; Then: correct response is returned ",
                       "uid": "b5b9fe7670327db2",
                       "parentUid": "35bb78435f56b2898177ce432cbb7cf2",
                       "status": "passed",
                       "time": {
                           "start": 1693221123612,
                           "stop": 1693221123813,
                           "duration": 201
                       },
                       "flaky": False,
                       "newFailed": False,
                       "newPassed": False,
                       "newBroken": False,
                       "retriesCount": 0,
                       "retriesStatusChange": False,
                       "parameters": [],
                       "tags": []
                   }
               ]
               }
        )
    ]


@pytest.mark.parametrize("children", [[], None])
def test_parse_behavior_data_empty_epic(children):
    foo = {
        "uid": "b1a8273437954620fa374b796ffaacdd",
        "name": "behaviors",
        "children": [
            {"name": "epic withouth children",
             "children": children},
            {
                "name": "/posts",
                "children": [
                    {
                        "name": "/posts/{}",
                        "children": [
                            {
                                "name": "Get a post",
                                "uid": "da00cba2c8f31eb464f743e786be8cd4",
                                "children": [
                                    {
                                        "name": "Given: a post exists; When: a post is queried; Then: correct response is returned ",
                                        "uid": "b5b9fe7670327db2",
                                        "parentUid": "35bb78435f56b2898177ce432cbb7cf2",
                                        "status": "passed",
                                        "time": {
                                            "start": 1693221123612,
                                            "stop": 1693221123813,
                                            "duration": 201
                                        },
                                        "flaky": False,
                                        "newFailed": False,
                                        "newPassed": False,
                                        "newBroken": False,
                                        "retriesCount": 0,
                                        "retriesStatusChange": False,
                                        "parameters": [],
                                        "tags": []
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ]
    }

    assert list(main.parse_behavior_data(json.dumps(foo))) == [
        main.Story(
            **{"name": "Get a post",
               "uid": "da00cba2c8f31eb464f743e786be8cd4",
               "children": [
                   {
                       "name": "Given: a post exists; When: a post is queried; Then: correct response is returned ",
                       "uid": "b5b9fe7670327db2",
                       "parentUid": "35bb78435f56b2898177ce432cbb7cf2",
                       "status": "passed",
                       "time": {
                           "start": 1693221123612,
                           "stop": 1693221123813,
                           "duration": 201
                       },
                       "flaky": False,
                       "newFailed": False,
                       "newPassed": False,
                       "newBroken": False,
                       "retriesCount": 0,
                       "retriesStatusChange": False,
                       "parameters": [],
                       "tags": []
                   }
               ]
               }
        )
    ]


@pytest.mark.parametrize("children", [[], None])
def test_parse_behavior_data_empty_feature(children):
    foo = {
        "uid": "b1a8273437954620fa374b796ffaacdd",
        "name": "behaviors",
        "children": [
            {
                "name": "/posts",
                "children": [
                    {"name": "feature withouth children",
                     "children": children},
                    {
                        "name": "/posts/{}",
                        "children": [
                            {
                                "name": "Get a post",
                                "uid": "da00cba2c8f31eb464f743e786be8cd4",
                                "children": [
                                    {
                                        "name": "Given: a post exists; When: a post is queried; Then: correct response is returned ",
                                        "uid": "b5b9fe7670327db2",
                                        "parentUid": "35bb78435f56b2898177ce432cbb7cf2",
                                        "status": "passed",
                                        "time": {
                                            "start": 1693221123612,
                                            "stop": 1693221123813,
                                            "duration": 201
                                        },
                                        "flaky": False,
                                        "newFailed": False,
                                        "newPassed": False,
                                        "newBroken": False,
                                        "retriesCount": 0,
                                        "retriesStatusChange": False,
                                        "parameters": [],
                                        "tags": []
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ]
    }

    assert list(main.parse_behavior_data(json.dumps(foo))) == [
        main.Story(
            **{"name": "Get a post",
               "uid": "da00cba2c8f31eb464f743e786be8cd4",
               "children": [
                   {
                       "name": "Given: a post exists; When: a post is queried; Then: correct response is returned ",
                       "uid": "b5b9fe7670327db2",
                       "parentUid": "35bb78435f56b2898177ce432cbb7cf2",
                       "status": "passed",
                       "time": {
                           "start": 1693221123612,
                           "stop": 1693221123813,
                           "duration": 201
                       },
                       "flaky": False,
                       "newFailed": False,
                       "newPassed": False,
                       "newBroken": False,
                       "retriesCount": 0,
                       "retriesStatusChange": False,
                       "parameters": [],
                       "tags": []
                   }
               ]
               }
        )
    ]
