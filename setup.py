import setuptools

with open("README.md", "r") as f:
    desc = f.read()

requirements = []
with open("requirements.txt", "r") as f:
    requirements = f.read().splitlines()

setuptools.setup(
    name="nbtui",
    version="0.0.2",
    author="Tony Chen",
    author_email="tchen1998@gmail.com",
    description="View jupyter notebooks (with images) from the command line",
    long_description=desc,
    long_description_content_type="text/markdown",
    url="https://github.com/chentau/nbtui",
    packages=setuptools.find_packages(),
    entry_points={
            "console_scripts": [
                    "nbtui=nbtui.__main__:main"
                ]
        },
    python_requires='>=3.6',
    install_requires = requirements
)
