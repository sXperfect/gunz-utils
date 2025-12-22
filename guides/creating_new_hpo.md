# Guide: Creating a New Hyperparameter Optimization (HPO) Experiment

This guide walks you through the process of setting up a new HPO experiment using the provided templates, which are based on the project's latest best practices.

## 1. Get the Templates

The reusable templates are located in the `templates/` directory.
-   `_template_opt_v2.py`: The main Python script.
-   `base_template_opt.yaml`: The base Hydra configuration file.

Copy these to your project:
```bash
# Copy the script to your project root
cp templates/_template_opt_v2.py opt_my_new_model.py

# Copy the base config to your configs directory
cp templates/base_template_opt.yaml configs/base_my_new_model.yaml
```

## 2. Customize the Python Script

Open your new script (e.g., `opt_my_new_model.py`) and follow the `TODO` comments to customize it for your project.

### Key Sections to Edit:

-   **Metadata:** Update the `__author__` and `__email__`.
-   **Imports:** Import your project-specific `DataModule`, `LightningModule` (your model), and `nn.Module` (your architecture).
    ```python
    # from my_project.datasets import MyDataModule
    # from my_project.models import MyLightningModel
    # from my_project.archs import MyArchitecture
    ```
-   **`objective_f` function:**
    -   **Hyperparameter Suggestion:** Define the hyperparameters you want to tune using Optuna's `trial.suggest_*` methods. The names must match what you will define in your YAML config.
        ```python
        # Example
        learning_rate = trial.suggest_float("learning_rate", 1e-5, 1e-2, log=True)
        dropout = trial.suggest_float("dropout", 0.1, 0.5)
        ```
    -   **Data Loading:** Replace the placeholder `MNISTDataModule` with your own `DataModule`.
    -   **Model Instantiation:** Replace the `PlaceholderModel` with your own architecture and Lightning model, passing in the hyperparameters.

-   **`@hydra.main` Decorator:** Update the `config_name` to point to your new base config file.
    ```python
    @hydra.main(version_base=None, config_path="configs", config_name="base_my_new_model")
    ```

## 3. Create an Experiment Configuration File

Create a new YAML file for your specific experiment, for example, `configs/exp/my_new_model/exp_001.yaml`.

This file should:
1.  Extend your new base configuration.
2.  Define the HPO search space in the `optuna.parameters` section.
3.  Set the optimization objectives.
4.  Override any other default settings (like `max_epochs` or `num_trials`).

**Example (`configs/exp/my_new_model/exp_001.yaml`):**
```yaml
# @package _global_

defaults:
  - /base_my_new_model # Extends your new base config
  - _self_

# Override base arguments
args:
  study_name: "my_new_model_study_001"
  num_trials: 150
  max_epochs: 100

# Define the search space
optuna:
  parameters:
    learning_rate:
      low: 1e-4
      high: 1e-2
    dropout:
      low: 0.0
      high: 0.5
  
  # Define what to optimize for
  objectives:
    val/my_metric: "minimize"
    val/another_metric: "maximize"
```

## 4. Run the HPO

You can now launch your HPO experiment using the new script and experiment config.

**To run locally:**
```bash
python opt_my_new_model.py --config-name exp/my_new_model/exp_001
```

**To submit to SLURM (using `slurm_launcher.py`):**
1.  Create a SLURM launcher config (e.g., `configs/slurm/my_new_model_hpo.yaml`).
2.  Set the `run.python_name` and `run.exp_name`.
3.  Launch it:
    ```bash
    python slurm_launcher.py --config-name my_new_model_hpo
    ```
This structured approach ensures consistency and makes setting up new experiments significantly faster.
