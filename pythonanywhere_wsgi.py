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
6. Set the environment variables below (either edit them directly in this file,
   or add them under the Web tab's "Environment variables" section):
       DATA_DIR         = /home/YOURUSERNAME/mtn-agent-request/persistent_data
       SECRET_KEY       = <any long random string>
       ROOT_NAME        = Auwal                 (shown as the Root/CEO account name)
       ROOT_PASSWORD    = AuwalControl           (change this to something only you know)
       GMAIL_ADDRESS    = youraddress@gmail.com  (used by Receiver Admin's "Send to Gmail")
       GMAIL_APP_PASSWORD = <16-character Gmail App Password, NOT your normal Gmail password>
   Note: ADMIN_PASSWORD / RECEIVER_PASSWORD are no longer used — the Root/CEO account
   (above) creates and manages all Admin and Receiver Admin accounts from inside the app,
   under Command Center -> Create Admin/Receiver.
7. Click the green "Reload" button on the Web tab. Your app will be live at
   https://YOURUSERNAME.pythonanywhere.com
"""
import sys
import os

# ----- EDIT THIS: replace with your actual PythonAnywhere username -----
project_home = '/home/auwalbussines/mtn-agent-request'
# -------------------------------------------------------------------

if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Persistent storage location (PythonAnywhere free tier disk persists across reloads,
# this just keeps data organized in its own folder)
os.environ.setdefault('DATA_DIR', os.path.join(project_home, 'persistent_data'))
os.environ.setdefault('SECRET_KEY', 'change-this-to-a-long-random-string')
os.environ.setdefault('ROOT_NAME', 'Auwal')
os.environ.setdefault('ROOT_PASSWORD', 'AuwalControl')
os.environ.setdefault('GMAIL_ADDRESS', 'alhajiauwalalhaji@gmail.com')
os.environ.setdefault('GMAIL_APP_PASSWORD', 'ivky rqye ncmh gmpt')

os.makedirs(os.environ['DATA_DIR'], exist_ok=True)
os.makedirs(os.path.join(os.environ['DATA_DIR'], 'uploads', 'photos'), exist_ok=True)
os.makedirs(os.path.join(os.environ['DATA_DIR'], 'uploads', 'signatures'), exist_ok=True)
os.makedirs(os.path.join(os.environ['DATA_DIR'], 'outputs'), exist_ok=True)

from app import app as application
