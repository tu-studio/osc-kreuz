from setuptools import setup

setup(
    name="seamless_oscrouter",
    version="1.0",
    packages=["seamless_oscrouter"],
    install_requires=["numpy", "oscpy"],
    entry_points="""
    [console_scripts]
    seamless-oscrouter=seamless_oscrouter.oscrouter:main
    """
)