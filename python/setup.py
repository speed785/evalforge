from pathlib import Path

from setuptools import find_packages, setup

root = Path(__file__).resolve().parents[1]
readme_path = root / "README.md"
if readme_path.exists():
    long_description = readme_path.read_text(encoding="utf-8")
else:
    long_description = "Agent Evaluation Harness — repeatable, measurable evals for AI agents"

_ = setup(
    name="evalforge",
    version="0.1.0",
    author="EvalForge Contributors",
    description="Agent Evaluation Harness — repeatable, measurable evals for AI agents",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/speed785/evalforge",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "aiohttp>=3.9",
    ],
    extras_require={
        "fuzzy": ["rapidfuzz>=3.0"],
        "openai": ["openai>=1.0"],
        "anthropic": ["anthropic>=0.25"],
        "rich": ["rich>=13.0"],
        "all": [
            "rapidfuzz>=3.0",
            "openai>=1.0",
            "anthropic>=0.25",
            "rich>=13.0",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Software Development :: Testing",
    ],
    keywords=[
        "ai",
        "agent",
        "llm",
        "evaluation",
        "evals",
        "testing",
        "benchmarking",
        "regression",
        "openai",
        "anthropic",
        "ci",
        "quality-assurance",
        "llm-eval",
    ],
    entry_points={
        "console_scripts": [
            "evalforge=evalforge.__main__:main",
        ],
    },
)
