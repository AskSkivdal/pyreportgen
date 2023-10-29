from setuptools import setup, find_packages

setup(
    name="pyreportgen",
    version="0.1.0",
    description="A package for creating reports and other pdf documents.",
    long_description=open('readme.md').read(),
    long_description_content_type='text/markdown',
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
)