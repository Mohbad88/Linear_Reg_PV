# Compatibility shim for azureml-core on Python 3.13+, where the stdlib
# imghdr module was removed. Azure ML imports it for image metric handling.

def what(file, h=None):
    return None