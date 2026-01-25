.PHONY: run install clean help

# Default target
help:
	@echo "Available commands:"
	@echo "  make run      - Run the GTT Orders Dashboard server"
	@echo "  make install  - Install required Python dependencies"
	@echo "  make clean    - Remove Python cache files"

run:
	python gtt_api_server.py

install:
	pip install -r requirements.txt

clean:
	@if exist __pycache__ (rmdir /s /q __pycache__ && echo Cleaned __pycache__) else (echo No __pycache__ found)
