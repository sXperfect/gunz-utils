# LLM LaTeX Formatting Guide
_version: 2.2.0_

This document outlines best practices for writing and prompting for LaTeX formulas to ensure they
render correctly, particularly when working with Large Language Models (LLMs) like Gemini.

## Core Principles for Correct Rendering
---

The most common reason for broken mathematical formulas is incorrect syntax that Markdown renderers
cannot parse. When generating LaTeX with an LLM, these errors are often introduced because the model
may incorrectly use code formatting, add extra spacing, or use the wrong syntax for commands.

To ensure correct rendering, adhere to these fundamental rules:

- **Use Proper Delimiters:** Use single dollar signs (`$...$`) for inline math (within a line of
  text) and double dollar signs (`$$...$$`) for display math (centered on its own line).
- **No Indentation:** Display math delimiters (`$$`) **must** start at the beginning of a new line
  with zero leading spaces. This is a strict requirement.
- **No Code Blocks:** LaTeX must not be wrapped in Markdown code fences (```).
- **Use Single Backslashes:** All LaTeX commands (e.g., `\frac`, `\sqrt`) must start with a single
  backslash.
- **Use `\mathbf` for Vectors:** For vectors, use the `\mathbf` command (e.g., `\mathbf{r}`) for
  correct mathematical styling.


## Prompting LLMs for Correct LaTeX
---

The key to getting correctly formatted LaTeX from an LLM is to be explicit in your instructions.

### Core Prompt Templates

Use these simple, direct prompts as a starting point for most mathematical queries.
- **For Mixed Inline and Display Math:**
    > "Please render all mathematical expressions in properly formatted LaTeX. Use single dollar
    signs (`$...$`) for inline math and double dollar signs (`$$...$$`) for display equations. Do
    not use code blocks or other formatting."

- **For Display Math Only:**
    > "Render all formulas as LaTeX display math, using double dollar signs, and avoid code or
    markdown formatting."

### Comprehensive System Prompt

For more complex tasks or to set a consistent behavior for an entire session, use a more detailed
system prompt.

> "You are a math problem solver who always uses LaTeX formatting for all equations. For display
math, use double dollar signs on a new line with no indentation. For inline math, use single dollar
signs. Do not use code blocks, markdown fences, or plain text for equations. Ensure all output
renders as LaTeX, not as raw code."

### Converting Formulas from Images

You can also use an LLM to extract and format formulas from images.
- **Prompt for Image-Based Conversion:**
    > "Extract the formula from this image and write it in LaTeX, formatted for Markdown without
    code blocks."


## Syntax and Examples
---

### Display Equations
- **Rule:** Use `$$` on a new, unindented line to open and close the block.
- **Example (in Markdown source):**

    ```latex
    The final loss function is:

    $$
    L_{\text{simple}}(\theta) = \mathbb{E}_{t, \mathbf{x}_0, \epsilon} \left[ || \epsilon - \epsilon_\theta(\mathbf{x}_t, t) ||^2 \right]
    $$
    ```

- **Example (in rendered form):**
    $$
    L_{\text{simple}}(\theta) = \mathbb{E}_{t, \mathbf{x}_0, \epsilon} \left[ || \epsilon -
    \epsilon_\theta(\mathbf{x}_t, t) ||^2 \right]
    $$


### Multi-line and Aligned Equations

- **Rule:** Use the `aligned` environment inside a `$$...$$` block. Use `&` to mark the alignment
  point and `\\` for line breaks.
- **Example (in Markdown source):**

    ```latex
    $$
    \begin{aligned}
    \mathbf{x}_t &= \sqrt{\alpha_t}(\sqrt{\alpha_{t-1}}\mathbf{x}_{t-2} + \sqrt{1-\alpha_{t-1}}\epsilon_{t-2}) + \sqrt{1-\alpha_t}\epsilon_{t-1} \\
    &= \sqrt{\alpha_t\alpha_{t-1}}\mathbf{x}_{t-2} + \sqrt{\alpha_t(1-\alpha_{t-1})}\epsilon_{t-2} + \sqrt{1-\alpha_t}\epsilon_{t-1}
    \end{aligned}
    $$
    ```

- **Example (in rendered form):**
$$
    \begin{aligned}
    \mathbf{x}_t &= \sqrt{\alpha_t}(\sqrt{\alpha_{t-1}}\mathbf{x}_{t-2} +
    \sqrt{1-\alpha_{t-1}}\epsilon_{t-2}) + \sqrt{1-\alpha_t}\epsilon_{t-1} \\
    &= \sqrt{\alpha_t\alpha_{t-1}}\mathbf{x}_{t-2} + \sqrt{\alpha_t(1-\alpha_{t-1})}\epsilon_{t-2} +
    \sqrt{1-\alpha_t}\epsilon_{t-1}
    \end{aligned}
$$


## Troubleshooting Common LLM Failures
---

- **Issue:** The LLM outputs raw code in a code block.
    - **Cause:** The model has wrapped the LaTeX in Markdown fences (```).
    - **Fix:** Explicitly prompt, "Do not use code blocks for equations." If it persists, manually
      remove the fences.

- **Issue:** The dollar signs are visible and the formula isn't rendered.
    - **Cause:** The model has added spaces or indentation before the opening `$$`.
    - **Fix:** Remind the model, "Start each display math block on a new, unindented line." Manually
      remove any leading spaces.

- **Issue:** Formatting breaks inside a list.
    - **Cause:** List indentation can interfere with the LaTeX renderer.
    - **Fix:** Ensure the `$$` block starts on a new, **unindented** line immediately after the list
      item's text. This is a strict rule.
