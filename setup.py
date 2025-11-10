"""Setup script for alpha-bench package."""

from setuptools import setup, find_packages
from pathlib import Path

# Read long description from README
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding="utf-8")

# Read requirements
requirements = (this_directory / "requirements.txt").read_text().splitlines()
requirements = [r.strip() for r in requirements if r.strip() and not r.startswith("#")]

dev_requirements = (this_directory / "requirements-dev.txt").read_text().splitlines()
dev_requirements = [r.strip() for r in dev_requirements if r.strip() and not r.startswith("#")]

setup(
    name="alpha-bench",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="Automated recurring simulation framework for LLM trading evaluation",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/alpha-bench",
    packages=find_packages(exclude=["tests", "tests.*", "docs", "scripts"]),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: Financial and Insurance Industry",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Office/Business :: Financial :: Investment",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    python_requires=">=3.10",
    install_requires=requirements,
    extras_require={
        "dev": dev_requirements,
        "all": requirements + dev_requirements,
    },
    entry_points={
        "console_scripts": [
            "alpha-bench=alpha_bench.cli:main",
        ],
    },
    include_package_data=True,
    package_data={
        "alpha_bench": [
            "airflow_dags/*.py",
            "dashboard/components/*.py",
        ],
    },
    zip_safe=False,
)
