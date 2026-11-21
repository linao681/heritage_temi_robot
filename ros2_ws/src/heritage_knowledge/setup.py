from setuptools import setup

setup(name='heritage_knowledge', version='0.1.0', packages=['heritage_knowledge'],
      data_files=[('share/ament_index/resource_index/packages', ['resource/heritage_knowledge']), ('share/heritage_knowledge', ['package.xml'])],
      install_requires=['setuptools', 'PyYAML'],
      entry_points={'console_scripts': ['knowledge_node = heritage_knowledge.main:main', 'knowledge_qa = heritage_knowledge.main:cli']})
