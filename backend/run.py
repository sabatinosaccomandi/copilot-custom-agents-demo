"""Application entry point for the Flask development server.

This module creates the Flask application via the factory function and
starts the built-in Werkzeug development server when executed directly.
It must **not** be used as the WSGI callable in production; use a proper
WSGI server (e.g. Gunicorn, uWSGI) pointing at the ``app`` object instead.

Example:
    Run the development server::

        $ python run.py

    Or via the Flask CLI::

        $ flask --app run:app run
"""
import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    # Debug mode must be explicitly opted-in via the environment variable.
    # It must NEVER be True in production: it exposes an interactive Python
    # debugger (with code-execution capability) over HTTP.
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(debug=debug)
