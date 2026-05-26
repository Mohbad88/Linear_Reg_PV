
from azureml.core import Workspace

ws = Workspace.from_config(path="C:\\Users\\mataou\\OneDrive - Delta Dore\\PV_Projetc\\Linear_Reg_PV\\config.json")
print(ws.name)
print(ws.resource_group)
print(ws.location)

