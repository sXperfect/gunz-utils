# A Modern CMake Project: Best Practices Guide
_version: 1.1.0_

This guide outlines a set of best practices for creating clean, robust, and maintainable CMake build
systems. It is based on modern CMake principles, focusing on modularity, clarity, and target-based
properties.

## The Preamble: Project Setup
---

The top of your root `CMakeLists.txt` should set project-wide basics.

- **`cmake_minimum_required`**: Always set this first. Use a reasonably recent version (e.g., `3.15`
  or higher) to access modern features. Using `FATAL_ERROR` ensures that an incompatible CMake
  version stops immediately.

    ```cmake
    cmake_minimum_required(VERSION 3.15 FATAL_ERROR)
    ```

- **`project()`**: Define your project's name, version, and languages in the _root_
  `CMakeLists.txt`. This sets important variables like `CMAKE_PROJECT_NAME` and `CMAKE_BINARY_DIR`.

    ```cmake
    project(MyAwesomeProject VERSION 1.0 LANGUAGES CXX)
    ```

- **`CMAKE_MODULE_PATH`**: If you have custom `.cmake` modules (e.g., for finding specific libraries
  or custom build steps), add their directory to this list.

    ```cmake
    list(APPEND CMAKE_MODULE_PATH "${CMAKE_SOURCE_DIR}/cmake")
    ```


## Build Type Configuration
---

A robust build script should handle build types gracefully.

- **Set a Default:** Users often forget to specify a build type (`-DCMAKE_BUILD_TYPE=...`). Set a
  sensible default (usually `Release`) and notify the user.

    ```cmake
    if(NOT CMAKE_BUILD_TYPE)
      set(CMAKE_BUILD_TYPE Release)
      message(STATUS "No build type specified. Using default: ${CMAKE_BUILD_TYPE}")
    endif()
    ```

- **Validate Build Types:** You can add logic to warn the user if they specify a build type you
  don't explicitly support or test for.

    ```cmake
    if(NOT "${CMAKE_BUILD_TYPE}" IN_LIST "Debug;Release;RelWithDebInfo;MinSizeRel")
        message(WARNING "Unsupported build type: ${CMAKE_BUILD_TYPE}")
    endif()
    ```


## Project-Wide Options
---

Use `option()` in your root file to define user-configurable build settings. This is the primary way
to control conditional compilation.

- **Define Options:** Use the `option(<NAME> "Description" <DEFAULT>)` syntax. `DEFAULT` must be
  `ON` or `OFF`.

    ```cmake
    option(MYPROJECT_BUILD_TESTS "Build the project's unit tests" ON)
    option(MYPROJECT_USE_FOOBAR "Enable the optional FooBar library" OFF)
    option(MYPROJECT_WERROR "Treat compiler warnings as errors" OFF)
    ```

- **Print an Options Summary:** This is an excellent practice for user feedback. It confirms exactly
  what is being built.

    ```cmake
    message(STATUS "")
    message(STATUS "******** ${CMAKE_PROJECT_NAME} Options ********")
    message(STATUS "  Build Tests:    ${MYPROJECT_BUILD_TESTS}")
    message(STATUS "  Use FooBar:     ${MYPROJECT_USE_FOOBAR}")
    message(STATUS "  Warnings as Errors: ${MYPROJECT_WERROR}")
    message(STATUS "***********************************")
    message(STATUS "")
    ```


## Compiler Configuration (The Modern Way)
---

**Principle:** Avoid global variables like `CMAKE_CXX_FLAGS`. Instead, apply settings _per-target_.
This makes your project modular and prevents settings from "leaking" between targets.

- **Set C++ Standard:** Use `target_compile_features` to specify the C++ standard. This is the most
  portable and modern method. It lets CMake figure out the correct flags (`-std=c++17`,
  `/std:c++17`, etc.).

    ```cmake
    # In src/CMakeLists.txt, after add_library(...)
    add_library(my_lib ...)
    target_compile_features(my_lib PRIVATE cxx_std_17)
    ```

- **Set Compiler-Specific Flags:** Use `target_compile_options` to add flags _to a specific target_.
  This is far cleaner than modifying global variables.

    - **Use `PUBLIC`/`PRIVATE`/`INTERFACE`:** This is the most important concept in modern CMake.

        - `PRIVATE`: The setting is only for building this target.

        - `PUBLIC`: The setting is for this target AND any target that links to it.

        - `INTERFACE`: The setting is _only_ for targets that link to it (used for header-only
          libraries).

    - **Real-World Example (from `genie-genotype`):**


    ```cmake
    # In src/genie-genotype/CMakeLists.txt
    add_library(genie-genotype ...)

    if(MSVC)
      # MSVC-specific linker flags (less common, but possible)
      set(CMAKE_EXE_LINKER_FLAGS /MANIFEST:NO)
    endif()

    if("${CMAKE_CXX_COMPILER_ID}" STREQUAL "GNU" OR "${CMAKE_CXX_COMPILER_ID}" MATCHES "Clang")
      # These compile options only apply to the 'genie-genotype' target
      target_compile_options(genie-genotype PRIVATE
          "-pedantic"
          "-fno-common"
          "-Wall"
          "-Wshadow"
          "-Wextra"
          "-Wundef"
          "-Wconversion"
          "-Wdouble-promotion"
          "-Wno-error=conversion"
      )
    endif ()
    ```


## Finding & Using Dependencies
---

- **`find_package()`**: This is the standard way to find dependencies.

- **Find Where Needed:** Find packages in the `CMakeLists.txt` that actually _uses_ them. If only
  `genie-genotype` needs `xtensor`, run `find_package(xtensor ...)` in
  `src/genie-genotype/CMakeLists.txt`, not in the root.

    ```cmake
    # In src/genie-genotype/CMakeLists.txt
    set(XTENSOR_USE_XSIMD 0) # Set hints *before* find_package
    find_package(xtl REQUIRED)
    find_package(xtensor REQUIRED)
    ```

- **Link Dependencies:** _Always_ link to the imported targets provided by `find_package` (e.g.,
  `Boost::program_options`, `xtensor`). Do _not_ manually add include directories or flags from
  variables. The imported target handles this automatically.

    ```cmake
    # The modern, correct way
    target_link_libraries(my_app PRIVATE
        Boost::program_options
        OpenMP::OpenMP_CXX
        xtensor # Link to the imported target
    )
    ```


## Structuring the Root Project
---

- **`add_subdirectory()`**: Use this in your root `CMakeLists.txt` to descend into sub-projects
  (like `src`, `tests`, `docs`).

- **Conditional Subdirectories:** _Crucially_, wrap optional subdirectories in `if()` blocks based
  on your options. This is the core of conditional configuration.

    ```cmake
    # In root CMakeLists.txt
    add_subdirectory(src) # Core source code

    if(MYPROJECT_BUILD_TESTS)
      enable_testing() # Enable CTest
      add_subdirectory(tests)
    endif()

    if(MYPROJECT_BUILD_DOCS)
      find_package(Doxygen)
      if(DOXYGEN_FOUND)
        add_subdirectory(docs)
      else()
        message(WARNING "Doxygen not found. Cannot build documentation.")
      endif()
    endif()
    ```


## Example: Subdirectory Library (`src/my_lib/CMakeLists.txt`)
---

This combines the patterns from your `genie-core` and `genie-genotype` examples into a template for
a sub-project library.

```cmake
# No project() call needed here if one exists in the root
# project(my_lib) # This is optional, but can be useful

# 1. Define source files
set(source_files
    file1.cpp
    file2.cpp
    # ...
)

# 2. Add the library target
add_library(my_lib ${source_files})

# 3. Add Include Directories
#
# Common pattern (broad, but simple):
get_filename_component(TOP_DIR ../../ ABSOLUTE)
target_include_directories(my_lib PUBLIC
    "${TOP_DIR}" # Makes all of 'src' available.
)

# Modern pattern (more precise):
target_include_directories(my_lib
    PUBLIC
        # For consumers building this project
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
        # For consumers installing this project
        $<INSTALL_INTERFACE:include>
    PRIVATE
        # For internal implementation headers
        ${CMAKE_CURRENT_SOURCE_DIR}/internal
)

# 4. Add Compile Options (from genie-genotype)
if("${CMAKE_CXX_COMPILER_ID}" STREQUAL "GNU" OR "${CMAKE_CXX_COMPILER_ID}" MATCHES "Clang")
    target_compile_options(my_lib PRIVATE
        "-Wall"
        "-Wshadow"
        "-Wextra"
        "-Wconversion"
    )
endif ()

# 5. Link to other targets (from genie-genotype)
target_link_libraries(my_lib
    PUBLIC
        # Targets that link to my_lib also need genie-util
        genie-util
        # Consumers of my_lib also need xtensor
        xtensor_no_warnings
    PRIVATE
        # my_lib uses mpeggCodecs internally,
        # but consumers of my_lib don't need to know about it.
        mpeggCodecs-static
)
```

## Output Organization
---

It's clean to have all binaries and libraries build into common `build/bin` and `build/lib`
directories. Add this to your root `CMakeLists.txt`.

- **Set Output Paths:**

    ```cmake
    set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/lib")
    set(CMAKE_LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/lib")
    set(CMAKE_RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")
    ```