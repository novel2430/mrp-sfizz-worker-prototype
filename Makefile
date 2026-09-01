.PHONY: all build test clean
all: build
build:
	cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
	cmake --build build -j$${JOBS:-2}
test: build
	python -m unittest discover -s tests -p 'test_*.py' -v
	bash tests/smoke_worker.sh
clean:
	rm -rf build .test-out
