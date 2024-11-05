from setuptools import setup, find_packages

setup(
    name="pg_utils",                      
    version="0.1.0",                          
    description="A simple database utility library using psycopg3",
    author="Lucas Soares",
    author_email="lucassoaresolv@outlook.com",
    url="https://github.com/lucassoaresol/pg-utils-python",  
    packages=find_packages(),                
    install_requires=[                      
        "psycopg[binary]>=3.0.0",
    ],
    python_requires=">=3.7",                 
    classifiers=[                           
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
)
