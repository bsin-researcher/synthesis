from setuptools import setup, find_packages

setup(
    name="synthesis-econ",
    version="0.4.0",
    author="Blake Sinclair",
    description="AI-powered economics research tool: QQA alignment of literature and empirical data.",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/bsin-researcher/synthesis",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "anthropic>=0.109.0",
        "requests>=2.34.0",
        "pandas>=2.0.0",
        "plotly>=5.20.0",
        "scipy>=1.10.0",
        "rich>=13.0.0",
        "typer>=0.9.0",
        "python-dotenv>=1.0.0",
    ],
    entry_points={
        "console_scripts": [
            "synthesis=synthesis.cli:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Intended Audience :: Science/Research",
    ],
)
