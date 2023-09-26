import argparse
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List

import jq


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


def save_image(filename, image):
    with open(filename, 'w') as file:
        file.write(image)


def generate_image_per_story(filename, target_directory):
    with open(filename, 'r') as file:
        data = file.read()
    for story_data in jq.compile('.children[].children | select(. != null ) |.[].children[]').input(text=data):
        story = Story(**story_data)
        image = generate_image(story)

        save_image(os.path.join(target_directory, story.name + '.svg'), image)
        generate_svgwrite_image(os.path.join(target_directory, story.name + "_svg.svg"), story)


def list_of_files():
    p = Path('../allure-results')
    yield from p.glob('*-result.json')


def generate_image(story: Story):
    image = f"""<svg version="1.1"
     width="600" height="200"
     xmlns="http://www.w3.org/2000/svg">"""
    image += f"".join([f"<text x=\"0\" y=\"60\">{child.name}</text>" for child in story.children])
    image += f"</svg>"
    return image


def generate_svgwrite_image(filename: str, story: Story):
    import svgwrite
    font_size = 14
    names = [child.name for child in story.children]

    width = font_size * max(len(name) for name in names)
    height = (font_size + 8) * len(names)
    dwg = svgwrite.Drawing(filename, size=(f"{width}px", f"{height}px"),
                           profile='tiny')
    for index, child in enumerate(story.children, start=1):
        dwg.add(dwg.text(child.name, insert=(0, index * 20), font_size=f"{font_size}px", font_family="Helvetica"))
    dwg.save()


def cli():
    parser = argparse.ArgumentParser()
    parser.add_argument("behaviors", help="location of behaviors.json")
    parser.add_argument("target", help="target directory for generated images")
    args = parser.parse_args()
    # generate_image_per_story('../tests/behaviors.json', target_directory='images')
    generate_image_per_story(args.behaviors, target_directory=args.target)


if __name__ == '__main__':
    cli()
    # import cProfile
    # cProfile.run("generate_image_per_story('behaviors.json', target_directory='images')", sort='tottime')
