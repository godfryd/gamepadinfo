PYPI_INSTANCE ?= testpypi

release: build
	twine register dist/gamepadinfo-*-py3-none-any.whl -r $(PYPI_INSTANCE)
	twine upload dist/* -r $(PYPI_INSTANCE)

build: clean
	python3 setup.py sdist bdist_wheel

clean:
	python3 setup.py clean
	rm -rf dist

.PHONY: release build clean
