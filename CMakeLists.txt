cmake_minimum_required(VERSION 3.16)
project(mrp_sfizz_worker_prototype LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_executable(mrp-sfizz-worker
    src/worker.cpp
    src/worker_engine.cpp
    src/sfizz_dyn.cpp
    src/events.cpp
    src/wav_writer.cpp)
target_include_directories(mrp-sfizz-worker PRIVATE include)
target_link_libraries(mrp-sfizz-worker PRIVATE dl)
target_compile_options(mrp-sfizz-worker PRIVATE -Wall -Wextra -Wpedantic)

option(BUILD_FAKE_SFIZZ "Build fake libsfizz used by local smoke tests" ON)
if(BUILD_FAKE_SFIZZ)
  add_library(fake_sfizz SHARED tests/fake_sfizz.cpp)
  target_include_directories(fake_sfizz PRIVATE include)
endif()
