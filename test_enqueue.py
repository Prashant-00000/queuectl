import subprocess

subprocess.run(['python', '-m', 'queuectl.cli', 'enqueue', '{"command": "echo Hello"}'])
subprocess.run(['python', '-m', 'queuectl.cli', 'enqueue', '{"command": "python --version"}'])
