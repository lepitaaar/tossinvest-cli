from setuptools import find_packages, setup


setup(
    name="tossinvest-ai-cli",
    version="0.1.0",
    description="AI-oriented CLI client for Toss Securities Open API",
    packages=find_packages(),
    python_requires=">=3.9",
    entry_points={"console_scripts": ["toss=tossinvest.cli:main"]},
)
