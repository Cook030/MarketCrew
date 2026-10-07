# CrewAIFullstackTest: Flask + CrewAI 后端 与 Vue + Vite 前端
# 在仓库根目录执行 make help 查看全部命令，默认目标为 help。
# 首次运行前请先复制 crewaiBackend/.env.example 为 crewaiBackend/.env 并填写模型凭据。

# 可覆盖，例如 make backend PYTHON=python
BASE_PYTHON ?= python
NPM         ?= npm

ifeq ($(OS),Windows_NT)
# Windows 下固定用 cmd 执行，避免从 Git Bash 调用时 sh.exe 改写路径与参数。
SHELL        := cmd.exe
BACKEND_DIR  := crewaiBackend
FRONTEND_DIR := crewaiFrontend
VENV_PYTHON  := $(BACKEND_DIR)\.venv\Scripts\python.exe
else
BACKEND_DIR  := crewaiBackend
FRONTEND_DIR := crewaiFrontend
VENV_PYTHON  := $(BACKEND_DIR)/.venv/bin/python
endif
PYTHON ?= $(VENV_PYTHON)

.DEFAULT_GOAL := help
.PHONY: help install install-backend install-frontend backend frontend dev build

help:
	@echo CrewAIFullstackTest targets
	@echo ----------------------------------------
	@echo make install           Install backend venv deps and frontend deps
	@echo make install-backend   Create .venv and install requirements.txt
	@echo make install-frontend  Install frontend deps
	@echo make backend           Start API at http://127.0.0.1:8012
	@echo make frontend          Start web UI at http://localhost:5173
	@echo make dev               Start API in a new window, web UI in this one
	@echo make build             Build frontend for production
	@echo ----------------------------------------
	@echo Custom interpreter: make backend PYTHON=python

install: install-backend install-frontend

install-backend:
	$(BASE_PYTHON) -m venv $(BACKEND_DIR)/.venv
	"$(PYTHON)" -m pip install -r $(BACKEND_DIR)/requirements.txt

install-frontend:
	$(NPM) --prefix $(FRONTEND_DIR) install

backend:
	"$(PYTHON)" -X utf8 $(BACKEND_DIR)/main.py

frontend:
	$(NPM) --prefix $(FRONTEND_DIR) run dev

ifeq ($(OS),Windows_NT)
dev:
	start "crewai-backend" cmd /k ""$(PYTHON)" -X utf8 $(BACKEND_DIR)/main.py"
	$(NPM) --prefix $(FRONTEND_DIR) run dev
else
dev:
	@echo Outside Windows run "make backend" and "make frontend" in two terminals
endif

build: install-frontend
	$(NPM) --prefix $(FRONTEND_DIR) run build
