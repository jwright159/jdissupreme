from setuptools import setup

with open('requirements.txt') as f:
	requirements = f.read().splitlines()

with open('README.md') as f:
	readme = f.read()

# Setting up
setup(
	name="jdissupreme", 
	version='1.0.0' ,
	author="Jade Wright",
	author_email="iamjwright159@gmail.com",
	description='A worse Discord library',
	long_description=readme,
	url='https://github.com/jwright159/jdissupreme',
	packages=['jdissupreme'],
	install_requires=requirements,
	
	keywords=['python', 'first package'],
	classifiers= [
		"Development Status :: 3 - Alpha",
		"Intended Audience :: Developers",
        'Natural Language :: English',
        'Operating System :: OS Independent',
		"Programming Language :: Python :: 3.10",
        'Typing :: Typed',
	]
)