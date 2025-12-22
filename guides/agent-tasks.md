# [TITLE]

_version: 1.2.0_
* **Date Created:** 2025-10-15
* **Status:** Not Started | In Progress | Blocked | Completed

## 1. User's Original Query
---

* **What to fill in:** The user's raw, unedited request.
* **Purpose:** This section preserves the original context and intent of the request. It is the source of truth to ensure the final solution directly addresses the user's initial needs.

> [Paste the user's exact query here.]

## 2. AI's Reformulated Query
---

* **What to fill in:** A structured, clear interpretation of the user's request, breaking it down into specific points.
* **Purpose:** To confirm understanding and align on the objectives. This step acts as a contract to ensure the proposed work matches the user's expectations before development begins.

> [Rewrite the user's query into a clear, itemized list of goals and identified problems.]

## 3. Project Overview
---

* **Purpose:** This section establishes the formal project plan. It defines the "why," "what," and "how" of the task, setting clear boundaries and success criteria.

### 3.1. Purpose

* **What to fill in:** A one or two-sentence summary of the high-level goal.
* **Purpose:** To explain the "why" behind the task. What is the ultimate objective or benefit of this work?

### 3.2. Functional Requirements

* **What to fill in:** A bulleted list of specific, measurable actions the system must perform.
* **Purpose:** To define **what** the solution must *do*. These are pass/fail criteria.

### 3.3. Non-functional Requirements

* **What to fill in:** A bulleted list of the quality attributes the system should have.
* **Purpose:** To define **how** the solution should *be*. These relate to performance, security, and maintainability.

### 3.4. Testing Plan

* **What to fill in:** An outline of how the solution will be verified.
* **Purpose:** To define how to prove that the requirements have been met.
    * **Input:** [Specify the input file(s), data, or user actions.]
    * **Output:** [Specify the expected output folder, data format, or system state.]
    * **Analysis:** [Describe the steps to compare the output with the expected result.]

### 3.5. Scope

* **What to fill in:** A clear definition of what is included ("In Scope") and explicitly excluded ("Out of Scope").
* **Purpose:** To prevent "scope creep" by setting clear boundaries for the task.

### 3.6. Assumptions and Constraints

* **What to fill in:** List any assumptions made (e.g., "Input data is always UTF-8 encoded") or constraints to operate within (e.g., "Must not use external paid APIs").
* **Purpose:** To explicitly state the conditions under which the solution is expected to work and the limitations that bound the project.

## 4. Prerequisites
---

* **What to fill in:** A checklist of all tools, dependencies, access credentials, and source files needed before work can begin.
* **Purpose:** To ensure the environment is correctly set up, preventing delays and issues during development.
    * `[ ]` **Tools:** [e.g., Python 3.9+, Node.js 18+]
    * `[ ]` **Libraries:** [e.g., `pandas`, `requests`]
    * `[ ]` **Access:** [e.g., API key for X service, Read access to Y database]
    * `[ ]` **Source Files:** [e.g., Link to `specs/23092-1-raw/file.html`]

## 5. Tasking
---

* **What to fill in:** A detailed checklist of all the concrete steps. For each item, provide a clear title and a separate description.
* **Purpose:** This is the core action plan. It turns the project requirements into a step-by-step guide for implementation, allowing for clear progress tracking.

* `[ ]` **Task 1: [Title of Major Task 1]**
    * **Description:** [Detailed description of what Major Task 1 entails.]
    * `[ ]` **Task 1.1: [Title of Sub-task 1.1]**
        * **Description:** [Detailed description of Sub-task 1.1.]
        * `[ ]` **Task 1.1.1: [Title of Sub-sub-task 1.1.1]**
            * **Description:** [Detailed description of the granular action.]
    * `[ ]` **Task 1.2: [Title of Sub-task 1.2]**
        * **Description:** [Detailed description of Sub-task 1.2.]
* `[ ]` **Task 2: [Title of Major Task 2]**
    * **Description:** [Detailed description of what Major Task 2 entails.]

## 6. Definition of Done
---

* **What to fill in:** A final checklist to be verified upon completion of all tasks.
* **Purpose:** To provide a clear, unambiguous confirmation that all aspects of the project are complete and meet the quality standards.
    * `[ ]` All tasks in the "Tasking" section are marked as complete.
    * `[ ]` The solution passes all checks outlined in the "Testing Plan".
    * `[ ]` All functional and non-functional requirements are met.
    * `[ ]` The code has been committed to the correct repository and branch.
    * `[ ]` Any necessary documentation has been updated.

## 7. Task-Specific Development Log
---

* **Purpose:** This log documents the development process for **each** corresponding item in the Tasking section. For the heading of each entry, copy the task number and its exact title from Section 5.

### Task 1.1: [Copy the task title here]

* **Initial Approach:** [Describe the initial plan for this specific task.]
* **Challenges Encountered:** [Detail any bugs, logical errors, or unexpected issues that arose.]
* **Key Decisions:** [Note any significant choices made, e.g., "Chose library X over Y because of performance."]
* **Final Solution & Reasoning:** [Explain how the challenges were overcome and describe the final implementation.]

## 8. Project Summary & Retrospective
---

* **Purpose:** To close the loop on the project by summarizing the final result and reflecting on the process for future improvement.
* **Final Outcome:** [Briefly describe the final result and where to find it.]
* **What Went Well:** [List 1-3 things that were successful in the process.]
* **What Could Be Improved:** [List 1-3 things that could be done better in the next project.]
