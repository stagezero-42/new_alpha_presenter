New Alpha Presenter
New Alpha Presenter is a Python-based multimedia application built with Qt6 (PySide6). It features a GUI for controlling and displaying various media types, including images, videos, audio, and text, organized through a JSON-based playlist system. The application supports auto or manual transitions and user-configurable keybindings, with media displayed on a secondary screen.
Installation

Clone the repository:

`git clone https://github.com/yourusername/new_alpha_presenter.git`

`cd new_alpha_presenter`


Create a virtual environment (optional but recommended):

`python -m venv venv`

`source venv/bin/activate  # On Windows: venv\Scripts\activate`


Install dependencies:
`pip install -r requirements.txt`

Running the Application
To run New Alpha Presenter, execute the following command from the project root:

`python -m myapp.main`

This will launch the main control window on the primary screen and the display window for media rendering on a secondary screen.
Running Tests
Tests are located in the tests directory and can be run using pytest. First, ensure you have pytest installed:
pip install pytest

Then, run the tests with:
pytest

Project Structure

myapp/: Main application package.

main.py: Entry point of the application.
app_context.py: Manages application-wide resources (e.g., logging, user feedback signals).
gui/: GUI components for the control and display windows.
media/: Modules for handling images, videos, audio, and text.
playlist/: Playlist management and editing.
settings/: Application settings and keybindings.
utils/: Utility modules, including logging for error handling.


tests/: Development-only test modules, excluded from the final build.

resources/: Static assets like icons and default media files.

docs/: Project documentation.

setup.py: Build configuration for creating executables (optional).
