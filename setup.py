import setuptools

with open('README.md', 'r') as fh:
    long_description = fh.read()

setuptools.setup(
    name="cliente-sec-ajendrex", # Replace with your own username
    version="0.0.1",
    author="Héctor Urbina",
    author_email="hurbinas@gmail.com",
    description="Un Cliente http para obtener inscripciones en www.sec.cl",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/ajendrex/cliente-sec",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)
