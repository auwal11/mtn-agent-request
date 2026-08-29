"""
WSGI config for PythonAnywhere deployment.

HOW TO USE (PythonAnywhere free tier):
1. Sign up at https://www.pythonanywhere.com (free account)
2. Open a Bash console from the PythonAnywhere dashboard and run:
       git clone https://github.com/auwal11/mtn-agent-request.git
       cd mtn-agent-request
       pip3.10 install --user -r requirements.txt
3. Go to the "Web" tab -> "Add a new web app" -> choose "Manual configuration" -> Python 3.10
4. In the "Code" section of the Web tab, set:
       Source code:      /home/YOURUSERNAME/mtn-agent-request
       Working directory: /home/YOURUSERNAME/mtn-agent-request
5. Click the "WSGI configuration file" link on the Web tab, DELETE everything in it,
   and replace the contents with this file's contents below (adjusting the path
   and username). Save.
6. In the "Web" tab, add an environment variable (or set it in this file, see below):
       DATA_DIR = /home/YOURUSERNAME/mtn-agent-request/persistent_data
       SECRET_KEY = <any long random string>
7. Click the green "Reload" button on the Web tab. Your app will be live at
   https://YOURUSERNAME.pythonanywhere.com
"""
import sys
import os

# ----- EDIT THIS: replace with your actual PythonAnywhere username -----
project_home = '/home/YOURUSERNAME/mtn-agent-request'
# -------------------------------------------------------------------

if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Persistent storage location (PythonAnywhere free tier disk persists across reloads,
# this just keeps data organized in its own folder)
os.environ.setdefault('DATA_DIR', os.path.join(project_home, 'persistent_data'))
os.environ.setdefault('SECRET_KEY', 'change-this-to-a-long-random-string')

os.makedirs(os.environ['DATA_DIR'], exist_ok=True)
os.makedirs(os.path.join(os.environ['DATA_DIR'], 'uploads', 'photos'), exist_ok=True)
os.makedirs(os.path.join(os.environ['DATA_DIR'], 'uploads', 'signatures'), exist_ok=True)
os.makedirs(os.path.join(os.environ['DATA_DIR'], 'outputs'), exist_ok=True)

from app import app as application
