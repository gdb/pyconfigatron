from setuptools import setup, find_packages
import sys, os.path

setup(name='pyconfigatron',
      version='0.0.2',
      packages=[package for package in find_packages()
                if package.startswith('pyconfigatron')],
)
