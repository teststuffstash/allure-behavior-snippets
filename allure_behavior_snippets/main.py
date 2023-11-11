import argparse
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List

import jq
import svgwrite
from svgwrite import container


# Code completion for data, inspiration from https://json2csharp.com/code-converters/json-to-python
@dataclass
class Time:
    start: object
    stop: object
    duration: int


@dataclass
class Test:
    name: str
    uid: str
    parentUid: str
    status: str
    time: Time
    flaky: bool
    newFailed: bool
    newPassed: bool
    newBroken: bool
    retriesCount: int
    retriesStatusChange: bool
    parameters: List[str]
    tags: List[str]

    def __post_init__(self):
        self.time = Time(**self.time)


@dataclass
class Story:
    name: str
    children: List[Test]
    uid: str

    def __post_init__(self):
        self.children = [Test(**child) for child in self.children]


def generate_image_per_story(filename, target_directory, report_url=None):
    with open(filename, 'r') as file:
        data = file.read()
    for story_data in jq.compile(
            '.children[].children | select(. != null ) | .[] | select(.children!=null) |.children[]').input(text=data):
        story = Story(**story_data)
        generate_svgwrite_image(os.path.join(target_directory, story.name + ".svg"), story, report_url)


def list_of_files():
    p = Path('../allure-results')
    yield from p.glob('*-result.json')


def generate_svgwrite_image(filename: str, story: Story, report_url: str):
    base_url = 'http://localhost:8081/#behaviors/'
    font_size = 14
    names = [child.name for child in story.children]
    checkmark = "✓"  # https://en.wikipedia.org/wiki/Check_mark
    crossmark = "❌"  # https://en.wikipedia.org/wiki/X_mark

    width = font_size * max(len(name) for name in names)
    height = (font_size + 8) * len(names)
    dwg = svgwrite.Drawing(filename, size=(f"{width}px", f"{height}px"),
                           profile='tiny')
    for index, child in enumerate(story.children, start=1):
        icon = checkmark if child.status == 'passed' else crossmark
        link = container.Hyperlink(f"{report_url}{child.parentUid}/{child.uid}")
        link.add(
            dwg.text(f"{icon} {child.name}", insert=(0, index * 20), font_size=f"{font_size}px",
                     font_family="Helvetica"))
        dwg.add(link)
    dwg.save()


def cli():
    parser = argparse.ArgumentParser()
    parser.add_argument("behaviors", help="location of behaviors.json")
    parser.add_argument("target", help="target directory for generated images")
    parser.add_argument("report_url", help="base URL of Allure report")
    args = parser.parse_args()
    # generate_image_per_story('../tests/allure-report/data/behaviors.json', target_directory='../images', report_url='http://localhost:8081/#behaviors/')
    generate_image_per_story(args.behaviors, target_directory=args.target, report_url=args.report_url)


if __name__ == '__main__':
    cli()
    # import cProfile
    # cProfile.run("generate_image_per_story('behaviors.json', target_directory='images')", sort='tottime')
