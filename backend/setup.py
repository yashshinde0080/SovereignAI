from setuptools import setup, find_packages

setup(
    name='sovereign',
    version='0.1.0',
    description='SovereignAI Edge - Portable Offline AI Platform',
    author='SovereignAI',
    packages=find_packages(),  # This automatically finds the 'app' module
    entry_points={
        'console_scripts': [
            'sovereign=app.cli.main:app',  # Points directly to the Typer app instance
        ],
    },
    install_requires=[
        'typer>=0.12.0',
        'rich==13.7.0',
        'httpx>=0.28.1',
        'prompt-toolkit==3.0.43',
    ],
)
