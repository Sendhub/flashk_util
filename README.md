# SendHub's flashk_util package

## Overview

SendHub's Flask utility library for authentication, entitlement management, and general backend utilities.

## Project Structure

- __init__.py
- auth.py
- authdigest.py
- baseconv.py
- converters.py
- crypto.py
- csrf.py
- helpers.py
- log_formatter.py
- log_request_id.py
- log_task_id.py
- request.py
- response.py
- serving.py
- AUTHORS
- LICENSE
- README.md
- copilot-instructions.md

## Setup

1. Clone the repository as a submodule or standalone package.
2. Ensure Python 3.13 is installed.
3. Install required dependencies (see requirements in your main project).
4. Import and use modules as needed in your Flask application.

## Runtime Requirements

- Python 3.13
- Flask
- Werkzeug
- Celery (for logging filters)
- simplejson

## Supported Python Version

- Python 3.13
