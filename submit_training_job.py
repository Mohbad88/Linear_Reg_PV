from azureml.core import Workspace, Experiment, ScriptRunConfig, Environment


ws = Workspace.from_config(path="C:\\Users\\mataou\\OneDrive - Delta Dore\\PV_Projetc\\Linear_Reg_PV\\config.json")


experiment = Experiment(ws, "pv-production-training")

env = Environment.from_pip_requirements(
    name="pv-env",
    file_path="requirements.txt"
)

# source_directory = racine du projet pour que main_training_pipeline.py
# ET le package src/ soient tous les deux uploadés sur le cluster
src = ScriptRunConfig(
    source_directory=".",
    script="main_training_pipeline.py",
    environment=env,
    compute_target="cpu-cluster"
)

# soumet le job
run = experiment.submit(src)
run.wait_for_completion(show_output=True)

# affichage optionnel de l'URL du run
print("Run details:", run.get_portal_url())
