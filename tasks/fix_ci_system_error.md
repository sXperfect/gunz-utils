# Fix CI System Error

## Description
The goal of this task was to fix the CI system errors preventing successful builds, which primarily involved missing dependency issues (`gitpython` and `loguru`), as well as executing the test suite utilizing the `unittest` framework rather than `pytest` and updating the `pyproject.toml` file to list those required packages explicitly.

## Lessons Learned
- Ensure all direct dependencies required by the source files (e.g. `src/gunz_utils/project.py`) are properly listed under the `dependencies` key in `pyproject.toml`.
- While evaluating project files and test workflows, strictly adhere to the user's specific test runner instruction (i.e. to use `unittest` rather than `pytest`).
- Avoid adding third-party testing utilities if standard library tools are requested or already sufficient. `unittest` was perfectly suited for executing the existing `TestCase` files in this repository without the need to introduce `pytest` as an optional dependency group.

## Future Improvements
- Periodically perform a dependency sweep to ensure `pyproject.toml` stays perfectly synchronized with any imports added to the source code to avoid sudden CI regressions.
