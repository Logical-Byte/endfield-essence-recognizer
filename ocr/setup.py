from setuptools import setup, find_packages

setup(
    name='endocr',
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
        'paddleocr',
        'paddlepaddle',
        'opencv-python',
        'numpy',
    ],
)
